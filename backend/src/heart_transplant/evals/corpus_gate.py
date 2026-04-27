from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def evaluate_corpus_gate(
    results_path: Path,
    *,
    min_attempted: int = 50,
    min_ok_rate: float = 1.0,
    max_ingest_failed: int = 0,
    max_zero_node_ok: int = 0,
) -> dict[str, Any]:
    """Evaluate a corpus smell-test JSONL as a reproducible quality gate."""

    rows = load_jsonl(results_path)
    status_counts = Counter(str(row.get("status", "unknown")) for row in rows)
    language_counts = Counter(str(row.get("language", "unknown")) for row in rows)
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    ingest_failed_rows = [row for row in rows if row.get("status") == "ingest_failed"]
    zero_node_ok_rows = [row for row in ok_rows if int(row.get("node_count") or 0) == 0]
    ok_rate = len(ok_rows) / max(len(rows), 1)

    checks = [
        {
            "check_id": "attempted_count",
            "status": "pass" if len(rows) >= min_attempted else "fail",
            "value": len(rows),
            "threshold": min_attempted,
        },
        {
            "check_id": "ok_rate",
            "status": "pass" if ok_rate >= min_ok_rate else "fail",
            "value": ok_rate,
            "threshold": min_ok_rate,
        },
        {
            "check_id": "ingest_failed_count",
            "status": "pass" if len(ingest_failed_rows) <= max_ingest_failed else "fail",
            "value": len(ingest_failed_rows),
            "threshold": max_ingest_failed,
        },
        {
            "check_id": "zero_node_ok_count",
            "status": "pass" if len(zero_node_ok_rows) <= max_zero_node_ok else "fail",
            "value": len(zero_node_ok_rows),
            "threshold": max_zero_node_ok,
        },
    ]
    failed = sum(1 for check in checks if check["status"] == "fail")

    return {
        "report_type": "corpus_quality_gate",
        "results_path": str(results_path.resolve()),
        "summary": {
            "attempted": len(rows),
            "ok": len(ok_rows),
            "ok_rate": ok_rate,
            "ingest_failed": len(ingest_failed_rows),
            "zero_node_ok": len(zero_node_ok_rows),
            "overall_status": "pass" if failed == 0 else "fail",
        },
        "thresholds": {
            "min_attempted": min_attempted,
            "min_ok_rate": min_ok_rate,
            "max_ingest_failed": max_ingest_failed,
            "max_zero_node_ok": max_zero_node_ok,
        },
        "checks": checks,
        "by_status": dict(sorted(status_counts.items())),
        "by_language": dict(sorted(language_counts.items())),
        "ingest_failures": [
            {
                "index": row.get("index"),
                "language": row.get("language"),
                "full_name": row.get("full_name"),
                "status": row.get("status"),
                "error": row.get("error"),
            }
            for row in ingest_failed_rows
        ],
        "zero_node_ok_artifacts": [
            {
                "index": row.get("index"),
                "language": row.get("language"),
                "full_name": row.get("full_name"),
                "parser_backends": row.get("parser_backends"),
            }
            for row in zero_node_ok_rows
        ],
    }
