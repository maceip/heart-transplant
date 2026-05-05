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


def test_walk_source_files_skips_pytest_tmp_and_artifact_caches(tmp_path: Path) -> None:
    repo_dir = tmp_path / "sample-repo"
    repo_dir.mkdir()
    (repo_dir / "keep.py").write_text("def keep_me():\n    return True\n", encoding="utf-8")
    pytest_tmp = repo_dir / ".pytest_tmp" / "fixture"
    pytest_tmp.mkdir(parents=True)
    (pytest_tmp / "fixture.py").write_text("def fixture():\n    return None\n", encoding="utf-8")
    artifacts = repo_dir / ".heart-transplant" / "artifacts" / "stamp"
    artifacts.mkdir(parents=True)
    (artifacts / "leftover.ts").write_text("export const x = 1;\n", encoding="utf-8")

    discovered = {path.relative_to(repo_dir).as_posix() for path in walk_source_files(repo_dir)}

    assert discovered == {"keep.py"}


def test_ingest_repository_handles_deep_parse_trees_without_recursion(tmp_path: Path) -> None:
    repo_dir = tmp_path / "deep-repo"
    repo_dir.mkdir()
    nested = "value"
    for _ in range(1600):
        nested = f"({nested})"
    (repo_dir / "deep.ts").write_text(
        f"export function deeplyNested() {{ return {nested}; }}\n",
        encoding="utf-8",
    )

    artifact = ingest_repository(repo_dir, "deep-repo")

    assert any(node.name == "deeplyNested" for node in artifact.code_nodes)


def test_ingest_repository_extracts_java_nodes(tmp_path: Path) -> None:
    repo_dir = tmp_path / "java-repo"
    repo_dir.mkdir()
    (repo_dir / "App.java").write_text(
        "public class App { public void run() {} }\n",
        encoding="utf-8",
    )

    artifact = ingest_repository(repo_dir, "java-repo")

    names = {node.name for node in artifact.code_nodes}
    assert {"App.java", "App", "run"} <= names
    assert "java" in artifact.parser_backends


def test_ingest_repository_extracts_rust_nodes(tmp_path: Path) -> None:
    repo_dir = tmp_path / "rust-repo"
    repo_dir.mkdir()
    (repo_dir / "lib.rs").write_text(
        "pub trait Store {}\npub struct DiskStore;\npub fn sync() {}\n",
        encoding="utf-8",
    )

    artifact = ingest_repository(repo_dir, "rust-repo")

    names = {node.name for node in artifact.code_nodes}
    assert {"lib.rs", "Store", "DiskStore", "sync"} <= names
    assert "rust" in artifact.parser_backends


def test_ingest_repository_extracts_cpp_nodes(tmp_path: Path) -> None:
    repo_dir = tmp_path / "cpp-repo"
    repo_dir.mkdir()
    (repo_dir / "engine.cpp").write_text(
        "class Engine {};\nint boot() { return 0; }\n",
        encoding="utf-8",
    )

    artifact = ingest_repository(repo_dir, "cpp-repo")

    names = {node.name for node in artifact.code_nodes}
    assert {"engine.cpp", "Engine", "boot"} <= names
    assert "cpp" in artifact.parser_backends

