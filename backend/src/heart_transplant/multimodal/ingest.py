from __future__ import annotations

from pathlib import Path

from heart_transplant.artifact_store import artifact_root, timestamp_slug, write_json
from heart_transplant.multimodal.correlator import correlate_openapi_to_routes, correlate_tests_to_sources
from heart_transplant.multimodal.flow_tracer import build_flow_hints
from heart_transplant.multimodal.models import MultimodalEdge, MultimodalIngestReport, MultimodalNode
from heart_transplant.multimodal.parsers.infra_parser import collect_infra_nodes
from heart_transplant.multimodal.parsers.openapi_parser import collect_openapi_nodes
from heart_transplant.multimodal.parsers.tests_parser import collect_test_nodes


def run_multimodal_ingest(
    directory: Path,
    *,
    include_tests: bool = True,
    include_infra: bool = True,
    write_artifact: Path | None = None,
) -> MultimodalIngestReport:
    root = directory.resolve()
    limitations = [
        "OpenAPI support is JSON only in this pass; YAML specs are skipped unless converted.",
        "Test-to-code mapping is heuristic (filename / stem matching).",
    ]

    nodes: list[MultimodalNode] = []
    edges: list[MultimodalEdge] = []
    if include_tests:
        tnodes = collect_test_nodes(root)
        nodes.extend(tnodes)
        edges.extend(correlate_tests_to_sources(tnodes, root))

    openapi_files: list[Path] = []
    onodes = collect_openapi_nodes(root)
    nodes.extend(onodes)
    for on in onodes:
        openapi_files.append(root / on.path)

    for oa in openapi_files:
        if oa.is_file():
            edges.extend(correlate_openapi_to_routes(oa, root))

    if include_infra:
        nodes.extend(collect_infra_nodes(root))

    nodes.extend(_materialize_codefile_nodes(root, nodes, edges))

    flow = build_flow_hints(openapi_files, root)

    dest = write_artifact or (artifact_root().parent / "reports" / f"{timestamp_slug()}__multimodal-ingest.json")
    dest.parent.mkdir(parents=True, exist_ok=True)

    report = MultimodalIngestReport(
        root=str(root),
        nodes=nodes,
        edges=edges,
        flow_hints=flow,
        limitations=limitations,
    )
    write_json(dest, report.model_dump(mode="json"))
    return report.model_copy(update={"limitations": [*limitations, f"Artifact written to {dest}"]})


def _materialize_codefile_nodes(
    root: Path,
    existing_nodes: list[MultimodalNode],
    edges: list[MultimodalEdge],
) -> list[MultimodalNode]:
    existing_ids = {node.node_id for node in existing_nodes}
    nodes: list[MultimodalNode] = []
    for target_id in sorted({edge.target_id for edge in edges if edge.target_id.startswith("codefile:")}):
        if target_id in existing_ids:
            continue
        rel = target_id.removeprefix("codefile:")
        path = root / rel
        if not path.is_file():
            continue
        nodes.append(
            MultimodalNode(
                node_id=target_id,
                kind="codefile",
                path=rel.replace("\\", "/"),
                name=path.name,
                meta={"materialized_from": "cross_layer_correlation"},
            )
        )
        existing_ids.add(target_id)
    return nodes
