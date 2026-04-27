from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class PaperFeatureStatus(BaseModel):
    feature_id: str
    paper_feature: str
    backend_mapping: str
    status: Literal["implemented", "partial", "missing"]
    gate_or_test: str
    artifact: str
    benchmark_mapping: str | None = None
    notes: list[str] = Field(default_factory=list)


class PaperReproductionChecklist(BaseModel):
    report_type: str = "logiclens_paper_reproduction_checklist"
    feature_count: int
    implemented: int
    partial: int
    missing: int
    features: list[PaperFeatureStatus]


def build_paper_reproduction_checklist(repo_root: Path | None = None) -> PaperReproductionChecklist:
    root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    features = [
        PaperFeatureStatus(
            feature_id="structural_graph",
            paper_feature="Repository program graph construction",
            backend_mapping="Tree-sitter ingest, FileNode/CodeNode graph, canonical graph export",
            status="implemented" if (root / "backend/src/heart_transplant/ingest/treesitter_ingest.py").is_file() else "missing",
            gate_or_test="backend/tests/test_ingest.py; validate-gates structural_ingest_produces_nodes",
            artifact="structural-artifact.json; canonical-graph.json",
            benchmark_mapping="Graph coverage contributes to block-benchmark missing-node rate.",
        ),
        PaperFeatureStatus(
            feature_id="symbol_identity",
            paper_feature="Stable symbol identity and reference graph",
            backend_mapping="SCIP index/consume, DEFINES/REFERENCES/CROSS_REFERENCE edges, orphan promotion",
            status="partial",
            gate_or_test="backend/tests/test_scip_consume.py; validate-gates scip_actually_resolves_nodes",
            artifact="index.scip; scip-index.json; scip-consumed.json; orphaned-symbols.json",
            benchmark_mapping="No direct paper benchmark committed; identity quality is measured by resolved_symbol_rate and orphaned_symbol_rate.",
            notes=["References exist, but cross-repo/reference completeness is not yet paper-grade."],
        ),
        PaperFeatureStatus(
            feature_id="semantic_blocks",
            paper_feature="Semantic component/block labeling",
            backend_mapping="24-block ontology, deterministic classifier, semantic artifact",
            status="partial",
            gate_or_test="block-benchmark; backend/tests/test_gold_benchmark.py",
            artifact="semantic-artifact.json; docs/evals/gold_block_benchmark*.json",
            benchmark_mapping="block-benchmark reports end-to-end accuracy, scorable accuracy, missing-node rate, per-block confusion.",
            notes=["Holdout baseline is below target; multi-label and file-surface scoring are now present."],
        ),
        PaperFeatureStatus(
            feature_id="evidence_retrieval",
            paper_feature="Evidence-grounded architecture question answering",
            backend_mapping="EvidenceBundle schema and artifact-backed explain/trace/find/answer helpers",
            status="partial",
            gate_or_test="backend/tests/test_evidence.py (to expand into question fixtures)",
            artifact="canonical-graph.json; structural-artifact.json; semantic-artifact.json",
            benchmark_mapping="Next benchmark should score fixture questions for exact/partial evidence match and unsupported-answer rate.",
        ),
        PaperFeatureStatus(
            feature_id="graph_persistence",
            paper_feature="Queryable graph backend",
            backend_mapping="SurrealDB load/verify and MCP graph query tools",
            status="partial",
            gate_or_test="backend/tests/test_surreal_phase3.py; validate-gates graph_smoke_structure_is_consistent",
            artifact="SurrealDB ht_code/ht_edge rows derived from structural-artifact.json",
            benchmark_mapping="Persistence is gate-based, not benchmark-scored.",
            notes=["Artifact-backed evidence helpers reduce dependence on a running DB for reproducibility."],
        ),
        PaperFeatureStatus(
            feature_id="temporal_reasoning",
            paper_feature="Architecture evolution over time",
            backend_mapping="temporal-scan, temporal snapshots/diffs, replayed Tree-sitter snapshots",
            status="partial",
            gate_or_test="backend/tests/test_temporal_scan.py; temporal-gates",
            artifact="phase-9 temporal reports; replayed_snapshots",
            benchmark_mapping="Temporal benchmark maps to replayed diff correctness and drift precision/recall fixtures.",
            notes=["SCIP + semantic replay is planned but not required on every commit yet."],
        ),
        PaperFeatureStatus(
            feature_id="multi_modal",
            paper_feature="Cross-layer reasoning over code, tests, API, and infra",
            backend_mapping="multimodal-ingest plus canonical graph cross-layer nodes/edges",
            status="partial",
            gate_or_test="backend/tests/test_phase_10_13.py; graph-integrity",
            artifact="multimodal ingest JSON; canonical-graph.json",
            benchmark_mapping="Future benchmark should score test/API/infra correlation accuracy.",
        ),
        PaperFeatureStatus(
            feature_id="regret_sdk",
            paper_feature="Actionable remediation planning on graph evidence",
            backend_mapping="RegretSurface, evidence bundle, surgery plan, execution ledger",
            status="partial",
            gate_or_test="backend/tests/test_phase_10_13.py; regret-sdk-scan",
            artifact="regret-sdk-scan JSON",
            benchmark_mapping="Future benchmark maps to regret fixture precision and plan specificity review.",
            notes=["This goes beyond the paper target and must stay evidence-gated."],
        ),
    ]
    counts = {status: sum(1 for item in features if item.status == status) for status in ("implemented", "partial", "missing")}
    return PaperReproductionChecklist(
        feature_count=len(features),
        implemented=counts["implemented"],
        partial=counts["partial"],
        missing=counts["missing"],
        features=features,
    )
