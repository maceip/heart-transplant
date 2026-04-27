from __future__ import annotations

from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json
from heart_transplant.db.connection import connect_surreal


def verify_artifact_in_db(artifact_dir: Path, db: Any | None = None) -> dict[str, Any]:
    """Assert counts in Surreal match the given structural artifact (same repo)."""
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    repo = str(structural["repo_name"])
    if db is None:
        db = connect_surreal()
    c_codes = _count(db, "ht_code", repo)
    c_files = _count(db, "ht_file", repo)
    c_edge = _count(db, "ht_edge", repo)
    c_project = _count(db, "ht_project", repo)
    expected_code = int(structural.get("node_count", 0) or 0)
    expected_file = len(structural.get("file_nodes", []))
    expected_e = len(structural.get("edges", []))
    ok = (
        c_codes == expected_code
        and c_files == expected_file
        and c_edge == expected_e
        and c_project >= 1
    )
    return {
        "repo_name": repo,
        "ht_code": c_codes,
        "expected_code": expected_code,
        "ht_file": c_files,
        "expected_file": expected_file,
        "ht_edge": c_edge,
        "expected_edges": expected_e,
        "ht_project_rows": c_project,
        "pass": bool(ok) and c_project >= 1,
    }


def _count(db: Any, table: str, repo: str) -> int:
    res = db.query(f"SELECT count() FROM {table} WHERE repo_name = $r GROUP ALL", {"r": repo})
    if not res:
        return 0
    if isinstance(res, list) and res and isinstance(res[0], dict):
        return int(res[0].get("count", 0))
    if isinstance(res, dict):
        return int(res.get("count", 0))
    return 0
