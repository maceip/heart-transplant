from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from heart_transplant.models import CodeNode, NeighborhoodRecord
from heart_transplant.ontology import iter_blocks
from heart_transplant.semantic.models import BlockAssignment


@dataclass(frozen=True)
class Signal:
    block: str
    pattern: str
    weight: float
    label: str


_SIGNALS: tuple[Signal, ...] = (
    Signal("Access Control", r"\b(auth|session|password|jwt|bearer|rbac|permission|role|guard)\b", 2.0, "auth/session token"),
    Signal("Access Control", r"\b(currentUser|signIn|signOut|login|signup|user_metadata|app_metadata)\b", 1.5, "identity operation"),
    Signal("Data Persistence", r"\b(prisma|database|postgres|sqlite|mysql|mongodb|schema|migration|model|supabase|drizzle|redis)\b", 2.0, "database/schema token"),
    Signal("Data Persistence", r"\b(upsert|insert|update|delete|select|query|findMany|findUnique|createClient)\b", 1.3, "persistence operation"),
    Signal("Network Edge", r"\b(elysia|express|hono|fastify|router|route|middleware|request|response)\b", 1.6, "http framework"),
    Signal("Network Edge", r"\b(fetch|axios|http\.|webhook|endpoint)\b", 1.2, "network call"),
    Signal("System Telemetry", r"\b(telemetry|logger?|log\.|tracer|metric|sentry|otel|opentelemetry)\b", 1.8, "observability token"),
    Signal("Security Ops", r"\b(secret|api[_-]?key|encrypt|decrypt|hash|salt|csrf|cors|helmet)\b", 1.5, "security token"),
    Signal("Traffic Control", r"\b(rate[_-]?limit|throttle|quota|cors|load balanc|proxy)\b", 1.4, "traffic control token"),
    Signal("Background Processing", r"\b(queue|worker|job|task|schedule|cron|bullmq)\b", 1.6, "async processing token"),
    Signal("Search Architecture", r"\b(search|index|meilisearch|typesense|elastic|opensearch)\b", 1.6, "search token"),
    Signal("Analytical Intelligence", r"\b(warehouse|etl|analytics|segment|amplitude|mixpanel|report)\b", 1.5, "analytics token"),
    Signal("Data Sovereignty", r"\b(gdpr|privacy|retention|archive|pii|cookie|consent)\b", 1.4, "privacy token"),
    Signal("Resiliency", r"\b(retry|fallback|circuit|backup|restore|catch|try\s*\{)\b", 1.2, "resilience token"),
    Signal("Identity UI", r"\b(login|signup|profile|avatar|account|auth form)\b", 1.6, "identity ui token"),
    Signal("State Management", r"\b(zustand|redux|context|useReducer|store|atom|signal)\b", 1.5, "state token"),
    Signal("Core Rendering", r"(</|className|jsx|tsx|render|component|return\s*\()", 1.3, "render token"),
    Signal("Interaction Design", r"\b(onClick|onSubmit|form|button|input|navigate|router\.push)\b", 1.3, "interaction token"),
    Signal("Asset Delivery", r"\b(vite|webpack|rollup|bundle|asset|image|font|css|tailwind)\b", 1.2, "asset/build token"),
    Signal("User Observability", r"\b(session replay|client analytics|browser metric|web vitals)\b", 1.5, "client observability token"),
    Signal("Error Boundaries", r"\b(error boundary|fallback ui|componentDidCatch|useErrorBoundary)\b", 1.7, "frontend fault boundary"),
)

_KIND_PRIORS: dict[str, tuple[str, float, str]] = {
    "route_handler": ("Network Edge", 2.5, "route handler seam"),
    "middleware": ("Network Edge", 2.0, "middleware seam"),
    "db_model": ("Data Persistence", 3.0, "database model seam"),
    "react_hook": ("State Management", 1.6, "custom hook seam"),
    "config_object": ("Security Ops", 0.4, "configuration seam"),
    "service_boundary": ("Connectivity Layer", 1.1, "service/client boundary"),
}

_PATH_PRIORS: tuple[Signal, ...] = (
    Signal("Data Persistence", r"(^|/)prisma(/|\.config)|(^|/)schema\.prisma$|(^|/)lib/prisma\.", 2.3, "persistence path"),
    Signal("Persistence Strategy", r"(^|/)(libs?/)?cache(/|\.)|(^|/)cache\.", 4.2, "cache/persistence strategy path"),
    Signal("Background Processing", r"(^|/)(bull|queues?|workers?)(/|\.)|(^|/).*(queue|worker)[^/]*\.", 3.2, "queue/worker path"),
    Signal("Global Interface", r"(^|/)(env|environment)\.config\.|(^|/)config/(env|environment)\.", 2.6, "environment interface path"),
    Signal("System Telemetry", r"(^|/)(logger|telemetry|tracing)\.", 2.0, "telemetry path"),
    Signal("Access Control", r"(^|/)(auth|passwords?|sessions?|permissions?)[^/]*\.", 1.7, "access-control path"),
    Signal("Access Control", r"(^|/)utils/(auth|docs-guard)\.", 1.7, "auth utility path"),
    Signal("Security Ops", r"(^|/)utils/security\.", 2.2, "security utility path"),
    Signal("Network Edge", r"(^|/)routes?/", 1.8, "route path"),
    Signal("Core Rendering", r"(^|/)emails?/.*\.(tsx|jsx)$", 2.4, "rendered email component path"),
    Signal("Background Processing", r"(^|/)(scripts|workers|jobs)/", 1.6, "worker/script path"),
    Signal("Connectivity Layer", r"(^|/)(services?|adapters|providers)/", 0.9, "service layer path"),
    Signal(
        "Search Architecture",
        r"(^|/)(index|config/index|database/index|middlewares/index|modules/index|modules/[^/]+/index)\.(ts|tsx|js|jsx)$",
        2.4,
        "architectural index path",
    ),
)


def classify_node_heuristic(
    node: CodeNode,
    neighbor: NeighborhoodRecord | None = None,
) -> BlockAssignment:
    """No-LLM baseline using path, content, and import tokens."""
    blocks = list(iter_blocks())
    hay = f"{node.file_path} {node.name} {node.content[:2000]}"
    if neighbor:
        hay += " " + " ".join(neighbor.imports) + " " + " ".join(neighbor.same_file[:20])
    scores: Counter[str] = Counter()
    evidence: dict[str, list[str]] = {}
    hlower = hay.lower()
    if prior := _KIND_PRIORS.get(node.kind.value):
        block, weight, label = prior
        scores[block] += weight
        evidence.setdefault(block, []).append(label)
    for signal in _PATH_PRIORS:
        if re.search(signal.pattern, node.file_path, re.I | re.S):
            scores[signal.block] += signal.weight
            evidence.setdefault(signal.block, []).append(signal.label)
    for signal in _SIGNALS:
        if re.search(signal.pattern, hlower, re.I | re.S):
            scores[signal.block] += signal.weight
            evidence.setdefault(signal.block, []).append(signal.label)

    if node.kind.value == "config_object":
        if re.search(r"\b(prisma|database|postgres|schema|migration)\b", hlower, re.I | re.S):
            scores["Data Persistence"] += 2.0
            evidence.setdefault("Data Persistence", []).append("database configuration")
        elif re.search(r"\b(secret|key|token|env)\b", hlower, re.I | re.S):
            scores["Security Ops"] += 1.5
            evidence.setdefault("Security Ops", []).append("secret/env configuration")
    if node.kind.value == "react_hook" and re.search(r"\b(auth|session|user|profile)\b", hlower, re.I | re.S):
        scores["Identity UI"] += 1.7
        evidence.setdefault("Identity UI", []).append("identity hook")
    if not scores:
        primary = blocks[0]
        conf = 0.1
        reasons = ["no matching deterministic signals"]
    else:
        ranked = scores.most_common(2)
        primary, score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = max(float(score) - float(runner_up), 0.0)
        conf = min(0.42 + 0.08 * float(score) + 0.06 * margin, 0.95)
        if margin < 0.75 and score > 0:
            conf = min(conf, 0.66)
        reasons = evidence.get(primary, [])
    if primary not in blocks:
        primary = blocks[0]
    return BlockAssignment(
        node_id=node.scip_id,
        primary_block=primary,
        confidence=conf,
        reasoning="heuristic: weighted block signals: " + ", ".join(reasons[:5]),
        supporting_neighbors=neighbor.imports if neighbor else [],
    )
