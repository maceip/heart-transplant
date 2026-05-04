from __future__ import annotations

from pathlib import Path
from typing import Any

from heart_transplant.artifact_manifest import write_artifact_manifest
from heart_transplant.artifact_store import persist_structural_artifact, write_json
from heart_transplant.canonical_graph import build_canonical_graph, write_canonical_graph
from heart_transplant.causal.simulation import run_change_simulation
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.evidence import answer_with_evidence
from heart_transplant.graph_integrity import run_graph_integrity
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.multimodal.ingest import run_multimodal_ingest
from heart_transplant.regret.scan import run_regret_sdk_scan
from heart_transplant.scip_consume import consume_scip_artifact
from heart_transplant.scip_typescript import run_scip_typescript_index
from heart_transplant.validation_gates import run_validation_gates


DEMO_QUESTIONS: tuple[str, ...] = (
    "Which files own authentication or access control?",
    "Where is database persistence handled?",
    "Where are routes or HTTP entry points handled?",
    "Where are queue, worker, or background jobs handled?",
    "Where is logging or telemetry handled?",
    "Where is environment or global configuration handled?",
    "Which files render UI components?",
)


DEMO_SIMULATIONS: tuple[tuple[str, str], ...] = (
    ("Access Control", "Replace or centralize the auth/session provider."),
    ("Data Persistence", "Replace the database client or persistence adapter."),
    ("Network Edge", "Change an API route contract or route middleware behavior."),
)


def run_logiclens_demo(
    target: Path,
    *,
    repo_name: str | None = None,
    out_dir: Path | None = None,
    with_scip: bool = False,
    install_deps: bool = False,
    use_openai: bool = False,
    mc_runs: int = 32,
    min_regret_confidence: float = 0.35,
) -> dict[str, Any]:
    """End-to-end LogicLens demonstration over a single repo.

    Runs ingest, optional SCIP, semantic classification, multimodal correlation,
    canonical-graph projection, evidence-grounded Q&A, blast-radius simulation,
    regret SDK scan, validation gates, and graph integrity. Writes a demo packet
    (JSON + markdown console) and returns a launch-ready summary.
    """

    target = target.resolve()
    artifact_dir = _ensure_artifact(target, repo_name=repo_name)

    scip: dict[str, Any] | None = None
    scip_consumed: dict[str, Any] | None = None
    if with_scip and target.is_dir() and not (target / "structural-artifact.json").is_file():
        meta = run_scip_typescript_index(target, repo_name or target.name, artifact_dir, install_deps=install_deps)
        write_json(artifact_dir / "scip-index.json", meta.model_dump(mode="json"))
        scip = meta.model_dump(mode="json")
        scip_consumed = consume_scip_artifact(artifact_dir, global_symbol_index_path=None)
        write_json(artifact_dir / "scip-consumed.json", scip_consumed)

    sem_path = artifact_dir / "semantic-artifact.json"
    if not sem_path.is_file():
        run_classification_on_artifact(artifact_dir, use_openai=use_openai)

    multimodal_dest = artifact_dir / "multimodal-ingest.json"
    structural_repo = _structural_repo_path(artifact_dir)
    multimodal_root = structural_repo if structural_repo and structural_repo.is_dir() else target
    if multimodal_root.is_dir():
        run_multimodal_ingest(multimodal_root, write_artifact=multimodal_dest)

    canonical = build_canonical_graph(
        artifact_dir,
        multimodal_report=multimodal_dest if multimodal_dest.is_file() else None,
    )
    canonical_path = artifact_dir / "canonical-graph.json"
    write_canonical_graph(canonical, canonical_path)

    integrity = run_graph_integrity(artifact_dir)
    answers = [_answer_question(artifact_dir, q) for q in DEMO_QUESTIONS]

    simulations = []
    for label, change in DEMO_SIMULATIONS:
        try:
            sim = run_change_simulation(change, artifact_dir, mc_runs=mc_runs)
            simulations.append(
                {
                    "scenario": label,
                    "change": change,
                    "impacted_file_count": len(sim.impacted_file_paths),
                    "impacted_node_count": len(sim.impacted_node_ids),
                    "confidence": sim.confidence,
                    "self_consistency": sim.self_consistency_score,
                    "top_files": sim.impacted_file_paths[:10],
                }
            )
        except Exception as exc:  # noqa: BLE001
            simulations.append({"scenario": label, "change": change, "error": str(exc)})

    regret = run_regret_sdk_scan(artifact_dir, min_confidence=min_regret_confidence)

    validation_repo = structural_repo if structural_repo and structural_repo.is_dir() else target
    try:
        gates = run_validation_gates(validation_repo, artifact_dir)
    except Exception as exc:  # noqa: BLE001
        gates = {"error": str(exc), "summary": {"overall_status": "error"}}

    manifest = write_artifact_manifest(artifact_dir, command="logiclens-demo")

    summary = {
        "repo_name": canonical.get("repo_name"),
        "artifact_dir": str(artifact_dir),
        "node_count": len(canonical.get("nodes", [])),
        "edge_count": len(canonical.get("edges", [])),
        "answered_questions": sum(1 for a in answers if a["confidence"] >= 0.5),
        "total_questions": len(answers),
        "regret_surface_count": len(regret.surfaces),
        "graph_integrity_status": integrity.get("summary", {}).get("status") or _integrity_status(integrity),
        "validation_status": (gates.get("summary") or {}).get("overall_status"),
    }

    report = {
        "report_type": "logiclens_demo",
        "summary": summary,
        "manifest": manifest,
        "scip": {"index": scip, "consumed": scip_consumed} if (scip or scip_consumed) else None,
        "canonical_graph": {
            "path": str(canonical_path),
            "node_count": len(canonical.get("nodes", [])),
            "edge_count": len(canonical.get("edges", [])),
            "layers": _layer_counts(canonical),
        },
        "graph_integrity": integrity,
        "evidence_answers": answers,
        "simulations": simulations,
        "regret": regret.model_dump(mode="json"),
        "validation_gates": gates,
    }

    packet_dir = (out_dir or artifact_dir / "demo").resolve()
    packet_dir.mkdir(parents=True, exist_ok=True)
    write_json(packet_dir / "logiclens-demo.json", report)
    (packet_dir / "logiclens-demo.md").write_text(_render_console(report), encoding="utf-8")

    return {
        "report_type": "logiclens_demo",
        "summary": summary,
        "packet_dir": str(packet_dir),
        "artifact_dir": str(artifact_dir),
        "files": [
            str(packet_dir / "logiclens-demo.json"),
            str(packet_dir / "logiclens-demo.md"),
            str(canonical_path),
            str(artifact_dir / "structural-artifact.json"),
            str(sem_path),
        ],
    }


def _ensure_artifact(target: Path, *, repo_name: str | None) -> Path:
    if (target / "structural-artifact.json").is_file():
        return target
    art = ingest_repository(target, repo_name or target.name)
    return persist_structural_artifact(art)


def _structural_repo_path(artifact_dir: Path) -> Path | None:
    structural = artifact_dir / "structural-artifact.json"
    if not structural.is_file():
        return None
    import json

    data = json.loads(structural.read_text(encoding="utf-8"))
    raw = data.get("repo_path")
    return Path(str(raw)).resolve() if raw else None


def _answer_question(artifact_dir: Path, question: str) -> dict[str, Any]:
    bundle = answer_with_evidence(artifact_dir, question)
    return {
        "question": question,
        "claim": bundle.claim,
        "confidence": bundle.confidence,
        "source_node_count": len(bundle.source_nodes),
        "files": sorted({n.file_path for n in bundle.source_nodes if n.file_path})[:10],
        "limitations": bundle.limitations,
    }


def _layer_counts(canonical: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in canonical.get("nodes", []):
        layer = str(node.get("layer") or "unknown")
        counts[layer] = counts.get(layer, 0) + 1
    return counts


def _integrity_status(integrity: dict[str, Any]) -> str:
    checks = integrity.get("checks") or []
    if any(c.get("status") == "fail" for c in checks):
        return "fail"
    if any(c.get("status") == "warn" for c in checks):
        return "warn"
    return "pass"


def _render_console(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        f"# LogicLens demo — {s.get('repo_name') or 'unknown'}",
        "",
        f"- Artifact: `{s['artifact_dir']}`",
        f"- Canonical graph: {s['node_count']} nodes / {s['edge_count']} edges",
        f"- Evidence Q&A: {s['answered_questions']}/{s['total_questions']} answered with confidence >= 0.5",
        f"- Regret surfaces: {s['regret_surface_count']}",
        f"- Graph integrity: {s['graph_integrity_status']}",
        f"- Validation gates: {s['validation_status']}",
        "",
        "## Canonical layers",
    ]
    for layer, count in sorted(report["canonical_graph"]["layers"].items()):
        lines.append(f"- {layer}: {count}")
    lines.extend(["", "## Evidence answers"])
    for answer in report["evidence_answers"]:
        lines.append(f"### {answer['question']}")
        lines.append(f"- claim: {answer['claim']}")
        lines.append(f"- confidence: {answer['confidence']:.2f}")
        if answer["files"]:
            lines.append("- files:")
            for path in answer["files"]:
                lines.append(f"  - `{path}`")
        lines.append("")
    lines.append("## Blast-radius simulations")
    for sim in report["simulations"]:
        if "error" in sim:
            lines.append(f"- {sim['scenario']}: error — {sim['error']}")
            continue
        lines.append(
            f"- {sim['scenario']}: {sim['impacted_file_count']} files / {sim['impacted_node_count']} nodes"
            f", confidence {sim['confidence']:.2f}, self-consistency {sim['self_consistency']:.2f}"
        )
    lines.extend(["", "## Regret SDK"])
    surfaces = report["regret"].get("surfaces", [])
    if not surfaces:
        lines.append("- no regrets detected above threshold")
    else:
        for surface in surfaces[:10]:
            regret = surface.get("regret", {})
            lines.append(
                f"- {regret.get('regret_id', '?')}: {regret.get('summary', '')} (confidence {regret.get('confidence', 0):.2f})"
            )
    return "\n".join(lines) + "\n"
