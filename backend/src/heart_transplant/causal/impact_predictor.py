from __future__ import annotations

import re
from pathlib import Path

from heart_transplant.artifact_store import read_json
from heart_transplant.models import CodeNode, StructuralArtifact
from heart_transplant.temporal.models import TemporalScanReport


def load_semantic_artifact(artifact_dir: Path) -> dict | None:
    p = artifact_dir / "semantic-artifact.json"
    if not p.is_file():
        return None
    data = read_json(p)
    return data if isinstance(data, dict) else None


def infer_blocks_from_change_tokens(tokens: set[str]) -> set[str]:
    """Map free-text tokens to 24-block labels (heuristic, no LLM)."""
    out: set[str] = set()
    t = " ".join(tokens).lower()
    if any(x in t for x in ("auth", "jwt", "session", "login", "bearer", "oauth")):
        out.add("Access Control")
    if any(x in t for x in ("database", "prisma", "drizzle", "sql", "persist", "repository")):
        out.add("Data Persistence")
    if any(x in t for x in ("route", "router", "api", "handler", "middleware", "endpoint")):
        out.add("Traffic Control")
        out.add("Network Edge")
    if any(x in t for x in ("log", "telemetry", "metric", "trace")):
        out.add("System Telemetry")
    if any(x in t for x in ("render", "react", "ui", "component")):
        out.add("Core Rendering")
    return out


def _assignments_map(semantic: dict | None) -> dict[str, str]:
    if not semantic:
        return {}
    m: dict[str, str] = {}
    for row in semantic.get("block_assignments", []) or []:
        nid = str(row.get("node_id", ""))
        blk = str(row.get("primary_block", ""))
        if nid and blk:
            m[nid] = blk
    return m


def load_temporal_scan(path: Path | None) -> TemporalScanReport | None:
    if path is None or not path.is_file():
        return None
    data = read_json(path)
    return TemporalScanReport.model_validate(data)


def tokenize_change(text: str) -> set[str]:
    parts = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    extra: set[str] = set()
    for p in parts:
        if len(p) >= 3:
            extra.add(p)
    for phrase in ("auth", "database", "route", "api", "middleware", "logger", "prisma", "supabase"):
        if phrase in text.lower():
            extra.add(phrase)
    return extra


def score_node(node: CodeNode, tokens: set[str], hotspot_files: set[str]) -> float:
    hay = f"{node.name} {node.file_path}".lower()
    score = sum(1.6 for t in tokens if t in hay)
    if node.file_path in hotspot_files:
        score += 1.0
    return score


def select_seed_nodes(
    change: str,
    artifact: StructuralArtifact,
    temporal: TemporalScanReport | None,
    semantic: dict | None = None,
    *,
    max_seeds: int = 6,
) -> tuple[list[str], list[str]]:
    """Return (seed_scip_ids, limitation_notes)."""
    notes: list[str] = []
    tokens = tokenize_change(change)
    if not tokens:
        notes.append("Change text yielded no tokens; using degree-based fallback seeds.")
    hotspots: set[str] = set()
    if temporal:
        for path, _ in sorted(temporal.file_hotspots.items(), key=lambda x: -x[1])[:25]:
            hotspots.add(path)

    inferred_blocks = infer_blocks_from_change_tokens(tokens)
    block_map = _assignments_map(semantic)

    scored: list[tuple[float, str]] = []
    for node in artifact.code_nodes:
        s = score_node(node, tokens, hotspots)
        blk = block_map.get(node.scip_id)
        if blk and blk in inferred_blocks:
            s += 2.4
        if s > 0:
            scored.append((s, node.scip_id))
    scored.sort(key=lambda x: -x[0])
    seeds = [sid for _, sid in scored[:max_seeds]]
    if not seeds:
        by_deg: dict[str, int] = {}
        for e in artifact.edges:
            by_deg[e.source_id] = by_deg.get(e.source_id, 0) + 1
            by_deg[e.target_id] = by_deg.get(e.target_id, 0) + 1
        for node in sorted(artifact.code_nodes, key=lambda n: -by_deg.get(n.scip_id, 0))[:max_seeds]:
            seeds.append(node.scip_id)
        notes.append("Fallback seeds: highest structural degree among code nodes.")
    return seeds, notes
