from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any
import shutil

from heart_transplant.artifact_store import read_json
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.db.indexes import INDEX_STATEMENTS
from heart_transplant.db.schema import apply_schema
from heart_transplant.db.surreal_loader import load_artifact
from heart_transplant.db.verify import verify_artifact_in_db
from heart_transplant.evals.gold_benchmark import load_gold_set, run_benchmark
from heart_transplant.graph_smoke import run_graph_smoke
from heart_transplant.temporal.metrics import temporal_metrics


def collect_phase_metrics(
    artifact_dir: Path,
    *,
    repo_path: Path | None = None,
    repo_root: Path | None = None,
    gold_set_path: Path | None = None,
    classify_if_missing: bool = False,
    use_openai: bool = False,
) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    repo_path = (repo_path or Path(str(structural["repo_path"]))).resolve()
    repo_root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    if gold_set_path is None:
        default_gold_set = repo_root / "docs" / "evals" / "gold_block_benchmark.json"
        if default_gold_set.is_file():
            gold_set_path = default_gold_set

    graph = run_graph_smoke(artifact_dir)
    scip_metadata = read_json(artifact_dir / "scip-index.json") if (artifact_dir / "scip-index.json").exists() else None
    scip_consumed = read_json(artifact_dir / "scip-consumed.json") if (artifact_dir / "scip-consumed.json").exists() else None

    phases = [
        _phase_zero_identity(structural, scip_metadata, scip_consumed),
        _phase_one_structure(structural, graph),
        _phase_two_scip_backbone(scip_consumed),
        _phase_three_surreal(artifact_dir),
        _phase_four_semantics(artifact_dir, structural, classify_if_missing=classify_if_missing, use_openai=use_openai),
        _phase_five_reactive_tools(repo_root),
        _phase_six_continue_bridge(repo_root),
        _phase_seven_eval(structural, gold_set_path),
        _phase_eight_regret_sdk(repo_root),
        _phase_nine_temporal(repo_path),
    ]

    availability = Counter(phase["availability"] for phase in phases)

    return {
        "artifact_dir": str(artifact_dir),
        "repo_path": str(repo_path),
        "repo_root": str(repo_root),
        "summary": {
            "phase_count": len(phases),
            "available": availability.get("available", 0),
            "blocked": availability.get("blocked", 0),
        },
        "phases": phases,
        "integrity": _integrity_metrics(repo_root),
    }


def _phase_zero_identity(structural: dict[str, Any], scip_metadata: dict[str, Any] | None, scip_consumed: dict[str, Any] | None) -> dict[str, Any]:
    if not scip_metadata or not scip_consumed:
        return _blocked_phase(
            "phase_0",
            "Structural honesty",
            "Resolve stable code identities from real SCIP output without leaving unresolved symbol debt behind.",
            ["scip-index.json", "scip-consumed.json"],
        )

    resolution = scip_consumed.get("resolution", {})
    documents = scip_consumed.get("documents", [])
    total_nodes = int(resolution.get("total_code_nodes", structural.get("node_count", 0)) or 0)
    scip_eligible_nodes = _scip_eligible_code_nodes(structural)
    total_scip_eligible_nodes = len(scip_eligible_nodes)
    with_scip = sum(1 for node in scip_eligible_nodes if node.get("symbol_source") == "scip")
    if with_scip == 0:
        with_scip = int(
            resolution.get("scip_eligible_nodes_with_scip_identity", resolution.get("nodes_with_scip_identity", 0))
            or 0
        )
    if total_scip_eligible_nodes == 0:
        total_scip_eligible_nodes = int(
            resolution.get("scip_eligible_code_nodes", resolution.get("total_code_nodes", 0))
            or 0
        )
    orphaned = int(scip_consumed.get("addressable_orphaned_symbol_count", scip_consumed.get("orphaned_symbol_count", 0)) or 0)
    raw_orphaned = int(scip_consumed.get("orphaned_symbol_count", 0) or 0)
    total_definitions = sum(int(doc.get("definition_count", 0) or 0) for doc in documents)
    if total_definitions <= 0:
        total_definitions = with_scip + raw_orphaned
    total_addressable_definitions = with_scip + orphaned

    return {
        "phase_id": "phase_0",
        "name": "Structural honesty",
        "hard_thing": "Stable identity reconciliation between Tree-sitter boundaries and SCIP symbols.",
        "availability": "available",
        "metrics": [
            _metric("resolved_symbol_rate", _ratio(with_scip, total_scip_eligible_nodes)),
            _metric("orphaned_symbol_rate", _ratio(orphaned, total_addressable_definitions)),
            _metric("raw_orphaned_symbol_rate", _ratio(raw_orphaned, total_definitions)),
            _metric("stale_provisional_target_count", _stale_provisional_target_count(structural)),
            _metric("total_code_nodes", total_nodes),
            _metric("scip_eligible_code_nodes", total_scip_eligible_nodes),
            _metric("nodes_with_scip_identity", with_scip),
            _metric("orphaned_symbol_count", orphaned),
            _metric("raw_orphaned_symbol_count", raw_orphaned),
            _metric("addressable_symbol_total", total_addressable_definitions),
        ],
        "artifacts": ["structural-artifact.json", "scip-index.json", "scip-consumed.json"],
    }


def _phase_one_structure(structural: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    edge_counts = Counter(str(edge["edge_type"]) for edge in structural.get("edges", []))
    node_count = int(structural.get("node_count", 0) or 0)
    neighborhoods_indexed = int(graph.get("neighborhoods_indexed", 0) or 0)
    dependency_edge_count = (
        int(edge_counts.get("DEPENDS_ON_FILE", 0))
        + int(edge_counts.get("DEPENDS_ON", 0))
        + int(edge_counts.get("IMPORTS_MODULE", 0))
    )
    cross_file_dependency_count = int(edge_counts.get("DEPENDS_ON_FILE", 0))

    return {
        "phase_id": "phase_1",
        "name": "Structural spine",
        "hard_thing": "Extract a useful graph of addressable code boundaries and cross-file structure without graph explosion.",
        "availability": "available",
        "metrics": [
            _metric("node_kind_diversity", len(graph.get("node_kind_counts", {}))),
            _metric("neighborhood_coverage_rate", _ratio(neighborhoods_indexed, node_count)),
            _metric("dependency_edge_count", dependency_edge_count),
            _metric("cross_file_dependency_count", cross_file_dependency_count),
            _metric("edges_per_code_node", _ratio(int(structural.get("edge_count", 0) or 0), node_count)),
        ],
        "artifacts": ["structural-artifact.json"],
    }


def _phase_two_scip_backbone(scip_consumed: dict[str, Any] | None) -> dict[str, Any]:
    if not scip_consumed:
        return _blocked_phase(
            "phase_2",
            "SCIP identity backbone",
            "Route local and cross-file references through the real SCIP graph instead of file-only fallbacks.",
            ["scip-consumed.json"],
        )

    resolution = scip_consumed.get("resolution", {})
    counts = scip_consumed.get("scip_backed_edge_counts", {})
    routing = scip_consumed.get("reference_routing", {})
    total_refs = int(routing.get("code_to_code", 0) or 0) + int(routing.get("file_fallback", 0) or 0)

    return {
        "phase_id": "phase_2",
        "name": "SCIP identity backbone",
        "hard_thing": "Produce real definition and reference edges from SCIP, with minimal fallback routing.",
        "availability": "available",
        "metrics": [
            _metric(
                "resolved_symbol_rate",
                _ratio(
                    int(resolution.get("scip_eligible_nodes_with_scip_identity", resolution.get("nodes_with_scip_identity", 0)) or 0),
                    int(resolution.get("scip_eligible_code_nodes", resolution.get("total_code_nodes", 0)) or 0),
                ),
            ),
            _metric("defines_edge_count", int(counts.get("DEFINES", 0) or 0)),
            _metric("reference_edge_count", int(counts.get("REFERENCES", 0) or 0)),
            _metric("cross_repo_reference_count", int(routing.get("cross_repo", 0) or 0)),
            _metric("file_fallback_reference_rate", _ratio(int(routing.get("file_fallback", 0) or 0), total_refs)),
        ],
        "artifacts": ["scip-consumed.json"],
    }


def _phase_three_surreal(artifact_dir: Path) -> dict[str, Any]:
    try:
        from surrealdb import Surreal  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        return _blocked_phase(
            "phase_3",
            "Surreal graph persistence",
            "Load the graph into a real graph store and verify it survives a read/write round-trip.",
            ["surrealdb package"],
            notes=[f"surrealdb unavailable: {exc}"],
        )

    try:
        with Surreal("mem://") as db:  # noqa: SIM117
            db.use("ht_phase", "graph")
            apply_schema(db)
            load = load_artifact(artifact_dir, db=db)
            verify = verify_artifact_in_db(artifact_dir, db=db)
    except Exception as exc:  # noqa: BLE001
        return {
            "phase_id": "phase_3",
            "name": "Surreal graph persistence",
            "hard_thing": "Load the graph into a real graph store and verify it survives a read/write round-trip.",
            "availability": "available",
            "metrics": [
                _metric("verify_pass", False),
                _metric("index_statement_count", len(INDEX_STATEMENTS)),
                _metric("load_exception", str(exc)),
            ],
            "artifacts": ["structural-artifact.json"],
            "notes": ["The phase is implemented enough to exercise, but the current run raised an exception."],
        }

    return {
        "phase_id": "phase_3",
        "name": "Surreal graph persistence",
        "hard_thing": "Load the graph into a real graph store and verify it survives a read/write round-trip.",
        "availability": "available",
        "metrics": [
            _metric("load_status", load.get("status")),
            _metric("verify_pass", bool(verify.get("pass"))),
            _metric("ht_code_rows", int(verify.get("ht_code", 0) or 0)),
            _metric("ht_edge_rows", int(verify.get("ht_edge", 0) or 0)),
            _metric("index_statement_count", len(INDEX_STATEMENTS)),
        ],
        "artifacts": ["structural-artifact.json", "SurrealDB mem://"],
    }


def _phase_four_semantics(
    artifact_dir: Path,
    structural: dict[str, Any],
    *,
    classify_if_missing: bool,
    use_openai: bool,
) -> dict[str, Any]:
    semantic_path = artifact_dir / "semantic-artifact.json"
    if not semantic_path.exists() and classify_if_missing:
        run_classification_on_artifact(artifact_dir, use_openai=use_openai)
    if not semantic_path.exists():
        return _blocked_phase(
            "phase_4",
            "Semantic enrichment",
            "Attach semantic block labels, summaries, entities, and actions to the structural graph.",
            ["semantic-artifact.json"],
        )

    semantic = read_json(semantic_path)
    assignments = semantic.get("block_assignments", [])
    confidence_values = [float(item.get("confidence", 0.0) or 0.0) for item in assignments]
    unique_blocks = {str(item.get("primary_block", "")) for item in assignments if item.get("primary_block")}
    node_count = int(structural.get("node_count", 0) or 0)

    return {
        "phase_id": "phase_4",
        "name": "Semantic enrichment",
        "hard_thing": "Produce useful semantic labels and higher-order meaning, not just one block tag per node.",
        "availability": "available",
        "metrics": [
            _metric("assignment_coverage_rate", _ratio(len(assignments), node_count)),
            _metric("average_assignment_confidence", mean(confidence_values) if confidence_values else 0.0),
            _metric("unique_block_count", len(unique_blocks)),
            _metric("semantic_summary_count", len(semantic.get("semantic_summaries", []))),
            _metric("entity_count", len(semantic.get("entities", []))),
            _metric("action_count", len(semantic.get("actions", []))),
        ],
        "artifacts": ["semantic-artifact.json"],
    }


def _phase_five_reactive_tools(repo_root: Path) -> dict[str, Any]:
    runtime_root = repo_root / "backend" / "src" / "heart_transplant"
    mcp_candidates = sorted(runtime_root.rglob("*mcp*.py")) + sorted(runtime_root.rglob("mcp_server.py"))
    if not mcp_candidates:
        return _blocked_phase(
            "phase_5",
            "Reactive graph tools",
            "Expose graph traversal as a real tool surface that an agent can call interactively.",
            ["mcp server implementation"],
        )

    return {
        "phase_id": "phase_5",
        "name": "Reactive graph tools",
        "hard_thing": "Expose graph traversal as a real tool surface that an agent can call interactively.",
        "availability": "available",
        "metrics": [
            _metric("mcp_candidate_count", len(mcp_candidates)),
        ],
        "artifacts": [str(path) for path in mcp_candidates[:10]],
    }


def _phase_six_continue_bridge(repo_root: Path) -> dict[str, Any]:
    runtime_root = repo_root / "backend" / "src" / "heart_transplant"
    integration_files = [path for path in runtime_root.rglob("*.py") if "continue" in path.name.lower()]
    continue_cli_present = shutil.which("cn") is not None
    if not integration_files:
        return _blocked_phase(
            "phase_6",
            "Continue operator surface",
            "Let a real operator query or drive the graph through a Continue-facing bridge.",
            ["continue integration module"],
            notes=[f"cn on path: {continue_cli_present}"],
        )

    return {
        "phase_id": "phase_6",
        "name": "Continue operator surface",
        "hard_thing": "Let a real operator query or drive the graph through a Continue-facing bridge.",
        "availability": "available",
        "metrics": [
            _metric("continue_cli_present", continue_cli_present),
            _metric("continue_integration_file_count", len(integration_files)),
        ],
        "artifacts": [str(path) for path in integration_files[:10]],
    }


def _phase_seven_eval(structural: dict[str, Any], gold_set_path: Path | None) -> dict[str, Any]:
    if gold_set_path is None or not gold_set_path.is_file():
        return _blocked_phase(
            "phase_7",
            "Evaluation harness",
            "Measure the system against explicit gold expectations instead of judging by vibes.",
            ["gold benchmark file"],
        )

    gold_items = load_gold_set(gold_set_path)
    benchmark = run_benchmark(structural, gold_items)
    rows = benchmark.get("rows", [])
    missing = sum(1 for row in rows if row.get("error") == "missing node")

    return {
        "phase_id": "phase_7",
        "name": "Evaluation harness",
        "hard_thing": "Measure the system against explicit gold expectations instead of judging by vibes.",
        "availability": "available",
        "metrics": [
            _metric("gold_example_count", int(benchmark.get("total", 0) or 0)),
            _metric("benchmark_accuracy", float(benchmark.get("accuracy", 0.0) or 0.0)),
            _metric("missing_node_rate", _ratio(missing, int(benchmark.get("total", 0) or 0))),
        ],
        "artifacts": [str(gold_set_path)],
    }


def _phase_eight_regret_sdk(repo_root: Path) -> dict[str, Any]:
    runtime_root = repo_root / "backend" / "src" / "heart_transplant"
    regret_candidates = [path for path in runtime_root.rglob("*.py") if "regret" in path.name.lower() or "blast" in path.name.lower()]
    if not regret_candidates:
        return _blocked_phase(
            "phase_8",
            "Regret-SDK readiness",
            "Expose enough architecture-aware impact information to power regret detection and graft planning.",
            ["regret planner / blast radius implementation"],
        )

    return {
        "phase_id": "phase_8",
        "name": "Regret-SDK readiness",
        "hard_thing": "Expose enough architecture-aware impact information to power regret detection and graft planning.",
        "availability": "available",
        "metrics": [
            _metric("regret_candidate_file_count", len(regret_candidates)),
        ],
        "artifacts": [str(path) for path in regret_candidates[:10]],
    }


def _phase_nine_temporal(repo_path: Path) -> dict[str, Any]:
    try:
        report_a = temporal_metrics(repo_path, max_commits=25)
        report_b = temporal_metrics(repo_path, max_commits=25)
    except Exception as exc:  # noqa: BLE001
        return _blocked_phase(
            "phase_9",
            "Temporal and evolutionary understanding",
            "Turn real git history into deterministic architecture snapshots, diffs, churn metrics, and drift signals.",
            ["git history readable by temporal metrics"],
            notes=[str(exc)],
        )

    stable = report_a.model_dump(mode="json") == report_b.model_dump(mode="json")
    non_empty_diffs = sum(1 for diff in report_a.diffs if diff.file_changes)
    drift_candidate_count = sum(
        1
        for diff in report_a.diffs
        for change in diff.file_changes
        if set(change.before_blocks) != set(change.after_blocks)
    )

    return {
        "phase_id": "phase_9",
        "name": "Temporal and evolutionary understanding",
        "hard_thing": "Turn real git history into deterministic architecture snapshots, diffs, churn metrics, and drift signals.",
        "availability": "available",
        "metrics": [
            _metric("commit_count", report_a.commit_count),
            _metric("architecture_snapshot_count", len(report_a.snapshots)),
            _metric("architecture_diff_count", len(report_a.diffs)),
            _metric("non_empty_diff_count", non_empty_diffs),
            _metric("tracked_block_count", len(report_a.block_churn_rate)),
            _metric("file_hotspot_count", len(report_a.file_hotspots)),
            _metric("drift_candidate_count", drift_candidate_count),
            _metric("architectural_drift_candidate_rate", report_a.architectural_drift_candidate_rate),
            _metric("regret_accumulation_score", report_a.regret_accumulation_score),
            _metric("pattern_success_index_block_count", len(report_a.pattern_success_index)),
            _metric("metrics_reproducible", stable),
        ],
        "artifacts": ["git history", "temporal_metrics(repo_path)", "ht_temporal via persist-temporal-surreal"],
        "notes": report_a.limitations,
    }


def _integrity_metrics(repo_root: Path) -> dict[str, Any]:
    runtime_root = repo_root / "backend" / "src" / "heart_transplant"
    vendored_root = repo_root / "vendor" / "github-repos"
    repo_tokens: set[str] = set()
    if vendored_root.is_dir():
        repo_tokens = {path.name.lower() for path in vendored_root.iterdir() if path.is_dir()}

    hits: list[dict[str, Any]] = []
    for py_file in runtime_root.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in sorted(repo_tokens):
            if token and token in lowered:
                hits.append({"file": str(py_file), "token": token})

    return {
        "runtime_repo_specific_hit_count": len(hits),
        "runtime_repo_specific_hits": hits[:20],
    }


def _blocked_phase(
    phase_id: str,
    name: str,
    hard_thing: str,
    missing: list[str],
    *,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "phase_id": phase_id,
        "name": name,
        "hard_thing": hard_thing,
        "availability": "blocked",
        "blocked_by": missing,
        "metrics": [],
        "artifacts": [],
        "notes": notes or [],
    }


def _metric(metric_id: str, value: Any) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "value": value,
    }


def _ratio(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _stale_provisional_target_count(structural: dict[str, Any]) -> int:
    code_nodes = structural.get("code_nodes", [])
    current_ids = {str(node.get("scip_id", "")) for node in code_nodes}
    retired_provisional_ids = {
        str(node.get("original_provisional_id", ""))
        for node in code_nodes
        if node.get("original_provisional_id")
        and str(node.get("original_provisional_id")) != str(node.get("scip_id"))
    }
    return sum(
        1
        for edge in structural.get("edges", [])
        if str(edge.get("target_id", "")) in retired_provisional_ids
        and str(edge.get("target_id", "")) not in current_ids
    )


def _scip_eligible_code_nodes(structural: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        node
        for node in structural.get("code_nodes", [])
        if str(node.get("kind", ""))
        in {
            "function",
            "class",
            "interface",
            "method",
            "variable",
            "react_hook",
            "config_object",
            "middleware",
            "service_boundary",
        }
    ]
