from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import artifact_root, read_json, timestamp_slug, write_json
from heart_transplant.evals.gold_benchmark import load_gold_set, run_benchmark
from heart_transplant.graph_smoke import run_graph_smoke
from heart_transplant.phase_metrics import collect_phase_metrics
from heart_transplant.validation_gates import run_validation_gates


def build_maximize_report(
    artifact_dir: Path,
    *,
    gold_set_path: Path | None = None,
    include_validation: bool = True,
) -> dict[str, Any]:
    """Build a machine-readable Phase 8.5 audit over one real artifact."""
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    repo_path = Path(str(structural["repo_path"])).resolve()
    semantic = read_json(artifact_dir / "semantic-artifact.json") if (artifact_dir / "semantic-artifact.json").is_file() else {}
    scip = read_json(artifact_dir / "scip-consumed.json") if (artifact_dir / "scip-consumed.json").is_file() else {}
    gold_items = load_gold_set(gold_set_path) if gold_set_path else []
    benchmark = run_benchmark(structural, gold_items) if gold_items else None
    phase_metrics = collect_phase_metrics(
        artifact_dir,
        repo_path=repo_path,
        gold_set_path=gold_set_path,
    )
    validation = run_validation_gates(repo_path, artifact_dir) if include_validation else None

    assignments = semantic.get("block_assignments", []) if isinstance(semantic, dict) else []
    return {
        "report_type": "phase_8_5_maximize_current_capabilities",
        "artifact_dir": str(artifact_dir),
        "repo_name": structural.get("repo_name"),
        "repo_path": str(repo_path),
        "summary": {
            "node_count": structural.get("node_count", 0),
            "edge_count": structural.get("edge_count", 0),
            "parser_backends": structural.get("parser_backends", []),
            "semantic_assignment_count": len(assignments),
            "semantic_block_count": len({str(row.get("primary_block")) for row in assignments if row.get("primary_block")}),
            "scip_eligible_resolved": scip.get("resolution", {}).get("scip_eligible_nodes_with_scip_identity"),
            "scip_eligible_total": scip.get("resolution", {}).get("scip_eligible_code_nodes"),
            "gold_scoped_total": benchmark.get("total") if benchmark else 0,
            "gold_scoped_accuracy": benchmark.get("accuracy") if benchmark else None,
        },
        "capability_matrix": capability_matrix(phase_metrics, validation),
        "graph_smoke": run_graph_smoke(artifact_dir),
        "phase_metrics": phase_metrics,
        "validation_gates": validation,
        "gold_benchmark": benchmark,
        "gold_breadth": gold_breadth(gold_items),
        "demo_candidates": demo_candidates(structural, semantic),
        "known_limitations": known_limitations(phase_metrics),
    }


def capability_matrix(phase_metrics: dict[str, Any], validation: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for phase in phase_metrics.get("phases", []):
        metrics = {m["metric_id"]: m.get("value") for m in phase.get("metrics", [])}
        rows.append(
            {
                "phase_id": phase.get("phase_id"),
                "name": phase.get("name"),
                "availability": phase.get("availability"),
                "hard_thing": phase.get("hard_thing"),
                "key_metrics": metrics,
            }
        )
    if validation:
        rows.append(
            {
                "phase_id": "validation_gates",
                "name": "Truthfulness validation gates",
                "availability": "available",
                "hard_thing": "Fresh ingest and artifact consistency checks must agree with stored claims.",
                "key_metrics": validation.get("summary", {}),
            }
        )
    return rows


def gold_breadth(gold_items: list[dict[str, Any]]) -> dict[str, Any]:
    repos = Counter(str(item.get("repo_name", "unknown")) for item in gold_items)
    blocks = Counter(str(item.get("expected_block", "unknown")) for item in gold_items)
    return {
        "total_items": len(gold_items),
        "repo_count": len(repos),
        "block_count": len(blocks),
        "repos": dict(sorted(repos.items())),
        "blocks": dict(sorted(blocks.items())),
    }


def demo_candidates(structural: dict[str, Any], semantic: object) -> dict[str, Any]:
    code_nodes = structural.get("code_nodes", [])
    assignments = semantic.get("block_assignments", []) if isinstance(semantic, dict) else []
    by_node_id = {str(row.get("node_id")): row for row in assignments}
    enriched: list[dict[str, Any]] = []
    for node in code_nodes:
        nid = str(node.get("scip_id", ""))
        assignment = by_node_id.get(nid, {})
        enriched.append(
            {
                "node_id": nid,
                "name": node.get("name"),
                "kind": node.get("kind"),
                "file_path": node.get("file_path"),
                "primary_block": assignment.get("primary_block"),
                "confidence": assignment.get("confidence"),
            }
        )
    high_conf = [row for row in enriched if float(row.get("confidence") or 0.0) >= 0.7]
    return {
        "high_confidence_block_nodes": sorted(high_conf, key=lambda r: (str(r.get("primary_block")), str(r.get("file_path"))))[:25],
        "impact_radius_start_nodes": sorted(enriched, key=lambda r: (str(r.get("kind")), str(r.get("file_path"))))[:15],
    }


def known_limitations(phase_metrics: dict[str, Any]) -> list[str]:
    limitations: list[str] = []
    for phase in phase_metrics.get("phases", []):
        if phase.get("phase_id") == "phase_6":
            metrics = {m["metric_id"]: m.get("value") for m in phase.get("metrics", [])}
            if metrics.get("continue_cli_present") is False:
                limitations.append("Continue CLI (`cn`) is not on PATH, so Phase 6 operator proof remains incomplete.")
        if phase.get("phase_id") == "phase_2":
            metrics = {m["metric_id"]: m.get("value") for m in phase.get("metrics", [])}
            if int(metrics.get("cross_repo_reference_count") or 0) == 0:
                limitations.append("Current reference artifact does not demonstrate cross-repo SCIP references.")
    return limitations


def write_maximize_report(report: dict[str, Any], out: Path | None = None) -> Path:
    dest = out or (artifact_root().parent / "reports" / f"{timestamp_slug()}__phase-8-5-audit.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, report)
    return dest
