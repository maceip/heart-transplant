from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from heart_transplant.artifact_store import read_json
from heart_transplant.blast_radius import compute_impact_subgraph
from heart_transplant.evals.gold_benchmark import build_block_benchmark_report, load_gold_set


class EvidenceNode(BaseModel):
    node_id: str
    kind: str
    file_path: str | None = None
    range: dict[str, int] | None = None
    label: str | None = None


class EvidencePath(BaseModel):
    node_ids: list[str] = Field(default_factory=list)
    edge_types: list[str] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    query_type: str
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_nodes: list[EvidenceNode] = Field(default_factory=list)
    file_ranges: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[EvidencePath] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def explain_node(artifact_dir: Path, node_id: str) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    node = graph["nodes_by_id"].get(node_id)
    if not node:
        return EvidenceBundle(
            query_type="explain_node",
            claim=f"No node found for {node_id}",
            confidence=0.0,
            limitations=["node_id was not present in structural artifact"],
        )
    neighbors = _incident_edges(graph, node_id)
    return EvidenceBundle(
        query_type="explain_node",
        claim=f"{node_id} is a {node.get('kind')} surface in {node.get('file_path') or 'the graph'}.",
        confidence=0.75,
        source_nodes=[_evidence_node(node)],
        file_ranges=_file_ranges([node]),
        paths=[EvidencePath(node_ids=[node_id], edge_types=[])],
        limitations=[f"{len(neighbors)} incident edges were found; semantic confidence depends on classifier output."],
    )


def explain_file(artifact_dir: Path, file_path: str) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    nodes = [node for node in graph["nodes_by_id"].values() if node.get("file_path") == file_path]
    if not nodes:
        return EvidenceBundle(
            query_type="explain_file",
            claim=f"No graph nodes found for {file_path}",
            confidence=0.0,
            limitations=["file was not materialized as a FileNode or CodeNode"],
        )
    blocks = _semantic_blocks(artifact_dir, [str(node["node_id"]) for node in nodes])
    label = ", ".join(sorted(set(blocks.values()))) if blocks else "unclassified"
    return EvidenceBundle(
        query_type="explain_file",
        claim=f"{file_path} has {len(nodes)} graph node(s) and block evidence: {label}.",
        confidence=0.7 if blocks else 0.45,
        source_nodes=[_evidence_node(node) for node in nodes[:20]],
        file_ranges=_file_ranges(nodes[:20]),
        limitations=[] if blocks else ["semantic-artifact.json missing or no block assignment for this file"],
    )


def trace_dependency(artifact_dir: Path, start_id: str, end_id: str, *, max_depth: int = 6) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    path = _bfs_path(graph, start_id, end_id, max_depth=max_depth)
    if not path:
        return EvidenceBundle(
            query_type="trace_dependency",
            claim=f"No dependency path found from {start_id} to {end_id} within depth {max_depth}.",
            confidence=0.25,
            limitations=["absence of a path may reflect incomplete extraction or SCIP fallback gaps"],
        )
    nodes = [graph["nodes_by_id"].get(node_id) for node_id in path["node_ids"]]
    return EvidenceBundle(
        query_type="trace_dependency",
        claim=f"Found path of {len(path['edge_types'])} edge(s) from {start_id} to {end_id}.",
        confidence=0.85,
        source_nodes=[_evidence_node(node) for node in nodes if node],
        file_ranges=_file_ranges([node for node in nodes if node]),
        paths=[EvidencePath(node_ids=path["node_ids"], edge_types=path["edge_types"])],
    )


def find_architectural_block(artifact_dir: Path, block_label: str, *, limit: int = 50) -> EvidenceBundle:
    sem = _load_semantic(artifact_dir)
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    nodes_by_id = _nodes_by_id(structural)
    matches = []
    for row in sem.get("block_assignments", []):
        secondary = [item.get("block") for item in row.get("secondary_blocks", []) if isinstance(item, dict)]
        if row.get("primary_block") == block_label or block_label in secondary:
            node = nodes_by_id.get(str(row.get("node_id", "")))
            if node:
                matches.append(node)
    return EvidenceBundle(
        query_type="find_architectural_block",
        claim=f"Found {len(matches)} node(s) assigned to {block_label}.",
        confidence=0.75 if matches else 0.35,
        source_nodes=[_evidence_node(node) for node in matches[:limit]],
        file_ranges=_file_ranges(matches[:limit]),
        limitations=[] if sem else ["semantic-artifact.json missing"],
    )


def impact_radius(artifact_dir: Path, start_id: str, *, max_depth: int = 3, max_nodes: int = 100) -> EvidenceBundle:
    try:
        impact = compute_impact_subgraph(start_id, max_depth=max_depth, max_nodes=max_nodes)
        return EvidenceBundle(
            query_type="impact_radius",
            claim=f"Impact radius from {start_id} reached {impact.get('node_count', 0)} node(s).",
            confidence=0.65,
            paths=[EvidencePath(node_ids=list(impact.get("nodes", [])), edge_types=[])],
            limitations=["impact_radius currently uses the configured graph DB; artifact_dir is retained for API symmetry"],
        )
    except Exception as exc:  # noqa: BLE001
        return EvidenceBundle(
            query_type="impact_radius",
            claim=f"Impact radius could not run for {start_id}.",
            confidence=0.0,
            limitations=[str(exc)],
        )


def answer_with_evidence(artifact_dir: Path, question: str) -> EvidenceBundle:
    q = question.lower()
    unsupported_terms = ("kafka", "graphql", "rabbitmq", "elasticsearch", "opensearch")
    if any(term in q for term in unsupported_terms):
        return EvidenceBundle(
            query_type="unsupported",
            claim="Insufficient evidence for this architecture question in the current graph.",
            confidence=0.0,
            limitations=["question references a technology or surface not detected in this artifact"],
        )
    if "auth" in q or "access" in q:
        return find_architectural_block(artifact_dir, "Access Control")
    if "database" in q or "persistence" in q:
        return find_architectural_block(artifact_dir, "Data Persistence")
    if "queue" in q or "worker" in q:
        return find_architectural_block(artifact_dir, "Background Processing")
    if "route" in q or "api" in q or "endpoint" in q or "http" in q:
        return find_architectural_block(artifact_dir, "Network Edge")
    if "config" in q or "environment" in q or "env" in q:
        return find_architectural_block(artifact_dir, "Global Interface")
    if "log" in q or "telemetry" in q or "observability" in q or "trace" in q:
        return find_architectural_block(artifact_dir, "System Telemetry")
    if "render" in q or "component" in q or "ui" in q:
        return find_architectural_block(artifact_dir, "Core Rendering")
    return EvidenceBundle(
        query_type="unsupported",
        claim="Insufficient evidence to answer this architecture question with the current deterministic router.",
        confidence=0.0,
        limitations=["question router only supports a small deterministic block vocabulary in this pass"],
    )


def benchmark_with_evidence(artifact_dir: Path, gold_set: Path) -> dict[str, Any]:
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    return build_block_benchmark_report(
        structural,
        load_gold_set(gold_set),
        artifact_dir=Path(artifact_dir),
        gold_set_path=gold_set,
    )


def _load_graph(artifact_dir: Path) -> dict[str, Any]:
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    return {"structural": structural, "nodes_by_id": _nodes_by_id(structural)}


def _nodes_by_id(structural: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    project = structural.get("project_node") or {}
    if project.get("node_id"):
        nodes[str(project["node_id"])] = {"node_id": project["node_id"], "kind": "project", **project}
    for node in structural.get("file_nodes", []):
        nodes[str(node["node_id"])] = {"kind": "file", **node}
    for node in structural.get("code_nodes", []):
        nodes[str(node.get("node_id") or node.get("scip_id"))] = {"node_id": node.get("node_id") or node.get("scip_id"), **node}
    return nodes


def _load_semantic(artifact_dir: Path) -> dict[str, Any]:
    path = Path(artifact_dir) / "semantic-artifact.json"
    return read_json(path) if path.is_file() else {}


def _semantic_blocks(artifact_dir: Path, node_ids: list[str]) -> dict[str, str]:
    sem = _load_semantic(artifact_dir)
    wanted = set(node_ids)
    return {
        str(row.get("node_id")): str(row.get("primary_block"))
        for row in sem.get("block_assignments", [])
        if str(row.get("node_id")) in wanted and row.get("primary_block")
    }


def _incident_edges(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [
        edge
        for edge in graph["structural"].get("edges", [])
        if edge.get("source_id") == node_id or edge.get("target_id") == node_id
    ]


def _bfs_path(graph: dict[str, Any], start_id: str, end_id: str, *, max_depth: int) -> dict[str, list[str]] | None:
    edges = graph["structural"].get("edges", [])
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        adjacency.setdefault(str(edge.get("source_id")), []).append((str(edge.get("target_id")), str(edge.get("edge_type"))))
    queue = deque([(start_id, [start_id], [])])
    seen = {start_id}
    while queue:
        node_id, path, edge_types = queue.popleft()
        if node_id == end_id:
            return {"node_ids": path, "edge_types": edge_types}
        if len(edge_types) >= max_depth:
            continue
        for nxt, edge_type in adjacency.get(node_id, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, [*path, nxt], [*edge_types, edge_type]))
    return None


def _evidence_node(node: dict[str, Any]) -> EvidenceNode:
    return EvidenceNode(
        node_id=str(node.get("node_id") or node.get("scip_id")),
        kind=str(node.get("kind", "")),
        file_path=node.get("file_path"),
        range=node.get("range") if isinstance(node.get("range"), dict) else None,
        label=str(node.get("name")) if node.get("name") else None,
    )


def _file_ranges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for node in nodes:
        if node.get("file_path") and isinstance(node.get("range"), dict):
            out.append({"file_path": node["file_path"], "range": node["range"], "node_id": node.get("node_id") or node.get("scip_id")})
    return out
