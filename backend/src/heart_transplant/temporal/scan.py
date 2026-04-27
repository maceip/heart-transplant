from __future__ import annotations

from collections import Counter
from pathlib import Path

from heart_transplant.artifact_store import artifact_root, timestamp_slug, write_json
from heart_transplant.temporal.git_miner import collect_commits
from heart_transplant.temporal.models import CommitRecord, TemporalScanReport


def temporal_scan(repo_path: Path, *, max_commits: int = 50, since: str | None = None) -> TemporalScanReport:
    commits = collect_commits(repo_path, max_commits=max_commits, since=since)
    block_churn: Counter[str] = Counter()
    file_hotspots: Counter[str] = Counter()
    for commit in commits:
        for changed in commit.changed_files:
            file_hotspots[changed.path] += 1
            for block in changed.inferred_blocks:
                block_churn[block] += 1
    return TemporalScanReport(
        repo_path=str(repo_path.resolve()),
        commit_count=len(commits),
        commits=commits,
        block_churn=dict(sorted(block_churn.items())),
        file_hotspots=dict(sorted(file_hotspots.items(), key=lambda item: (-item[1], item[0]))[:100]),
        limitations=limitations(commits),
    )


def limitations(commits: list[CommitRecord]) -> list[str]:
    notes: list[str] = []
    if not commits:
        notes.append("No commits were returned for the requested range.")
    notes.append("Phase 9 temporal scan currently infers blocks from changed file paths only; it does not yet replay full graph snapshots per commit.")
    notes.append("No drift detection claim is made yet; this report is a deterministic git-history baseline.")
    return notes


def write_temporal_scan(report: TemporalScanReport, out: Path | None = None) -> Path:
    dest = out or (artifact_root().parent / "reports" / f"{timestamp_slug()}__phase-9-temporal-scan.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, report.model_dump(mode="json"))
    return dest
