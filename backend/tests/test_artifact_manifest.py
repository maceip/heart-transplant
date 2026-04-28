from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from heart_transplant.artifact_manifest import build_artifact_manifest, write_artifact_manifest
from heart_transplant.artifact_store import write_json
from heart_transplant.cli import app
from heart_transplant.ingest.treesitter_ingest import ingest_repository


def test_artifact_manifest_records_artifact_layers_and_file_hashes(tmp_path: Path) -> None:
    artifact_dir = _artifact_dir(tmp_path)

    manifest = write_artifact_manifest(artifact_dir, command="test")

    assert (artifact_dir / "artifact-manifest.json").is_file()
    assert manifest["schema"] == "heart-transplant.artifact-manifest.v1"
    assert manifest["layers"]["structural"]["present"] is True
    assert manifest["layers"]["structural"]["code_node_count"] >= 1
    assert any(item["path"] == "structural-artifact.json" and item["sha256"] for item in manifest["files"])
    assert all(item["path"] != "artifact-manifest.json" for item in write_artifact_manifest(artifact_dir)["files"])


def test_run_manifest_cli_writes_manifest(tmp_path: Path) -> None:
    artifact_dir = _artifact_dir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["run-manifest", str(artifact_dir)])

    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["summary"]["required_artifacts_present"] is True
    assert build_artifact_manifest(artifact_dir)["summary"]["file_count"] >= 1


def test_run_manifest_cli_accepts_manifest_file(tmp_path: Path) -> None:
    artifact_dir = _artifact_dir(tmp_path)
    manifest = write_artifact_manifest(artifact_dir, command="test")
    manifest_path = artifact_dir / "artifact-manifest.json"
    runner = CliRunner()

    result = runner.invoke(app, ["run-manifest", str(manifest_path)])

    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["report_type"] == "manifest_run"
    assert report["summary"]["overall_status"] == "pass"
    assert manifest["schema"] == "heart-transplant.artifact-manifest.v1"


def _artifact_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return true; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/manifest")
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    write_json(artifact_dir / "structural-artifact.json", artifact.model_dump(mode="json"))
    return artifact_dir
