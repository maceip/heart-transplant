from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.artifact_store import write_json
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.evals.gold_audit import audit_gold_set
from heart_transplant.evidence import run_evidence_benchmark
from heart_transplant.graph_integrity import run_graph_integrity
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.repro_manifest import build_artifact_manifest, run_manifest, summarize_manifest, write_artifact_manifest


def test_gold_audit_flags_duplicate_and_contradictory_rows(tmp_path: Path) -> None:
    gold = tmp_path / "gold.json"
    gold.write_text(
        json.dumps(
            [
                {"repo_name": "r", "file_path": "a.ts", "expected_block": "Access Control"},
                {"repo_name": "r", "file_path": "a.ts", "expected_block": "Access Control"},
                {"repo_name": "r", "file_path": "a.ts", "expected_block": "Data Persistence"},
            ]
        ),
        encoding="utf-8",
    )

    report = audit_gold_set(gold)

    assert report["summary"]["duplicate_key_count"] == 1
    assert report["summary"]["contradictory_target_count"] == 1
    assert report["summary"]["overall_status"] == "needs_review"


def test_evidence_benchmark_scores_expected_files_blocks_and_unsupported(tmp_path: Path) -> None:
    artifact_dir, _artifact = _artifact_with_semantics(tmp_path)
    questions = tmp_path / "questions.json"
    questions.write_text(
        json.dumps(
            [
                {
                    "id": "auth",
                    "question": "Where is auth handled?",
                    "expected_file_paths": ["auth.ts"],
                    "expected_blocks": ["Access Control"],
                    "unsupported": False,
                },
                {
                    "id": "unsupported",
                    "question": "Which Kafka topic owns billing?",
                    "unsupported": True,
                },
            ]
        ),
        encoding="utf-8",
    )

    report = run_evidence_benchmark(artifact_dir, questions)

    assert report["summary"]["question_count"] == 2
    assert report["summary"]["file_match_rate"] >= 0.5
    assert report["summary"]["unsupported_correct_rate"] == 1.0


def test_repro_manifest_records_and_runs_core_gates(tmp_path: Path) -> None:
    artifact_dir, _artifact = _artifact_with_semantics(tmp_path)
    manifest = build_artifact_manifest(artifact_dir)
    manifest_path = write_artifact_manifest(manifest, tmp_path / "manifest.json")

    summary = summarize_manifest(manifest_path)
    report = run_manifest(manifest_path)

    assert summary["schema"] == "heart-transplant.repro-manifest.v1"
    assert "canonical_graph" in summary["artifacts"]
    assert report["summary"]["overall_status"] in {"pass", "fail"}
    assert {result["command_id"] for result in report["results"]} >= {"graph-integrity", "validate-gates"}


def test_graph_integrity_reports_layer_specific_canonical_checks(tmp_path: Path) -> None:
    artifact_dir, _artifact = _artifact_with_semantics(tmp_path)

    report = run_graph_integrity(artifact_dir)
    checks = {check["check_id"]: check["status"] for check in report["checks"]}

    assert checks["canonical_graph_all_edges_have_provenance"] == "pass"
    assert checks["canonical_graph_manifest_present"] == "pass"
    assert checks["canonical_graph_stable_node_ids"] == "pass"


def _artifact_with_semantics(tmp_path: Path) -> tuple[Path, object]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return true; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/quality-rails")
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    write_json(artifact_dir / "structural-artifact.json", artifact.model_dump(mode="json"))
    run_classification_on_artifact(artifact_dir, use_openai=False)
    return artifact_dir, artifact
