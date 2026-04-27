from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.graph_smoke import run_graph_smoke


def test_graph_smoke_reports_structure_and_scip_presence(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    (artifact_dir / "index.scip").write_bytes(b"SCIP")
    (artifact_dir / "scip-index.json").write_text('{"indexer":"scip-typescript"}', encoding="utf-8")
    (artifact_dir / "structural-artifact.json").write_text(
        json.dumps(
            {
                "repo_name": "acme/repo",
                "node_count": 2,
                "edge_count": 2,
                "code_nodes": [
                    {
                        "scip_id": "scip://acme/repo/src/auth.ts#createSession:function:1",
                        "name": "createSession",
                        "kind": "function",
                        "file_path": "src/auth.ts",
                        "content": "function createSession() { return token; }",
                    },
                    {
                        "scip_id": "scip://acme/repo/src/db.ts#seed:function:4",
                        "name": "seed",
                        "kind": "function",
                        "file_path": "src/db.ts",
                        "content": "function seed() { return prisma.user.create(); }",
                    },
                ],
                "edges": [
                    {"source_id": "file://acme/repo/src/auth.ts", "target_id": "scip://acme/repo/src/auth.ts#createSession:function:1", "edge_type": "CONTAINS", "repo_name": "acme/repo"},
                    {"source_id": "file://acme/repo/src/db.ts", "target_id": "scip://acme/repo/src/db.ts#seed:function:4", "edge_type": "CONTAINS", "repo_name": "acme/repo"},
                ],
            }
        ),
        encoding="utf-8",
    )

    report = run_graph_smoke(artifact_dir)

    assert report["node_count"] == 2
    assert report["contains_edge_count"] == 2
    assert report["scip_present"] is True
    assert report["scip_metadata_present"] is True
    assert report["missing_containment"] == []
    assert report["auth_nodes"]
    assert report["data_nodes"]

