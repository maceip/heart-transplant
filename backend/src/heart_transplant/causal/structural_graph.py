from __future__ import annotations

import random
from collections import defaultdict

from heart_transplant.causal.models import TraceStep
from heart_transplant.models import StructuralArtifact


def edge_propagation_weight(edge_type: str) -> float:
    weights: dict[str, float] = {
        "REFERENCES": 0.92,
        "CALLS": 0.9,
        "IMPLEMENTS": 0.88,
        "DEFINES": 0.85,
        "IMPORTS_MODULE": 0.72,
        "DEPENDS_ON": 0.68,
        "DEPENDS_ON_FILE": 0.55,
        "CROSS_REFERENCE": 0.8,
        "CONTAINS": 0.35,
    }
    return weights.get(edge_type, 0.5)


def build_adjacency(artifact: StructuralArtifact) -> dict[str, list[tuple[str, str, float]]]:
    """Undirected adjacency: neighbor_id, edge_type, weight."""
    adj: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for e in artifact.edges:
        et = str(e.edge_type)
        w = edge_propagation_weight(et)
        adj[e.source_id].append((e.target_id, et, w))
        adj[e.target_id].append((e.source_id, et, w))
    return adj


def monte_carlo_reachable(
    seeds: list[str],
    adj: dict[str, list[tuple[str, str, float]]],
    *,
    rng: random.Random,
    runs: int,
    max_depth: int,
    max_nodes: int,
) -> tuple[list[int], list[TraceStep]]:
    """Return per-run reachable node counts (seeds always in set) and a summary trace."""
    trace: list[TraceStep] = [
        TraceStep(step_index=0, kind="seed", detail="Starting Monte Carlo impact sampling from seed nodes.", node_ids=list(seeds))
    ]
    counts: list[int] = []
    step_i = 1
    for r in range(runs):
        visited: set[str] = set(seeds)
        frontier: list[tuple[str, int]] = [(s, 0) for s in seeds]
        while frontier and len(visited) < max_nodes:
            cur, d = frontier.pop()
            if d >= max_depth:
                continue
            for nbr, et, w in adj.get(cur, []):
                if nbr in visited:
                    continue
                if rng.random() <= w:
                    visited.add(nbr)
                    frontier.append((nbr, d + 1))
        counts.append(len(visited))
        if r == 0:
            trace.append(
                TraceStep(
                    step_index=step_i,
                    kind="mc_sample",
                    detail=f"First MC run expanded to {len(visited)} nodes (depth cap {max_depth}, node cap {max_nodes}).",
                    node_ids=sorted(visited)[:50],
                )
            )
            step_i += 1
    mean_c = sum(counts) / max(len(counts), 1)
    trace.append(
        TraceStep(
            step_index=step_i,
            kind="mc_aggregate",
            detail=f"Completed {runs} runs; mean reachable nodes ≈ {mean_c:.2f}.",
            node_ids=[],
        )
    )
    return counts, trace
