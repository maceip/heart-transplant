from __future__ import annotations

import random
import statistics
from pathlib import Path

from heart_transplant.artifact_store import read_json
from heart_transplant.causal.calibration import adjusted_confidence
from heart_transplant.causal.impact_predictor import (
    load_semantic_artifact,
    load_temporal_scan,
    select_seed_nodes,
    tokenize_change,
)
from heart_transplant.causal.models import CausalSimulationResult, TraceStep
from heart_transplant.causal.overlay import build_causal_overlay, overlay_to_adjacency
from heart_transplant.causal.structural_graph import monte_carlo_reachable
from heart_transplant.models import StructuralArtifact


def _code_ids(artifact: StructuralArtifact) -> set[str]:
    return {c.scip_id for c in artifact.code_nodes}


def _union_mc_nodes(
    seeds: list[str],
    adj: dict[str, list[tuple[str, str, float]]],
    *,
    rng_seed: int,
    runs: int,
    max_depth: int,
    max_nodes: int,
) -> set[str]:
    acc: set[str] = set()
    for r in range(runs):
        rng = random.Random(rng_seed + r * 1_000_003)
        visited: set[str] = set(seeds)
        frontier: list[tuple[str, int]] = [(s, 0) for s in seeds]
        while frontier and len(visited) < max_nodes:
            cur, d = frontier.pop()
            if d >= max_depth:
                continue
            for nbr, _et, w in adj.get(cur, []):
                if nbr in visited:
                    continue
                if rng.random() <= w:
                    visited.add(nbr)
                    frontier.append((nbr, d + 1))
        acc |= visited
    return acc


def run_change_simulation(
    change_description: str,
    artifact_dir: Path,
    *,
    temporal_report_path: Path | None = None,
    rng_seed: int = 42,
    mc_runs: int = 64,
    max_depth: int = 8,
    max_nodes: int = 200,
    confidence_threshold: float = 0.7,
) -> CausalSimulationResult:
    """Monte Carlo impact simulation on the **causal overlay** (Phase 10 core)."""

    artifact_dir = artifact_dir.resolve()
    raw = read_json(artifact_dir / "structural-artifact.json")
    artifact = StructuralArtifact.model_validate(raw)
    temporal = load_temporal_scan(temporal_report_path.resolve() if temporal_report_path else None)
    semantic = load_semantic_artifact(artifact_dir)
    tokens = tokenize_change(change_description)

    overlay = build_causal_overlay(artifact, semantic=semantic, temporal=temporal, change_tokens=tokens)
    adj = overlay_to_adjacency(overlay)

    seeds, seed_notes = select_seed_nodes(
        change_description,
        artifact,
        temporal,
        semantic=semantic,
    )
    code_ids = _code_ids(artifact)

    rng = random.Random(rng_seed)
    counts, mc_trace = monte_carlo_reachable(seeds, adj, rng=rng, runs=mc_runs, max_depth=max_depth, max_nodes=max_nodes)
    mean_c = sum(counts) / max(len(counts), 1)
    mc_std = statistics.pstdev(counts) if len(counts) > 1 else 0.0
    cv = mc_std / mean_c if mean_c > 1e-6 else 0.0
    self_consistency = max(0.0, min(1.0, 1.0 - min(1.0, cv)))

    union_nodes = _union_mc_nodes(seeds, adj, rng_seed=rng_seed, runs=mc_runs, max_depth=max_depth, max_nodes=max_nodes)
    impacted_code = sorted(n for n in union_nodes if n in code_ids)
    files: set[str] = set()
    by_id = {c.scip_id: c for c in artifact.code_nodes}
    for nid in impacted_code:
        node = by_id.get(nid)
        if node:
            files.add(node.file_path)

    raw_conf = (
        0.15
        + 0.45 * self_consistency
        + 0.4 * min(1.0, mean_c / max(len(code_ids), 1))
    )
    raw_conf = min(0.92, raw_conf)
    conf = adjusted_confidence(raw_conf)

    steps: list[TraceStep] = [
        TraceStep(
            step_index=0,
            kind="causal_overlay",
            detail=(
                f"Built causal overlay: {len(overlay.edges)} edges, "
                f"mean adjusted propagation weight {overlay.mean_adjusted_weight} "
                f"(mean delta from structural base {overlay.mean_delta_from_base:+.4f})."
            ),
            node_ids=[],
        ),
        TraceStep(
            step_index=1,
            kind="seed_selection",
            detail="Seeds from change tokens, temporal hotspots, and optional semantic block alignment.",
            node_ids=seeds,
        ),
    ]
    for step in mc_trace:
        steps.append(TraceStep(step_index=len(steps), kind=step.kind, detail=step.detail, node_ids=step.node_ids))

    limitations = [
        "Propagation uses fused per-edge weights (structural type + temporal + semantic + change-text overlap), not live Surreal blast-radius.",
        "No LLM interpretation of the change string beyond token/bucket heuristics for seeds and path overlap on edges.",
        f"Union of MC reachability over {mc_runs} runs: {len(impacted_code)} code nodes.",
    ]
    if semantic is None:
        limitations.append("No semantic-artifact.json — semantic block fusion in overlay and seeds is reduced.")
    limitations.extend(seed_notes)
    if conf < confidence_threshold:
        limitations.append(
            f"Calibrated confidence {conf:.3f} is below requested threshold {confidence_threshold:.3f} (informational)."
        )

    return CausalSimulationResult(
        change_description=change_description,
        trace=steps,
        impacted_node_ids=impacted_code,
        impacted_file_paths=sorted(files),
        mean_impact_count=mean_c,
        mc_std_impact_count=mc_std,
        self_consistency_score=self_consistency,
        confidence=conf,
        mc_runs=mc_runs,
        rng_seed=rng_seed,
        seed_node_ids=seeds,
        causal_overlay=overlay,
        limitations=limitations,
    )
