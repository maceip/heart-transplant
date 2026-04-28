from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.graph_integrity import run_graph_integrity
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.artifact_manifest import write_artifact_manifest


def test_graph_integrity_passes_for_ingested_artifact(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "auth.ts").write_text("export function sessionGuard() { return true; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/integrity")
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    (artifact_dir / "structural-artifact.json").write_text(
        json.dumps(artifact.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    report = run_graph_integrity(artifact_dir)

    assert report["summary"]["overall_status"] == "pass"
    assert report["summary"]["dangling_edge_count"] == 0
    assert report["layers"]["structural"] == "pass"


def test_graph_integrity_fails_on_dangling_edge(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "x.ts").write_text("export const x = 1;\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/dangling")
    data = artifact.model_dump(mode="json")
    data["edges"].append(
        {
            "source_id": data["project_node"]["node_id"],
            "target_id": "codefile:missing.ts",
            "edge_type": "CONTAINS",
            "repo_name": "test/dangling",
        }
    )
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    (artifact_dir / "structural-artifact.json").write_text(json.dumps(data), encoding="utf-8")

    report = run_graph_integrity(artifact_dir)

    assert report["summary"]["overall_status"] == "fail"
    assert report["summary"]["dangling_edge_count"] == 1


def test_graph_integrity_fails_on_semantic_assignment_to_missing_node(tmp_path: Path) -> None:
    artifact_dir = _basic_artifact_dir(tmp_path)
    (artifact_dir / "semantic-artifact.json").write_text(
        json.dumps({"block_assignments": [{"node_id": "missing", "primary_block": "Access Control"}]}),
        encoding="utf-8",
    )

    report = run_graph_integrity(artifact_dir)

    assert report["summary"]["overall_status"] == "fail"
    assert report["layers"]["semantic"] == "fail"
    assert any(check["check_id"] == "semantic_assignments_target_graph_nodes" for check in report["checks"])


def test_graph_integrity_fails_on_stale_manifest_hash(tmp_path: Path) -> None:
    artifact_dir = _basic_artifact_dir(tmp_path)
    write_artifact_manifest(artifact_dir)
    (artifact_dir / "structural-artifact.json").write_text("{}", encoding="utf-8")

    report = run_graph_integrity(artifact_dir)

    assert report["summary"]["overall_status"] == "fail"
    assert report["layers"]["manifest"] == "fail"


def _basic_artifact_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "repo-basic"
    repo.mkdir()
    (repo / "x.ts").write_text("export const x = 1;\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/basic")
    artifact_dir = tmp_path / "artifact-basic"
    artifact_dir.mkdir()
    (artifact_dir / "structural-artifact.json").write_text(json.dumps(artifact.model_dump(mode="json")), encoding="utf-8")
    return artifact_dir
