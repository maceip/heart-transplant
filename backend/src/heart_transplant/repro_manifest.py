from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from heart_transplant.artifact_store import read_json, write_json
from heart_transplant.graph_integrity import run_graph_integrity
from heart_transplant.validation_gates import run_validation_gates


class ManifestCommand(BaseModel):
    command_id: str
    argv: list[str]
    cwd: str = "."
    expected_status: Literal["pass", "fail", "any"] = "pass"


class ArtifactManifestContract(BaseModel):
    schema: str = "heart-transplant.repro-manifest.v1"
    repo_name: str
    repo_path: str
    artifact_dir: str
    generated_at: str | None = None
    tool_versions: dict[str, str] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    gold_sets: dict[str, str] = Field(default_factory=dict)
    commands: list[ManifestCommand] = Field(default_factory=list)


def build_artifact_manifest(
    artifact_dir: Path,
    *,
    gold_set: Path | None = None,
    holdout_gold_set: Path | None = None,
) -> ArtifactManifestContract:
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    artifacts = {
        "structural": str(artifact_dir / "structural-artifact.json"),
        "canonical_graph": str(artifact_dir / "canonical-graph.json"),
    }
    for name in ("semantic-artifact.json", "scip-index.json", "scip-consumed.json", "index.scip"):
        path = artifact_dir / name
        if path.exists():
            artifacts[name.replace(".json", "").replace(".", "_").replace("-", "_")] = str(path)
    gold_sets = {}
    if gold_set:
        gold_sets["main"] = str(gold_set.resolve())
    if holdout_gold_set:
        gold_sets["holdout"] = str(holdout_gold_set.resolve())
    commands = [
        ManifestCommand(
            command_id="graph-integrity",
            argv=["python", "-m", "heart_transplant.cli", "graph-integrity", str(artifact_dir)],
        ),
        ManifestCommand(
            command_id="validate-gates",
            argv=["python", "-m", "heart_transplant.cli", "validate-gates", "--artifact-dir", str(artifact_dir)],
        ),
    ]
    return ArtifactManifestContract(
        repo_name=str(structural.get("repo_name", "")),
        repo_path=str(structural.get("repo_path", "")),
        artifact_dir=str(artifact_dir),
        tool_versions={
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        artifacts=artifacts,
        gold_sets=gold_sets,
        commands=commands,
    )


def write_artifact_manifest(manifest: ArtifactManifestContract, out: Path) -> Path:
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, manifest.model_dump(mode="json"))
    return out


def run_manifest(manifest_path: Path, *, execute_commands: bool = False) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = ArtifactManifestContract.model_validate(read_json(manifest_path))
    artifact_dir = Path(manifest.artifact_dir)
    results: list[dict[str, Any]] = []
    integrity = run_graph_integrity(artifact_dir)
    results.append(
        {
            "command_id": "graph-integrity",
            "status": integrity["summary"]["overall_status"],
            "summary": integrity["summary"],
        }
    )
    validation = run_validation_gates(Path(manifest.repo_path), artifact_dir)
    results.append(
        {
            "command_id": "validate-gates",
            "status": validation["summary"]["overall_status"],
            "summary": validation["summary"],
        }
    )
    if execute_commands:
        for command in manifest.commands:
            if command.command_id in {"graph-integrity", "validate-gates"}:
                continue
            proc = subprocess.run(
                [sys.executable if arg == "python" else arg for arg in command.argv],
                cwd=Path(command.cwd).resolve() if command.cwd != "." else manifest_path.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            actual = "pass" if proc.returncode == 0 else "fail"
            results.append(
                {
                    "command_id": command.command_id,
                    "status": actual,
                    "expected_status": command.expected_status,
                    "exit_code": proc.returncode,
                    "stdout_tail": proc.stdout[-500:],
                    "stderr_tail": proc.stderr[-500:],
                }
            )
    failed = [
        result
        for result in results
        if result.get("status") == "fail"
        and next((cmd.expected_status for cmd in manifest.commands if cmd.command_id == result["command_id"]), "pass") == "pass"
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


def summarize_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = ArtifactManifestContract.model_validate(read_json(manifest_path))
    return {
        "report_type": "manifest_status",
        "schema": manifest.schema,
        "manifest_path": str(manifest_path),
        "repo_name": manifest.repo_name,
        "artifact_dir": manifest.artifact_dir,
        "artifact_count": len(manifest.artifacts),
        "artifacts": manifest.artifacts,
        "gold_sets": manifest.gold_sets,
        "commands": [command.model_dump(mode="json") for command in manifest.commands],
    }

