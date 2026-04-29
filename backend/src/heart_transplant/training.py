from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import persist_structural_artifact, read_json, write_json
from heart_transplant.canonical_graph import build_canonical_graph, write_canonical_graph
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.ingest.treesitter_ingest import ingest_repository


ARCHITECTURE_BLOCK_QUESTIONS = {
    "Access Control": "Where is auth or access control handled?",
    "Data Persistence": "Where is database persistence handled?",
    "Persistence Strategy": "Where is cache or persistence strategy handled?",
    "Network Edge": "Where are routes or API entry points handled?",
    "Background Processing": "Where are queue, worker, or background jobs handled?",
    "System Telemetry": "Where is logging or telemetry handled?",
    "Global Interface": "Where is environment or global configuration handled?",
}

SCENARIO_TEMPLATES = {
    "Access Control": "Replace or centralize the auth/session provider.",
    "Data Persistence": "Replace the database client or persistence adapter.",
    "Persistence Strategy": "Replace the cache implementation or persistence strategy.",
    "Network Edge": "Change an API route contract or route middleware behavior.",
    "Background Processing": "Replace or reorganize the queue/worker provider.",
    "System Telemetry": "Standardize logging and telemetry output.",
    "Global Interface": "Rename or restructure environment/configuration variables.",
}


def build_training_packet(
    target: Path,
    *,
    repo_name: str | None = None,
    out_dir: Path | None = None,
    classify: bool = True,
    with_scip: bool = False,
    install_deps: bool = False,
    use_openai: bool = False,
) -> dict[str, Any]:
    """Create a human-review packet from a repo or existing artifact.

    This is the labeling entrypoint for non-implementers: the system generates
    candidates and humans mark them correct / wrong / missing.
    """

    artifact_dir = ensure_artifact(target, repo_name=repo_name)
    if classify and not (artifact_dir / "semantic-artifact.json").is_file():
        run_classification_on_artifact(artifact_dir, use_openai=use_openai)

    graph = build_canonical_graph(artifact_dir)
    out = (out_dir or artifact_dir / "training-packet").resolve()
    out.mkdir(parents=True, exist_ok=True)

    packet = {
        "report_type": "fixture_training_packet",
        "artifact_dir": str(artifact_dir),
        "repo_name": graph.get("repo_name"),
        "review_protocol": {
            "labels": ["correct", "wrong", "missing_important_context", "not_sure"],
            "instruction": "Review generated candidates. Do not hand-search first; mark what the system surfaced and add missing items only when obvious.",
        },
        "candidate_nodes": candidate_nodes(graph),
        "candidate_reference_edges": candidate_reference_edges(graph),
        "candidate_evidence_questions": candidate_evidence_questions(graph),
        "candidate_blast_radius_scenarios": candidate_blast_radius_scenarios(graph),
    }

    write_json(out / "fixture-candidates.json", packet)
    write_json(out / "candidate_nodes.review.json", packet["candidate_nodes"])
    write_json(out / "candidate_reference_edges.review.json", packet["candidate_reference_edges"])
    write_json(out / "candidate_evidence_questions.review.json", packet["candidate_evidence_questions"])
    write_json(out / "candidate_blast_radius_scenarios.review.json", packet["candidate_blast_radius_scenarios"])
    write_json(out / "review-nodes.json", packet["candidate_nodes"])
    write_json(out / "review-edges.json", packet["candidate_reference_edges"])
    write_json(out / "review-questions.json", packet["candidate_evidence_questions"])
    write_json(out / "review-evidence-questions.json", packet["candidate_evidence_questions"])
    write_json(out / "review-scenarios.json", packet["candidate_blast_radius_scenarios"])
    write_json(out / "review-blast-radius-scenarios.json", packet["candidate_blast_radius_scenarios"])
    write_json(out / "canonical-graph.snapshot.json", graph)
    (out / "README.md").write_text(review_readme(packet), encoding="utf-8")

    return {
        "report_type": "training_packet",
        "packet_dir": str(out),
        "artifact_dir": str(artifact_dir),
        "repo_name": graph.get("repo_name"),
        "counts": {
            "candidate_nodes": len(packet["candidate_nodes"]),
            "candidate_reference_edges": len(packet["candidate_reference_edges"]),
            "candidate_evidence_questions": len(packet["candidate_evidence_questions"]),
            "candidate_blast_radius_scenarios": len(packet["candidate_blast_radius_scenarios"]),
        },
        "files": [
            str(out / "README.md"),
            str(out / "fixture-candidates.json"),
            str(out / "candidate_nodes.review.json"),
            str(out / "candidate_reference_edges.review.json"),
            str(out / "candidate_evidence_questions.review.json"),
            str(out / "candidate_blast_radius_scenarios.review.json"),
            str(out / "review-nodes.json"),
            str(out / "review-edges.json"),
            str(out / "review-questions.json"),
            str(out / "review-scenarios.json"),
            str(out / "canonical-graph.snapshot.json"),
        ],
    }


def ensure_artifact(target: Path, *, repo_name: str | None = None) -> Path:
    target = target.resolve()
    if (target / "structural-artifact.json").is_file():
        return target
    artifact = ingest_repository(target, repo_name or target.name)
    return persist_structural_artifact(artifact)


def candidate_nodes(graph: dict[str, Any], *, limit: int = 80) -> list[dict[str, Any]]:
    semantic_by_target = semantic_labels_by_target(graph)
    nodes = []
    for node in graph.get("nodes", []):
        if node.get("layer") not in {"code", "file"}:
            continue
        node_id = str(node.get("node_id"))
        labels = semantic_by_target.get(node_id, [])
        if not labels and node.get("kind") not in {"file_surface", "route_handler", "service_boundary", "config_object", "db_model"}:
            continue
        nodes.append(
            {
                "node_id": node_id,
                "kind": node.get("kind"),
                "file_path": node.get("file_path"),
                "label": node.get("label"),
                "suggested_blocks": labels,
                "review": "unreviewed",
                "human_notes": "",
            }
        )
    return sorted(nodes, key=lambda item: (str(item.get("file_path")), str(item.get("kind")), str(item.get("label"))))[:limit]


def candidate_reference_edges(graph: dict[str, Any], *, limit: int = 120) -> list[dict[str, Any]]:
    nodes = {str(node.get("node_id")): node for node in graph.get("nodes", [])}
    wanted = {"REFERENCES", "CROSS_REFERENCE", "DEPENDS_ON_FILE", "IMPORTS_MODULE", "IMPLEMENTS", "PERFORMS_AUTHORIZE", "PERFORMS_PERSIST", "PERFORMS_CONNECT"}
    edges = []
    for edge in graph.get("edges", []):
        edge_type = str(edge.get("edge_type"))
        if edge_type not in wanted and not edge_type.startswith("PERFORMS_"):
            continue
        source = nodes.get(str(edge.get("source_id")), {})
        target = nodes.get(str(edge.get("target_id")), {})
        edges.append(
            {
                "source_id": edge.get("source_id"),
                "source_file": source.get("file_path"),
                "source_label": source.get("label"),
                "target_id": edge.get("target_id"),
                "target_file": target.get("file_path"),
                "target_label": target.get("label"),
                "relationship": edge_type,
                "resolution_expectation": "not_sure",
                "review": "unreviewed",
                "human_notes": "",
            }
        )
    return edges[:limit]


def candidate_evidence_questions(graph: dict[str, Any]) -> list[dict[str, Any]]:
    by_block = files_by_block(graph)
    questions = []
    for block, question in ARCHITECTURE_BLOCK_QUESTIONS.items():
        files = sorted(by_block.get(block, set()))
        if not files:
            continue
        questions.append(
            {
                "id": slug(f"{graph.get('repo_name')}-{block}"),
                "question": question,
                "expected_blocks": [block],
                "expected_files": files[:8],
                "expected_file_globs": [],
                "unsupported": False,
                "review": "unreviewed",
                "human_notes": "",
            }
        )
    questions.extend(
        [
            {
                "id": "unsupported-kafka",
                "question": "Where is Kafka configured?",
                "expected_blocks": [],
                "expected_files": [],
                "expected_file_globs": [],
                "unsupported": True,
                "review": "unreviewed",
                "human_notes": "Mark correct if this repo does not use Kafka.",
            },
            {
                "id": "unsupported-graphql",
                "question": "Where is GraphQL schema execution configured?",
                "expected_blocks": [],
                "expected_files": [],
                "expected_file_globs": [],
                "unsupported": True,
                "review": "unreviewed",
                "human_notes": "Mark correct if this repo does not use GraphQL.",
            },
        ]
    )
    return questions


def candidate_blast_radius_scenarios(graph: dict[str, Any]) -> list[dict[str, Any]]:
    by_block = files_by_block(graph)
    all_files = sorted({path for paths in by_block.values() for path in paths})
    scenarios = []
    for block, change in SCENARIO_TEMPLATES.items():
        impacted = sorted(by_block.get(block, set()))
        if not impacted:
            continue
        should_not = [path for path in all_files if path not in set(impacted)][:5]
        scenarios.append(
            {
                "id": slug(f"{graph.get('repo_name')}-{block}-change"),
                "change": change,
                "expected_impacted_files": impacted[:10],
                "expected_impacted_blocks": [block],
                "should_not_impact": should_not,
                "risk_level": "not_sure",
                "validation_command": "",
                "review": "unreviewed",
                "human_notes": "",
            }
        )
    return scenarios


def semantic_labels_by_target(graph: dict[str, Any]) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = defaultdict(list)
    for edge in graph.get("edges", []):
        if edge.get("edge_type") not in {"DESCRIBES", "SECONDARY_DESCRIBES"}:
            continue
        source_id = str(edge.get("source_id"))
        target_id = str(edge.get("target_id"))
        semantic_node = next((node for node in graph.get("nodes", []) if node.get("node_id") == source_id), None)
        if semantic_node and semantic_node.get("label"):
            labels[target_id].append(str(semantic_node["label"]))
    return labels


def files_by_block(graph: dict[str, Any]) -> dict[str, set[str]]:
    by_id = {str(node.get("node_id")): node for node in graph.get("nodes", [])}
    out: dict[str, set[str]] = defaultdict(set)
    for edge in graph.get("edges", []):
        if edge.get("edge_type") not in {"DESCRIBES", "SECONDARY_DESCRIBES"}:
            continue
        semantic = by_id.get(str(edge.get("source_id")), {})
        target = by_id.get(str(edge.get("target_id")), {})
        block = semantic.get("label")
        file_path = target.get("file_path")
        if block and file_path:
            out[str(block)].add(str(file_path))
    return out


def review_readme(packet: dict[str, Any]) -> str:
    return f"""# LogicLens Fixture Review Packet

Repo: `{packet.get('repo_name')}`

This packet was generated by `heart-transplant fixture-candidates`.

## What to do

Open the `*.review.json` files and change each `review` field from `unreviewed` to one of:

- `correct`
- `wrong`
- `missing_important_context`
- `not_sure`

Add notes in `human_notes`.

## Files

- `candidate_nodes.review.json`: architecture surfaces the system thinks matter.
- `candidate_reference_edges.review.json`: graph edges the system thinks may matter.
- `candidate_evidence_questions.review.json`: questions and expected evidence candidates.
- `candidate_blast_radius_scenarios.review.json`: change-impact scenarios.
- `canonical-graph.snapshot.json`: source graph snapshot for this packet.

You do not need to grep the repo. Review what the system surfaced and add missing items only when obvious.
"""


def slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-").replace("--", "-")
