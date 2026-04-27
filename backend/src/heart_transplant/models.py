from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field, model_validator


class SymbolKind(str, Enum):
    FUNCTION = "function"
    CLASS = "class"
    INTERFACE = "interface"
    METHOD = "method"
    ROUTE_HANDLER = "route_handler"
    VARIABLE = "variable"
    """Exported const/let used as a value (including function-like)."""
    REACT_HOOK = "react_hook"
    """Top-level custom hook boundary, e.g. ``useSession``."""
    CONFIG_OBJECT = "config_object"
    """Top-level configuration/env/schema object or factory."""
    MIDDLEWARE = "middleware"
    """Top-level request/auth middleware boundary."""
    SERVICE_BOUNDARY = "service_boundary"
    """Top-level service/repository/client boundary."""
    DB_MODEL = "db_model"
    """Database model/schema definition, e.g. Prisma ``model User``."""


class SourceRange(BaseModel):
    start_line: int
    start_col: int
    end_line: int
    end_col: int


class FileNode(BaseModel):
    node_id: str
    file_path: str
    repo_name: str
    language: str
    project_id: str


class ProjectNode(BaseModel):
    node_id: str
    name: str
    repo_name: str


class CodeNode(BaseModel):
    """Atomic structural unit destined for graph storage.

    Ownership contract:
    - Tree-sitter owns `range` and `content`.
    - SCIP owns `scip_id` once resolution succeeds.
    - `original_provisional_id` is the first provisional symbol id and never changes.
    """

    scip_id: str = Field(..., description="Global symbol id: provisional before SCIP, then the SCIP symbol string.")
    name: str
    kind: SymbolKind
    file_path: str
    range: SourceRange
    content: str
    repo_name: str
    language: str
    project_id: str
    original_provisional_id: str = Field(
        ...,
        description="Ingest-time provisional id; stable across SCIP resolution.",
    )
    provisional_scip_id: str | None = None
    symbol_source: Literal["provisional", "scip"] = "provisional"
    scip_kind: str | None = None

    @computed_field
    @property
    def node_id(self) -> str:
        """Canonical graph id (identical to ``scip_id`` once SCIP is the source of truth)."""
        return self.scip_id

    @model_validator(mode="before")
    @classmethod
    def _default_original_provisional_from_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = {k: v for k, v in data.items() if k != "node_id"}
        if not data.get("original_provisional_id"):
            if data.get("provisional_scip_id"):
                data = {**data, "original_provisional_id": data["provisional_scip_id"]}
            else:
                data = {**data, "original_provisional_id": data.get("scip_id", "")}
        if not data.get("project_id") and data.get("repo_name"):
            from heart_transplant.scip.path_normalization import build_project_node_id

            data = {**data, "project_id": build_project_node_id(str(data["repo_name"]))}
        return data


EdgeType = Literal[
    "CALLS",
    "IMPLEMENTS",
    "CONTAINS",
    "DEFINES",
    "REFERENCES",
    "IMPORTS_MODULE",
    "DEPENDS_ON_FILE",
    "DEPENDS_ON",
    "CROSS_REFERENCE",
]


class StructuralEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: EdgeType
    repo_name: str
    target_repo: str | None = None
    """Set when the target node lives in a different ``repo_name`` (multi-corpus)."""
    provenance: str | None = None
    """E.g. ``scip_reference``, ``scip_file_fallback``."""


class NeighborhoodRecord(BaseModel):
    """Query-friendly one-hop view for a code node (by current `scip_id`)."""

    code_id: str
    file_path: str
    project_id: str
    file_node_id: str
    imports: list[str] = Field(default_factory=list)
    imported_by: list[str] = Field(default_factory=list)
    same_file: list[str] = Field(default_factory=list)


class StructuralArtifact(BaseModel):
    artifact_id: str
    repo_name: str
    repo_path: str
    project_id: str
    node_count: int
    edge_count: int
    parser_backends: list[str]
    project_node: ProjectNode
    file_nodes: list[FileNode]
    code_nodes: list[CodeNode]
    edges: list[StructuralEdge]
    neighborhoods: dict[str, NeighborhoodRecord] = Field(default_factory=dict)
    """Maps code node id (``scip_id``) to immediate neighborhood metadata."""


class ScipIndexMetadata(BaseModel):
    repo_name: str
    repo_path: str
    indexer: str
    version: str | None
    output_path: str
    detected_package_manager: str | None
    install_command: list[str] | None
    install_performed: bool
    index_command: list[str]


class IngestTarget(BaseModel):
    repo_name: str
    repo_path: Path
