from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RegretItem(BaseModel):
    regret_id: str
    pattern_id: str
    title: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    file_paths: list[str] = Field(default_factory=list)


class RegretEvidence(BaseModel):
    kind: Literal["keyword", "block", "graph", "temporal", "manual"]
    summary: str
    node_ids: list[str] = Field(default_factory=list)
    file_paths: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class SimulationResult(BaseModel):
    status: Literal["not_run", "available"] = "not_run"
    summary: str = "Simulation not run for SDK scan."
    impacted_node_ids: list[str] = Field(default_factory=list)
    risk_score: float | None = Field(default=None, ge=0.0, le=1.0)


class SurgeryStep(BaseModel):
    order: int
    action: str
    rationale: str
    risk: str
    verification: str


class SurgeryPlan(BaseModel):
    regret_id: str
    title: str
    steps: list[SurgeryStep] = Field(default_factory=list)


class ExecutionLedger(BaseModel):
    status: Literal["not_started", "planned", "executed"] = "not_started"
    validation_commands: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RegretSurface(BaseModel):
    regret: RegretItem
    evidence_bundle: list[RegretEvidence] = Field(default_factory=list)
    surgery_plan: SurgeryPlan | None = None
    simulation: SimulationResult = Field(default_factory=SimulationResult)
    execution_ledger: ExecutionLedger = Field(default_factory=ExecutionLedger)


class RegretScanReport(BaseModel):
    phase_id: str = "phase_11"
    repo_name: str
    artifact_dir: str
    regrets: list[RegretItem] = Field(default_factory=list)
    surgery_plans: list[SurgeryPlan] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RegretSdkReport(BaseModel):
    sdk_schema_version: str = "regret-sdk.v1"
    repo_name: str
    artifact_dir: str
    surfaces: list[RegretSurface] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
