from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from heart_transplant.artifact_store import read_json
from heart_transplant.blast_radius import compute_impact_subgraph
from heart_transplant.evals.gold_benchmark import build_block_benchmark_report, load_gold_set


class EvidenceNode(BaseModel):
    node_id: str
    kind: str
    file_path: str | None = None
    range: dict[str, int] | None = None
    label: str | None = None
    snippet: str | None = None


class EvidencePath(BaseModel):
    node_ids: list[str] = Field(default_factory=list)
    edge_types: list[str] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    query_type: str
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_nodes: list[EvidenceNode] = Field(default_factory=list)
    file_ranges: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[EvidencePath] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class QuestionIntent:
    blocks: tuple[str, ...]
    keywords: tuple[str, ...]
    requires_trace: bool = False


_BLOCK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Access Control": ("auth", "access", "permission", "role", "guard", "jwt", "session", "user"),
    "Identity UI": ("identity", "login", "signin", "profile", "account"),
    "Data Persistence": ("database", "db", "schema", "model", "migration", "prisma", "drizzle", "sql", "redis", "store"),
    "Persistence Strategy": ("cache", "redis", "store"),
    "Network Edge": ("route", "http", "request", "response", "endpoint", "middleware", "webhook", "server"),
    "Background Processing": ("queue", "worker", "job", "cron", "schedule", "background", "async"),
    "System Telemetry": ("log", "logger", "telemetry", "metric", "tracing", "observability", "sentry", "otel"),
    "Security Ops": ("secret", "encrypt", "decrypt", "hash", "csrf", "cors", "key", "token"),
    "Core Rendering": ("render", "component", "ui", "view", "page", "screen"),
    "Global Interface": ("config", "configuration", "environment", "env", "settings"),
}


def explain_node(artifact_dir: Path, node_id: str) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    node = graph["nodes_by_id"].get(node_id)
    if not node:
        return EvidenceBundle(
            query_type="explain_node",
            claim=f"No node found for {node_id}",
            confidence=0.0,
            limitations=["node_id was not present in structural artifact"],
        )
    neighbors = _incident_edges(graph, node_id)
    return EvidenceBundle(
        query_type="explain_node",
        claim=f"{node_id} is a {node.get('kind')} surface in {node.get('file_path') or 'the graph'}.",
        confidence=0.75,
        source_nodes=[_evidence_node(node)],
        file_ranges=_file_ranges([node]),
        paths=[EvidencePath(node_ids=[node_id], edge_types=[])],
        limitations=[f"{len(neighbors)} incident edges were found; semantic confidence depends on classifier output."],
    )


def explain_file(artifact_dir: Path, file_path: str) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    nodes = [node for node in graph["nodes_by_id"].values() if node.get("file_path") == file_path]
    if not nodes:
        return EvidenceBundle(
            query_type="explain_file",
            claim=f"No graph nodes found for {file_path}",
            confidence=0.0,
            limitations=["file was not materialized as a FileNode or CodeNode"],
        )
    blocks = _semantic_blocks(artifact_dir, [str(node["node_id"]) for node in nodes])
    label = ", ".join(sorted(set(blocks.values()))) if blocks else "unclassified"
    return EvidenceBundle(
        query_type="explain_file",
        claim=f"{file_path} has {len(nodes)} graph node(s) and block evidence: {label}.",
        confidence=0.7 if blocks else 0.45,
        source_nodes=[_evidence_node(node) for node in nodes[:20]],
        file_ranges=_file_ranges(nodes[:20]),
        limitations=[] if blocks else ["semantic-artifact.json missing or no block assignment for this file"],
    )


def trace_dependency(artifact_dir: Path, start_id: str, end_id: str, *, max_depth: int = 6) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    path = _bfs_path(graph, start_id, end_id, max_depth=max_depth)
    if not path:
        return EvidenceBundle(
            query_type="trace_dependency",
            claim=f"No dependency path found from {start_id} to {end_id} within depth {max_depth}.",
            confidence=0.25,
            limitations=["absence of a path may reflect incomplete extraction or SCIP fallback gaps"],
        )
    nodes = [graph["nodes_by_id"].get(node_id) for node_id in path["node_ids"]]
    return EvidenceBundle(
        query_type="trace_dependency",
        claim=f"Found path of {len(path['edge_types'])} edge(s) from {start_id} to {end_id}.",
        confidence=0.85,
        source_nodes=[_evidence_node(node) for node in nodes if node],
        file_ranges=_file_ranges([node for node in nodes if node]),
        paths=[EvidencePath(node_ids=path["node_ids"], edge_types=path["edge_types"])],
    )


def find_architectural_block(artifact_dir: Path, block_label: str, *, limit: int = 50) -> EvidenceBundle:
    sem = _load_semantic(artifact_dir)
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    nodes_by_id = _nodes_by_id(structural)
    matches = []
    for row in sem.get("block_assignments", []):
        secondary = [item.get("block") for item in row.get("secondary_blocks", []) if isinstance(item, dict)]
        if row.get("primary_block") == block_label or block_label in secondary:
            node = nodes_by_id.get(str(row.get("node_id", "")))
            if node:
                matches.append(node)
    return EvidenceBundle(
        query_type="find_architectural_block",
        claim=f"Found {len(matches)} node(s) assigned to {block_label}.",
        confidence=0.75 if matches else 0.35,
        source_nodes=[_evidence_node(node) for node in matches[:limit]],
        file_ranges=_file_ranges(matches[:limit]),
        limitations=[] if sem else ["semantic-artifact.json missing"],
    )


def impact_radius(artifact_dir: Path, start_id: str, *, max_depth: int = 3, max_nodes: int = 100) -> EvidenceBundle:
    try:
        impact = compute_impact_subgraph(start_id, max_depth=max_depth, max_nodes=max_nodes)
        return EvidenceBundle(
            query_type="impact_radius",
            claim=f"Impact radius from {start_id} reached {impact.get('node_count', 0)} node(s).",
            confidence=0.65,
            paths=[EvidencePath(node_ids=list(impact.get("nodes", [])), edge_types=[])],
            limitations=["impact_radius currently uses the configured graph DB; artifact_dir is retained for API symmetry"],
        )
    except Exception as exc:  # noqa: BLE001
        return EvidenceBundle(
            query_type="impact_radius",
            claim=f"Impact radius could not run for {start_id}.",
            confidence=0.0,
            limitations=[str(exc)],
        )


def answer_with_evidence(artifact_dir: Path, question: str) -> EvidenceBundle:
    intent = _plan_question(question)
    if intent.blocks:
        return _answer_from_ranked_evidence(artifact_dir, question, intent)
    return EvidenceBundle(
        query_type="unsupported",
        claim="Insufficient evidence to answer this architecture question with the current deterministic router.",
        confidence=0.0,
        limitations=["question router could not map the prompt onto a supported architecture block"],
    )


def benchmark_with_evidence(artifact_dir: Path, gold_set: Path) -> dict[str, Any]:
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    return build_block_benchmark_report(
        structural,
        load_gold_set(gold_set),
        artifact_dir=Path(artifact_dir),
        gold_set_path=gold_set,
    )


def _load_graph(artifact_dir: Path) -> dict[str, Any]:
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    return {"structural": structural, "nodes_by_id": _nodes_by_id(structural)}


def _nodes_by_id(structural: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    project = structural.get("project_node") or {}
    if project.get("node_id"):
        nodes[str(project["node_id"])] = {"node_id": project["node_id"], "kind": "project", **project}
    for node in structural.get("file_nodes", []):
        nodes[str(node["node_id"])] = {"kind": "file", **node}
    for node in structural.get("code_nodes", []):
        nodes[str(node.get("node_id") or node.get("scip_id"))] = {"node_id": node.get("node_id") or node.get("scip_id"), **node}
    return nodes


def _load_semantic(artifact_dir: Path) -> dict[str, Any]:
    path = Path(artifact_dir) / "semantic-artifact.json"
    return read_json(path) if path.is_file() else {}


def _semantic_rows_by_node(artifact_dir: Path) -> dict[str, dict[str, Any]]:
    sem = _load_semantic(artifact_dir)
    return {str(row.get("node_id")): row for row in sem.get("block_assignments", []) if row.get("node_id")}


def _semantic_blocks(artifact_dir: Path, node_ids: list[str]) -> dict[str, str]:
    sem = _load_semantic(artifact_dir)
    wanted = set(node_ids)
    return {
        str(row.get("node_id")): str(row.get("primary_block"))
        for row in sem.get("block_assignments", [])
        if str(row.get("node_id")) in wanted and row.get("primary_block")
    }


def _incident_edges(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [
        edge
        for edge in graph["structural"].get("edges", [])
        if edge.get("source_id") == node_id or edge.get("target_id") == node_id
    ]


def _bfs_path(graph: dict[str, Any], start_id: str, end_id: str, *, max_depth: int) -> dict[str, list[str]] | None:
    edges = graph["structural"].get("edges", [])
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        adjacency.setdefault(str(edge.get("source_id")), []).append((str(edge.get("target_id")), str(edge.get("edge_type"))))
    queue = deque([(start_id, [start_id], [])])
    seen = {start_id}
    while queue:
        node_id, path, edge_types = queue.popleft()
        if node_id == end_id:
            return {"node_ids": path, "edge_types": edge_types}
        if len(edge_types) >= max_depth:
            continue
        for nxt, edge_type in adjacency.get(node_id, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, [*path, nxt], [*edge_types, edge_type]))
    return None


def _evidence_node(node: dict[str, Any]) -> EvidenceNode:
    return EvidenceNode(
        node_id=str(node.get("node_id") or node.get("scip_id")),
        kind=str(node.get("kind", "")),
        file_path=node.get("file_path"),
        range=node.get("range") if isinstance(node.get("range"), dict) else None,
        label=str(node.get("name")) if node.get("name") else None,
        snippet=_snippet(node),
    )


def _file_ranges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for node in nodes:
        if node.get("file_path") and isinstance(node.get("range"), dict):
            out.append({"file_path": node["file_path"], "range": node["range"], "node_id": node.get("node_id") or node.get("scip_id")})
    return out


def _plan_question(question: str) -> QuestionIntent:
    q = question.lower()
    blocks: list[str] = []
    keywords: list[str] = []

    def add(block: str, *terms: str) -> None:
        if block not in blocks:
            blocks.append(block)
        for term in terms:
            if term not in keywords:
                keywords.append(term)

    if re.search(r"\b(auth|access|permission|role|rbac|guard|jwt|session|identity|user)\b", q):
        add("Access Control", "auth", "access", "permission", "role", "guard", "jwt", "session", "user")
    if re.search(r"\b(identity ui|login|sign[- ]?in|profile|account)\b", q):
        add("Identity UI", "identity", "login", "signin", "profile", "account")
    if re.search(r"\b(database|db|persistence|persist|schema|model|migration|prisma|drizzle|sql|redis|store)\b", q):
        add("Data Persistence", "database", "db", "schema", "model", "migration", "prisma", "drizzle", "sql", "redis", "store")
    if re.search(r"\b(cache|persistence strategy)\b", q):
        add("Persistence Strategy", "cache", "redis", "store")
    if re.search(r"\b(route|api|http|request|response|endpoint|middleware|webhook)\b", q):
        add("Network Edge", "route", "api", "http", "request", "response", "endpoint", "middleware")
    if re.search(r"\b(queue|worker|job|cron|schedule|background|async)\b", q):
        add("Background Processing", "queue", "worker", "job", "cron", "schedule", "background")
    if re.search(r"\b(log|logging|telemetry|metric|tracing|observability|sentry|otel)\b", q):
        add("System Telemetry", "log", "logger", "telemetry", "metric", "tracing", "observability")
    if re.search(r"\b(secret|encrypt|decrypt|hash|csrf|cors|key|token)\b", q):
        add("Security Ops", "secret", "encrypt", "decrypt", "hash", "csrf", "cors", "key", "token")
    if re.search(r"\b(render|component|ui|view|page|screen)\b", q):
        add("Core Rendering", "render", "component", "ui", "view", "page", "screen")
    if re.search(r"\b(config|configuration|environment|env|settings)\b", q):
        add("Global Interface", "config", "configuration", "environment", "env", "settings")
    if re.search(r"\b(trace|flow|from .* to |touch|impact|change)\b", q):
        return QuestionIntent(tuple(blocks), tuple(keywords), requires_trace=True)
    return QuestionIntent(tuple(blocks), tuple(keywords))


def _answer_from_ranked_evidence(artifact_dir: Path, question: str, intent: QuestionIntent) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    semantic_rows = _semantic_rows_by_node(artifact_dir)
    if not semantic_rows:
        return EvidenceBundle(
            query_type="answer_with_evidence",
            claim="No semantic-artifact.json assignments were available, so the question cannot be answered from block evidence.",
            confidence=0.0,
            limitations=["semantic-artifact.json missing or empty"],
        )

    nodes_by_id = graph["nodes_by_id"]
    ranked: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for node_id, row in semantic_rows.items():
        node = nodes_by_id.get(node_id)
        if not node:
            continue
        score = _score_candidate(node, row, intent)
        if score > 0:
            ranked.append((score, node, row))
    ranked.sort(key=lambda item: (-item[0], _is_test_path(str(item[1].get("file_path") or "")), str(item[1].get("file_path") or "")))

    chosen = _balanced_top_nodes(ranked, intent.blocks, per_block=4)
    if not chosen:
        return EvidenceBundle(
            query_type="answer_with_evidence",
            claim=f"No graph evidence matched the requested architecture concept(s): {', '.join(intent.blocks)}.",
            confidence=0.25,
            limitations=["semantic blocks exist, but none matched the question intent"],
        )

    source_nodes = [_evidence_node(node) for _score, node, _row in chosen]
    observed_blocks = set(intent.blocks).intersection(_blocks_for_rows([row for _score, _node, row in chosen]))
    confidence = _bundle_confidence(chosen, intent)
    paths = _paths_between_chosen_nodes(graph, [node for _score, node, _row in chosen])
    missing_blocks = [block for block in intent.blocks if block not in observed_blocks]
    limitations = []
    if missing_blocks:
        limitations.append(f"No selected evidence node covered expected block(s): {', '.join(missing_blocks)}")
    if not paths and intent.requires_trace and len(chosen) > 1:
        limitations.append("No explicit structural path connected the selected evidence nodes; answer is grouped evidence, not a proven flow trace.")

    return EvidenceBundle(
        query_type="answer_with_evidence",
        claim=_claim_for_answer(question, observed_blocks, source_nodes),
        confidence=confidence,
        source_nodes=source_nodes,
        file_ranges=_file_ranges([node for _score, node, _row in chosen]),
        paths=paths,
        limitations=limitations,
    )


def _score_candidate(node: dict[str, Any], row: dict[str, Any], intent: QuestionIntent) -> float:
    blocks = _blocks_for_rows([row])
    matched_blocks = set(intent.blocks).intersection(blocks)
    if not matched_blocks:
        return 0.0
    confidence = float(row.get("confidence") or 0.0)
    text = " ".join(
        str(part or "")
        for part in [
            node.get("file_path"),
            node.get("name"),
            node.get("kind"),
            row.get("reasoning"),
            node.get("content"),
        ]
    ).lower()
    block_keywords = {
        keyword
        for block in matched_blocks
        for keyword in _BLOCK_KEYWORDS.get(block, ())
    }
    keyword_hits = sum(1 for keyword in block_keywords if keyword and keyword.lower() in text)
    score = 3.0 * len(matched_blocks) + confidence * 3.0 + min(keyword_hits, 5) * 0.9
    if node.get("kind") == "file_surface":
        score -= 0.25
    if _is_test_path(str(node.get("file_path") or "")):
        score -= 1.5
    if intent.keywords and keyword_hits == 0:
        score -= 2.0
    if confidence < 0.35 and keyword_hits == 0:
        score -= 2.5
    return score


def _blocks_for_rows(rows: list[dict[str, Any]]) -> set[str]:
    blocks: set[str] = set()
    for row in rows:
        if row.get("primary_block"):
            blocks.add(str(row["primary_block"]))
        for secondary in row.get("secondary_blocks", []):
            if isinstance(secondary, dict) and secondary.get("block"):
                blocks.add(str(secondary["block"]))
    return blocks


def _balanced_top_nodes(
    ranked: list[tuple[float, dict[str, Any], dict[str, Any]]],
    blocks: tuple[str, ...],
    *,
    per_block: int,
) -> list[tuple[float, dict[str, Any], dict[str, Any]]]:
    chosen: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    seen_ids: set[str] = set()
    seen_file_block: set[tuple[str, str]] = set()
    for block in blocks:
        picked_for_block = 0
        block_ranked = sorted(ranked, key=lambda item: (-_score_for_block(item[1], item[2], block), _is_test_path(str(item[1].get("file_path") or ""))))
        for item in block_ranked:
            _score, node, row = item
            node_id = str(node.get("node_id") or node.get("scip_id"))
            file_path = str(node.get("file_path") or "")
            if node_id in seen_ids:
                continue
            if (file_path, block) in seen_file_block:
                continue
            if block in _blocks_for_rows([row]):
                chosen.append(item)
                seen_ids.add(node_id)
                seen_file_block.add((file_path, block))
                picked_for_block += 1
                if picked_for_block >= per_block:
                    break
    return chosen


def _score_for_block(node: dict[str, Any], row: dict[str, Any], block: str) -> float:
    primary = str(row.get("primary_block") or "")
    secondary_confidence = 0.0
    for secondary in row.get("secondary_blocks", []):
        if isinstance(secondary, dict) and secondary.get("block") == block:
            secondary_confidence = max(secondary_confidence, float(secondary.get("confidence") or 0.0))
    block_fit = float(row.get("confidence") or 0.0) if primary == block else secondary_confidence
    text = " ".join(
        str(part or "")
        for part in [node.get("file_path"), node.get("name"), node.get("kind"), row.get("reasoning"), node.get("content")]
    ).lower()
    keyword_hits = sum(1 for keyword in _BLOCK_KEYWORDS.get(block, ()) if keyword in text)
    score = block_fit * 4.0 + min(keyword_hits, 5) * 1.2
    if _is_test_path(str(node.get("file_path") or "")):
        score -= 2.0
    return score


def _paths_between_chosen_nodes(graph: dict[str, Any], nodes: list[dict[str, Any]]) -> list[EvidencePath]:
    ids = [str(node.get("node_id") or node.get("scip_id")) for node in nodes]
    out: list[EvidencePath] = []
    for start, end in zip(ids, ids[1:], strict=False):
        path = _bfs_path(graph, start, end, max_depth=4)
        if path:
            out.append(EvidencePath(node_ids=path["node_ids"], edge_types=path["edge_types"]))
        if len(out) >= 4:
            break
    return out


def _bundle_confidence(chosen: list[tuple[float, dict[str, Any], dict[str, Any]]], intent: QuestionIntent) -> float:
    observed = _blocks_for_rows([row for _score, _node, row in chosen])
    coverage = len(set(intent.blocks).intersection(observed)) / max(len(intent.blocks), 1)
    avg_semantic = sum(float(row.get("confidence") or 0.0) for _score, _node, row in chosen[:8]) / max(min(len(chosen), 8), 1)
    return round(min(0.25 + coverage * 0.45 + avg_semantic * 0.3, 0.95), 3)


def _claim_for_answer(question: str, observed_blocks: set[str], source_nodes: list[EvidenceNode]) -> str:
    files = sorted({node.file_path for node in source_nodes if node.file_path})
    block_text = ", ".join(sorted(observed_blocks)) or "unclassified architecture evidence"
    file_text = ", ".join(files[:5])
    suffix = f" Evidence starts in {file_text}." if file_text else ""
    return f"Question: {question} Matched block evidence for {block_text}.{suffix}"


def _snippet(node: dict[str, Any]) -> str | None:
    content = str(node.get("content") or "").strip()
    if not content:
        return None
    snippet = re.sub(r"\s+", " ", content[:240]).strip()
    return snippet.encode("ascii", errors="backslashreplace").decode("ascii")


def _is_test_path(path: str) -> bool:
    return bool(re.search(r"(^|/)(tests?|__tests__)/|(_test|\.test|\.spec)\.", path, re.I))
