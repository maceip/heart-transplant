from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from heart_transplant.cli import app
from heart_transplant.training import build_training_packet


def test_training_packet_generates_review_files_from_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return true; }\n", encoding="utf-8")
    out_dir = tmp_path / "packet"

    result = build_training_packet(repo, repo_name="test/training", out_dir=out_dir)

    assert result["report_type"] == "training_packet"
    assert Path(result["artifact_dir"]).is_dir()
    assert (out_dir / "README.md").is_file()
    assert (out_dir / "review-nodes.json").is_file()
    assert (out_dir / "review-edges.json").is_file()
    assert (out_dir / "review-evidence-questions.json").is_file()
    assert (out_dir / "review-blast-radius-scenarios.json").is_file()
    questions = json.loads((out_dir / "review-evidence-questions.json").read_text(encoding="utf-8"))
    assert any("auth" in row["question"].lower() for row in questions)


def test_fixture_candidates_cli_is_one_command(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "db.ts").write_text("export function queryUsers() { return []; }\n", encoding="utf-8")
    out_dir = tmp_path / "packet"
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["fixture-candidates", str(repo), "--repo-name", "test/training-cli", "--out-dir", str(out_dir)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["counts"]["candidate_nodes"] >= 1
    assert (out_dir / "review-nodes.json").is_file()
