from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.phase_metrics import collect_phase_metrics


def test_phase_metrics_reports_real_phase_availability(tmp_path: Path) -> None:
    repo_dir, artifact_dir, repo_root = _build_fixture_artifact(tmp_path)

    report = collect_phase_metrics(artifact_dir, repo_path=repo_dir, repo_root=repo_root)

    phases = {phase["phase_id"]: phase for phase in report["phases"]}
    assert phases["phase_0"]["availability"] == "available"
    assert phases["phase_1"]["availability"] == "available"
    assert phases["phase_2"]["availability"] == "available"
    assert phases["phase_3"]["availability"] == "available"
    assert phases["phase_4"]["availability"] == "blocked"
    assert phases["phase_5"]["availability"] == "blocked"
    assert phases["phase_6"]["availability"] == "blocked"
    assert phases["phase_7"]["availability"] == "blocked"
    assert phases["phase_8"]["availability"] == "blocked"

    metrics0 = {item["metric_id"]: item["value"] for item in phases["phase_0"]["metrics"]}
    metrics1 = {item["metric_id"]: item["value"] for item in phases["phase_1"]["metrics"]}
    metrics3 = {item["metric_id"]: item["value"] for item in phases["phase_3"]["metrics"]}

    assert metrics0["resolved_symbol_rate"] == 1.0
    assert metrics0["orphaned_symbol_count"] == 0
    assert metrics1["node_kind_diversity"] >= 1
    assert metrics3["verify_pass"] is True
    assert report["integrity"]["runtime_repo_specific_hit_count"] == 0


def test_phase_metrics_can_hydrate_semantic_and_eval_phases(tmp_path: Path) -> None:
    repo_dir, artifact_dir, repo_root = _build_fixture_artifact(tmp_path, code="export function sessionGuard() { return 'ok'; }\n")
    structural = json.loads((artifact_dir / "structural-artifact.json").read_text(encoding="utf-8"))
    node_id = structural["code_nodes"][0]["scip_id"]
    gold_path = tmp_path / "gold.json"
    gold_path.write_text(
        json.dumps([{"node_id": node_id, "expected_block": "Access Control"}]),
        encoding="utf-8",
    )

    report = collect_phase_metrics(
        artifact_dir,
        repo_path=repo_dir,
        repo_root=repo_root,
        gold_set_path=gold_path,
        classify_if_missing=True,
        use_openai=False,
    )

    phases = {phase["phase_id"]: phase for phase in report["phases"]}
    assert phases["phase_4"]["availability"] == "available"
    assert phases["phase_7"]["availability"] == "available"

    metrics4 = {item["metric_id"]: item["value"] for item in phases["phase_4"]["metrics"]}
    metrics7 = {item["metric_id"]: item["value"] for item in phases["phase_7"]["metrics"]}

    assert metrics4["assignment_coverage_rate"] > 0.0
    assert metrics4["semantic_summary_count"] > 0
    assert metrics4["entity_count"] > 0
    assert metrics4["action_count"] > 0
    assert metrics7["gold_example_count"] == 1
    assert 0.0 <= metrics7["benchmark_accuracy"] <= 1.0


def _build_fixture_artifact(tmp_path: Path, *, code: str | None = None) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "workspace"
    runtime_root = repo_root / "backend" / "src" / "heart_transplant"
    vendor_root = repo_root / "vendor" / "github-repos"
    runtime_root.mkdir(parents=True)
    vendor_root.mkdir(parents=True)
    (vendor_root / "sample-repo").mkdir()

    repo_dir = tmp_path / "repo"
    (repo_dir / "src").mkdir(parents=True)
    (repo_dir / "src" / "util.ts").write_text("export const helper = () => 1;\n", encoding="utf-8")
    (repo_dir / "src" / "app.ts").write_text(
        code or "import { helper } from './util';\nexport function runApp() { return helper(); }\n",
        encoding="utf-8",
    )

    artifact = ingest_repository(repo_dir, "acme/repo")
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    (artifact_dir / "structural-artifact.json").write_text(
        json.dumps(artifact.model_dump(mode="json")),
        encoding="utf-8",
    )
    (artifact_dir / "index.scip").write_bytes(b"SCIP")
    (artifact_dir / "scip-index.json").write_text(
        json.dumps(
            {
                "indexer": "scip-typescript",
                "version": "0.4.0",
                "output_path": str(artifact_dir / "index.scip"),
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "scip-consumed.json").write_text(
        json.dumps(
            {
                "resolution": {
                    "resolved_code_nodes": artifact.node_count,
                    "nodes_with_scip_identity": artifact.node_count,
                    "total_code_nodes": artifact.node_count,
                    "unresolved_code_nodes": 0,
                },
                "documents": [
                    {
                        "relative_path": "src/app.ts",
                        "definition_count": max(artifact.node_count - 1, 1),
                        "reference_count": 1,
                    },
                    {
                        "relative_path": "src/util.ts",
                        "definition_count": 1,
                        "reference_count": 0,
                    },
                ],
                "reference_routing": {
                    "code_to_code": 1,
                    "file_fallback": 0,
                    "cross_repo": 0,
                },
                "scip_backed_edge_counts": {
                    "DEFINES": artifact.node_count,
                    "REFERENCES": 1,
                    "CROSS_REFERENCE": 0,
                    "IMPLEMENTS": 0,
                },
                "orphaned_symbol_count": 0,
            }
        ),
        encoding="utf-8",
    )
    return repo_dir, artifact_dir, repo_root
