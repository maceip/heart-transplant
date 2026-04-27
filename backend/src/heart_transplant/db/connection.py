from __future__ import annotations

import os
from typing import Any

from surrealdb import RecordID, Surreal


def connect_surreal(url: str | None = None) -> Any:
    """Connect to SurrealDB (``mem://`` for tests, ``ws://`` / ``http://`` for real servers)."""
    u = url or os.environ.get("HEART_TRANSPLANT_SURREAL_URL", "mem://")
    db: Surreal = Surreal(u)
    db.connect()
    ns, database = (os.environ.get("HEART_TRANSPLANT_SURREAL_NS", "ht"), os.environ.get("HEART_TRANSPLANT_SURREAL_DB", "graph"))
    db.use(ns, database)
    return db


def rid(table: str, key: str) -> RecordID:
    """Short deterministic record id (SCIP and URIs are too long for raw ids)."""
    import hashlib

    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return RecordID(table, h)
