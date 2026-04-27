from __future__ import annotations

from collections import Counter
from pathlib import Path

from heart_transplant.temporal.block_churn import infer_blocks_for_path
from heart_transplant.temporal.git_miner import commit_metadata, list_files_at_commit
from heart_transplant.temporal.models import ArchitectureSnapshot, FileBlockSnapshot


IGNORED_ARCHIVE_PATH_PARTS = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".turbo",
    "__pycache__",
}


def architecture_snapshot(repo_path: Path, ref: str = "HEAD") -> ArchitectureSnapshot:
    repo_path = repo_path.resolve()
    sha, authored_at, subject = commit_metadata(repo_path, ref)
    files = [
        FileBlockSnapshot(path=path, inferred_blocks=infer_blocks_for_path(path))
        for path in list_files_at_commit(repo_path, sha)
        if include_architectural_file(path)
    ]
    block_counts: Counter[str] = Counter()
    for file in files:
        for block in file.inferred_blocks:
            block_counts[block] += 1
    return ArchitectureSnapshot(
        repo_path=str(repo_path),
        commit_sha=sha,
        authored_at=authored_at,
        subject=subject,
        reconstruction_mode="path_inference",
        file_count=len(files),
        files=files,
        block_file_counts=dict(sorted(block_counts.items())),
        limitations=[
            "Snapshot reconstructs versioned file lists and block labels from normalized paths; it does not replay Tree-sitter plus SCIP over historical source.",
        ],
    )


def include_architectural_file(path: str) -> bool:
    normalized = path.replace("\\", "/")
    parts = set(normalized.split("/"))
    if parts & IGNORED_ARCHIVE_PATH_PARTS:
        return False
    if normalized.endswith((".lock", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".map")):
        return False
    return True
