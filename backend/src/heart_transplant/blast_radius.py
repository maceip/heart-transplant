from __future__ import annotations

"""Bounded impact subgraph (blast radius) for graph-backed operator flows."""

from collections import deque
from typing import Any

from heart_transplant.db.graph_queries import edge_incident_count, get_code_node, get_neighbors
from heart_transplant.db.connection import connect_surreal


def compute_impact_subgraph(
    start_id: str,
    *,
    max_depth: int = 4,
    max_nodes: int = 200,
    high_degree_threshold: int = 80,
    prune_high_degree: bool = True,
    db: Any | None = None,
) -> dict[str, Any]:
    """
    BFS over all edge types, stopping at ``max_nodes`` or ``max_depth``.

    If ``prune_high_degree`` is true, we do not expand from nodes whose
    total incident edge count in the DB is above ``high_degree_threshold``,
    except the start node (always expanded once).
    """
    if db is None:
        db = connect_surreal()
    start = get_code_node(start_id, db=db)
    repo = str(start.get("repo_name", "")) if start else None
    cap_n = max(1, min(int(max_nodes), 5_000))
    depth_max = max(0, min(int(max_depth), 32))
    thr = max(1, int(high_degree_threshold))

    visited: set[str] = {start_id}
    frontier: deque[tuple[str, int]] = deque([(start_id, 0)])
    collected_edges: list[dict[str, Any]] = []
    pruned: list[dict[str, str | int]] = []

    while frontier and len(visited) < cap_n:
        cur, d = frontier.popleft()
        if d > depth_max:
            continue
        if prune_high_degree and cur != start_id:
            inc = edge_incident_count(cur, repo_name=repo, db=db)
            if inc > thr:
                pruned.append({"node_id": cur, "incident_edges": inc})
                continue
        nbr = get_neighbors(cur, direction="both", limit=2_000, db=db)
        for e in nbr.get("edges", []):
            if len(collected_edges) < cap_n * 4:
                collected_edges.append(e)
            sid = e.get("source_id")
            tid = e.get("target_id")
            o: str | None
            if tid == cur and isinstance(sid, str):
                o = sid
            elif sid == cur and isinstance(tid, str):
                o = tid
            else:
                o = None
            if o is None or o in visited:
                continue
            if len(visited) >= cap_n:
                break
            visited.add(o)
            if d < depth_max:
                frontier.append((o, d + 1))

    return {
        "start_id": start_id,
        "max_depth": depth_max,
        "max_nodes": cap_n,
        "node_count": len(visited),
        "prune_high_degree": prune_high_degree,
        "high_degree_threshold": thr,
        "nodes": sorted(visited),
        "edges": collected_edges[: cap_n * 4],
        "pruned_from_expansion": pruned,
    }
