from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json, timestamp_slug, write_json
from heart_transplant.graph_integrity import run_graph_integrity
from heart_transplant.validation_gates import run_validation_gates


MANIFEST_FILENAME = "artifact-manifest.json"


def build_artifact_manifest(
    artifact_dir: Path,
    *,
    command: str = "run-manifest",
    gold_set: Path | None = None,
    holdout_gold_set: Path | None = None,
    extra_commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    structural = _read_json_if_present(artifact_dir / "structural-artifact.json")
    semantic = _read_json_if_present(artifact_dir / "semantic-artifact.json")
    scip_index = _read_json_if_present(artifact_dir / "scip-index.json")
    scip_consumed = _read_json_if_present(artifact_dir / "scip-consumed.json")
    files = [
        _file_entry(path, artifact_dir)
        for path in sorted(artifact_dir.iterdir())
        if path.is_file() and path.name != MANIFEST_FILENAME
    ]
    layers = {
        "structural": {
            "present": bool(structural),
            "file": "structural-artifact.json",
            "repo_name": structural.get("repo_name") if structural else None,
            "node_count": structural.get("node_count") if structural else 0,
            "edge_count": structural.get("edge_count") if structural else 0,
            "file_node_count": len(structural.get("file_nodes", [])) if structural else 0,
            "code_node_count": len(structural.get("code_nodes", [])) if structural else 0,
        },
        "scip": {
            "present": bool(scip_index or scip_consumed or (artifact_dir / "index.scip").is_file()),
            "index_present": bool(scip_index),
            "consumed_present": bool(scip_consumed),
            "binary_present": (artifact_dir / "index.scip").is_file(),
            "resolved_code_nodes": (scip_consumed.get("resolution") or {}).get("resolved_code_nodes") if scip_consumed else 0,
        },
        "semantic": {
            "present": bool(semantic),
            "file": "semantic-artifact.json",
            "block_assignment_count": len(semantic.get("block_assignments", [])) if semantic else 0,
            "entity_count": len(semantic.get("entities", [])) if semantic else 0,
            "action_count": len(semantic.get("actions", [])) if semantic else 0,
        },
    }
    commands = [
        {
            "command_id": "graph-integrity",
            "argv": ["python", "-m", "heart_transplant.cli", "graph-integrity", str(artifact_dir)],
            "expected_status": "pass",
        },
        {
            "command_id": "validate-gates",
            "argv": ["python", "-m", "heart_transplant.cli", "validate-gates", "--artifact-dir", str(artifact_dir)],
            "expected_status": "pass" if layers["scip"]["present"] else "any",
        },
    ]
    if extra_commands:
        commands.extend(extra_commands)
    gold_sets = {}
    if gold_set:
        gold_sets["main"] = str(gold_set.resolve())
    if holdout_gold_set:
        gold_sets["holdout"] = str(holdout_gold_set.resolve())
    return {
        "schema": "heart-transplant.artifact-manifest.v1",
        "report_type": "artifact_manifest",
        "generated_at": timestamp_slug(),
        "command": command,
        "artifact_dir": str(artifact_dir),
        "repo_name": layers["structural"]["repo_name"],
        "repo_path": structural.get("repo_path") if structural else None,
        "layers": layers,
        "files": files,
        "gold_sets": gold_sets,
        "commands": commands,
        "summary": {
            "file_count": len(files),
            "required_artifacts_present": bool(structural),
            "optional_layers_present": [name for name, layer in layers.items() if name != "structural" and layer["present"]],
        },
    }


def write_artifact_manifest(
    artifact_dir: Path,
    *,
    command: str = "run-manifest",
    gold_set: Path | None = None,
    holdout_gold_set: Path | None = None,
    extra_commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = build_artifact_manifest(
        artifact_dir,
        command=command,
        gold_set=gold_set,
        holdout_gold_set=holdout_gold_set,
        extra_commands=extra_commands,
    )
    write_json(Path(artifact_dir) / MANIFEST_FILENAME, manifest)
    return manifest


def run_artifact_manifest(manifest_path: Path, *, execute_commands: bool = False) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = read_json(manifest_path)
    artifact_dir = Path(str(manifest["artifact_dir"]))
    repo_path = Path(str(manifest.get("repo_path") or ""))
    results: list[dict[str, Any]] = []

    integrity = run_graph_integrity(artifact_dir)
    results.append({"command_id": "graph-integrity", "status": integrity["summary"]["overall_status"], "summary": integrity["summary"]})
    if repo_path.exists():
        validation = run_validation_gates(repo_path, artifact_dir)
        results.append({"command_id": "validate-gates", "status": validation["summary"]["overall_status"], "summary": validation["summary"]})
    else:
        results.append({"command_id": "validate-gates", "status": "fail", "summary": {"error": f"repo_path missing: {repo_path}"}})

    if execute_commands:
        handled = {"graph-integrity", "validate-gates"}
        for command in manifest.get("commands", []):
            if command.get("command_id") in handled:
                continue
            argv = [sys.executable if arg == "python" else str(arg) for arg in command.get("argv", [])]
            if not argv:
                continue
            proc = subprocess.run(argv, cwd=manifest_path.parent, capture_output=True, text=True, check=False)
            results.append(
                {
                    "command_id": command.get("command_id", "unknown"),
                    "status": "pass" if proc.returncode == 0 else "fail",
                    "expected_status": command.get("expected_status", "pass"),
                    "exit_code": proc.returncode,
                    "stdout_tail": proc.stdout[-500:],
                    "stderr_tail": proc.stderr[-500:],
                }
            )

    failed = [
        result
        for result in results
        if result.get("status") == "fail"
        and _expected_status(manifest, str(result.get("command_id"))) == "pass"
    ]
    return {
        "report_type": "manifest_run",
        "manifest_path": str(manifest_path),
        "summary": {
            "overall_status": "pass" if not failed else "fail",
            "checked": len(results),
            "failed": len(failed),
        },
        "results": results,
    }


def summarize_artifact_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = read_json(manifest_path)
    return {
        "report_type": "manifest_status",
        "schema": manifest.get("schema"),
        "manifest_path": str(manifest_path),
        "repo_name": manifest.get("repo_name"),
        "artifact_dir": manifest.get("artifact_dir"),
        "artifacts": {item["path"]: item for item in manifest.get("files", []) if isinstance(item, dict) and item.get("path")},
        "gold_sets": manifest.get("gold_sets", {}),
        "commands": manifest.get("commands", []),
        "summary": manifest.get("summary", {}),
    }


def _read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def _file_entry(path: Path, artifact_dir: Path) -> dict[str, Any]:
    content = path.read_bytes()
    return {
        "path": path.relative_to(artifact_dir).as_posix(),
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _expected_status(manifest: dict[str, Any], command_id: str) -> str:
    for command in manifest.get("commands", []):
        if command.get("command_id") == command_id:
            return str(command.get("expected_status", "pass"))
    return "pass"
