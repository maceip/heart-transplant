from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.generated import scip_pb2
from heart_transplant.scip_consume import consume_scip_artifact
from heart_transplant.scip.path_normalization import build_file_uri, build_provisional_symbol_uri


def test_consume_scip_resolves_provisional_code_node_ids(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifact"
    repo_dir = tmp_path / "repo"
    artifact_dir.mkdir()
    (repo_dir / "src").mkdir(parents=True)
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
                "scip_id": build_provisional_symbol_uri("acme/repo", "src/auth.ts", "createSession", "function", 1),
                "provisional_scip_id": build_provisional_symbol_uri("acme/repo", "src/auth.ts", "createSession", "function", 1),
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
                "source_id": build_file_uri("acme/repo", "src/auth.ts"),
                "target_id": build_provisional_symbol_uri("acme/repo", "src/auth.ts", "createSession", "function", 1),
                "edge_type": "CONTAINS",
                "repo_name": "acme/repo",
            }
        ],
    }
    (artifact_dir / "structural-artifact.json").write_text(json.dumps(structural), encoding="utf-8")

    index = scip_pb2.Index()
    index.metadata.project_root = str(repo_dir)
    index.metadata.tool_info.name = "scip-typescript"
    index.metadata.tool_info.version = "0.4.0"
    document = index.documents.add()
    document.language = "typescript"
    document.relative_path = "src/auth.ts"
    document.position_encoding = scip_pb2.UTF16CodeUnitOffsetFromLineStart

    occurrence = document.occurrences.add()
    occurrence.range.extend([0, 16, 29])
    occurrence.symbol = "scip-typescript npm sample 1.0.0 createSession()."
    occurrence.symbol_roles = int(scip_pb2.SymbolRole.Value("Definition"))

    symbol = document.symbols.add()
    symbol.symbol = "scip-typescript npm sample 1.0.0 createSession()."
    symbol.display_name = "createSession"
    symbol.kind = scip_pb2.SymbolInformation.Kind.Function

    (artifact_dir / "index.scip").write_bytes(index.SerializeToString())

    report = consume_scip_artifact(artifact_dir)

    updated = json.loads((artifact_dir / "structural-artifact.json").read_text(encoding="utf-8"))
    node = updated["code_nodes"][0]
    assert node["symbol_source"] == "scip"
    assert node["scip_id"] == "scip-typescript npm sample 1.0.0 createSession()."
    assert report["resolution"]["resolved_code_nodes"] == 1
    assert any(edge["edge_type"] == "DEFINES" for edge in updated["edges"])
    assert any(edge["target_id"] == "scip-typescript npm sample 1.0.0 createSession()." for edge in updated["edges"])


def test_consume_scip_normalizes_windows_paths_and_logs_orphans(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifact"
    repo_dir = tmp_path / "repo"
    artifact_dir.mkdir()
    (repo_dir / "src").mkdir(parents=True)
    (repo_dir / "src" / "auth.ts").write_text(
        "export function createSession() { return token; }\nexport function makeToken() { return 'x'; }\n",
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
                "scip_id": build_provisional_symbol_uri("acme/repo", "src/auth.ts", "createSession", "function", 1),
                "provisional_scip_id": build_provisional_symbol_uri("acme/repo", "src/auth.ts", "createSession", "function", 1),
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
                "source_id": build_file_uri("acme/repo", "src/auth.ts"),
                "target_id": build_provisional_symbol_uri("acme/repo", "src/auth.ts", "createSession", "function", 1),
                "edge_type": "CONTAINS",
                "repo_name": "acme/repo",
            }
        ],
    }
    (artifact_dir / "structural-artifact.json").write_text(json.dumps(structural), encoding="utf-8")

    index = scip_pb2.Index()
    index.metadata.project_root = str(repo_dir)
    index.metadata.tool_info.name = "scip-typescript"
    index.metadata.tool_info.version = "0.4.0"
    document = index.documents.add()
    document.language = "typescript"
    document.relative_path = "src\\auth.ts"
    document.position_encoding = scip_pb2.UTF16CodeUnitOffsetFromLineStart

    first_occurrence = document.occurrences.add()
    first_occurrence.range.extend([0, 16, 29])
    first_occurrence.symbol = "scip-typescript npm sample 1.0.0 createSession()."
    first_occurrence.symbol_roles = int(scip_pb2.SymbolRole.Value("Definition"))

    first_symbol = document.symbols.add()
    first_symbol.symbol = "scip-typescript npm sample 1.0.0 createSession()."
    first_symbol.display_name = "createSession"
    first_symbol.kind = scip_pb2.SymbolInformation.Kind.Function

    orphan_occurrence = document.occurrences.add()
    orphan_occurrence.range.extend([1, 16, 25])
    orphan_occurrence.symbol = "scip-typescript npm sample 1.0.0 makeToken()."
    orphan_occurrence.symbol_roles = int(scip_pb2.SymbolRole.Value("Definition"))

    orphan_symbol = document.symbols.add()
    orphan_symbol.symbol = "scip-typescript npm sample 1.0.0 makeToken()."
    orphan_symbol.display_name = "makeToken"
    orphan_symbol.kind = scip_pb2.SymbolInformation.Kind.Function

    (artifact_dir / "index.scip").write_bytes(index.SerializeToString())

    report = consume_scip_artifact(artifact_dir)

    updated = json.loads((artifact_dir / "structural-artifact.json").read_text(encoding="utf-8"))
    orphaned = json.loads((artifact_dir / "orphaned-symbols.json").read_text(encoding="utf-8"))
    node = updated["code_nodes"][0]

    assert node["symbol_source"] == "scip"
    assert report["resolution"]["resolved_code_nodes"] == 1
    assert report["addressable_orphaned_symbol_count"] == 1
    assert report["orphaned_symbol_count"] == 1
    assert orphaned[0]["display_name"] == "makeToken"
    assert orphaned[0]["kind"] == "Function"
