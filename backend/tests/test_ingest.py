from __future__ import annotations

from pathlib import Path

from heart_transplant.ingest.treesitter_ingest import ingest_repository, walk_source_files


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
    assert "auth.ts" in names
    assert any(node.kind == "file_surface" for node in artifact.code_nodes)
    assert artifact.node_count == len(artifact.code_nodes)
    assert artifact.edge_count == len(artifact.edges)
    assert "typescript" in artifact.parser_backends


def test_walk_source_files_skips_windows_virtualenv(tmp_path: Path) -> None:
    repo_dir = tmp_path / "sample-repo"
    repo_dir.mkdir()
    (repo_dir / "app.py").write_text("def keep_me():\n    return True\n", encoding="utf-8")
    venv_dir = repo_dir / ".venv-win" / "Lib" / "site-packages" / "pkg"
    venv_dir.mkdir(parents=True)
    (venv_dir / "ignored.py").write_text("def should_not_scan():\n    return False\n", encoding="utf-8")

    discovered = {path.relative_to(repo_dir).as_posix() for path in walk_source_files(repo_dir)}

    assert discovered == {"app.py"}

