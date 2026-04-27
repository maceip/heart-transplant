from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from heart_transplant.artifact_store import read_json


def run_graph_smoke(artifact_dir: Path) -> dict[str, object]:
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    code_nodes: list[dict[str, object]] = structural["code_nodes"]
    edges: list[dict[str, object]] = structural["edges"]
    scip_consumed_path = artifact_dir / "scip-consumed.json"
    scip_consumed = read_json(scip_consumed_path) if scip_consumed_path.exists() else None

    contains_edges = [edge for edge in edges if edge["edge_type"] == "CONTAINS"]
    edge_type_counts: Counter[str] = Counter(str(edge["edge_type"]) for edge in edges)
    scip_backed = (
        (scip_consumed or {}).get("scip_backed_edge_counts", {})
        if isinstance(scip_consumed, dict)
        else None
    )
    nodes_by_file: dict[str, list[dict[str, object]]] = defaultdict(list)
    for node in code_nodes:
        nodes_by_file[str(node["file_path"])].append(node)

    kind_counts = Counter(str(node["kind"]) for node in code_nodes)
    top_files = sorted(
        (
            {
                "file_path": file_path,
                "node_count": len(nodes),
                "node_names": [str(node["name"]) for node in nodes[:5]],
            }
            for file_path, nodes in nodes_by_file.items()
        ),
        key=lambda item: (-item["node_count"], item["file_path"]),
    )

    auth_nodes = [
        summarize_node(node)
        for node in code_nodes
        if is_auth_or_identity_node(node)
    ][:8]
    data_nodes = [
        summarize_node(node)
        for node in code_nodes
        if is_data_or_schema_node(node)
    ][:8]

    missing_containment = [
        str(node["scip_id"])
        for node in code_nodes
        if not any(str(edge["target_id"]) == str(node["scip_id"]) for edge in contains_edges)
    ]

    scip_path = artifact_dir / "index.scip"
    scip_metadata_path = artifact_dir / "scip-index.json"

    resolved_from_report = 0
    if scip_consumed and isinstance(scip_consumed, dict) and "resolution" in scip_consumed:
        resolved_from_report = int(scip_consumed["resolution"].get("nodes_with_scip_identity", 0) or 0)
    scip_resolved = sum(1 for node in code_nodes if node.get("symbol_source") == "scip")
    if resolved_from_report and not scip_resolved:
        scip_resolved = resolved_from_report

    scip_orphans = 0
    if scip_consumed and isinstance(scip_consumed, dict):
        scip_orphans = int(scip_consumed.get("orphaned_symbol_count", 0) or 0)

    if scip_path.exists() and not scip_consumed_path.exists():
        scip_integration = "degraded: index.scip without scip-consumed.json; run consume-scip"
    elif not scip_path.exists():
        scip_integration = "not_applicable: no index.scip"
    elif not scip_consumed_path.exists():
        scip_integration = "degraded: missing scip-consumed"
    elif scip_resolved == 0 and len(code_nodes) > 0:
        scip_integration = "fail: SCIP present but no code nodes were resolved to scip symbol_source"
    elif scip_resolved == 0:
        scip_integration = "degraded: zero code nodes in artifact"
    else:
        scip_integration = f"ok: {scip_resolved} code node(s) carry SCIP identity"

    return {
        "artifact_dir": str(artifact_dir),
        "repo_name": structural["repo_name"],
        "file_node_count": len(structural.get("file_nodes", [])) if isinstance(structural.get("file_nodes"), list) else 0,
        "has_project_node": bool(structural.get("project_node")),
        "neighborhoods_indexed": len(structural.get("neighborhoods", {})) if isinstance(structural.get("neighborhoods"), dict) else 0,
        "node_count": structural["node_count"],
        "edge_count": structural["edge_count"],
        "edge_type_counts": dict(edge_type_counts),
        "contains_edge_count": len(contains_edges),
        "node_kind_counts": dict(kind_counts),
        "top_files": top_files[:10],
        "auth_nodes": auth_nodes,
        "data_nodes": data_nodes,
        "missing_containment": missing_containment,
        "scip_resolved_nodes": scip_resolved,
        "scip_backed_edge_counts": scip_backed,
        "scip_orphaned_definition_count": scip_orphans,
        "scip_present": scip_path.exists(),
        "scip_size_bytes": scip_path.stat().st_size if scip_path.exists() else 0,
        "scip_metadata_present": scip_metadata_path.exists(),
        "scip_consumed_present": scip_consumed_path.exists(),
        "scip_implementation_edge_count": len(scip_consumed.get("implementation_edges", [])) if scip_consumed else 0,
        "scip_integration_status": scip_integration,
    }


def summarize_node(node: dict[str, object]) -> dict[str, object]:
    return {
        "name": node["name"],
        "kind": node["kind"],
        "file_path": node["file_path"],
        "scip_id": node["scip_id"],
    }


def is_auth_or_identity_node(node: dict[str, object]) -> bool:
    haystack = " ".join(
        [
            str(node["name"]).lower(),
            str(node["file_path"]).lower(),
            str(node.get("content", "")).lower()[:500],
        ]
    )
    return any(token in haystack for token in ("auth", "login", "session", "password", "token", "profile"))


def is_data_or_schema_node(node: dict[str, object]) -> bool:
    haystack = " ".join(
        [
            str(node["name"]).lower(),
            str(node["file_path"]).lower(),
            str(node.get("content", "")).lower()[:500],
        ]
    )
    return any(token in haystack for token in ("prisma", "schema", "db", "database", "profile", "query", "seed"))
