from __future__ import annotations

from collections import deque
from typing import Any, Literal

from heart_transplant.db.connection import connect_surreal
from heart_transplant.db.queries import assignments_for_block

# Edges the roadmap treats as “symbol-ish” for tracing; structural CONTAINS etc. are excluded.
_TRACE_EDGE_TYPES: frozenset[str] = frozenset(
    {
        "REFERENCES",
        "CALLS",
        "CROSS_REFERENCE",
        "DEFINES",
        "IMPLEMENTS",
    }
)


def _rows(raw: Any) -> list[dict[str, Any]]:
    """Normalize Surreal Python ``query`` results to a list of record dicts."""
    if raw is None:
        return []
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, list):
            return [r for r in first if isinstance(r, dict)]
        if isinstance(first, dict):
            return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def get_code_node(node_id: str, *, db: Any | None = None) -> dict[str, Any] | None:
    """Return one ``ht_code`` row for ``scip_id`` / ``node_id``."""
    if not node_id:
        return None
    if db is None:
        db = connect_surreal()
    raw = db.query(
        "SELECT * FROM ht_code WHERE scip_id = $n OR node_id = $n LIMIT 1",
        {"n": node_id},
    )
    rows = _rows(raw)
    return rows[0] if rows else None


def get_neighbors(
    node_id: str,
    *,
    direction: Literal["out", "in", "both"] = "both",
    limit: int = 200,
    db: Any | None = None,
) -> dict[str, Any]:
    """Return incident ``ht_edge`` rows for a code (or other) id, capped."""
    if db is None:
        db = connect_surreal()
    lim = max(1, min(int(limit), 10_000))
    out: list[dict[str, Any]] = []
    if direction in ("out", "both"):
        r = db.query(
            f"SELECT * FROM ht_edge WHERE source_id = $n LIMIT {lim}",
            {"n": node_id},
        )
        out.extend(_rows(r))
    if direction in ("in", "both"):
        r = db.query(
            f"SELECT * FROM ht_edge WHERE target_id = $n LIMIT {lim}",
            {"n": node_id},
        )
        out.extend(_rows(r))
    return {"node_id": node_id, "direction": direction, "edges": out, "edge_count": len(out)}


def trace_symbol_path(
    start_id: str,
    end_id: str | None = None,
    *,
    max_depth: int = 8,
    db: Any | None = None,
) -> dict[str, Any]:
    """BFS over symbol-ish edges; optional target stops early and returns a node-id path."""
    if db is None:
        db = connect_surreal()
    depth_limit = max(1, min(int(max_depth), 64))
    visited: set[str] = {start_id}
    parent: dict[str, str | None] = {start_id: None}
    q: deque[tuple[str, int]] = deque([(start_id, 0)])
    found: str | None = None

    while q:
        cur, d = q.popleft()
        if end_id and cur == end_id:
            found = cur
            break
        if d >= depth_limit:
            continue
        nbrs = _symbol_neighbors(cur, db)
        for nxt in nbrs:
            if nxt in visited:
                continue
            visited.add(nxt)
            parent[nxt] = cur
            q.append((nxt, d + 1))
            if end_id and nxt == end_id:
                found = nxt
                break
        if found:
            break

    if end_id and found:
        path: list[str] = []
        x: str | None = end_id
        while x is not None:
            path.append(x)
            x = parent.get(x)  # type: ignore[assignment]
        path.reverse()
        return {"start_id": start_id, "end_id": end_id, "found": True, "path": path, "visited_count": len(visited)}

    return {
        "start_id": start_id,
        "end_id": end_id,
        "found": bool(found),
        "visited": sorted(visited)[:500],
        "visited_count": len(visited),
    }


def _symbol_neighbors(node_id: str, db: Any) -> list[str]:
    out: set[str] = set()
    for field_from, field_to in (("source_id", "target_id"), ("target_id", "source_id")):
        r = db.query(
            f"SELECT * FROM ht_edge WHERE {field_from} = $n",
            {"n": node_id},
        )
        for row in _rows(r):
            et = str(row.get("edge_type", ""))
            if et not in _TRACE_EDGE_TYPES:
                continue
            other = row.get(field_to)
            if other and isinstance(other, str):
                out.add(other)
    return list(out)


def find_block_nodes(
    block_label: str,
    *,
    min_confidence: float = 0.0,
    with_code: bool = True,
    limit: int = 200,
    db: Any | None = None,
) -> dict[str, Any]:
    """Block assignments, optionally with joined ``ht_code`` rows (capped)."""
    if db is None:
        db = connect_surreal()
    assigns = assignments_for_block(block_label, min_confidence=min_confidence, db=db)
    cap = max(1, min(int(limit), 5_000))
    rows: list[dict[str, Any]] = []
    for a in assigns[:cap]:
        nid = str(a.get("node_id", ""))
        if not nid:
            continue
        row: dict[str, Any] = dict(a)
        if with_code:
            c = get_code_node(nid, db=db)
            row["code"] = c
        rows.append(row)
    return {
        "block_label": block_label,
        "min_confidence": min_confidence,
        "assignments": rows,
        "returned": len(rows),
    }


def edge_incident_count(node_id: str, *, repo_name: str | None = None, db: Any | None = None) -> int:
    """Count all edges touching ``node_id`` (for pruning high-degree nodes)."""
    if db is None:
        db = connect_surreal()
    if repo_name:
        q1 = db.query(
            "SELECT count() FROM ht_edge WHERE repo_name = $r AND source_id = $n GROUP ALL",
            {"r": repo_name, "n": node_id},
        )
        q2 = db.query(
            "SELECT count() FROM ht_edge WHERE repo_name = $r AND target_id = $n GROUP ALL",
            {"r": repo_name, "n": node_id},
        )
    else:
        q1 = db.query("SELECT count() FROM ht_edge WHERE source_id = $n GROUP ALL", {"n": node_id})
        q2 = db.query("SELECT count() FROM ht_edge WHERE target_id = $n GROUP ALL", {"n": node_id})
    c1 = _count_value(q1)
    c2 = _count_value(q2)
    return c1 + c2


def _count_value(q: Any) -> int:
    raw = _rows(q)
    if raw and "count" in raw[0]:
        return int(raw[0].get("count", 0) or 0)
    if isinstance(q, list) and q and isinstance(q[0], dict) and "count" in q[0]:
        return int(q[0].get("count", 0) or 0)
    return 0
