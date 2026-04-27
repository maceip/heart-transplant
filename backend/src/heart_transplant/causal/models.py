from __future__ import annotations

from pydantic import BaseModel, Field


class TraceStep(BaseModel):
    """Auditable simulation step (no LLM — overlay math and RNG only)."""

    step_index: int
    kind: str
    detail: str
    node_ids: list[str] = Field(default_factory=list)
    edge_types: list[str] = Field(default_factory=list)


class CausalEdge(BaseModel):
    """One directed structural relationship with a propagation probability after adjustment."""

    source_id: str
    target_id: str
    structural_edge_type: str
    base_weight: float = Field(ge=0.0, le=1.0)
    adjusted_weight: float = Field(ge=0.0, le=1.0)
    adjustment_factors: list[str] = Field(default_factory=list)


class CausalGraphOverlay(BaseModel):
    """Explicit causal layer on top of the structural artifact (Phase 10 core deliverable)."""

    repo_name: str
    edges: list[CausalEdge] = Field(default_factory=list)
    mean_adjusted_weight: float = 0.0
    mean_delta_from_base: float = 0.0


class CausalSimulationResult(BaseModel):
    phase_id: str = "phase_10"
    change_description: str
    trace: list[TraceStep]
    impacted_node_ids: list[str]
    impacted_file_paths: list[str]
    mean_impact_count: float
    mc_std_impact_count: float = 0.0
    self_consistency_score: float = Field(
        0.0,
        description="Higher when MC runs agree (low relative variance of impacted set sizes).",
    )
    confidence: float
    mc_runs: int
    rng_seed: int
    seed_node_ids: list[str] = Field(default_factory=list)
    causal_overlay: CausalGraphOverlay | None = None
    limitations: list[str] = Field(default_factory=list)
