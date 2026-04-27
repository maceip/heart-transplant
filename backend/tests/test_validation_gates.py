from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.validation_gates import run_validation_gates


def test_validation_gates_report_passes_and_failures(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    artifact_dir = tmp_path / "artifact"
    (repo_dir / "src").mkdir(parents=True)
    artifact_dir.mkdir()

    (repo_dir / "src" / "auth.ts").write_text(
        "export function createSession() { return token; }\n",
        encoding="utf-8",
    )

    structural = {
        "artifact_id": "sample",
        "repo_name": "acme/repo",
        "repo_path": str(repo_dir),
        "node_count": 1,
        "edge_count": 1,
        "parser_backends": ["typescript"],
        "code_nodes": [
            {
                "scip_id": "scip://acme/repo/src/auth.ts#createSession:function:1",
                "provisional_scip_id": "scip://acme/repo/src/auth.ts#createSession:function:1",
                "symbol_source": "provisional",
                "name": "createSession",
                "kind": "function",
                "file_path": "src/auth.ts",
                "range": {"start_line": 1, "start_col": 8, "end_line": 1, "end_col": 45},
                "content": "createSession() { return token; }",
                "repo_name": "acme/repo",
                "language": "typescript",
            }
        ],
        "edges": [
            {
                "source_id": "file://acme/repo/src/auth.ts",
                "target_id": "scip://acme/repo/src/auth.ts#createSession:function:1",
                "edge_type": "CONTAINS",
                "repo_name": "acme/repo",
            }
        ],
    }
    (artifact_dir / "structural-artifact.json").write_text(json.dumps(structural), encoding="utf-8")
    (artifact_dir / "index.scip").write_bytes(b"SCIP")
    (artifact_dir / "scip-index.json").write_text(
        json.dumps(
            {
                "indexer": "scip-typescript",
                "version": "0.4.0",
                "output_path": str(artifact_dir / "index.scip"),
            }
        ),
        encoding="utf-8",
    )
    (artifact_dir / "scip-consumed.json").write_text(
        json.dumps(
            {
                "resolution": {
                    "resolved_code_nodes": 0,
                    "total_code_nodes": 1,
                    "unresolved_code_nodes": 1,
                },
                "implementation_edges": [],
            }
        ),
        encoding="utf-8",
    )

    report = run_validation_gates(repo_dir, artifact_dir)

    gate_status = {gate["gate_id"]: gate["status"] for gate in report["gates"]}
    assert gate_status["structural_ingest_produces_nodes"] == "pass"
    assert gate_status["artifact_contains_expected_files"] == "pass"
    assert gate_status["graph_smoke_structure_is_consistent"] == "pass"
    assert gate_status["scip_metadata_is_real"] == "pass"
    assert gate_status["scip_actually_resolves_nodes"] == "fail"
    assert report["summary"]["overall_status"] == "fail"
