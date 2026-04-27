from __future__ import annotations

import subprocess
from pathlib import Path

from heart_transplant.temporal.block_churn import infer_blocks_for_path
from heart_transplant.temporal.models import ChangedFile, CommitRecord


def git_available(repo_path: Path) -> bool:
    try:
        run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    except RuntimeError:
        return False
    return True


def collect_commits(repo_path: Path, *, max_commits: int = 50, since: str | None = None) -> list[CommitRecord]:
    repo_path = repo_path.resolve()
    if not git_available(repo_path):
        raise RuntimeError(f"Not a git repository: {repo_path}")
    args = [
        "log",
        f"--max-count={max(1, int(max_commits))}",
        "--date=iso-strict",
        "--pretty=format:%H%x1f%aI%x1f%s",
    ]
    if since:
        args.append(f"--since={since}")
    raw = run_git(repo_path, args)
    commits: list[CommitRecord] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        pieces = line.split("\x1f", 2)
        if len(pieces) != 3:
            continue
        sha, authored_at, subject = pieces
        commits.append(
            CommitRecord(
                sha=sha,
                authored_at=authored_at,
                subject=subject,
                changed_files=changed_files_for_commit(repo_path, sha),
            )
        )
    return commits


def resolve_ref(repo_path: Path, ref: str) -> str:
    return run_git(repo_path.resolve(), ["rev-parse", ref]).strip()


def commit_metadata(repo_path: Path, ref: str) -> tuple[str, str, str]:
    raw = run_git(repo_path.resolve(), ["show", "-s", "--date=iso-strict", "--format=%H%x1f%aI%x1f%s", ref]).strip()
    pieces = raw.split("\x1f", 2)
    if len(pieces) != 3:
        raise RuntimeError(f"Could not parse commit metadata for {ref}")
    return pieces[0], pieces[1], pieces[2]


def list_files_at_commit(repo_path: Path, ref: str) -> list[str]:
    raw = run_git(repo_path.resolve(), ["ls-tree", "-r", "--name-only", ref])
    return sorted(path.replace("\\", "/") for path in raw.splitlines() if path.strip())


def changed_files_between(repo_path: Path, before_ref: str, after_ref: str) -> list[tuple[str, str]]:
    raw = run_git(repo_path.resolve(), ["diff", "--name-status", "--find-renames", before_ref, after_ref])
    changes: list[tuple[str, str]] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            old_path = parts[1].replace("\\", "/")
            new_path = parts[2].replace("\\", "/")
            changes.append(("D", old_path))
            changes.append(("A", new_path))
            continue
        path = parts[-1].replace("\\", "/")
        changes.append((status, path))
    return sorted(changes, key=lambda item: (item[1], item[0]))


def changed_files_for_commit(repo_path: Path, sha: str) -> list[ChangedFile]:
    raw = run_git(repo_path, ["show", "--name-status", "--format=", "--find-renames", sha])
    changed: list[ChangedFile] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        changed.append(
            ChangedFile(
                path=path.replace("\\", "/"),
                status=status,
                inferred_blocks=infer_blocks_for_path(path),
            )
        )
    return changed


def run_git(repo_path: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout
