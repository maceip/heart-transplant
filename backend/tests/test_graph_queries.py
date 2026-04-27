from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Generator
from typing import Any

import pytest
from surrealdb import Surreal  # type: ignore[import-not-found]

from heart_transplant.blast_radius import compute_impact_subgraph
from heart_transplant.db import graph_queries as gq
from heart_transplant.db.schema import apply_schema
from heart_transplant.db.surreal_loader import load_artifact
from heart_transplant.ingest.treesitter_ingest import ingest_repository


@pytest.fixture()
def mem_db() -> Generator[Any, None, None]:
    with Surreal("mem://") as db:
        db.use("gqtest", "g1")
        apply_schema(db)
        yield db


def test_get_node_and_neighbors_with_passed_db(tmp_path: Path, mem_db: Any) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "a.ts").write_text("export function secretAuth() { return 1; }\n", encoding="utf-8")
    a = ingest_repository(repo, "gq/repo")
    d = a.model_dump(mode="json")
    ad = tmp_path / "art"
    ad.mkdir()
    (ad / "structural-artifact.json").write_text(json.dumps(d), encoding="utf-8")
    load_artifact(ad, db=mem_db)
    nid = a.code_nodes[0].scip_id
    row = gq.get_code_node(nid, db=mem_db)
    assert row is not None
    nbr = gq.get_neighbors(nid, db=mem_db)
    assert nbr["node_id"] == nid
    assert nbr["edge_count"] == len(nbr["edges"])


def test_impact_subgraph_includes_start(tmp_path: Path, mem_db: Any) -> None:
    repo = tmp_path / "r2"
    repo.mkdir()
    (repo / "a.ts").write_text("export function otherAuth() { return 2; }\n", encoding="utf-8")
    a = ingest_repository(repo, "gq/repo2")
    ad = tmp_path / "art2"
    ad.mkdir()
    (ad / "structural-artifact.json").write_text(json.dumps(a.model_dump(mode="json")), encoding="utf-8")
    load_artifact(ad, db=mem_db)
    nid = a.code_nodes[0].scip_id
    r = compute_impact_subgraph(nid, max_depth=2, max_nodes=50, db=mem_db)
    assert r["node_count"] >= 1
    assert nid in r["nodes"]


def test_mcp_module_imports() -> None:
    from heart_transplant import mcp_server

    assert getattr(mcp_server.mcp, "name", "heart-transplant") == "heart-transplant"
