from __future__ import annotations

from collections import Counter
from pathlib import Path

from heart_transplant.artifact_store import artifact_root, timestamp_slug, write_json
from heart_transplant.temporal.diff import diff_snapshots
from heart_transplant.temporal.git_miner import collect_commits
from heart_transplant.temporal.models import ArchitectureDiff, TemporalMetricsReport
from heart_transplant.temporal.snapshot import architecture_snapshot


def temporal_metrics(repo_path: Path, *, max_commits: int = 25, since: str | None = None) -> TemporalMetricsReport:
    repo_path = repo_path.resolve()
    # collect_commits returns newest first; metrics should be chronological.
    commits = list(reversed(collect_commits(repo_path, max_commits=max_commits, since=since)))
    snapshots = [architecture_snapshot(repo_path, commit.sha) for commit in commits]
    diffs: list[ArchitectureDiff] = [
        diff_snapshots(repo_path, before, after)
        for before, after in zip(snapshots, snapshots[1:], strict=False)
    ]
    block_delta_total: Counter[str] = Counter()
    file_hotspots: Counter[str] = Counter()
    block_activity: Counter[str] = Counter()
    block_drift_candidates: Counter[str] = Counter()
    coupling_trend: list[float] = []
    drift_candidate_count = 0
    for diff in diffs:
        block_delta_total.update(diff.block_delta)
        changed_block_sets = []
        for changed in diff.file_changes:
            file_hotspots[changed.path] += 1
            involved_blocks = set(changed.before_blocks) | set(changed.after_blocks)
            changed_block_sets.append(involved_blocks)
            for block in involved_blocks:
                block_activity[block] += 1
            if set(changed.before_blocks) != set(changed.after_blocks):
                drift_candidate_count += 1
                for block in involved_blocks:
                    block_drift_candidates[block] += 1
        coupling_trend.append(
            sum(len(blocks) for blocks in changed_block_sets) / max(len(changed_block_sets), 1)
        )
    denominator = max(len(diffs), 1)
    changed_file_count = sum(len(diff.file_changes) for diff in diffs)
    drift_rate = drift_candidate_count / max(changed_file_count, 1)
    hotspot_total = sum(file_hotspots.values())
    hotspot_concentration = (
        max(file_hotspots.values(), default=0) / hotspot_total
        if hotspot_total
        else 0.0
    )
    return TemporalMetricsReport(
        repo_path=str(repo_path),
        commit_count=len(commits),
        commits=[commit.sha for commit in commits],
        snapshots=snapshots,
        diffs=diffs,
        block_churn_rate={k: abs(v) / denominator for k, v in sorted(block_delta_total.items())},
        block_delta_total=dict(sorted(block_delta_total.items())),
        file_hotspots=dict(sorted(file_hotspots.items(), key=lambda item: (-item[1], item[0]))[:100]),
        coupling_tightness_trend=[round(value, 4) for value in coupling_trend],
        architectural_drift_candidate_rate=round(drift_rate, 4),
        regret_accumulation_score=round(min(1.0, drift_rate + hotspot_concentration), 4),
        pattern_success_index=pattern_success_index(block_activity, block_drift_candidates),
        limitations=limitations(len(commits)),
    )


def limitations(commit_count: int) -> list[str]:
    notes = [
        "Phase 9 metrics are deterministic and git-backed.",
        "Current snapshots infer blocks from versioned file paths; they do not yet replay full Tree-sitter/SCIP ingest for every commit.",
    ]
    if commit_count < 2:
        notes.append("At least two commits are required for non-empty architectural diffs.")
    return notes


def pattern_success_index(
    block_activity: Counter[str],
    block_drift_candidates: Counter[str],
) -> dict[str, float]:
    """Score blocks that change often without changing inferred responsibility."""
    scores: dict[str, float] = {}
    for block, activity in block_activity.items():
        if not activity:
            continue
        stable_rate = 1.0 - (block_drift_candidates.get(block, 0) / activity)
        scores[block] = round(max(0.0, min(1.0, stable_rate)), 4)
    return dict(sorted(scores.items()))


def write_temporal_metrics(report: TemporalMetricsReport, out: Path | None = None) -> Path:
    dest = out or (artifact_root().parent / "reports" / f"{timestamp_slug()}__phase-9-temporal-metrics.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, report.model_dump(mode="json"))
    return dest
