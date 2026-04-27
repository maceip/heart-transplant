from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegretPattern:
    pattern_id: str
    title: str
    keywords: tuple[str, ...]
    block_hints: tuple[str, ...]
    """Primary block labels that strengthen a hit."""
    base_score: float


PATTERNS: tuple[RegretPattern, ...] = (
    RegretPattern(
        pattern_id="scattered_auth",
        title="Auth logic spread across many route files",
        keywords=("auth", "session", "jwt", "bearer", "login"),
        block_hints=("Access Control",),
        base_score=0.55,
    ),
    RegretPattern(
        pattern_id="logging_inconsistency",
        title="Multiple logging or telemetry entry styles",
        keywords=("logger", "console.log", "pino", "winston", "telemetry"),
        block_hints=("System Telemetry",),
        base_score=0.45,
    ),
    RegretPattern(
        pattern_id="database_sprawl",
        title="Database access scattered outside a small persistence layer",
        keywords=("prisma", "drizzle", "sql", "query", "database", "supabase"),
        block_hints=("Data Persistence",),
        base_score=0.5,
    ),
    RegretPattern(
        pattern_id="fat_routes",
        title="Route module may be doing too much (many handlers in one file)",
        keywords=("routes", "router", "controller"),
        block_hints=("Traffic Control", "Network Edge"),
        base_score=0.4,
    ),
)
