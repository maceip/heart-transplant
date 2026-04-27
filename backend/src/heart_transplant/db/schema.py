from __future__ import annotations

from typing import Any

from heart_transplant.db import connection as _conn
from heart_transplant.db.connection import connect_surreal

SCHEMA_VERSION = 1

SCHEMA_STATEMENTS: list[str] = [
    f"DEFINE TABLE IF NOT EXISTS ht_meta TYPE ANY SCHEMALESS PERMISSIONS FULL",
    f"DEFINE TABLE IF NOT EXISTS ht_project TYPE ANY SCHEMALESS PERMISSIONS FULL",
    f"DEFINE TABLE IF NOT EXISTS ht_file TYPE ANY SCHEMALESS PERMISSIONS FULL",
    f"DEFINE TABLE IF NOT EXISTS ht_code TYPE ANY SCHEMALESS PERMISSIONS FULL",
    f"DEFINE TABLE IF NOT EXISTS ht_module TYPE ANY SCHEMALESS PERMISSIONS FULL",
    f"DEFINE TABLE IF NOT EXISTS ht_block TYPE ANY SCHEMALESS PERMISSIONS FULL",
    f"DEFINE TABLE IF NOT EXISTS ht_block_assign TYPE ANY SCHEMALESS PERMISSIONS FULL",
    f"DEFINE TABLE IF NOT EXISTS ht_edge TYPE ANY SCHEMALESS PERMISSIONS FULL",
    f"DEFINE TABLE IF NOT EXISTS ht_temporal TYPE ANY SCHEMALESS PERMISSIONS FULL",
]


def apply_schema(db: Any | None = None) -> None:
    if db is None:
        db = connect_surreal()
    for stmt in SCHEMA_STATEMENTS:
        db.query(stmt)
    meta = _conn.rid("ht_meta", "schema")
    db.upsert(meta, {"version": SCHEMA_VERSION, "name": "heart_transplant", "indexing": "see apply_indexes()"})
