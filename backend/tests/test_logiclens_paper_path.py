from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from heart_transplant.artifact_store import write_json
from heart_transplant.canonical_graph import build_canonical_graph
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.cli import app
from heart_transplant.evidence import answer_with_evidence, explain_file, explain_node, trace_dependency
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.paper_checklist import build_paper_reproduction_checklist


def test_canonical_graph_unifies_structural_and_semantic_layers(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)

    graph = build_canonical_graph(artifact_dir)

    assert graph["schema"] == "heart-transplant.canonical-graph.v1"
    assert graph["summary"]["dangling_edge_count"] == 0
    layers = set(graph["summary"]["layers"])
    assert {"project", "file", "code", "semantic"} <= layers
    assert any(edge["provenance"] == "semantic_classifier" for edge in graph["edges"])
    assert any(node["node_id"] == artifact.code_nodes[0].scip_id for node in graph["nodes"])


def test_evidence_bundle_queries_return_receipts(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)
    code_node = next(node for node in artifact.code_nodes if node.kind.value == "function")

    explained = explain_node(artifact_dir, code_node.scip_id)
    file_explained = explain_file(artifact_dir, "auth.ts")
    block = answer_with_evidence(artifact_dir, "Where is auth handled?")
    missing_path = trace_dependency(artifact_dir, code_node.scip_id, "missing", max_depth=2)

    assert explained.source_nodes[0].node_id == code_node.scip_id
    assert explained.file_ranges
    assert file_explained.source_nodes
    assert block.query_type == "find_architectural_block"
    assert block.source_nodes
    assert missing_path.confidence < 0.5
    assert missing_path.limitations


def test_paper_reproduction_checklist_maps_features_to_gates_and_benchmarks() -> None:
    checklist = build_paper_reproduction_checklist(Path(__file__).resolve().parents[2])

    by_id = {feature.feature_id: feature for feature in checklist.features}
    assert checklist.feature_count >= 8
    assert by_id["structural_graph"].gate_or_test
    assert by_id["semantic_blocks"].benchmark_mapping
    assert by_id["evidence_retrieval"].status == "partial"


def test_cli_exposes_logiclens_paper_path_commands(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)
    code_node = next(node for node in artifact.code_nodes if node.kind.value == "function")
    runner = CliRunner()

    canonical = runner.invoke(app, ["canonical-graph", str(artifact_dir)])
    explain = runner.invoke(app, ["explain-node", code_node.scip_id, "--artifact-dir", str(artifact_dir)])
    paper = runner.invoke(app, ["paper-checklist"])

    assert canonical.exit_code == 0
    assert json.loads(canonical.output)["schema"] == "heart-transplant.canonical-graph.v1"
    assert explain.exit_code == 0
    assert json.loads(explain.output)["query_type"] == "explain_node"
    assert paper.exit_code == 0
    assert json.loads(paper.output)["report_type"] == "logiclens_paper_reproduction_checklist"


def _artifact_with_semantics(tmp_path: Path) -> tuple[Path, object]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return true; }\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/logiclens")
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    write_json(artifact_dir / "structural-artifact.json", artifact.model_dump(mode="json"))
    run_classification_on_artifact(artifact_dir, use_openai=False)
    return artifact_dir, artifact
