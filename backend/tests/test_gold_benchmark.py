from __future__ import annotations

import json
from pathlib import Path

import pytest

from heart_transplant.evals.build_gold import build_gold_from_ground_truth
from heart_transplant.evals.gold_benchmark import build_block_benchmark_report, run_benchmark
from heart_transplant.ingest.treesitter_ingest import ingest_repository


def test_gold_benchmark_runs_against_ingest(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "x.ts").write_text("export function sessionGuard() { return 'ok'; }\n", encoding="utf-8")
    a = ingest_repository(repo, "test/gold")
    d = a.model_dump(mode="json")
    nid = a.code_nodes[0].scip_id
    gold = [{"node_id": nid, "expected_block": "Access Control"}]
    r = run_benchmark(d, gold)
    assert r["total"] == 1
    assert 0.0 <= r["accuracy"] <= 1.0
    assert "classified" in r["rows"][0]


def test_block_benchmark_report_exposes_coverage_and_confusion(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return 'ok'; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/block-report")

    report = build_block_benchmark_report(
        artifact.model_dump(mode="json"),
        [
            {"file_path": "auth.ts", "expected_block": "Access Control"},
            {"file_path": "missing.ts", "expected_block": "Network Edge"},
        ],
    )

    assert report["summary"]["end_to_end_accuracy"] == 0.5
    assert report["summary"]["scorable_accuracy"] == 1.0
    assert report["summary"]["missing_node_rate"] == 0.5
    assert report["per_block"]["Access Control"]["correct"] == 1
    assert report["confusion"]["Network Edge"]["__missing_node__"] == 1


def test_gold_benchmark_supports_file_path_items(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return 'ok'; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/file-gold")
    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [{"file_path": "auth.ts", "expected_block": "Access Control"}],
    )

    assert report["total"] == 1
    assert report["rows"][0]["match"] is True


def test_gold_benchmark_uses_file_surface_when_file_has_no_symbols(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "index.ts").write_text("export * from './missing';\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/file-surface-gold")

    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [{"file_path": "src/index.ts", "expected_block": "Search Architecture"}],
    )

    assert report["total"] == 1
    assert report["rows"][0]["match"] is True
    assert any(row["node_id"] == "codefile:src/index.ts" for row in report["rows"][0]["classified"])


def test_gold_benchmark_counts_secondary_block_matches(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "src").mkdir()
    (repo / "src" / "config").mkdir()
    (repo / "src" / "config" / "index.ts").write_text(
        "export const envConfig = { DATABASE_URL: 'postgres://x', redis: true };\n",
        encoding="utf-8",
    )
    artifact = ingest_repository(repo, "test/multilabel")

    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [{"file_path": "src/config/index.ts", "expected_block": "Data Persistence"}],
    )

    assert report["rows"][0]["match"] is True


def test_build_gold_from_ground_truth_uses_high_confidence_file_blocks(tmp_path: Path) -> None:
    gt = tmp_path / "ground.json"
    gt.write_text(
        """
        [
          {
            "repoName": "demo",
            "topFileBlocks": [
              {"filePath": "package.json", "blockId": "data_persistence", "confidence": "high"},
              {"filePath": "src/auth.ts", "blockId": "access_control", "confidence": "high"},
              {"filePath": "src/db.ts", "blockId": "data_persistence", "confidence": "low"}
            ]
          }
        ]
        """,
        encoding="utf-8",
    )

    items = build_gold_from_ground_truth(gt, repo_name="demo", min_items=1)

    assert items == [
        {
            "id": "demo:src/auth.ts:access_control",
            "repo_name": "demo",
            "file_path": "src/auth.ts",
            "expected_block": "Access Control",
            "confidence": "high",
            "source": str(gt),
        }
    ]


def test_build_gold_excludes_named_repos(tmp_path: Path) -> None:
    gt = tmp_path / "ground.json"
    gt.write_text(
        """
        [
          {
            "repoName": "repo-a",
            "topFileBlocks": [
              {"filePath": "a.ts", "blockId": "access_control", "confidence": "high"}
            ]
          },
          {
            "repoName": "repo-b",
            "topFileBlocks": [
              {"filePath": "b.ts", "blockId": "network_edge", "confidence": "high"}
            ]
          }
        ]
        """,
        encoding="utf-8",
    )

    items = build_gold_from_ground_truth(gt, max_items=10, exclude_repo_names=frozenset({"repo-b"}))

    assert [item["repo_name"] for item in items] == ["repo-a"]


def test_build_gold_round_robins_across_repos_when_expanding(tmp_path: Path) -> None:
    gt = tmp_path / "ground.json"
    gt.write_text(
        """
        [
          {
            "repoName": "repo-a",
            "topFileBlocks": [
              {"filePath": "src/auth.ts", "blockId": "access_control", "confidence": "high"},
              {"filePath": "src/db.ts", "blockId": "data_persistence", "confidence": "medium"}
            ]
          },
          {
            "repoName": "repo-b",
            "topFileBlocks": [
              {"filePath": "src/server.ts", "blockId": "network_edge", "confidence": "medium"}
            ]
          }
        ]
        """,
        encoding="utf-8",
    )

    items = build_gold_from_ground_truth(gt, include_medium=True, min_items=1, max_items=3)

    assert [item["repo_name"] for item in items] == ["repo-a", "repo-b", "repo-a"]


def test_gold_benchmark_filters_rows_by_artifact_repo(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return 'ok'; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "vendor/current-repo")

    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [
            {"repo_name": "current-repo", "file_path": "auth.ts", "expected_block": "Access Control"},
            {"repo_name": "other-repo", "file_path": "auth.ts", "expected_block": "Data Persistence"},
        ],
    )

    assert report["input_total"] == 2
    assert report["total"] == 1
    assert report["skipped_repo_scope"] == 1
    assert report["rows"][0]["match"] is True


def test_gold_benchmark_catches_architectural_understanding_for_prisma_config(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "prisma.config.ts").write_text(
        "import { defineConfig, env } from '@prisma/config';\n"
        "export default defineConfig({ datasource: { url: env('DATABASE_URL') } });\n",
        encoding="utf-8",
    )
    artifact = ingest_repository(repo, "test/prisma-gold")

    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [{"file_path": "prisma.config.ts", "expected_block": "Data Persistence"}],
    )

    assert report["rows"][0]["match"] is True


def test_gold_benchmark_catches_architectural_index_files(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / "src" / "config").mkdir(parents=True)
    (repo / "src" / "config" / "index.ts").write_text(
        "export const appConfig = { port: 3000, workers: 4 };\n",
        encoding="utf-8",
    )
    (repo / "src" / "index.ts").write_text(
        "import { appConfig } from './config/index';\n"
        "export const workers = appConfig.workers;\n"
        "export const port = appConfig.port;\n",
        encoding="utf-8",
    )
    artifact = ingest_repository(repo, "test/index-gold")

    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [
            {"file_path": "src/config/index.ts", "expected_block": "Search Architecture"},
            {"file_path": "src/index.ts", "expected_block": "Search Architecture"},
        ],
    )

    assert report["accuracy"] == 1.0


def test_gold_benchmark_scores_file_surface_when_no_symbol_boundary(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / "src" / "bull").mkdir(parents=True)
    (repo / "src" / "bull" / "index.ts").write_text(
        "export * from './queue';\nexport const queueName = 'mail';\n",
        encoding="utf-8",
    )
    artifact = ingest_repository(repo, "test/file-surface")

    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [{"file_path": "src/bull/index.ts", "expected_block": "Background Processing"}],
    )

    assert report["rows"][0]["match"] is True


def test_gold_benchmark_catches_supabase_adapter_as_data_persistence(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / "src" / "lib").mkdir(parents=True)
    (repo / "src" / "lib" / "supabase.ts").write_text(
        "import { createClient } from '@supabase/supabase-js';\n"
        "export const supabaseAdmin = createClient('url', 'key');\n",
        encoding="utf-8",
    )
    artifact = ingest_repository(repo, "test/supabase-gold")

    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [{"file_path": "src/lib/supabase.ts", "expected_block": "Data Persistence"}],
    )

    assert report["rows"][0]["match"] is True


def test_gold_benchmark_treats_cache_wrappers_as_persistence_strategy(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / "src" / "libs" / "cache").mkdir(parents=True)
    (repo / "src" / "libs" / "cache" / "cache.ts").write_text(
        "import Redis from 'ioredis';\n"
        "export class Cache { async remember(key: string) { return Redis.get(key); } }\n",
        encoding="utf-8",
    )
    artifact = ingest_repository(repo, "test/cache-gold")

    report = run_benchmark(
        artifact.model_dump(mode="json"),
        [{"file_path": "src/libs/cache/cache.ts", "expected_block": "Persistence Strategy"}],
    )

    assert report["rows"][0]["match"] is True


def test_committed_gold_benchmark_meets_phase_8_5_breadth_thresholds() -> None:
    gold_path = Path(__file__).resolve().parents[2] / "docs" / "evals" / "gold_block_benchmark.json"
    if not gold_path.is_file():
        pytest.skip("docs/evals/gold_block_benchmark.json not present in this checkout")
    items = json.loads(gold_path.read_text(encoding="utf-8"))
    repos = {str(i.get("repo_name")) for i in items if i.get("repo_name")}
    blocks = {str(i.get("expected_block")) for i in items if i.get("expected_block")}
    assert len(items) >= 25
    assert len(repos) >= 4
    assert len(blocks) >= 8


def test_committed_gold_benchmark_excludes_invalid_supabase_experimentation_row() -> None:
    gold_path = Path(__file__).resolve().parents[2] / "docs" / "evals" / "gold_block_benchmark.json"
    if not gold_path.is_file():
        pytest.skip("docs/evals/gold_block_benchmark.json not present in this checkout")
    items = json.loads(gold_path.read_text(encoding="utf-8"))
    assert not any(
        item.get("repo_name") == "elysia-supabase-tempate"
        and item.get("file_path") == "src/lib/supabase.ts"
        and item.get("expected_block") == "Experimentation"
        for item in items
    )
