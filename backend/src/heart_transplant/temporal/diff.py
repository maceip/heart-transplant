from __future__ import annotations

from collections import Counter
from pathlib import Path

from heart_transplant.temporal.git_miner import changed_files_between
from heart_transplant.temporal.models import ArchitectureDiff, ArchitectureSnapshot, FileArchitectureChange
from heart_transplant.temporal.snapshot import architecture_snapshot, include_architectural_file


def architecture_diff(repo_path: Path, before_ref: str, after_ref: str) -> ArchitectureDiff:
    before = architecture_snapshot(repo_path, before_ref)
    after = architecture_snapshot(repo_path, after_ref)
    return diff_snapshots(repo_path, before, after)


def diff_snapshots(repo_path: Path, before: ArchitectureSnapshot, after: ArchitectureSnapshot) -> ArchitectureDiff:
    before_files = {file.path: file for file in before.files}
    after_files = {file.path: file for file in after.files}
    git_changes = changed_files_between(Path(repo_path), before.commit_sha, after.commit_sha)
    file_changes: list[FileArchitectureChange] = []
    block_delta: Counter[str] = Counter()

    for status, path in git_changes:
        if not include_architectural_file(path):
            continue
        before_blocks = before_files.get(path).inferred_blocks if path in before_files else []
        after_blocks = after_files.get(path).inferred_blocks if path in after_files else []
        if not before_blocks and not after_blocks:
            continue
        file_changes.append(
            FileArchitectureChange(
                path=path,
                status=status,
                before_blocks=before_blocks,
                after_blocks=after_blocks,
            )
        )
        for block in before_blocks:
            block_delta[block] -= 1
        for block in after_blocks:
            block_delta[block] += 1

    return ArchitectureDiff(
        repo_path=str(Path(repo_path).resolve()),
        before_sha=before.commit_sha,
        after_sha=after.commit_sha,
        file_changes=sorted(file_changes, key=lambda item: (item.path, item.status)),
        block_delta={k: v for k, v in sorted(block_delta.items()) if v != 0},
    )
