from __future__ import annotations

from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json, write_json


CANONICAL_GRAPH_SCHEMA = "heart-transplant.canonical-graph.v1"


def build_canonical_graph(
    artifact_dir: Path,
    *,
    multimodal_report: Path | None = None,
) -> dict[str, Any]:
    """Project structural, semantic, and optional multimodal data into one graph-shaped artifact."""

    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    semantic_path = artifact_dir / "semantic-artifact.json"
    semantic = read_json(semantic_path) if semantic_path.is_file() else {}
    multimodal = read_json(multimodal_report.resolve()) if multimodal_report else {}

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    project = structural.get("project_node") or {}
    if project.get("node_id"):
        nodes[str(project["node_id"])] = {
            "node_id": str(project["node_id"]),
            "layer": "project",
            "kind": "project",
            "label": project.get("name") or structural.get("repo_name"),
            "repo_name": structural.get("repo_name"),
            "provenance": "tree_sitter",
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

    summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "layers": sorted({str(node.get("layer")) for node in nodes.values()}),
        "dangling_edge_count": sum(
            1 for edge in edges if edge["source_id"] not in nodes or edge["target_id"] not in nodes
        ),
    }
    return {
        "schema": CANONICAL_GRAPH_SCHEMA,
        "artifact_dir": str(artifact_dir),
        "repo_name": structural.get("repo_name"),
        "summary": summary,
        "nodes": sorted(nodes.values(), key=lambda node: str(node["node_id"])),
        "edges": edges,
    }


def write_canonical_graph(graph: dict[str, Any], out: Path) -> Path:
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, graph)
    return out


def canonical_edge(
    source_id: str,
    target_id: str,
    edge_type: str,
    repo_name: str | None,
    *,
    provenance: str,
    target_repo: str | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "target_id": target_id,
        "edge_type": edge_type,
        "repo_name": repo_name,
        "target_repo": target_repo,
        "provenance": provenance,
    }


def infer_edge_provenance(edge_type: str) -> str:
    if edge_type in {"REFERENCES", "DEFINES", "IMPLEMENTS", "CROSS_REFERENCE"}:
        return "scip"
    return "tree_sitter"
