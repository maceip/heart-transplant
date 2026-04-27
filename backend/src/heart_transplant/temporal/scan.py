from __future__ import annotations

from collections import Counter
import subprocess
import tarfile
import tempfile
from pathlib import Path

from heart_transplant.artifact_store import artifact_root, timestamp_slug, write_json
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.temporal.git_miner import collect_commits, run_git
from heart_transplant.temporal.models import CommitRecord, TemporalGraphSnapshot, TemporalScanReport


def temporal_scan(
    repo_path: Path,
    *,
    max_commits: int = 50,
    since: str | None = None,
    replay_snapshots: bool = False,
    replay_limit: int = 5,
) -> TemporalScanReport:
    commits = collect_commits(repo_path, max_commits=max_commits, since=since)
    block_churn: Counter[str] = Counter()
    file_hotspots: Counter[str] = Counter()
    for commit in commits:
        for changed in commit.changed_files:
            file_hotspots[changed.path] += 1
            for block in changed.inferred_blocks:
                block_churn[block] += 1
    replayed = replay_temporal_ingest(repo_path, commits[: max(0, replay_limit)]) if replay_snapshots else []
    return TemporalScanReport(
        repo_path=str(repo_path.resolve()),
        commit_count=len(commits),
        commits=commits,
        block_churn=dict(sorted(block_churn.items())),
        file_hotspots=dict(sorted(file_hotspots.items(), key=lambda item: (-item[1], item[0]))[:100]),
        replayed_snapshots=replayed,
        limitations=limitations(commits, replay_snapshots=replay_snapshots, replayed=replayed),
    )


def replay_temporal_ingest(repo_path: Path, commits: list[CommitRecord]) -> list[TemporalGraphSnapshot]:
    """Replay Tree-sitter ingest against selected historical commits without mutating the worktree."""

    repo_path = repo_path.resolve()
    snapshots: list[TemporalGraphSnapshot] = []
    for commit in commits:
        with tempfile.TemporaryDirectory(prefix="heart-transplant-replay-") as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "repo"
            target.mkdir()
            archive_path = tmp_path / "archive.tar"
            with archive_path.open("wb") as archive:
                subprocess.run(
                    ["git", "archive", commit.sha, "--format=tar"],
                    cwd=repo_path,
                    check=True,
                    stdout=archive,
                    stderr=subprocess.PIPE,
                )
            with tarfile.open(archive_path) as archive:
                archive.extractall(target)
            artifact = ingest_repository(target, f"temporal/{repo_path.name}@{commit.sha[:12]}")
            snapshots.append(
                TemporalGraphSnapshot(
                    commit_sha=commit.sha,
                    authored_at=commit.authored_at,
                    subject=commit.subject,
                    node_count=artifact.node_count,
                    edge_count=artifact.edge_count,
                    file_node_count=len(artifact.file_nodes),
                    parser_backends=artifact.parser_backends,
                )
            )
    return snapshots


def limitations(commits: list[CommitRecord], *, replay_snapshots: bool = False, replayed: list[TemporalGraphSnapshot] | None = None) -> list[str]:
    notes: list[str] = []
    if not commits:
        notes.append("No commits were returned for the requested range.")
    if replay_snapshots:
        notes.append(f"Tree-sitter replay was run for {len(replayed or [])} selected commits; SCIP replay is still omitted for speed.")
    else:
        notes.append("Phase 9 temporal scan infers blocks from changed file paths unless --replay-snapshots is enabled.")
    notes.append("No drift detection claim is made yet; this report is a deterministic git-history baseline.")
    return notes


def write_temporal_scan(report: TemporalScanReport, out: Path | None = None) -> Path:
    dest = out or (artifact_root().parent / "reports" / f"{timestamp_slug()}__phase-9-temporal-scan.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, report.model_dump(mode="json"))
    return dest
