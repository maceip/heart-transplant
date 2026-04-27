from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from heart_transplant.temporal.drift import detect_architectural_drift
from heart_transplant.temporal.metrics import temporal_metrics


def run_temporal_gates(
    repo_path: Path,
    *,
    max_commits: int = 25,
    expected_changes: list[dict[str, str]] | None = None,
    drift_before: str | None = None,
    drift_after: str | None = None,
    expected_drift_paths: set[str] | None = None,
) -> dict[str, Any]:
    """Run Phase 9 gates that can be checked without hidden state."""
    repo_path = repo_path.resolve()
    metrics_a = temporal_metrics(repo_path, max_commits=max_commits)
    metrics_b = temporal_metrics(repo_path, max_commits=max_commits)
    reproducible = stable_json(metrics_a.model_dump(mode="json")) == stable_json(metrics_b.model_dump(mode="json"))

    gates = [
        {
            "gate_id": "temporal_gate_metrics_reproducible",
            "status": "pass" if reproducible else "fail",
            "outputs": {
                "commit_count": metrics_a.commit_count,
                "bit_for_bit_equal": reproducible,
            },
        }
    ]

    if expected_changes is None:
        gates.append(
            {
                "gate_id": "temporal_gate_known_changes",
                "status": "blocked",
                "blocked_by": ["expected_changes"],
                "outputs": {},
            }
        )
    else:
        observed = observed_changes(metrics_a.model_dump(mode="json"))
        expected = {change_key(row) for row in expected_changes}
        matched = observed & expected
        gates.append(
            {
                "gate_id": "temporal_gate_known_changes",
                "status": "pass" if len(matched) >= min(3, len(expected)) and matched == expected else "fail",
                "outputs": {
                    "expected_count": len(expected),
                    "matched_count": len(matched),
                    "unmatched": sorted(expected - matched),
                    "unexpected_exact_matches": sorted(matched - expected),
                },
            }
        )

    if not drift_before or not drift_after or expected_drift_paths is None:
        gates.append(
            {
                "gate_id": "temporal_gate_drift_detection",
                "status": "blocked",
                "blocked_by": ["drift_before", "drift_after", "expected_drift_paths"],
                "outputs": {},
            }
        )
    else:
        drift = detect_architectural_drift(
            repo_path,
            drift_before,
            drift_after,
            expected_paths=expected_drift_paths,
        )
        precision = float(drift.precision or 0.0)
        recall = float(drift.recall or 0.0)
        gates.append(
            {
                "gate_id": "temporal_gate_drift_detection",
                "status": "pass" if precision >= 0.85 and recall >= 0.85 else "fail",
                "outputs": {
                    "precision": precision,
                    "recall": recall,
                    "finding_paths": [finding.path for finding in drift.findings],
                },
            }
        )

    failed = sum(1 for gate in gates if gate["status"] == "fail")
    blocked = sum(1 for gate in gates if gate["status"] == "blocked")
    return {
        "repo_path": str(repo_path),
        "summary": {
            "gate_count": len(gates),
            "failed": failed,
            "blocked": blocked,
            "overall_status": "pass" if failed == 0 and blocked == 0 else "blocked" if blocked else "fail",
        },
        "gates": gates,
    }


def observed_changes(metrics: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for diff in metrics.get("diffs", []):
        after_sha = str(diff.get("after_sha", ""))
        for change in diff.get("file_changes", []):
            out.add(change_key({"after_sha": after_sha, "path": change.get("path", ""), "status": change.get("status", "")}))
    return out


def change_key(row: dict[str, Any]) -> str:
    return f"{row.get('after_sha')}|{row.get('path')}|{row.get('status')}"


def stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
