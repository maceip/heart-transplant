from __future__ import annotations

from heart_transplant.causal.overlay import build_causal_overlay
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.models import StructuralArtifact
from heart_transplant.temporal.models import TemporalScanReport


def _minimal_two_node_call_graph() -> StructuralArtifact:
    node = {
        "scip_id": "c1",
        "name": "fa",
        "kind": "function",
        "file_path": "f.ts",
        "range": {"start_line": 1, "start_col": 0, "end_line": 2, "end_col": 1},
        "content": "",
        "repo_name": "r",
        "language": "typescript",
        "project_id": "p",
        "original_provisional_id": "c1",
    }
    node2 = {**node, "scip_id": "c2", "name": "fb", "original_provisional_id": "c2"}
    return StructuralArtifact.model_validate(
        {
            "artifact_id": "min",
            "repo_name": "r",
            "repo_path": "/tmp",
            "project_id": "p",
            "node_count": 2,
            "edge_count": 1,
            "parser_backends": ["test"],
            "project_node": {"node_id": "proj", "name": "r", "repo_name": "r"},
            "file_nodes": [],
            "code_nodes": [node, node2],
            "edges": [{"source_id": "c1", "target_id": "c2", "edge_type": "CALLS", "repo_name": "r"}],
        }
    )


def test_overlay_applies_temporal_hotspot_factor(tmp_path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "a.ts").write_text(
        "export function one() { return two(); }\nexport function two() { return 1; }\n",
        encoding="utf-8",
    )
    art = ingest_repository(repo, "ovtest")
    temporal = TemporalScanReport(
        repo_path=str(repo),
        commit_count=0,
        commits=[],
        block_churn={},
        file_hotspots={art.code_nodes[0].file_path: 99},
        limitations=[],
    )
    overlay = build_causal_overlay(
        art,
        semantic=None,
        temporal=temporal,
        change_tokens=set(),
    )
    assert overlay.edges
    boosted = [e for e in overlay.edges if "temporal:" in "".join(e.adjustment_factors)]
    assert boosted, "expected at least one edge to pick up temporal hotspot signal"


def test_semantic_same_block_factor_when_assignments_present() -> None:
    art = _minimal_two_node_call_graph()
    semantic = {
        "block_assignments": [
            {"node_id": "c1", "primary_block": "Access Control", "confidence": 0.9, "reasoning": "t"},
            {"node_id": "c2", "primary_block": "Access Control", "confidence": 0.9, "reasoning": "t"},
        ]
    }
    overlay = build_causal_overlay(art, semantic=semantic, temporal=None, change_tokens=set())
    ce = overlay.edges[0]
    assert "semantic:same_block" in ce.adjustment_factors
    assert ce.adjusted_weight >= ce.base_weight
