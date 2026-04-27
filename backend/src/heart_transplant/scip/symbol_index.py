from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json, write_json


def build_symbol_index_from_artifacts(artifact_paths: list[Path]) -> dict[str, Any]:
    """Map SCIP / provisional symbol id -> list of {repo_name, node_id} across artifacts."""
    symbols: dict[str, list[dict[str, str]]] = {}
    for ap in artifact_paths:
        p = (ap / "structural-artifact.json").resolve()
        if not p.is_file():
            continue
        structural = read_json(p)
        repo = str(structural.get("repo_name", ""))
        for node in structural.get("code_nodes", []):
            sid = str(node.get("scip_id", ""))
            if not sid:
                continue
            symbols.setdefault(sid, []).append({"repo_name": repo, "node_id": sid})
    return {
        "version": 1,
        "artifact_count": len(artifact_paths),
        "symbol_count": len(symbols),
        "symbols": symbols,
    }


def load_symbol_index(path: Path) -> dict[str, list[dict[str, str]]]:
    data = read_json(path)
    if not isinstance(data, dict):
        return {}
    s = data.get("symbols", data) if "symbols" in data else data
    if not isinstance(s, dict):
        return {}
    out: dict[str, list[dict[str, str]]] = {}
    for k, v in s.items():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "node_id" in v[0]:
            out[str(k)] = v  # type: ignore[assignment]
    return out


def save_symbol_index(path: Path, index: dict[str, Any]) -> None:
    write_json(path, index)


def resolve_cross_repo_target(
    symbol: str,
    local_repo: str,
    _local_node_id: str | None,
    global_index: dict[str, list[dict[str, str]]] | None,
) -> tuple[str | None, str | None]:
    """Return (target_node_id, target_repo) for the same symbol id in a different ``repo_name``."""
    if not global_index or not symbol:
        return None, None
    entries = global_index.get(symbol) or global_index.get(symbol.strip())
    if not entries:
        return None, None
    for ent in entries:
        rrepo = str(ent.get("repo_name", ""))
        rid = str(ent.get("node_id", ""))
        if rrepo and rrepo != local_repo and rid:
            return rid, rrepo
    return None, None
