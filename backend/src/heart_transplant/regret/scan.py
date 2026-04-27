from __future__ import annotations

from pathlib import Path

from heart_transplant.artifact_store import read_json
from heart_transplant.models import StructuralArtifact
from heart_transplant.regret.detector import detect_regrets
from heart_transplant.regret.models import (
    ExecutionLedger,
    RegretEvidence,
    RegretScanReport,
    RegretSdkReport,
    RegretSurface,
    SimulationResult,
)
from heart_transplant.regret.surgery_planner import plan_for_regret


def run_regret_scan(
    artifact_dir: Path,
    *,
    min_confidence: float = 0.35,
) -> RegretScanReport:
    artifact_dir = artifact_dir.resolve()
    structural = read_json(artifact_dir / "structural-artifact.json")
    art = StructuralArtifact.model_validate(structural)
    sem_path = artifact_dir / "semantic-artifact.json"
    semantic = read_json(sem_path) if sem_path.is_file() else None

    regrets = detect_regrets(art, semantic, min_score=min_confidence)
    regrets = [r for r in regrets if r.confidence >= min_confidence]
    plans = [plan_for_regret(r) for r in regrets]

    limitations = [
        "Heuristic keyword + block-alignment detector — not a substitute for blind human-validated gates.",
        "Temporal drift and causal risk are not yet fused into scores (hooks reserved).",
    ]

    return RegretScanReport(
        repo_name=art.repo_name,
        artifact_dir=str(artifact_dir),
        regrets=regrets,
        surgery_plans=plans,
        limitations=limitations,
    )


def run_regret_sdk_scan(
    artifact_dir: Path,
    *,
    min_confidence: float = 0.35,
) -> RegretSdkReport:
    """Return the stable SDK contract for agent consumers.

    This wraps the Phase 11 scan without requiring callers to correlate separate
    regret and surgery-plan arrays.
    """

    report = run_regret_scan(artifact_dir, min_confidence=min_confidence)
    plans_by_id = {plan.regret_id: plan for plan in report.surgery_plans}
    surfaces: list[RegretSurface] = []
    for regret in report.regrets:
        surfaces.append(
            RegretSurface(
                regret=regret,
                evidence_bundle=[
                    RegretEvidence(
                        kind="keyword",
                        summary=line,
                        node_ids=regret.node_ids,
                        file_paths=regret.file_paths,
                        confidence=regret.confidence,
                    )
                    for line in regret.evidence
                ],
                surgery_plan=plans_by_id.get(regret.regret_id),
                simulation=SimulationResult(
                    status="not_run",
                    summary="Run simulate-change with this regret's affected files before execution.",
                    impacted_node_ids=regret.node_ids,
                    risk_score=regret.score,
                ),
                execution_ledger=ExecutionLedger(
                    status="planned" if regret.regret_id in plans_by_id else "not_started",
                    validation_commands=[
                        "python -m compileall backend/src",
                        "python -m pytest",
                    ],
                    notes=["No source edits are performed by regret-sdk-scan."],
                ),
            )
        )

    return RegretSdkReport(
        repo_name=report.repo_name,
        artifact_dir=report.artifact_dir,
        surfaces=surfaces,
        limitations=report.limitations,
    )
