from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json
from heart_transplant.canonical_graph import CanonicalGraph, build_canonical_graph


def run_graph_integrity(artifact_dir: Path) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    canonical = build_canonical_graph(artifact_dir)
    project_node = structural.get("project_node") or {}
    node_ids = {str(project_node.get("node_id", ""))}
    node_ids.update(str(node["node_id"]) for node in structural.get("file_nodes", []))
    node_ids.update(str(node["scip_id"]) for node in structural.get("code_nodes", []))

    dangling_edges = []
    provisional_targets = []
    edge_counts: Counter[str] = Counter()
    for edge in structural.get("edges", []):
        source_id = str(edge.get("source_id", ""))
        target_id = str(edge.get("target_id", ""))
        edge_type = str(edge.get("edge_type", ""))
        edge_counts[edge_type] += 1
        if source_id not in node_ids or target_id not in node_ids:
            dangling_edges.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "edge_type": edge_type,
                    "missing": [
                        side
                        for side, value in (("source", source_id), ("target", target_id))
                        if value not in node_ids
                    ],
                }
            )
        if target_id.startswith("provisional://") or source_id.startswith("provisional://"):
            provisional_targets.append({"source_id": source_id, "target_id": target_id, "edge_type": edge_type})

    file_node_paths = {str(node.get("file_path", "")) for node in structural.get("file_nodes", [])}
    code_paths = {str(node.get("file_path", "")) for node in structural.get("code_nodes", [])}
    missing_file_nodes = sorted(path for path in code_paths if path not in file_node_paths)
    canonical_nodes = canonical.get("nodes", [])
    canonical_edges = canonical.get("edges", [])
    canonical_node_ids = [str(node.get("node_id", "")) for node in canonical_nodes]
    canonical_node_id_set = set(canonical_node_ids)
    unstable_node_ids = [node_id for node_id in canonical_node_ids if not node_id or node_id.lower() in {"none", "null"}]
    derived_without_evidence = [
        node
        for node in canonical_nodes
        if node.get("layer") in {"semantic", "temporal", "regret"}
        and not _derived_node_has_source_edge(str(node.get("node_id", "")), canonical_edges, canonical_node_id_set)
    ]
    roundtrip_ok = True
    try:
        CanonicalGraph.model_validate(canonical).model_dump(mode="json")
    except Exception:
        roundtrip_ok = False

    checks = [
        _check("no_dangling_edges", not dangling_edges, f"{len(dangling_edges)} dangling edges"),
        _check("no_provisional_edge_leakage", not provisional_targets, f"{len(provisional_targets)} provisional edge endpoints"),
        _check("code_files_materialized", not missing_file_nodes, f"{len(missing_file_nodes)} code paths without FileNode"),
        _check(
            "canonical_graph_no_dangling_targets",
            int(canonical.get("summary", {}).get("dangling_edge_count", 0) or 0) == 0,
            f"{canonical.get('summary', {}).get('dangling_edge_count', 0)} canonical dangling edges",
        ),
        _check(
            "canonical_graph_all_edges_have_provenance",
            all(edge.get("provenance") for edge in canonical.get("edges", [])),
            "canonical graph edges include provenance",
        ),
        _check(
            "canonical_graph_manifest_present",
            bool(canonical.get("manifest", {}).get("source_artifacts", {}).get("structural")),
            "canonical graph manifest records structural source artifact",
        ),
        _check(
            "canonical_graph_stable_node_ids",
            not unstable_node_ids and len(canonical_node_ids) == len(canonical_node_id_set),
            f"{len(unstable_node_ids)} unstable IDs; {len(canonical_node_ids) - len(canonical_node_id_set)} duplicate IDs",
        ),
        _check(
            "canonical_graph_derived_nodes_link_to_evidence",
            not derived_without_evidence,
            f"{len(derived_without_evidence)} derived nodes without source evidence edges",
        ),
        _check(
            "canonical_graph_reloads_without_loss",
            roundtrip_ok,
            "canonical graph validates through CanonicalGraph model roundtrip",
        ),
    ]
    failed = [check for check in checks if check["status"] != "pass"]
    return {
        "report_type": "graph_integrity",
        "artifact_dir": str(artifact_dir),
        "repo_name": structural.get("repo_name"),
        "summary": {
            "status": "pass" if not failed else "fail",
            "overall_status": "pass" if not failed else "fail",
            "node_id_count": len(node_ids),
            "edge_count": len(structural.get("edges", [])),
            "edge_type_counts": dict(edge_counts),
            "failed_checks": len(failed),
            "dangling_edge_count": len(dangling_edges),
            "provisional_edge_endpoint_count": len(provisional_targets),
            "missing_file_node_count": len(missing_file_nodes),
            "canonical_node_count": canonical.get("summary", {}).get("node_count", 0),
            "canonical_edge_count": canonical.get("summary", {}).get("edge_count", 0),
            "canonical_dangling_edge_count": canonical.get("summary", {}).get("dangling_edge_count", 0),
            "canonical_unstable_node_id_count": len(unstable_node_ids),
            "canonical_derived_without_evidence_count": len(derived_without_evidence),
        },
        "checks": checks,
        "dangling_edges": dangling_edges[:50],
        "provisional_edge_endpoints": provisional_targets[:50],
        "missing_file_nodes": missing_file_nodes[:50],
    }


def _check(check_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "detail": detail,
    }


def _derived_node_has_source_edge(node_id: str, edges: list[dict[str, Any]], node_ids: set[str]) -> bool:
    if not node_id:
        return False
    for edge in edges:
        if edge.get("source_id") == node_id and edge.get("target_id") in node_ids:
            return True
        if edge.get("target_id") == node_id and edge.get("source_id") in node_ids:
            return True
    return False
