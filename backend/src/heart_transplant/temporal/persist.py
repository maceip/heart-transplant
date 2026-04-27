from __future__ import annotations

from typing import Any

from heart_transplant.db.connection import connect_surreal, rid
from heart_transplant.db.indexes import apply_indexes
from heart_transplant.db.schema import apply_schema
from heart_transplant.temporal.models import TemporalMetricsReport


def persist_temporal_metrics(
    report: TemporalMetricsReport,
    *,
    db: Any | None = None,
    clear_repo: bool = True,
) -> dict[str, Any]:
    """Persist deterministic temporal snapshots, diffs, and summary metrics."""
    if db is None:
        db = connect_surreal()
    apply_schema(db)
    apply_indexes(db)

    repo_path = report.repo_path
    if clear_repo:
        try:
            db.query("DELETE ht_temporal WHERE repo_path = $repo_path", {"repo_path": repo_path})
        except Exception:  # noqa: BLE001
            pass

    rows = 0
    for snapshot in report.snapshots:
        db.upsert(
            rid("ht_temporal", f"{repo_path}:snapshot:{snapshot.commit_sha}"),
            {
                "record_kind": "snapshot",
                "repo_path": repo_path,
                "commit_sha": snapshot.commit_sha,
                "authored_at": snapshot.authored_at,
                "subject": snapshot.subject,
                "file_count": snapshot.file_count,
                "block_file_counts": snapshot.block_file_counts,
            },
        )
        rows += 1

    for diff in report.diffs:
        db.upsert(
            rid("ht_temporal", f"{repo_path}:diff:{diff.before_sha}:{diff.after_sha}"),
            {
                "record_kind": "diff",
                "repo_path": repo_path,
                "before_sha": diff.before_sha,
                "after_sha": diff.after_sha,
                "commit_sha": diff.after_sha,
                "file_change_count": len(diff.file_changes),
                "block_delta": diff.block_delta,
            },
        )
        rows += 1

    db.upsert(
        rid("ht_temporal", f"{repo_path}:summary:{report.commits[-1] if report.commits else 'empty'}"),
        {
            "record_kind": "summary",
            "repo_path": repo_path,
            "commit_sha": report.commits[-1] if report.commits else "",
            "commit_count": report.commit_count,
            "block_churn_rate": report.block_churn_rate,
            "file_hotspots": report.file_hotspots,
            "coupling_tightness_trend": report.coupling_tightness_trend,
            "architectural_drift_candidate_rate": report.architectural_drift_candidate_rate,
            "regret_accumulation_score": report.regret_accumulation_score,
            "pattern_success_index": report.pattern_success_index,
        },
    )
    rows += 1

    return {"status": "ok", "repo_path": repo_path, "ht_temporal_rows": rows}

