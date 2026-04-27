from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from heart_transplant.cli import app
from heart_transplant.causal.simulation import run_change_simulation
from heart_transplant.execution.orchestrator import run_transplant
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.multimodal.ingest import run_multimodal_ingest
from heart_transplant.regret.models import RegretItem
from heart_transplant.regret.scan import run_regret_scan
from heart_transplant.regret.surgery_planner import plan_for_regret


def test_phase_10_simulation_runs_on_minimal_artifact(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function login() { return 'ok'; }\n", encoding="utf-8")
    art = ingest_repository(repo, "test/causal")
    adir = tmp_path / "artifact"
    adir.mkdir()
    (adir / "structural-artifact.json").write_text(
        json.dumps(art.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    r = run_change_simulation("refactor login auth", adir, mc_runs=4, max_depth=3, max_nodes=30)
    assert r.phase_id == "phase_10"
    assert r.trace
    assert r.mc_runs == 4
    assert isinstance(r.impacted_node_ids, list)
    assert r.causal_overlay is not None
    assert r.causal_overlay.mean_adjusted_weight > 0
    assert r.self_consistency_score >= 0.0
    dumped = r.model_dump_json()
    assert "Δ" not in dumped
    assert "mean delta from structural base" in dumped

    cli = CliRunner().invoke(
        app,
        ["simulate-change", "refactor login auth", "--artifact-dir", str(adir), "--mc-runs", "4"],
    )
    assert cli.exit_code == 0
    cli.output.encode("cp1252")


def test_phase_11_regret_scan_emits_report(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text(
        "export function sessionGuard() {\n console.log('auth'); return true;\n}\n",
        encoding="utf-8",
    )
    art = ingest_repository(repo, "test/regret")
    adir = tmp_path / "artifact"
    adir.mkdir()
    (adir / "structural-artifact.json").write_text(
        json.dumps(art.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    report = run_regret_scan(adir, min_confidence=0.2)
    assert report.phase_id == "phase_11"
    assert isinstance(report.regrets, list)


def test_phase_11_logging_regret_gets_logging_specific_plan() -> None:
    item = RegretItem(
        regret_id="r1",
        pattern_id="logging_inconsistency",
        title="Logging inconsistency",
        score=0.8,
        confidence=0.8,
    )

    plan = plan_for_regret(item)

    text = " ".join(step.action for step in plan.steps).lower()
    assert "logging" in text
    assert "telemetry" in text
    assert "repository or data-access" not in text


def test_phase_12_transplant_planner_logs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "x.ts").write_text("export const x = 1;\n", encoding="utf-8")
    art = ingest_repository(repo, "test/exec")
    adir = tmp_path / "artifact"
    adir.mkdir()
    (adir / "structural-artifact.json").write_text(
        json.dumps(art.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    r = run_transplant("test/exec:scattered_auth", adir, dry_run=True)
    assert r.status == "planned"
    assert r.ledger_path


def test_phase_13_multimodal_ingest_writes_report(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src" / "api.ts").write_text("export function users() {}\n", encoding="utf-8")
    (root / "src" / "api.test.ts").write_text("import './api';\n", encoding="utf-8")
    (root / "openapi.json").write_text(
        json.dumps({"paths": {"/users": {"get": {"operationId": "listUsers"}}}}),
        encoding="utf-8",
    )
    out = tmp_path / "mm.json"
    report = run_multimodal_ingest(root, write_artifact=out, include_infra=False)
    assert report.phase_id == "phase_13"
    assert out.is_file()
    assert any(n.kind == "test" for n in report.nodes)
    assert any(n.kind == "openapi" for n in report.nodes)
    node_ids = {n.node_id for n in report.nodes}
    assert any(n.kind == "codefile" and n.node_id == "codefile:src/api.ts" for n in report.nodes)
    assert all(edge.target_id in node_ids for edge in report.edges if edge.target_id.startswith("codefile:"))
