from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from heart_transplant.cli import app
from heart_transplant.demo import run_logiclens_demo


def _seed_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "auth.ts").write_text(
        "export function sessionGuard(token: string) { return token.length > 0; }\n"
        "export function requireAuth() { return sessionGuard('x'); }\n",
        encoding="utf-8",
    )
    (repo / "db.ts").write_text(
        "export async function queryUsers() { return []; }\n"
        "export async function migrate() { return true; }\n",
        encoding="utf-8",
    )
    (repo / "routes.ts").write_text(
        "export function registerRoutes(app: any) {\n"
        "  app.get('/health', () => 'ok');\n"
        "  app.post('/login', () => 'ok');\n"
        "}\n",
        encoding="utf-8",
    )
    (repo / "config.ts").write_text(
        "export const config = { env: 'test', logLevel: 'info' };\n",
        encoding="utf-8",
    )


def test_run_logiclens_demo_writes_packet_and_summary(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_repo(repo)
    out_dir = tmp_path / "demo"

    result = run_logiclens_demo(repo, repo_name="test/demo", out_dir=out_dir, mc_runs=4)

    assert result["report_type"] == "logiclens_demo"
    summary = result["summary"]
    assert summary["node_count"] > 0
    assert summary["edge_count"] >= 0
    assert summary["total_questions"] == 7
    assert (out_dir / "logiclens-demo.json").is_file()
    assert (out_dir / "logiclens-demo.md").is_file()

    report = json.loads((out_dir / "logiclens-demo.json").read_text(encoding="utf-8"))
    assert report["canonical_graph"]["node_count"] == summary["node_count"]
    assert any(answer["files"] for answer in report["evidence_answers"])
    assert len(report["simulations"]) == 3
    assert "regret" in report

    console = (out_dir / "logiclens-demo.md").read_text(encoding="utf-8")
    assert "LogicLens demo" in console
    assert "Canonical layers" in console
    assert "Evidence answers" in console


def test_logiclens_demo_cli_is_one_command(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _seed_repo(repo)
    out_dir = tmp_path / "packet"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "logiclens-demo",
            str(repo),
            "--repo-name",
            "test/demo-cli",
            "--out-dir",
            str(out_dir),
            "--mc-runs",
            "4",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["report_type"] == "logiclens_demo"
    assert payload["summary"]["node_count"] > 0
    assert (out_dir / "logiclens-demo.json").is_file()
    assert (out_dir / "logiclens-demo.md").is_file()
