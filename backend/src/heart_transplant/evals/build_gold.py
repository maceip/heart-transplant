from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json, write_json


BLOCK_ID_TO_LABEL = {
    "access_control": "Access Control",
    "system_telemetry": "System Telemetry",
    "data_persistence": "Data Persistence",
    "background_processing": "Background Processing",
    "traffic_control": "Traffic Control",
    "network_edge": "Network Edge",
    "search_architecture": "Search Architecture",
    "security_ops": "Security Ops",
    "connectivity_layer": "Connectivity Layer",
    "resiliency": "Resiliency",
    "data_sovereignty": "Data Sovereignty",
    "analytical_intelligence": "Analytical Intelligence",
    "identity_ui": "Identity UI",
    "state_management": "State Management",
    "core_rendering": "Core Rendering",
    "interaction_design": "Interaction Design",
    "asset_delivery": "Asset Delivery",
    "global_interface": "Global Interface",
    "edge_support": "Edge Support",
    "experimentation": "Experimentation",
    "user_observability": "User Observability",
    "error_boundaries": "Error Boundaries",
    "persistence_strategy": "Persistence Strategy",
    "visual_systems": "Visual Systems",
}


def build_gold_from_ground_truth(
    ground_truth_path: Path,
    *,
    repo_name: str | None = None,
    min_items: int = 5,
    max_items: int = 40,
    include_medium: bool = False,
    exclude_repo_names: Collection[str] | None = None,
    only_repo_names: Collection[str] | None = None,
) -> list[dict[str, Any]]:
    """Build file-level benchmark items from vendored ground truth.

    The output is artifact-stable because it targets file paths, not SCIP IDs.
    """
    excluded = frozenset(exclude_repo_names or ())
    only = frozenset(only_repo_names or ())
    data = read_json(ground_truth_path)
    repos = data if isinstance(data, list) else []
    if repo_name:
        repos = [repo for repo in repos if str(repo.get("repoName")) == repo_name or str(repo.get("repoDir", "")).endswith(repo_name)]

    per_repo_items: list[list[dict[str, Any]]] = []
    allowed_confidence = {"high", "medium"} if include_medium else {"high"}
    for repo in repos:
        name = str(repo.get("repoName", "unknown"))
        if only and name not in only:
            continue
        if name in excluded:
            continue
        repo_items: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in repo.get("topFileBlocks", []):
            confidence = str(row.get("confidence"))
            if confidence not in allowed_confidence:
                continue
            block_id = str(row.get("blockId", ""))
            block = BLOCK_ID_TO_LABEL.get(block_id)
            file_path = str(row.get("filePath", ""))
            if not block or not file_path or file_path == "package.json":
                continue
            key = (name, file_path, block)
            if key in seen:
                continue
            seen.add(key)
            repo_items.append(
                {
                    "id": f"{name}:{file_path}:{block_id}",
                    "repo_name": name,
                    "file_path": file_path,
                    "expected_block": block,
                    "confidence": confidence,
                    "source": str(ground_truth_path),
                }
            )
        if repo_items:
            per_repo_items.append(repo_items)

    items = round_robin(per_repo_items, max_items)
    if len(items) < min_items:
        return items
    return items


def round_robin(groups: list[list[dict[str, Any]]], max_items: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    index = 0
    while len(out) < max_items:
        added = False
        for group in groups:
            if index < len(group):
                out.append(group[index])
                added = True
                if len(out) >= max_items:
                    break
        if not added:
            break
        index += 1
    return out


def write_gold_from_ground_truth(
    ground_truth_path: Path,
    out_path: Path,
    *,
    repo_name: str | None = None,
    min_items: int = 5,
    max_items: int = 40,
    include_medium: bool = False,
    exclude_repo_names: Collection[str] | None = None,
    only_repo_names: Collection[str] | None = None,
) -> list[dict[str, Any]]:
    items = build_gold_from_ground_truth(
        ground_truth_path,
        repo_name=repo_name,
        min_items=min_items,
        max_items=max_items,
        include_medium=include_medium,
        exclude_repo_names=exclude_repo_names,
        only_repo_names=only_repo_names,
    )
    write_json(out_path, items)
    return items
