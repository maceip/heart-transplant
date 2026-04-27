from __future__ import annotations

from pathlib import Path

from heart_transplant.artifact_store import read_json
from heart_transplant.models import StructuralArtifact
from heart_transplant.regret.detector import detect_regrets
from heart_transplant.regret.models import RegretScanReport
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
