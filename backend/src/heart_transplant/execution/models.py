from __future__ import annotations

from pydantic import BaseModel, Field


class ProposedEdit(BaseModel):
    path: str
    description: str
    patch_hint: str


class ValidationSummary(BaseModel):
    ran: bool
    command: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    stdout_tail: str = ""
    note: str = ""


class TransplantResult(BaseModel):
    phase_id: str = "phase_12"
    transplant_id: str
    regret_id: str
    dry_run: bool
    proposed_edits: list[ProposedEdit] = Field(default_factory=list)
    validation: ValidationSummary | None = None
    ledger_path: str | None = None
    status: str
    limitations: list[str] = Field(default_factory=list)
