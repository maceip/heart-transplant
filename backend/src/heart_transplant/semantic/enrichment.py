from __future__ import annotations

import hashlib
import re
from collections import Counter

from heart_transplant.models import CodeNode, NeighborhoodRecord, ProjectNode
from heart_transplant.semantic.models import BlockAssignment, SemanticAction, SemanticEntity, SemanticSummary


_ACTION_PATTERNS: list[tuple[str, str]] = [
    ("AUTHORIZE", r"auth|session|jwt|token|role|permission|guard|password"),
    ("PERSIST", r"prisma|database|query|insert|update|delete|select|schema|profile"),
    ("CONNECT", r"route|fetch|http|request|response|elysia|express|hono"),
    ("OBSERVE", r"log|metric|trace|telemetry|sentry|error"),
    ("RENDER", r"component|jsx|tsx|render|className|useState|form"),
    ("CONFIGURE", r"env|config|cors|rate|limit|secret|key"),
    ("PROCESS", r"queue|worker|job|task|schedule|cron"),
]

_ENTITY_PATTERNS: list[tuple[str, str]] = [
    ("Identity principal", r"\b(user|profile|account|identity|session)\b"),
    ("Authorization policy", r"\b(role|permission|rbac|guard|admin)\b"),
    ("Database model", r"\b(prisma|model|schema|table|profile|user)\b"),
    ("Database client", r"\b(db|database|client|pool|adapter|postgres)\b"),
    ("HTTP surface", r"\b(route|router|endpoint|request|response|elysia|express|hono)\b"),
    ("Configuration contract", r"\b(config|env|secret|key|url)\b"),
    ("Worker process", r"\b(queue|job|worker|task|cron)\b"),
    ("Telemetry stream", r"\b(log|metric|trace|telemetry|event)\b"),
    ("UI component", r"\b(component|page|form|button|input|view)\b"),
]


def build_semantic_summaries(
    items: list[tuple[CodeNode, NeighborhoodRecord | None, BlockAssignment]],
) -> list[SemanticSummary]:
    summaries: list[SemanticSummary] = []
    for node, neighbor, assignment in items:
        imported = len(neighbor.imports) if neighbor else 0
        same_file = len(neighbor.same_file) if neighbor else 0
        summaries.append(
            SemanticSummary(
                node_id=node.scip_id,
                summary_type="code_node",
                text=(
                    f"{node.kind.value} {node.name} in {node.file_path} maps to "
                    f"{assignment.primary_block} with {imported} import edge(s) and "
                    f"{same_file} sibling code node(s)."
                ),
                provenance="heuristic_semantic_enrichment",
            )
        )
    return summaries


def build_project_summary(project: ProjectNode, summaries: list[SemanticSummary]) -> SemanticSummary:
    block_counts: Counter[str] = Counter()
    for summary in summaries:
        match = re.search(r" maps to ([^ ](?:.*?)) with \d+ import", summary.text)
        if match:
            block_counts[match.group(1)] += 1
    top_blocks = ", ".join(block for block, _count in block_counts.most_common(5)) or "unclassified code"
    return SemanticSummary(
        node_id=project.node_id,
        summary_type="project",
        text=(
            f"Project {project.name} represents repository {project.repo_name}. "
            f"Its strongest observed responsibilities are {top_blocks}. "
            f"The summary is derived from {len(summaries)} code-node semantic summaries."
        ),
        provenance="heuristic_semantic_enrichment",
    )


def build_system_summary(system_name: str, project_summaries: list[SemanticSummary]) -> SemanticSummary:
    project_text = " ".join(summary.text for summary in project_summaries)
    return SemanticSummary(
        node_id="system:local",
        summary_type="system",
        text=(
            f"System {system_name} currently contains {len(project_summaries)} project graph(s). "
            f"It exposes cross-cutting architecture evidence through structural code nodes, "
            f"semantic entities, project summaries, and action edges. {project_text[:500]}"
        ),
        provenance="heuristic_semantic_enrichment",
    )


def build_semantic_entities(
    items: list[tuple[CodeNode, NeighborhoodRecord | None, BlockAssignment]],
) -> list[SemanticEntity]:
    candidates: Counter[tuple[str, str]] = Counter()
    descriptions: dict[tuple[str, str], str] = {}
    for node, neighbor, assignment in items:
        category = assignment.primary_block
        for name in entity_names_for_node(node) + inferred_domain_entities(node):
            key = (category, name)
            candidates[key] += 1
            descriptions.setdefault(key, entity_description(name, node, category))
        if neighbor:
            for imported in neighbor.imports[:8]:
                if imported.startswith("module:"):
                    name = imported.removeprefix("module:")
                    key = (category, name)
                    candidates[key] += 1
                    descriptions.setdefault(key, f"{name} is imported by code assigned to {category}.")

    entities: list[SemanticEntity] = []
    for (category, name), _count in sorted(candidates.items(), key=lambda item: (-item[1], item[0]))[:200]:
        entities.append(
            SemanticEntity(
                entity_id=entity_id(category, name),
                name=name,
                category=category,
                description=descriptions[(category, name)],
            )
        )
    return entities


def build_semantic_actions(
    items: list[tuple[CodeNode, NeighborhoodRecord | None, BlockAssignment]],
    entities: list[SemanticEntity],
) -> list[SemanticAction]:
    by_category: dict[str, list[SemanticEntity]] = {}
    for entity in entities:
        by_category.setdefault(entity.category, []).append(entity)

    actions: list[SemanticAction] = []
    for node, _neighbor, assignment in items:
        target = first_entity_for_node(node, assignment.primary_block, by_category)
        if target is None:
            continue
        action = infer_action(node)
        actions.append(
            SemanticAction(
                source_code_node_id=node.scip_id,
                entity_id=target.entity_id,
                action=action,
                confidence=max(0.1, min(float(assignment.confidence), 0.95)),
                reasoning=f"heuristic: {action.lower()} signal from node name/path/content",
            )
        )
    return actions


def entity_names_for_node(node: CodeNode) -> list[str]:
    names: list[str] = []
    if node.name:
        names.append(split_identifier(node.name))
    path_stem = node.file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if path_stem:
        names.append(split_identifier(path_stem))
    for segment in node.file_path.split("/")[:-1]:
        if segment in {"src", "lib", "app", "server", "client", "components", "pages"}:
            continue
        names.append(split_identifier(segment))
    return [name for name in dict.fromkeys(names) if name]


def inferred_domain_entities(node: CodeNode) -> list[str]:
    haystack = f"{node.kind.value} {node.name} {node.file_path} {node.content[:2000]}"
    entities: list[str] = []
    for label, pattern in _ENTITY_PATTERNS:
        if re.search(pattern, haystack, re.I | re.S):
            entities.append(label)
    if node.kind.value == "db_model":
        entities.append(f"{split_identifier(node.name)} model")
    if node.kind.value == "route_handler":
        entities.append("HTTP route")
    if node.kind.value in {"middleware", "service_boundary", "config_object", "react_hook"}:
        entities.append(split_identifier(node.kind.value))
    return [name for name in dict.fromkeys(entities) if name]


def entity_description(name: str, node: CodeNode, category: str) -> str:
    return (
        f"{name} is inferred from {node.kind.value} {node.name} in "
        f"{node.file_path}, assigned to {category}."
    )


def first_entity_for_node(
    node: CodeNode,
    category: str,
    by_category: dict[str, list[SemanticEntity]],
) -> SemanticEntity | None:
    wanted = set(entity_names_for_node(node))
    for entity in by_category.get(category, []):
        if entity.name in wanted:
            return entity
    entities = by_category.get(category, [])
    return entities[0] if entities else None


def infer_action(node: CodeNode) -> str:
    haystack = f"{node.name} {node.file_path} {node.content[:2000]}".lower()
    for action, pattern in _ACTION_PATTERNS:
        if re.search(pattern, haystack, re.I | re.S):
            return action
    return "REPRESENT"


def split_identifier(value: str) -> str:
    cleaned = value.replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or value


def entity_id(category: str, name: str) -> str:
    raw = f"{category}:{name}".lower()
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"entity:{digest}"
