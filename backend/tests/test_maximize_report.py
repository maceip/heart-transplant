from __future__ import annotations

from pathlib import Path

from heart_transplant.artifact_store import write_json
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.maximize.report import build_maximize_report


def test_maximize_report_summarizes_artifact_capabilities(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    artifact_dir = tmp_path / "artifact"
    repo.mkdir()
    artifact_dir.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return 'ok'; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "demo/maximize")
    write_json(artifact_dir / "structural-artifact.json", artifact.model_dump(mode="json"))
    run_classification_on_artifact(artifact_dir, use_openai=False)

    report = build_maximize_report(artifact_dir, include_validation=False)

    assert report["report_type"] == "phase_8_5_maximize_current_capabilities"
    assert report["summary"]["node_count"] == 1
    assert report["summary"]["semantic_assignment_count"] == 1
    assert report["capability_matrix"]
    assert report["demo_candidates"]["high_confidence_block_nodes"]
