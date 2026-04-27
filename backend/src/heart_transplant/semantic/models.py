from __future__ import annotations

from pydantic import BaseModel, Field


class SemanticSummary(BaseModel):
    node_id: str
    summary_type: str
    text: str
    provenance: str


class SemanticEntity(BaseModel):
    entity_id: str
    name: str
    category: str
    description: str | None = None


class SemanticAction(BaseModel):
    source_code_node_id: str
    entity_id: str
    action: str
    confidence: float
    reasoning: str


class BlockClassifyResult(BaseModel):
    """LLM output without node id; stitched into :class:`BlockAssignment` in the pipeline."""

    primary_block: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class SecondaryBlock(BaseModel):
    block: str
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class BlockAssignment(BaseModel):
    node_id: str
    primary_block: str
    secondary_blocks: list[SecondaryBlock] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    supporting_neighbors: list[str] = Field(default_factory=list)


class SemanticArtifact(BaseModel):
    artifact_id: str
    semantic_summaries: list[SemanticSummary] = Field(default_factory=list)
    entities: list[SemanticEntity] = Field(default_factory=list)
    actions: list[SemanticAction] = Field(default_factory=list)
    block_assignments: list[BlockAssignment] = Field(default_factory=list)
