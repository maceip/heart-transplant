from __future__ import annotations

import uuid
from pathlib import Path

from heart_transplant.artifact_store import read_json
from heart_transplant.execution.ledger import append_ledger_event
from heart_transplant.execution.models import ProposedEdit, TransplantResult, ValidationSummary
from heart_transplant.execution.validator import run_post_edit_validation
from heart_transplant.models import StructuralArtifact
from heart_transplant.regret.models import RegretScanReport, SurgeryPlan


def load_plan(path: Path) -> RegretScanReport:
    data = read_json(path)
    return RegretScanReport.model_validate(data)


def run_transplant(
    regret_id: str,
    artifact_dir: Path,
    *,
    plan_path: Path | None = None,
    dry_run: bool = True,
) -> TransplantResult:
    """Human-in-the-loop transplant planner: proposes edits, never writes source by default."""

    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    art = StructuralArtifact.model_validate(structural)
    repo_path = Path(art.repo_path).resolve()

    surgery: SurgeryPlan | None = None
    if plan_path and plan_path.is_file():
        report = load_plan(plan_path)
        surgery = next((p for p in report.surgery_plans if p.regret_id == regret_id), None)

    proposed: list[ProposedEdit] = []
    if surgery:
        for st in surgery.steps:
            proposed.append(
                ProposedEdit(
                    path=str(repo_path),
                    description=st.action,
                    patch_hint=st.verification,
                )
            )
    else:
        proposed.append(
            ProposedEdit(
                path=str(repo_path),
                description=f"Manual triage required for `{regret_id}` (no surgery plan row).",
                patch_hint="Run `regret-scan --output` and pass `--plan` to execute-transplant.",
            )
        )

    tid = str(uuid.uuid4())
    validation: ValidationSummary | None = None
    if not dry_run:
        validation = run_post_edit_validation(repo_path)

    ledger_p = append_ledger_event(
        {
            "type": "transplant",
            "transplant_id": tid,
            "regret_id": regret_id,
            "dry_run": dry_run,
            "repo": art.repo_name,
            "proposed_count": len(proposed),
        }
    )

    limitations = [
        "No automatic file patches are applied; `--execute` only runs compileall validation (Phase 12 safety stub).",
        "Full MCP/Cursor-driven edits belong in a future iteration with explicit file locks.",
    ]

    return TransplantResult(
        transplant_id=tid,
        regret_id=regret_id,
        dry_run=dry_run,
        proposed_edits=proposed,
        validation=validation,
        ledger_path=str(ledger_p),
        status="planned" if dry_run else "validated_compileall",
        limitations=limitations,
    )
