from __future__ import annotations

from pydantic import BaseModel, Field


class ChangedFile(BaseModel):
    path: str
    status: str
    inferred_blocks: list[str] = Field(default_factory=list)


class CommitRecord(BaseModel):
    sha: str
    authored_at: str
    subject: str
    changed_files: list[ChangedFile] = Field(default_factory=list)


class TemporalScanReport(BaseModel):
    repo_path: str
    commit_count: int
    commits: list[CommitRecord]
    block_churn: dict[str, int]
    file_hotspots: dict[str, int]
    limitations: list[str] = Field(default_factory=list)


class FileBlockSnapshot(BaseModel):
    path: str
    inferred_blocks: list[str] = Field(default_factory=list)


class ArchitectureSnapshot(BaseModel):
    repo_path: str
    commit_sha: str
    authored_at: str
    subject: str
    reconstruction_mode: str = "path_inference"
    file_count: int
    files: list[FileBlockSnapshot]
    block_file_counts: dict[str, int]
    limitations: list[str] = Field(default_factory=list)


class FileArchitectureChange(BaseModel):
    path: str
    status: str
    before_blocks: list[str] = Field(default_factory=list)
    after_blocks: list[str] = Field(default_factory=list)


class ArchitectureDiff(BaseModel):
    repo_path: str
    before_sha: str
    after_sha: str
    file_changes: list[FileArchitectureChange]
    block_delta: dict[str, int]


class TemporalMetricsReport(BaseModel):
    repo_path: str
    commit_count: int
    commits: list[str]
    snapshots: list[ArchitectureSnapshot]
    diffs: list[ArchitectureDiff]
    block_churn_rate: dict[str, float]
    block_delta_total: dict[str, int]
    file_hotspots: dict[str, int]
    coupling_tightness_trend: list[float] = Field(default_factory=list)
    architectural_drift_candidate_rate: float = 0.0
    regret_accumulation_score: float = 0.0
    pattern_success_index: dict[str, float] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class DriftFinding(BaseModel):
    path: str
    before_blocks: list[str]
    after_blocks: list[str]
    first_seen_commit: str
    confidence: float
    reason: str


class DriftReport(BaseModel):
    repo_path: str
    before_ref: str
    after_ref: str
    before_sha: str
    after_sha: str
    findings: list[DriftFinding]
    precision: float | None = None
    recall: float | None = None
    limitations: list[str] = Field(default_factory=list)
