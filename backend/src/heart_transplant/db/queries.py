from __future__ import annotations

from typing import Any

from heart_transplant.db.connection import connect_surreal


def assignments_for_block(
    block_label: str,
    *,
    min_confidence: float = 0.0,
    db: Any | None = None,
) -> list[dict[str, Any]]:
    """Which code node ids (``node_id``) are classified to this **primary_block**?"""
    if db is None:
        db = connect_surreal()
    res = db.query(
        "SELECT * FROM ht_block_assign WHERE primary_block = $b AND confidence >= $c",
        {"b": block_label, "c": min_confidence},
    )
    return res if isinstance(res, list) else []


def file_paths_for_block(
    block_label: str,
    *,
    min_confidence: float = 0.5,
    db: Any | None = None,
) -> list[str]:
    """Distinct ``file_path`` for code under ``ht_code`` with a high-confidence block assignment."""
    if db is None:
        db = connect_surreal()
    a = assignments_for_block(block_label, min_confidence=min_confidence, db=db)
    out: set[str] = set()
    for row in a:
        nid = str(row.get("node_id", ""))
        if not nid:
            continue
        c = db.query("SELECT file_path FROM ht_code WHERE scip_id = $n OR node_id = $n LIMIT 1", {"n": nid})
        if c and isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get("file_path"):
            out.add(str(c[0]["file_path"]))
    return sorted(out)
