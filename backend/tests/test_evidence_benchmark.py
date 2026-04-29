from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from heart_transplant.artifact_store import write_json
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.cli import app
from heart_transplant.evals.evidence_benchmark import load_evidence_questions, run_evidence_benchmark
from heart_transplant.ingest.treesitter_ingest import ingest_repository


def test_evidence_benchmark_scores_expected_blocks_and_files(tmp_path: Path) -> None:
    artifact_dir = _artifact_with_semantics(tmp_path)
    questions = [
        {
            "id": "fixture-auth",
            "repo_name": "test/evidence",
            "question": "Where is auth handled?",
            "expected_blocks": ["Access Control"],
            "expected_files": ["auth.ts"],
            "expected_file_globs": [],
            "source": "test",
            "notes": "",
            "status": "active",
        }
    ]

    report = run_evidence_benchmark(artifact_dir, questions)

    assert report["summary"]["scored_questions"] == 1
    assert report["summary"]["accuracy"] == 1.0
    assert report["rows"][0]["block_match"] is True
    assert report["rows"][0]["file_match"] is True
    assert report["summary"]["hallucination_rate"] == 0.0


def test_evidence_benchmark_scores_unsupported_questions(tmp_path: Path) -> None:
    artifact_dir = _artifact_with_semantics(tmp_path)
    questions = [
        {
            "id": "fixture-kafka",
            "repo_name": "test/evidence",
            "question": "Where is Kafka configured?",
            "expected_blocks": [],
            "expected_files": [],
            "expected_file_globs": [],
            "unsupported": True,
            "source": "test",
            "notes": "",
            "status": "active",
        }
    ]

    report = run_evidence_benchmark(artifact_dir, questions)

    assert report["summary"]["unsupported_correct_rate"] == 1.0
    assert report["summary"]["hallucination_rate"] == 0.0
    assert report["rows"][0]["unsupported_correct"] is True


def test_evidence_benchmark_cli_runs_question_file(tmp_path: Path) -> None:
    artifact_dir = _artifact_with_semantics(tmp_path)
    questions = tmp_path / "questions.json"
    write_json(
        questions,
        [
            {
                "id": "fixture-auth",
                "repo_name": "test/evidence",
                "question": "Where is auth handled?",
                "expected_blocks": ["Access Control"],
                "expected_files": ["auth.ts"],
                "expected_file_globs": [],
                "source": "test",
                "notes": "",
                "status": "active",
            }
        ],
    )
    runner = CliRunner()

    result = runner.invoke(app, ["evidence-benchmark", str(artifact_dir), "--questions", str(questions)])

    assert result.exit_code == 0
    assert json.loads(result.output)["summary"]["correct"] == 1
    assert load_evidence_questions(questions)[0]["id"] == "fixture-auth"


def _artifact_with_semantics(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return true; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/evidence")
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    write_json(artifact_dir / "structural-artifact.json", artifact.model_dump(mode="json"))
    run_classification_on_artifact(artifact_dir, use_openai=False)
    return artifact_dir
