from __future__ import annotations

from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import artifact_root, read_json
from heart_transplant.graph_smoke import run_graph_smoke
from heart_transplant.ingest.treesitter_ingest import ingest_repository


def latest_artifact_dir(root: Path | None = None) -> Path:
    search_root = (root or artifact_root()).resolve()
    candidates = [path for path in search_root.iterdir() if path.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No artifact directories found under {search_root}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def run_validation_gates(repo_path: Path, artifact_dir: Path) -> dict[str, Any]:
    repo_path = repo_path.resolve()
    artifact_dir = artifact_dir.resolve()

    structural = read_json(artifact_dir / "structural-artifact.json")
    repo_name = str(structural["repo_name"])
    fresh_ingest = ingest_repository(repo_path=repo_path, repo_name=repo_name)
    graph_report = run_graph_smoke(artifact_dir)
    scip_metadata = read_json(artifact_dir / "scip-index.json") if (artifact_dir / "scip-index.json").exists() else None
    scip_consumed = read_json(artifact_dir / "scip-consumed.json") if (artifact_dir / "scip-consumed.json").exists() else None

    gates = [
        build_gate(
            gate_id="structural_ingest_produces_nodes",
            description="Tree-sitter ingest over a real repo must emit code nodes and parser backends.",
            inputs={
                "repo_path": str(repo_path),
                "repo_name": repo_name,
            },
            outputs={
                "node_count": fresh_ingest.node_count,
                "edge_count": fresh_ingest.edge_count,
                "parser_backends": fresh_ingest.parser_backends,
            },
            pass_condition=fresh_ingest.node_count > 0 and len(fresh_ingest.parser_backends) > 0,
            criteria=[
                "node_count > 0",
                "parser_backends is not empty",
            ],
        ),
        build_gate(
            gate_id="artifact_contains_expected_files",
            description="The persisted artifact directory must contain the files we claim to have produced.",
            inputs={
                "artifact_dir": str(artifact_dir),
            },
            outputs={
                "structural_artifact_exists": (artifact_dir / "structural-artifact.json").exists(),
                "index_scip_exists": (artifact_dir / "index.scip").exists(),
                "scip_index_json_exists": (artifact_dir / "scip-index.json").exists(),
                "scip_consumed_json_exists": (artifact_dir / "scip-consumed.json").exists(),
            },
            pass_condition=all(
                [
                    (artifact_dir / "structural-artifact.json").exists(),
                    (artifact_dir / "index.scip").exists(),
                    (artifact_dir / "scip-index.json").exists(),
                    (artifact_dir / "scip-consumed.json").exists(),
                ]
            ),
            criteria=[
                "structural-artifact.json exists",
                "index.scip exists",
                "scip-index.json exists",
                "scip-consumed.json exists",
            ],
        ),
        build_gate(
            gate_id="graph_smoke_structure_is_consistent",
            description="The stored graph must at least be structurally self-consistent.",
            inputs={
                "artifact_dir": str(artifact_dir),
            },
            outputs={
                "node_count": graph_report["node_count"],
                "contains_edge_count": graph_report["contains_edge_count"],
                "missing_containment": graph_report["missing_containment"],
                "scip_present": graph_report["scip_present"],
            },
            pass_condition=(
                int(graph_report["node_count"]) > 0
                and int(graph_report["contains_edge_count"]) > 0
                and list(graph_report["missing_containment"]) == []
            ),
            criteria=[
                "node_count > 0",
                "contains_edge_count > 0",
                "missing_containment is empty",
            ],
        ),
        build_gate(
            gate_id="scip_metadata_is_real",
            description="The artifact must record a real SCIP indexer invocation and output path.",
            inputs={
                "artifact_dir": str(artifact_dir),
            },
            outputs={
                "indexer": scip_metadata["indexer"] if scip_metadata else None,
                "version": scip_metadata["version"] if scip_metadata else None,
                "output_path": scip_metadata["output_path"] if scip_metadata else None,
                "output_exists": Path(str(scip_metadata["output_path"])).exists() if scip_metadata else False,
            },
            pass_condition=bool(
                scip_metadata
                and scip_metadata.get("indexer") == "scip-typescript"
                and scip_metadata.get("version")
                and Path(str(scip_metadata["output_path"])).exists()
            ),
            criteria=[
                "scip-index.json exists",
                "indexer == scip-typescript",
                "version is present",
                "output_path exists",
            ],
        ),
        build_gate(
            gate_id="scip_actually_resolves_nodes",
            description="SCIP must do more than exist: it must resolve real CodeNode identities in the artifact.",
            inputs={
                "artifact_dir": str(artifact_dir),
            },
            outputs={
                "resolved_code_nodes": scip_consumed["resolution"]["resolved_code_nodes"] if scip_consumed else None,
                "total_code_nodes": scip_consumed["resolution"]["total_code_nodes"] if scip_consumed else None,
                "unresolved_code_nodes": scip_consumed["resolution"]["unresolved_code_nodes"] if scip_consumed else None,
                "implementation_edge_count": len(scip_consumed.get("implementation_edges", [])) if scip_consumed else None,
            },
            pass_condition=bool(
                scip_consumed
                and int(scip_consumed["resolution"]["resolved_code_nodes"]) > 0
            ),
            criteria=[
                "resolved_code_nodes > 0",
            ],
            notes=[
                "This gate is intentionally strict. It is allowed to fail today if SCIP is present but not yet linked correctly.",
            ],
        ),
    ]

    passed = sum(1 for gate in gates if gate["status"] == "pass")
    failed = sum(1 for gate in gates if gate["status"] == "fail")

    return {
        "repo_path": str(repo_path),
        "artifact_dir": str(artifact_dir),
        "summary": {
            "total_gates": len(gates),
            "passed": passed,
            "failed": failed,
            "overall_status": "pass" if failed == 0 else "fail",
        },
        "gates": gates,
    }


def build_gate(
    *,
    gate_id: str,
    description: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    pass_condition: bool,
    criteria: list[str],
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "description": description,
        "status": "pass" if pass_condition else "fail",
        "inputs": inputs,
        "outputs": outputs,
        "criteria": criteria,
        "notes": notes or [],
    }
