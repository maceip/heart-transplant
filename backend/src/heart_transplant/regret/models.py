from __future__ import annotations

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


class RegretScanReport(BaseModel):
    phase_id: str = "phase_11"
    repo_name: str
    artifact_dir: str
    regrets: list[RegretItem] = Field(default_factory=list)
    surgery_plans: list[SurgeryPlan] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
