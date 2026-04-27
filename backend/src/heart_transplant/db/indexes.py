from __future__ import annotations

from typing import Any

from heart_transplant.db.connection import connect_surreal

# Versioned with SCHEMA_VERSION in schema.py — document here for the roadmap.
INDEX_STATEMENTS: list[str] = [
    "DEFINE INDEX IF NOT EXISTS idx_code_node_id ON TABLE ht_code FIELDS node_id",
    "DEFINE INDEX IF NOT EXISTS idx_code_scip ON TABLE ht_code FIELDS scip_id",
    "DEFINE INDEX IF NOT EXISTS idx_code_repo ON TABLE ht_code FIELDS repo_name",
    "DEFINE INDEX IF NOT EXISTS idx_edge_type ON TABLE ht_edge FIELDS edge_type",
    "DEFINE INDEX IF NOT EXISTS idx_edge_repo ON TABLE ht_edge FIELDS repo_name",
    "DEFINE INDEX IF NOT EXISTS idx_block_assign_block ON TABLE ht_block_assign FIELDS primary_block",
    "DEFINE INDEX IF NOT EXISTS idx_file_repo ON TABLE ht_file FIELDS repo_name",
    "DEFINE INDEX IF NOT EXISTS idx_ba_conf ON TABLE ht_block_assign FIELDS confidence",
    "DEFINE INDEX IF NOT EXISTS idx_temporal_repo ON TABLE ht_temporal FIELDS repo_path",
    "DEFINE INDEX IF NOT EXISTS idx_temporal_commit ON TABLE ht_temporal FIELDS commit_sha",
    "DEFINE INDEX IF NOT EXISTS idx_temporal_kind ON TABLE ht_temporal FIELDS record_kind",
]


def apply_indexes(db: Any | None = None) -> None:
    if db is None:
        db = connect_surreal()
    for stmt in INDEX_STATEMENTS:
        db.query(stmt)
