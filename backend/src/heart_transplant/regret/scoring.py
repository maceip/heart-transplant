from __future__ import annotations

from heart_transplant.regret.models import RegretItem
from heart_transplant.regret.patterns import RegretPattern


def score_pattern_match(
    pattern: RegretPattern,
    *,
    keyword_hits: int,
    block_alignment: float,
    file_spread: float,
) -> float:
    """Combine structural signals into [0,1] regret intensity."""
    kw = min(1.0, keyword_hits / 5.0)
    raw = pattern.base_score + 0.15 * kw + 0.2 * block_alignment + 0.15 * min(1.0, file_spread / 8.0)
    return max(0.0, min(1.0, raw))


def to_regret_item(
    pattern: RegretPattern,
    *,
    regret_id: str,
    score: float,
    evidence: list[str],
    node_ids: list[str],
    file_paths: list[str],
) -> RegretItem:
    confidence = max(0.0, min(1.0, score))
    return RegretItem(
        regret_id=regret_id,
        pattern_id=pattern.pattern_id,
        title=pattern.title,
        score=score,
        confidence=confidence,
        evidence=evidence,
        node_ids=node_ids,
        file_paths=sorted(set(file_paths)),
    )
