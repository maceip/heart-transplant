from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import artifact_root


def calibration_path() -> Path:
    return artifact_root().parent / "causal_calibration.json"


def load_calibration() -> dict[str, Any]:
    p = calibration_path()
    if not p.is_file():
        return {"bias": 0.0, "events": []}
    return json.loads(p.read_text(encoding="utf-8"))


def brier_score(data: dict[str, Any] | None = None) -> float | None:
    """Mean squared error of stored probabilistic predictions (``p`` vs outcome ``y`` in {{0,1}})."""
    data = data or load_calibration()
    rows = [e for e in data.get("events", []) if "p" in e and "y" in e]
    if len(rows) < 3:
        return None
    return sum((float(r["p"]) - float(r["y"])) ** 2 for r in rows) / len(rows)


def adjusted_confidence(raw: float) -> float:
    """Apply learned bias and optional Brier-based uncertainty shrinkage (Phase 10)."""
    data = load_calibration()
    bias = float(data.get("bias", 0.0))
    b = brier_score(data)
    shrink = 0.0 if b is None else max(0.0, min(0.15, float(b) - 0.1))
    return max(0.02, min(0.98, raw - bias - shrink))


def record_probability_outcome(*, predicted_prob: float, outcome: float) -> None:
    """Append a calibration row for Brier tracking (``outcome`` is 0.0 or 1.0)."""

    p = calibration_path()
    cal = load_calibration()
    events: list[dict[str, Any]] = list(cal.get("events", []))
    events.append({"p": predicted_prob, "y": outcome})
    cal["events"] = events[-500:]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cal, indent=2), encoding="utf-8")


def record_outcome(*, predicted_impact: int, actual_impact: int | None) -> None:
    """Append an outcome row; recomputes a crude bias toward measured over-prediction."""
    p = calibration_path()
    data = load_calibration()
    events: list[dict[str, Any]] = list(data.get("events", []))
    row: dict[str, Any] = {"predicted_impact": predicted_impact}
    if actual_impact is not None:
        row["actual_impact"] = actual_impact
    events.append(row)
    data["events"] = events[-500:]
    if actual_impact is not None and len(events) >= 3:
        recent = [e for e in events if "actual_impact" in e][-20:]
        if recent:
            err = sum(e["predicted_impact"] - e["actual_impact"] for e in recent) / len(recent)
            data["bias"] = max(-0.15, min(0.15, err / 100.0))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
