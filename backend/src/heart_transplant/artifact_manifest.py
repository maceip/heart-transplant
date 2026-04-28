from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json, timestamp_slug, write_json


MANIFEST_FILENAME = "artifact-manifest.json"


def build_artifact_manifest(artifact_dir: Path, *, command: str = "run-manifest") -> dict[str, Any]:
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
    return {
        "schema": "heart-transplant.artifact-manifest.v1",
        "report_type": "artifact_manifest",
        "generated_at": timestamp_slug(),
        "command": command,
        "artifact_dir": str(artifact_dir),
        "repo_name": layers["structural"]["repo_name"],
        "layers": layers,
        "files": files,
        "summary": {
            "file_count": len(files),
            "required_artifacts_present": bool(structural),
            "optional_layers_present": [name for name, layer in layers.items() if name != "structural" and layer["present"]],
        },
    }


def write_artifact_manifest(artifact_dir: Path, *, command: str = "run-manifest") -> dict[str, Any]:
    manifest = build_artifact_manifest(artifact_dir, command=command)
    write_json(Path(artifact_dir) / MANIFEST_FILENAME, manifest)
    return manifest


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
