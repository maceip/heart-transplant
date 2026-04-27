from __future__ import annotations

from pathlib import Path

from heart_transplant.ingest.treesitter_ingest import ingest_repository


def test_ingest_repository_extracts_code_nodes_from_typescript(tmp_path: Path) -> None:
    repo_dir = tmp_path / "sample-repo"
    repo_dir.mkdir()
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "auth.ts").write_text(
        "export interface SessionUser { id: string }\n"
        "export class AuthService {}\n"
        "export function createSession() { return new AuthService(); }\n",
        encoding="utf-8",
    )

    artifact = ingest_repository(repo_dir, "sample-repo")

    names = {node.name for node in artifact.code_nodes}
    assert {"SessionUser", "AuthService", "createSession"} <= names
    assert artifact.node_count == len(artifact.code_nodes)
    assert artifact.edge_count == len(artifact.edges)
    assert "typescript" in artifact.parser_backends

