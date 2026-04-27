from __future__ import annotations

from pydantic import BaseModel, Field


class MultimodalNode(BaseModel):
    node_id: str
    kind: str
    path: str
    name: str = ""
    meta: dict[str, str] = Field(default_factory=dict)


class MultimodalEdge(BaseModel):
    source_id: str
    target_id: str
    edge_kind: str


class FlowHint(BaseModel):
    summary: str
    path_template: str = ""
    method: str = ""
    code_file_guess: str = ""


class MultimodalIngestReport(BaseModel):
    phase_id: str = "phase_13"
    root: str
    nodes: list[MultimodalNode] = Field(default_factory=list)
    edges: list[MultimodalEdge] = Field(default_factory=list)
    flow_hints: list[FlowHint] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
