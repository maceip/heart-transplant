from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from heart_transplant.execution.models import ValidationSummary


def run_post_edit_validation(repo_path: Path, *, timeout: int = 120) -> ValidationSummary:
    """Best-effort checks: `python -m compileall` on repo (no network)."""

    repo_path = repo_path.resolve()
    target = str(repo_path / "src") if (repo_path / "src").is_dir() else str(repo_path)
    cmd = [sys.executable, "-m", "compileall", "-q", target]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        ok = proc.returncode == 0
        return ValidationSummary(
            ran=True,
            command=cmd,
            exit_code=proc.returncode,
            stdout_tail=(proc.stdout + proc.stderr)[-800:],
            note="compileall ok" if ok else "compileall reported issues (see tail)",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return ValidationSummary(
            ran=False,
            command=cmd,
            exit_code=None,
            note=str(exc),
        )
