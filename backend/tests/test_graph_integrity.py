from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.graph_integrity import run_graph_integrity
from heart_transplant.ingest.treesitter_ingest import ingest_repository


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
