from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json
from heart_transplant.db.connection import connect_surreal, rid
from heart_transplant.db.indexes import apply_indexes
from heart_transplant.db.schema import SCHEMA_VERSION, apply_schema
from heart_transplant.semantic.models import BlockAssignment


def load_artifact(
    artifact_dir: Path,
    *,
    db: Any | None = None,
    clear_repo: bool = True,
) -> dict[str, Any]:
    """Load one structural (and optional semantic) artifact. Idempotent per repo via prior delete or upsert."""
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    if db is None:
        db = connect_surreal()
    apply_schema(db)
    apply_indexes(db)

    repo = str(structural["repo_name"])
    if clear_repo:
        for table in ("ht_edge", "ht_code", "ht_file", "ht_project", "ht_block_assign", "ht_module"):
            try:
                db.query(f"DELETE {table} WHERE repo_name = $r", {"r": repo})
            except Exception:  # noqa: BLE001 — defensive across Surreal versions
                pass

    pn = structural["project_node"]
    pr = rid("ht_project", f"{repo}:{pn['node_id']}")
    db.upsert(
        pr,
        {
            "node_id": pn["node_id"],
            "name": pn["name"],
            "repo_name": repo,
            "schema_version": SCHEMA_VERSION,
        },
    )

    for fn in structural.get("file_nodes", []):
        r = rid("ht_file", f"{repo}:{fn['node_id']}")
        db.upsert(
            r,
            {
                "node_id": fn["node_id"],
                "file_path": fn["file_path"],
                "repo_name": repo,
                "language": fn.get("language"),
                "project_id": fn.get("project_id"),
            },
        )

    for cn in structural.get("code_nodes", []):
        r = rid("ht_code", str(cn.get("scip_id", cn.get("node_id", "x"))))
        n = dict(cn)
        n["node_id"] = n.get("scip_id")
        n["repo_name"] = repo
        n["schema_version"] = SCHEMA_VERSION
        db.upsert(r, n)

    for e in structural.get("edges", []):
        r = rid("ht_edge", f"{repo}|{e['source_id']}|{e['target_id']}|{e['edge_type']}")
        row = {**e, "repo_name": e.get("repo_name", repo)}
        if row.get("provenance") is None:
            row["provenance"] = "structural"
        db.upsert(r, row)

    for mod in _external_modules_from_edges(structural.get("edges", [])):
        r = rid("ht_module", mod)
        db.upsert(r, {"package_ref": mod, "repo_name": repo})

    sem = artifact_dir / "semantic-artifact.json"
    if sem.is_file():
        sa = read_json(sem)
        for ba in sa.get("block_assignments", []):
            load_block_assignments([BlockAssignment.model_validate(ba)], db=db, repo=repo, clear_repo=False)

    return {"status": "ok", "repo_name": repo, "nodes": len(structural.get("code_nodes", [])), "edges": len(structural.get("edges", []))}


def _external_modules_from_edges(edges: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for e in edges:
        if e.get("edge_type") == "IMPORTS_MODULE" and str(e.get("target_id", "")).startswith("module:"):
            out.add(str(e["target_id"]))
    return out


def load_block_assignments(
    items: list[BlockAssignment],
    *,
    db: Any | None = None,
    repo: str = "",
    clear_repo: bool = False,
) -> int:
    if not items:
        return 0
    if db is None:
        db = connect_surreal()
    apply_schema(db)
    apply_indexes(db)
    n = 0
    for ba in items:
        r = rid("ht_block_assign", f"{repo}:{ba.node_id}:{ba.primary_block}")
        rec = {
            "node_id": ba.node_id,
            "primary_block": ba.primary_block,
            "confidence": ba.confidence,
            "reasoning": ba.reasoning,
            "repo_name": repo,
            "neighbors": json.dumps(ba.supporting_neighbors),
        }
        db.upsert(r, rec)
        br = rid("ht_block", ba.primary_block)
        db.upsert(br, {"label": ba.primary_block})
        n += 1
    return n
