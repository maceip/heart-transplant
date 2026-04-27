from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.evals.corpus_gate import evaluate_corpus_gate


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_corpus_gate_fails_on_ingest_failures_and_zero_node_successes(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {"status": "ok", "language": "TypeScript", "full_name": "demo/ok", "node_count": 3},
            {"status": "ok", "language": "Java", "full_name": "demo/zero", "node_count": 0},
            {"status": "ingest_failed", "language": "Go", "full_name": "demo/fail"},
        ],
    )

    report = evaluate_corpus_gate(results, min_attempted=3)

    assert report["summary"]["overall_status"] == "fail"
    assert report["summary"]["ingest_failed"] == 1
    assert report["summary"]["zero_node_ok"] == 1
    assert {check["check_id"]: check["status"] for check in report["checks"]} == {
        "attempted_count": "pass",
        "ok_rate": "fail",
        "ingest_failed_count": "fail",
        "zero_node_ok_count": "fail",
    }


def test_corpus_gate_can_pass_with_explicit_thresholds(tmp_path: Path) -> None:
    results = tmp_path / "results.jsonl"
    _write_jsonl(
        results,
        [
            {"status": "ok", "language": "TypeScript", "full_name": "demo/a", "node_count": 1},
            {"status": "ok", "language": "Go", "full_name": "demo/b", "node_count": 2},
        ],
    )

    report = evaluate_corpus_gate(
        results,
        min_attempted=2,
        min_ok_rate=1.0,
        max_ingest_failed=0,
        max_zero_node_ok=0,
    )

    assert report["summary"]["overall_status"] == "pass"
