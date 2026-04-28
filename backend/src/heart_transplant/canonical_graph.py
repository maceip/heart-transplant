from __future__ import annotations

from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json, write_json
from pydantic import BaseModel, Field


CANONICAL_GRAPH_SCHEMA = "heart-transplant.canonical-graph.v1"


class ArtifactManifest(BaseModel):
    artifact_dir: str
    repo_name: str | None = None
    repo_path: str | None = None
    source_artifacts: dict[str, str] = Field(default_factory=dict)


class CanonicalNode(BaseModel):
    node_id: str
    layer: str
    kind: str
    label: str | None = None
    repo_name: str | None = None
    file_path: str | None = None
    range: dict[str, Any] | None = None
    provenance: str
    meta: dict[str, Any] = Field(default_factory=dict)


class CanonicalEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: str
    repo_name: str | None = None
    target_repo: str | None = None
    provenance: str
    meta: dict[str, Any] = Field(default_factory=dict)


class CanonicalGraph(BaseModel):
    schema: str = CANONICAL_GRAPH_SCHEMA
    artifact_dir: str
    repo_name: str | None = None
    manifest: ArtifactManifest
    summary: dict[str, Any]
    nodes: list[CanonicalNode] = Field(default_factory=list)
    edges: list[CanonicalEdge] = Field(default_factory=list)


def build_canonical_graph(
    artifact_dir: Path,
    *,
    multimodal_report: Path | None = None,
    temporal_report: Path | None = None,
    regret_report: Path | None = None,
) -> dict[str, Any]:
    """Project all known artifacts/reports into one graph-shaped backend contract."""

    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    semantic_path = artifact_dir / "semantic-artifact.json"
    scip_path = artifact_dir / "scip-consumed.json"
    semantic = read_json(semantic_path) if semantic_path.is_file() else {}
    scip = read_json(scip_path) if scip_path.is_file() else {}
    multimodal = read_json(multimodal_report.resolve()) if multimodal_report else {}
    temporal = read_json(temporal_report.resolve()) if temporal_report else {}
    regret = read_json(regret_report.resolve()) if regret_report else {}

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    manifest = build_manifest(
        artifact_dir,
        structural,
        semantic_path=semantic_path if semantic_path.is_file() else None,
        scip_path=scip_path if scip_path.is_file() else None,
        multimodal_report=multimodal_report,
        temporal_report=temporal_report,
        regret_report=regret_report,
    )

    project = structural.get("project_node") or {}
    if project.get("node_id"):
        nodes[str(project["node_id"])] = {
            "node_id": str(project["node_id"]),
            "layer": "project",
            "kind": "project",
            "label": project.get("name") or structural.get("repo_name"),
            "repo_name": structural.get("repo_name"),
            "provenance": "tree_sitter",
            "meta": {},
        }

    for file_node in structural.get("file_nodes", []):
        node_id = str(file_node.get("node_id"))
        nodes[node_id] = {
            "node_id": node_id,
            "layer": "file",
            "kind": "file",
            "label": file_node.get("file_path"),
            "file_path": file_node.get("file_path"),
            "repo_name": file_node.get("repo_name"),
            "language": file_node.get("language"),
            "provenance": "tree_sitter",
            "meta": {"language": file_node.get("language")},
        }

    for code_node in structural.get("code_nodes", []):
        node_id = str(code_node.get("scip_id") or code_node.get("node_id"))
        nodes[node_id] = {
            "node_id": node_id,
            "layer": "code",
            "kind": code_node.get("kind"),
            "label": code_node.get("name"),
            "file_path": code_node.get("file_path"),
            "range": code_node.get("range"),
            "repo_name": code_node.get("repo_name"),
            "symbol_source": code_node.get("symbol_source"),
            "provenance": code_node.get("symbol_source") if code_node.get("symbol_source") == "scip" else "tree_sitter",
            "meta": {
                "symbol_source": code_node.get("symbol_source"),
                "scip_kind": code_node.get("scip_kind"),
            },
        }

    for assignment in semantic.get("block_assignments", []) or []:
        source = str(assignment.get("node_id", ""))
        if not source:
            continue
        semantic_id = f"semantic:{source}:{assignment.get('primary_block')}"
        nodes[semantic_id] = {
            "node_id": semantic_id,
            "layer": "semantic",
            "kind": "block_assignment",
            "label": assignment.get("primary_block"),
            "confidence": assignment.get("confidence"),
            "secondary_blocks": assignment.get("secondary_blocks", []),
            "provenance": "semantic_classifier",
            "meta": {
                "confidence": assignment.get("confidence"),
                "secondary_blocks": assignment.get("secondary_blocks", []),
                "reasoning": assignment.get("reasoning"),
            },
        }
        edges.append(
            canonical_edge(
                semantic_id,
                source,
                "DESCRIBES",
                structural.get("repo_name"),
                provenance="semantic_classifier",
            )
        )
        for secondary in assignment.get("secondary_blocks", []) or []:
            block = secondary.get("block") if isinstance(secondary, dict) else None
            if not block:
                continue
            secondary_id = f"semantic:{source}:{block}"
            nodes[secondary_id] = {
                "node_id": secondary_id,
                "layer": "semantic",
                "kind": "secondary_block_assignment",
                "label": block,
                "confidence": secondary.get("confidence"),
                "provenance": "semantic_classifier",
                "meta": secondary,
            }
            edges.append(canonical_edge(secondary_id, source, "SECONDARY_DESCRIBES", structural.get("repo_name"), provenance="semantic_classifier"))

    for entity in semantic.get("entities", []) or []:
        entity_id = str(entity.get("entity_id", ""))
        if not entity_id:
            continue
        nodes[entity_id] = {
            "node_id": entity_id,
            "layer": "semantic",
            "kind": "entity",
            "label": entity.get("name"),
            "repo_name": structural.get("repo_name"),
            "provenance": "semantic_enrichment",
            "meta": entity,
        }
    for action in semantic.get("actions", []) or []:
        source = str(action.get("source_code_node_id", ""))
        target = str(action.get("entity_id", ""))
        if source and target:
            edges.append(canonical_edge(source, target, f"PERFORMS_{action.get('action', 'ACTION')}", structural.get("repo_name"), provenance="semantic_enrichment", meta=action))

    for edge in structural.get("edges", []):
        edges.append(
            canonical_edge(
                str(edge.get("source_id")),
                str(edge.get("target_id")),
                str(edge.get("edge_type")),
                edge.get("repo_name") or structural.get("repo_name"),
                provenance=edge.get("provenance") or infer_edge_provenance(str(edge.get("edge_type"))),
                target_repo=edge.get("target_repo"),
            )
        )

    for item in scip.get("documents", []) or []:
        rel = str(item.get("relative_path", ""))
        if not rel:
            continue
        doc_id = f"scip-document:{rel}"
        nodes[doc_id] = {
            "node_id": doc_id,
            "layer": "scip",
            "kind": "document",
            "label": rel,
            "file_path": rel,
            "repo_name": structural.get("repo_name"),
            "provenance": "scip",
            "meta": item,
        }
        file_id = f"repo://{structural.get('repo_name')}/{rel}"
        if file_id in nodes:
            edges.append(canonical_edge(doc_id, file_id, "DESCRIBES_FILE", structural.get("repo_name"), provenance="scip"))
    for item in scip.get("addressable_orphaned_symbols", []) or []:
        symbol = str(item.get("symbol", ""))
        if symbol and symbol in nodes:
            nodes[symbol]["meta"] = {**nodes[symbol].get("meta", {}), "scip_orphan": item}
    for item in scip.get("implementation_edges", []) or []:
        source = str(item.get("source_symbol", ""))
        target = str(item.get("target_symbol", ""))
        if source and target:
            edges.append(canonical_edge(source, target, "IMPLEMENTS", structural.get("repo_name"), provenance="scip", meta=item))

    for node in multimodal.get("nodes", []) or []:
        node_id = str(node.get("node_id", ""))
        if not node_id:
            continue
        nodes[node_id] = {
            "node_id": node_id,
            "layer": "multimodal" if node.get("kind") not in {"test", "openapi", "infra", "codefile"} else node.get("kind"),
            "kind": node.get("kind"),
            "label": node.get("name") or node.get("path"),
            "file_path": node.get("path"),
            "meta": node.get("meta", {}),
            "provenance": f"{node.get('kind')}_parser",
        }
    for edge in multimodal.get("edges", []) or []:
        edges.append(
            canonical_edge(
                str(edge.get("source_id")),
                str(edge.get("target_id")),
                str(edge.get("edge_kind")),
                structural.get("repo_name"),
                provenance="multimodal_correlation",
            )
        )
    for item in temporal.get("replayed_snapshots", []) or []:
        commit = str(item.get("commit_sha", ""))
        if not commit:
            continue
        node_id = f"temporal-snapshot:{commit}"
        nodes[node_id] = {
            "node_id": node_id,
            "layer": "temporal",
            "kind": "graph_snapshot",
            "label": item.get("subject") or commit[:12],
            "repo_name": structural.get("repo_name"),
            "provenance": "temporal_replay",
            "meta": item,
        }
    for item in regret.get("surfaces", []) or []:
        regret_item = item.get("regret", {}) if isinstance(item, dict) else {}
        regret_id = str(regret_item.get("regret_id", ""))
        if not regret_id:
            continue
        node_id = f"regret:{regret_id}"
        nodes[node_id] = {
            "node_id": node_id,
            "layer": "regret",
            "kind": "regret_surface",
            "label": regret_item.get("title"),
            "repo_name": structural.get("repo_name"),
            "provenance": "regret_detector",
            "meta": item,
        }
        for evidence in item.get("evidence_bundle", []) or []:
            for source_node in evidence.get("node_ids", []) or []:
                edges.append(canonical_edge(node_id, str(source_node), "EVIDENCED_BY", structural.get("repo_name"), provenance="regret_detector", meta=evidence))

    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "layers": sorted({str(node.get("layer")) for node in nodes.values()}),
        "dangling_edge_count": sum(
            1 for edge in edges if edge["source_id"] not in nodes or edge["target_id"] not in nodes
        ),
    }
    graph = CanonicalGraph(
        artifact_dir=str(artifact_dir),
        repo_name=structural.get("repo_name"),
        manifest=manifest,
        summary=summary,
        nodes=[CanonicalNode.model_validate(node) for node in sorted(nodes.values(), key=lambda node: str(node["node_id"]))],
        edges=[CanonicalEdge.model_validate(edge) for edge in edges],
    )
    return graph.model_dump(mode="json")


def write_canonical_graph(graph: dict[str, Any], out: Path) -> Path:
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, graph)
    return out


def write_canonical_graph_for_artifact(
    artifact_dir: Path,
    *,
    multimodal_report: Path | None = None,
    temporal_report: Path | None = None,
    regret_report: Path | None = None,
    out: Path | None = None,
) -> Path:
    artifact_dir = artifact_dir.resolve()
    graph = build_canonical_graph(
        artifact_dir,
        multimodal_report=multimodal_report,
        temporal_report=temporal_report,
        regret_report=regret_report,
    )
    return write_canonical_graph(graph, out or artifact_dir / "canonical-graph.json")


def canonical_edge(
    source_id: str,
    target_id: str,
    edge_type: str,
    repo_name: str | None,
    *,
    provenance: str,
    target_repo: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "target_id": target_id,
        "edge_type": edge_type,
        "repo_name": repo_name,
        "target_repo": target_repo,
        "provenance": provenance,
        "meta": meta or {},
    }


def infer_edge_provenance(edge_type: str) -> str:
    if edge_type in {"REFERENCES", "DEFINES", "IMPLEMENTS", "CROSS_REFERENCE"}:
        return "scip"
    return "tree_sitter"


def build_manifest(
    artifact_dir: Path,
    structural: dict[str, Any],
    *,
    semantic_path: Path | None = None,
    scip_path: Path | None = None,
    multimodal_report: Path | None = None,
    temporal_report: Path | None = None,
    regret_report: Path | None = None,
) -> ArtifactManifest:
    sources = {"structural": str(artifact_dir / "structural-artifact.json")}
    if semantic_path:
        sources["semantic"] = str(semantic_path)
    if scip_path:
        sources["scip"] = str(scip_path)
    if multimodal_report:
        sources["multimodal"] = str(multimodal_report.resolve())
    if temporal_report:
        sources["temporal"] = str(temporal_report.resolve())
    if regret_report:
        sources["regret"] = str(regret_report.resolve())
    return ArtifactManifest(
        artifact_dir=str(artifact_dir),
        repo_name=structural.get("repo_name"),
        repo_path=structural.get("repo_path"),
        source_artifacts=sources,
    )
