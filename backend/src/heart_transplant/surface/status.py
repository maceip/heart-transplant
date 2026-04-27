from __future__ import annotations

import importlib
from typing import Any


def program_surface_status() -> dict[str, Any]:
    """Summarize which roadmap phase packages are importable and their declared readiness."""

    phases: list[dict[str, Any]] = [
        _phase("phase_8_5", "heart_transplant.maximize.gates", "run_maximize_gates"),
        _phase("phase_9", "heart_transplant.temporal.scan", "temporal_scan"),
        _phase("phase_10", "heart_transplant.causal.simulation", "run_change_simulation"),
        _phase("phase_11", "heart_transplant.regret.scan", "run_regret_scan"),
        _phase("phase_12", "heart_transplant.execution.orchestrator", "run_transplant"),
        _phase("phase_13", "heart_transplant.multimodal.ingest", "run_multimodal_ingest"),
    ]
    return {
        "report_type": "phase_14_program_surface",
        "phases": phases,
        "note": "Phase 14 indexes import health for Phases 8.5–13 entrypoints; Phases 10–13 are first-pass implementations pending full non-gamable gates.",
    }


def _phase(phase_id: str, module: str, symbol: str) -> dict[str, Any]:
    try:
        mod = importlib.import_module(module)
        obj = getattr(mod, symbol, None)
        ok = callable(obj)
        return {"phase_id": phase_id, "module": module, "symbol": symbol, "import_ok": ok}
    except ImportError as exc:
        return {
            "phase_id": phase_id,
            "module": module,
            "symbol": symbol,
            "import_ok": False,
            "error": str(exc),
        }
