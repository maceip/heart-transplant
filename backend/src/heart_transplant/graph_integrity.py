from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json
from heart_transplant.canonical_graph import CanonicalGraph, build_canonical_graph


def run_graph_integrity(artifact_dir: Path) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    project_node = structural.get("project_node") or {}
    node_ids = {str(project_node.get("node_id", ""))}
    node_ids.update(str(node["node_id"]) for node in structural.get("file_nodes", []))
    node_ids.update(str(node["scip_id"]) for node in structural.get("code_nodes", []))

    dangling_edges = []
    external_edge_endpoints = []
    provisional_targets = []
    edge_counts: Counter[str] = Counter()
    for edge in structural.get("edges", []):
        source_id = str(edge.get("source_id", ""))
        target_id = str(edge.get("target_id", ""))
        edge_type = str(edge.get("edge_type", ""))
        edge_counts[edge_type] += 1
        missing_sides = []
        external_sides = []
        for side, value in (("source", source_id), ("target", target_id)):
            if value in node_ids:
                continue
            if _is_allowed_external_endpoint(edge_type, side, value):
                external_sides.append(side)
            else:
                missing_sides.append(side)
        if external_sides:
            external_edge_endpoints.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "edge_type": edge_type,
                    "external": external_sides,
                }
            )
        if missing_sides:
            dangling_edges.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "edge_type": edge_type,
                    "missing": missing_sides,
                }
            )
        if target_id.startswith("provisional://") or source_id.startswith("provisional://"):
            provisional_targets.append({"source_id": source_id, "target_id": target_id, "edge_type": edge_type})

    file_node_paths = {str(node.get("file_path", "")) for node in structural.get("file_nodes", [])}
    code_paths = {str(node.get("file_path", "")) for node in structural.get("code_nodes", [])}
    missing_file_nodes = sorted(path for path in code_paths if path not in file_node_paths)
    canonical = build_canonical_graph(artifact_dir)
    canonical_nodes = canonical.get("nodes", [])
    canonical_edges = canonical.get("edges", [])
    canonical_node_ids = [str(node.get("node_id", "")) for node in canonical_nodes]
    canonical_node_id_set = set(canonical_node_ids)
    unstable_node_ids = [node_id for node_id in canonical_node_ids if not node_id or node_id.lower() in {"none", "null"}]
    derived_without_evidence = [
        node
        for node in canonical_nodes
        if node.get("layer") in {"semantic", "scip", "test", "openapi", "infra", "temporal", "regret"}
        and not _derived_node_has_source_edge(str(node.get("node_id", "")), canonical_edges, canonical_node_id_set)
    ]
    roundtrip_ok = True
    try:
        CanonicalGraph.model_validate(canonical).model_dump(mode="json")
    except Exception:
        roundtrip_ok = False

    checks = [
        _check("structural", "no_dangling_edges", not dangling_edges, f"{len(dangling_edges)} dangling edges"),
        _check("structural", "no_provisional_edge_leakage", not provisional_targets, f"{len(provisional_targets)} provisional edge endpoints"),
        _check("structural", "code_files_materialized", not missing_file_nodes, f"{len(missing_file_nodes)} code paths without FileNode"),
        _check(
            "canonical",
            "canonical_graph_no_dangling_targets",
            int(canonical.get("summary", {}).get("dangling_edge_count", 0) or 0) == 0,
            f"{canonical.get('summary', {}).get('dangling_edge_count', 0)} canonical dangling edges",
        ),
        _check(
            "canonical",
            "canonical_graph_all_edges_have_provenance",
            all(edge.get("provenance") for edge in canonical_edges),
            "canonical graph edges include provenance",
        ),
        _check(
            "canonical",
            "canonical_graph_stable_node_ids",
            not unstable_node_ids and len(canonical_node_ids) == len(canonical_node_id_set),
            f"{len(unstable_node_ids)} unstable IDs; {len(canonical_node_ids) - len(canonical_node_id_set)} duplicate IDs",
        ),
        _check(
            "canonical",
            "canonical_graph_derived_nodes_link_to_evidence",
            not derived_without_evidence,
            f"{len(derived_without_evidence)} derived nodes without source evidence edges",
        ),
        _check(
            "canonical",
            "canonical_graph_reloads_without_loss",
            roundtrip_ok,
            "canonical graph validates through CanonicalGraph model roundtrip",
        ),
    ]
    scip_checks = _scip_checks(artifact_dir)
    semantic_checks = _semantic_checks(artifact_dir, node_ids)
    manifest_checks = _manifest_checks(artifact_dir)
    checks.extend(scip_checks)
    checks.extend(semantic_checks)
    checks.extend(manifest_checks)
    failed = [check for check in checks if check["status"] == "fail"]
    layers = _layer_statuses(checks)
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
            "external_edge_endpoint_count": len(external_edge_endpoints),
            "missing_file_node_count": len(missing_file_nodes),
            "canonical_node_count": canonical.get("summary", {}).get("node_count", 0),
            "canonical_edge_count": canonical.get("summary", {}).get("edge_count", 0),
            "canonical_dangling_edge_count": canonical.get("summary", {}).get("dangling_edge_count", 0),
            "canonical_unstable_node_id_count": len(unstable_node_ids),
            "canonical_derived_without_evidence_count": len(derived_without_evidence),
            "layer_statuses": layers,
        },
        "layers": layers,
        "checks": checks,
        "dangling_edges": dangling_edges[:50],
        "external_edge_endpoints": external_edge_endpoints[:50],
        "provisional_edge_endpoints": provisional_targets[:50],
        "missing_file_nodes": missing_file_nodes[:50],
    }


def _scip_checks(artifact_dir: Path) -> list[dict[str, str]]:
    index = artifact_dir / "index.scip"
    metadata = artifact_dir / "scip-index.json"
    consumed = artifact_dir / "scip-consumed.json"
    if not any(path.is_file() for path in (index, metadata, consumed)):
        return [_check("scip", "scip_layer_optional", True, "SCIP layer not present")]
    checks = [
        _check("scip", "scip_binary_has_metadata", not index.is_file() or metadata.is_file(), "index.scip has scip-index.json"),
        _check("scip", "scip_consumed_has_index", not consumed.is_file() or index.is_file(), "scip-consumed.json has index.scip"),
    ]
    if consumed.is_file():
        data = read_json(consumed)
        resolution = data.get("resolution", {}) if isinstance(data, dict) else {}
        resolved = int(resolution.get("resolved_code_nodes") or 0)
        total = int(resolution.get("total_code_nodes") or 0)
        checks.append(_warn("scip", "scip_resolution_counts_bounded", resolved <= total, f"{resolved} resolved of {total} total code nodes"))
    return checks


def _semantic_checks(artifact_dir: Path, node_ids: set[str]) -> list[dict[str, str]]:
    semantic_path = artifact_dir / "semantic-artifact.json"
    if not semantic_path.is_file():
        return [_check("semantic", "semantic_layer_optional", True, "semantic-artifact.json not present")]
    semantic = read_json(semantic_path)
    assignments = semantic.get("block_assignments", []) if isinstance(semantic, dict) else []
    missing_targets = [
        str(row.get("node_id"))
        for row in assignments
        if isinstance(row, dict) and str(row.get("node_id", "")) not in node_ids
    ]
    return [
        _check("semantic", "semantic_assignments_target_graph_nodes", not missing_targets, f"{len(missing_targets)} semantic assignments target missing graph nodes"),
        _check("semantic", "semantic_assignments_nonempty", bool(assignments), f"{len(assignments)} semantic block assignments"),
    ]


def _manifest_checks(artifact_dir: Path) -> list[dict[str, str]]:
    manifest_path = artifact_dir / "artifact-manifest.json"
    if not manifest_path.is_file():
        return [_check("manifest", "manifest_layer_optional", True, "artifact-manifest.json not present")]
    manifest = read_json(manifest_path)
    files = manifest.get("files", []) if isinstance(manifest, dict) else []
    stale = []
    missing = []
    for item in files:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("path") or "")
        path = artifact_dir / rel
        if not path.is_file():
            missing.append(rel)
            continue
        expected = str(item.get("sha256") or "")
        if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            stale.append(rel)
    return [
        _check("manifest", "manifest_files_exist", not missing, f"{len(missing)} manifest files missing"),
        _check("manifest", "manifest_hashes_current", not stale, f"{len(stale)} manifest hashes stale"),
    ]


def _layer_statuses(checks: list[dict[str, str]]) -> dict[str, str]:
    layers: dict[str, str] = {}
    for check in checks:
        layer = check["layer"]
        if layers.get(layer) == "fail":
            continue
        if layers.get(layer) == "warn" and check["status"] == "pass":
            continue
        layers[layer] = check["status"]
    return layers


def _derived_node_has_source_edge(node_id: str, edges: list[dict[str, Any]], node_ids: set[str]) -> bool:
    if not node_id:
        return False
    for edge in edges:
        if edge.get("source_id") == node_id and edge.get("target_id") in node_ids:
            return True
        if edge.get("target_id") == node_id and edge.get("source_id") in node_ids:
            return True
    return False


def _is_allowed_external_endpoint(edge_type: str, side: str, value: str) -> bool:
    if side != "target":
        return False
    if edge_type == "IMPORTS_MODULE" and value.startswith("module:"):
        return True
    if edge_type in {"REFERENCES", "IMPLEMENTS"} and (
        value.startswith("scip-typescript npm ")
        or value.startswith("local ")
    ):
        return True
    return False


def _warn(layer: str, check_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "layer": layer,
        "check_id": check_id,
        "status": "pass" if passed else "warn",
        "detail": detail,
    }


def _check(layer: str, check_id: str, passed: bool, detail: str) -> dict[str, str]:
    return {
        "layer": layer,
        "check_id": check_id,
        "status": "pass" if passed else "fail",
        "detail": detail,
    }
