from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json


def run_graph_integrity(artifact_dir: Path) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
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

    checks = [
        _check("no_dangling_edges", not dangling_edges, f"{len(dangling_edges)} dangling edges"),
        _check("no_provisional_edge_leakage", not provisional_targets, f"{len(provisional_targets)} provisional edge endpoints"),
        _check("code_files_materialized", not missing_file_nodes, f"{len(missing_file_nodes)} code paths without FileNode"),
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
