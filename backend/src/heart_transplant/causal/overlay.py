from __future__ import annotations

from collections import defaultdict

from heart_transplant.causal.models import CausalEdge, CausalGraphOverlay
from heart_transplant.causal.structural_graph import edge_propagation_weight
from heart_transplant.models import StructuralArtifact
from heart_transplant.temporal.models import TemporalScanReport


def _path_for_node_id(artifact: StructuralArtifact, node_id: str) -> str | None:
    for c in artifact.code_nodes:
        if c.scip_id == node_id:
            return c.file_path
    for f in artifact.file_nodes:
        if f.node_id == node_id:
            return f.file_path
    return None


def _semantic_blocks(semantic: dict | None) -> dict[str, str]:
    if not semantic:
        return {}
    out: dict[str, str] = {}
    for row in semantic.get("block_assignments", []) or []:
        nid = str(row.get("node_id", ""))
        blk = str(row.get("primary_block", ""))
        if nid and blk:
            out[nid] = blk
    return out


def _hotspot_files(temporal: TemporalScanReport | None, top_n: int = 40) -> set[str]:
    if not temporal:
        return set()
    return {p for p, _ in sorted(temporal.file_hotspots.items(), key=lambda x: -x[1])[:top_n]}


def _edge_touches_change_tokens(
    source_path: str | None,
    target_path: str | None,
    tokens: set[str],
) -> bool:
    blob = f"{source_path or ''} {target_path or ''}".lower()
    return any(t in blob for t in tokens if len(t) >= 3)


def _same_block(
    source_id: str,
    target_id: str,
    blocks: dict[str, str],
) -> bool:
    a, b = blocks.get(source_id), blocks.get(target_id)
    return bool(a and b and a == b)


def build_causal_overlay(
    artifact: StructuralArtifact,
    *,
    semantic: dict | None = None,
    temporal: TemporalScanReport | None = None,
    change_tokens: set[str],
) -> CausalGraphOverlay:
    """Derive propagation probabilities on each structural edge from multi-signal fusion."""

    blocks = _semantic_blocks(semantic)
    hotspots = _hotspot_files(temporal)
    causal_edges: list[CausalEdge] = []
    deltas: list[float] = []

    for e in artifact.edges:
        et = str(e.edge_type)
        base = edge_propagation_weight(et)
        w = base
        factors: list[str] = []

        sp = _path_for_node_id(artifact, e.source_id)
        tp = _path_for_node_id(artifact, e.target_id)
        if sp and tp:
            if sp in hotspots and tp in hotspots:
                w *= 1.1
                factors.append("temporal:both_endpoints_hot")
            elif sp in hotspots or tp in hotspots:
                w *= 1.05
                factors.append("temporal:one_endpoint_hot")

        if _same_block(e.source_id, e.target_id, blocks):
            w *= 1.08
            factors.append("semantic:same_block")

        if change_tokens and _edge_touches_change_tokens(sp, tp, change_tokens):
            w *= 1.12
            factors.append("change_text:endpoint_path_overlap")

        w = min(0.98, max(0.04, w))
        deltas.append(w - base)
        causal_edges.append(
            CausalEdge(
                source_id=e.source_id,
                target_id=e.target_id,
                structural_edge_type=et,
                base_weight=round(base, 4),
                adjusted_weight=round(w, 4),
                adjustment_factors=factors,
            )
        )

    mean_adj = sum(ce.adjusted_weight for ce in causal_edges) / max(len(causal_edges), 1)
    mean_delta = sum(deltas) / max(len(deltas), 1)
    return CausalGraphOverlay(
        repo_name=artifact.repo_name,
        edges=causal_edges,
        mean_adjusted_weight=round(mean_adj, 4),
        mean_delta_from_base=round(mean_delta, 4),
    )


def overlay_to_adjacency(
    overlay: CausalGraphOverlay,
) -> dict[str, list[tuple[str, str, float]]]:
    """Undirected adjacency for MC: neighbor_id, edge_type, adjusted_weight."""

    adj: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
    for ce in overlay.edges:
        et = ce.structural_edge_type
        w = ce.adjusted_weight
        adj[ce.source_id].append((ce.target_id, et, w))
        adj[ce.target_id].append((ce.source_id, et, w))
    return adj
