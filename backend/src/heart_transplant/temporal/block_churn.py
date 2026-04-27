from __future__ import annotations

import re


PATH_BLOCK_RULES: tuple[tuple[str, str], ...] = (
    ("Access Control", r"(^|/)(auth|session|password|permission|rbac|guard|login|signup)"),
    ("System Telemetry", r"(^|/)(log|logger|telemetry|trace|metrics?|observability)"),
    ("Data Persistence", r"(^|/)(prisma|db|database|schema|model|migration)|\.(sql|prisma)$"),
    ("Background Processing", r"(^|/)(worker|job|queue|cron|schedule|task|script)s?(/|$)"),
    ("Traffic Control", r"(^|/)(rate|throttle|proxy|cors|gateway)"),
    ("Network Edge", r"(^|/)(route|router|api|server|controller)s?(/|\.|$)"),
    ("Search Architecture", r"(^|/)(search|index|elastic|opensearch|typesense)"),
    ("Security Ops", r"(^|/)(security|secret|csrf|crypto|encrypt|policy)"),
    ("Connectivity Layer", r"(^|/)(client|adapter|provider|service|gateway)s?(/|\.|$)"),
    ("Resiliency", r"(^|/)(backup|retry|fallback|circuit|restore)"),
    ("Data Sovereignty", r"(^|/)(privacy|gdpr|retention|archive|cookie|consent)"),
    ("Analytical Intelligence", r"(^|/)(analytics|warehouse|etl|report|segment|amplitude)"),
    ("Identity UI", r"(^|/)(login|signup|profile|account|avatar).*\.(tsx|jsx|vue|svelte)$"),
    ("State Management", r"(^|/)(store|state|context|reducer|hook)s?(/|\.)"),
    ("Core Rendering", r"\.(tsx|jsx|vue|svelte)$|(^|/)(page|component|view)s?(/|\.)"),
    ("Interaction Design", r"(^|/)(form|button|input|interaction|navigation)s?(/|\.)"),
    ("Asset Delivery", r"(^|/)(assets?|public|static|styles?|css|vite|webpack|rollup)"),
    ("Global Interface", r"(^|/)(i18n|locale|a11y|accessibility|translation)s?(/|\\.)"),
    ("Edge Support", r"(^|/)(support|chat|help|intercom|zendesk)"),
    ("Experimentation", r"(^|/)(experiment|feature-flag|ab-test|growth)s?(/|\.)"),
    ("User Observability", r"(^|/)(analytics|session-replay|web-vitals|client-metrics?)"),
    ("Error Boundaries", r"(^|/)(error-boundary|fallback|crash|exception)s?(/|\.)"),
    ("Persistence Strategy", r"(^|/)(cookie|localstorage|storage|cache|persist)"),
    ("Visual Systems", r"(^|/)(theme|design|tokens|typography|storybook|style)s?(/|\.)"),
)


def infer_blocks_for_path(path: str) -> list[str]:
    normalized = path.replace("\\", "/").lower()
    blocks = [block for block, pattern in PATH_BLOCK_RULES if re.search(pattern, normalized, re.I)]
    return list(dict.fromkeys(blocks)) or ["Unclassified"]
