from __future__ import annotations

from pathlib import Path

from heart_transplant.ingest.neighborhoods import get_neighborhood
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.scip.path_normalization import build_file_uri, build_project_node_id


def test_ingest_spine_emits_file_project_and_imports(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "util.ts").write_text("export const n = 1;\n", encoding="utf-8")
    (repo / "src" / "app.ts").write_text("import { n } from './util';\nexport const x = () => n;\n", encoding="utf-8")

    a = ingest_repository(repo, "demo/proj")
    project_id = build_project_node_id("demo/proj")
    assert a.project_node.node_id == project_id
    assert len(a.file_nodes) == 2
    assert a.node_count > 0
    edge_types = {e.edge_type for e in a.edges}
    assert "CONTAINS" in edge_types
    assert "DEPENDS_ON_FILE" in edge_types
    futil = build_file_uri("demo/proj", "src/util.ts")
    assert futil in {fn.node_id for fn in a.file_nodes}
    n0 = a.code_nodes[0]
    nb = a.neighborhoods.get(n0.scip_id) or a.neighborhoods.get(str(n0.scip_id))
    assert nb is not None
    assert nb.file_path in {"src/app.ts", "src/util.ts"}
    has_dep = any(e.edge_type == "DEPENDS_ON_FILE" and e.target_id == futil for e in a.edges)
    assert has_dep


def test_get_neighborhood_accessor(tmp_path: Path) -> None:
    repo = tmp_path / "d"
    repo.mkdir()
    (repo / "a.ts").write_text("export function f() {}\n", encoding="utf-8")
    a = ingest_repository(repo, "demo/x")
    d = a.model_dump(mode="json")
    cid = a.code_nodes[0].scip_id
    assert get_neighborhood(d, cid) is not None


def test_ingest_promotes_top_level_variables_but_not_locals(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.ts").write_text(
        "export const envSchema = { PORT: 3000 };\n"
        "export function makeConfig() { const localValue = 1; return envSchema; }\n",
        encoding="utf-8",
    )

    artifact = ingest_repository(repo, "demo/config")
    nodes = {(node.name, node.kind.value) for node in artifact.code_nodes}

    assert ("envSchema", "config_object") in nodes
    assert ("makeConfig", "config_object") in nodes
    assert ("localValue", "variable") not in nodes


def test_ingest_stamps_architectural_seams_without_locals(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "services").mkdir(parents=True)
    (repo / "src" / "middleware").mkdir(parents=True)
    (repo / "src" / "hooks").mkdir(parents=True)
    (repo / "prisma").mkdir()
    (repo / "src" / "hooks" / "useSession.ts").write_text(
        "export const useSession = () => ({ user: null });\n",
        encoding="utf-8",
    )
    (repo / "src" / "middleware" / "auth.ts").write_text(
        "export function authGuard() { return true; }\n",
        encoding="utf-8",
    )
    (repo / "src" / "services" / "profile.ts").write_text(
        "export class ProfileService { list() { return []; } }\n",
        encoding="utf-8",
    )
    (repo / "config.ts").write_text(
        "export const appConfig = { databaseUrl: process.env.DATABASE_URL };\n",
        encoding="utf-8",
    )
    (repo / "prisma" / "schema.prisma").write_text(
        "model Profile {\n  id String @id\n  name String\n}\n",
        encoding="utf-8",
    )

    artifact = ingest_repository(repo, "demo/seams")
    nodes = {(node.name, node.kind.value) for node in artifact.code_nodes}

    assert ("useSession", "react_hook") in nodes
    assert ("authGuard", "middleware") in nodes
    assert ("ProfileService", "service_boundary") in nodes
    assert ("appConfig", "config_object") in nodes
    assert ("Profile", "db_model") in nodes
