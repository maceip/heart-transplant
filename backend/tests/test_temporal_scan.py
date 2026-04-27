from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from heart_transplant.temporal.diff import architecture_diff
from heart_transplant.temporal.drift import detect_architectural_drift
from heart_transplant.temporal.gates import run_temporal_gates
from heart_transplant.temporal.metrics import temporal_metrics
from heart_transplant.temporal.persist import persist_temporal_metrics
from heart_transplant.temporal.scan import temporal_scan
from heart_transplant.temporal.snapshot import architecture_snapshot


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def out(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for temporal scan tests")
def test_temporal_scan_reports_block_churn_from_real_git_history(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Tester"], repo)

    (repo / "src").mkdir()
    (repo / "src" / "auth.ts").write_text("export function login() { return true; }\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "add auth"], repo)

    (repo / "src" / "db.ts").write_text("export function query() { return []; }\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "add db"], repo)

    report = temporal_scan(repo, max_commits=10)

    assert report.commit_count == 2
    assert report.block_churn["Access Control"] == 1
    assert report.block_churn["Data Persistence"] == 1
    assert report.file_hotspots["src/auth.ts"] == 1
    assert report.file_hotspots["src/db.ts"] == 1
    assert report.limitations


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for temporal scan tests")
def test_temporal_snapshot_diff_metrics_and_gates_are_exact_and_reproducible(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Tester"], repo)

    (repo / "src").mkdir()
    (repo / "src" / "auth.ts").write_text("export function login() { return true; }\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "add auth"], repo)
    sha1 = out(["git", "rev-parse", "HEAD"], repo)

    (repo / "src" / "db.ts").write_text("export function query() { return []; }\n", encoding="utf-8")
    run(["git", "add", "."], repo)
    run(["git", "commit", "-m", "add db"], repo)
    sha2 = out(["git", "rev-parse", "HEAD"], repo)

    (repo / "src" / "routes").mkdir()
    (repo / "src" / "routes" / "auth.ts").write_text((repo / "src" / "auth.ts").read_text(encoding="utf-8"), encoding="utf-8")
    (repo / "src" / "auth.ts").unlink()
    run(["git", "add", "-A"], repo)
    run(["git", "commit", "-m", "move auth to route"], repo)
    sha3 = out(["git", "rev-parse", "HEAD"], repo)

    snap = architecture_snapshot(repo, sha2)
    assert snap.commit_sha == sha2
    assert snap.reconstruction_mode == "path_inference"
    assert "does not replay Tree-sitter plus SCIP" in snap.limitations[0]
    assert snap.block_file_counts["Access Control"] == 1
    assert snap.block_file_counts["Data Persistence"] == 1

    diff = architecture_diff(repo, sha1, sha2)
    assert diff.after_sha == sha2
    assert any(change.path == "src/db.ts" and change.status == "A" for change in diff.file_changes)

    metrics_a = temporal_metrics(repo, max_commits=10)
    metrics_b = temporal_metrics(repo, max_commits=10)
    assert metrics_a.model_dump(mode="json") == metrics_b.model_dump(mode="json")
    assert metrics_a.coupling_tightness_trend
    assert metrics_a.pattern_success_index
    assert metrics_a.architectural_drift_candidate_rate >= 0.0

    drift = detect_architectural_drift(repo, sha2, sha3, expected_paths={"src/routes/auth.ts"})
    assert drift.after_sha == sha3
    assert drift.precision == 1.0
    assert drift.recall == 1.0

    gate_report = run_temporal_gates(
        repo,
        max_commits=10,
        expected_changes=[
            {"after_sha": sha2, "path": "src/db.ts", "status": "A"},
            {"after_sha": sha3, "path": "src/auth.ts", "status": "D"},
            {"after_sha": sha3, "path": "src/routes/auth.ts", "status": "A"},
        ],
        drift_before=sha2,
        drift_after=sha3,
        expected_drift_paths={"src/routes/auth.ts"},
    )
    assert gate_report["summary"]["overall_status"] == "pass"

    from surrealdb import Surreal  # type: ignore[import-not-found]

    with Surreal("mem://") as db:  # noqa: SIM117
        db.use("htp9", "temporal")
        persisted = persist_temporal_metrics(metrics_a, db=db)
        assert persisted["ht_temporal_rows"] == len(metrics_a.snapshots) + len(metrics_a.diffs) + 1
        rows = db.query("SELECT count() FROM ht_temporal WHERE repo_path = $repo_path GROUP ALL", {"repo_path": metrics_a.repo_path})
        assert int(rows[0]["count"]) == persisted["ht_temporal_rows"]
