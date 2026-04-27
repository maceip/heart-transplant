from __future__ import annotations

from heart_transplant.causal.calibration import record_outcome


def learn_from_transplant(*, predicted_impact: int, observed_impact: int | None) -> None:
    """Hook causal calibration when an executed transplant supplies measured impact."""

    record_outcome(predicted_impact=predicted_impact, actual_impact=observed_impact)
