from __future__ import annotations

from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json, write_json
from heart_transplant.generated import scip_pb2
from heart_transplant.ingest.neighborhoods import build_neighborhood_index
from heart_transplant.models import CodeNode, FileNode, ProjectNode, StructuralEdge
from heart_transplant.scip.path_normalization import build_file_uri, normalize_relative_path
from heart_transplant.scip.symbol_index import load_symbol_index, resolve_cross_repo_target

DEFINITION_ROLE = int(scip_pb2.SymbolRole.Value("Definition"))

ADDRESSABLE_SCIP_KINDS = frozenset(
    {
        "Class",
        "Constant",
        "Constructor",
        "Enum",
        "Function",
        "Interface",
        "Method",
        "Module",
        "Namespace",
        "StaticMethod",
        "StaticVariable",
        "TypeAlias",
        "Variable",
    }
)


def consume_scip_artifact(
    artifact_dir: Path,
    *,
    global_symbol_index_path: Path | None = None,
) -> dict[str, Any]:
    artifact_dir = artifact_dir.resolve()
    structural_path = artifact_dir / "structural-artifact.json"
    scip_path = artifact_dir / "index.scip"

    structural = read_json(structural_path)
    index = scip_pb2.Index()
    index.ParseFromString(scip_path.read_bytes())

    repo_path = Path(structural["repo_path"])
    local_repo = str(structural["repo_name"])
    symbol_info = build_symbol_info_map(index)
    global_symbol_map: dict[str, list[dict[str, str]]] | None = None
    if global_symbol_index_path and global_symbol_index_path.is_file():
        global_symbol_map = load_symbol_index(global_symbol_index_path)

    implementation_edges: list[dict[str, str]] = []
    structural_edges: list[dict[str, Any]] = list(structural["edges"])
    resolved_definitions = 0
    reference_edges_code = 0
    reference_edges_file = 0
    cross_ref_edges = 0
    documents_report: list[dict[str, Any]] = []
    orphaned_symbols: list[dict[str, Any]] = []

    nodes_by_file: dict[str, list[dict[str, Any]]] = {}
    for node in structural["code_nodes"]:
        nodes_by_file.setdefault(normalize_relative_path(str(node["file_path"])), []).append(node)

    # —— Pass 1: definitions (resolve Tree-sitter nodes, DEFINES, IMPLEMENTS) ——
    for document in index.documents:
        relative_path = normalize_relative_path(document.relative_path)
        file_nodes = nodes_by_file.get(relative_path, [])
        file_text = load_document_text(repo_path, document, relative_path)
        definition_count = 0

        for occurrence in document.occurrences:
            if not occurrence.symbol:
                continue
            if not bool(occurrence.symbol_roles & DEFINITION_ROLE):
                continue
            definition_count += 1
            resolution = resolve_definition_occurrence(
                occurrence=occurrence,
                document=document,
                relative_path=relative_path,
                file_text=file_text,
                file_nodes=file_nodes,
                symbol_info=symbol_info,
            )
            if resolution["matched_node"] is not None:
                resolved_definitions += resolution["resolved_count"]
                rewrite_edge_targets(
                    structural_edges,
                    old_target_ids=resolution["old_target_ids"],
                    new_target_id=resolution["matched_node"]["scip_id"],
                )
                structural_edges.append(
                    {
                        "source_id": occurrence.symbol,
                        "target_id": resolution["matched_node"]["scip_id"],
                        "edge_type": "DEFINES",
                        "repo_name": local_repo,
                        "provenance": "scip_definition",
                    }
                )
            elif resolution["orphaned_symbol"] is not None:
                orphaned_symbols.append(resolution["orphaned_symbol"])

        for symbol in document.symbols:
            for relationship in symbol.relationships:
                if relationship.is_implementation:
                    implementation_edges.append(
                        {
                            "source_symbol": symbol.symbol,
                            "target_symbol": relationship.symbol,
                            "is_reference": relationship.is_reference,
                            "is_definition": relationship.is_definition,
                        }
                    )
                    structural_edges.append(
                        {
                            "source_id": symbol.symbol,
                            "target_id": relationship.symbol,
                            "edge_type": "IMPLEMENTS",
                            "repo_name": local_repo,
                        }
                    )

    # Rebuild name-based lookup after all definitions patched nodes in place
    symbol_to_resolved_id: dict[str, str] = {}
    for node in structural["code_nodes"]:
        if node.get("symbol_source") == "scip" and node.get("scip_id"):
            symbol_to_resolved_id[str(node["scip_id"])] = str(node["scip_id"])

    # —— Pass 2: references (code → code where possible) ——
    for document in index.documents:
        relative_path = normalize_relative_path(document.relative_path)
        file_nodes = nodes_by_file.get(relative_path, [])
        file_text = load_document_text(repo_path, document, relative_path)

        for occurrence in document.occurrences:
            if not occurrence.symbol:
                continue
            if bool(occurrence.symbol_roles & DEFINITION_ROLE):
                continue
            ref_line = occurrence.range[0] + 1 if occurrence.range else 1
            from_node = find_containing_code_node(file_nodes, ref_line, occurrence.range)
            target_sym = occurrence.symbol
            to_id = symbol_to_resolved_id.get(target_sym)
            t_repo: str | None = None
            etype = "REFERENCES"
            if to_id is None and global_symbol_map is not None:
                cross_id, t_repo = resolve_cross_repo_target(
                    target_sym,
                    local_repo,
                    from_node["scip_id"] if from_node else None,
                    global_symbol_map,
                )
                if cross_id and t_repo and t_repo != local_repo:
                    to_id = cross_id
                    etype = "CROSS_REFERENCE"
                    cross_ref_edges += 1

            if from_node is not None:
                tid = to_id if to_id is not None else target_sym
                if tid == from_node["scip_id"]:
                    continue
                structural_edges.append(
                    {
                        "source_id": from_node["scip_id"],
                        "target_id": tid,
                        "edge_type": etype,
                        "repo_name": local_repo,
                        "target_repo": t_repo,
                        "provenance": "scip_reference_code" if etype == "REFERENCES" else "scip_cross_repo",
                    }
                )
                reference_edges_code += 1
            else:
                structural_edges.append(
                    {
                        "source_id": reference_source_id(local_repo, relative_path),
                        "target_id": to_id if to_id is not None else target_sym,
                        "edge_type": "REFERENCES",
                        "repo_name": local_repo,
                        "target_repo": t_repo,
                        "provenance": "scip_file_fallback",
                    }
                )
                reference_edges_file += 1

    for document in index.documents:
        relative_path = normalize_relative_path(document.relative_path)
        definition_count = sum(
            1
            for occ in document.occurrences
            if occ.symbol and (occ.symbol_roles & DEFINITION_ROLE)
        )
        reference_count = sum(
            1
            for occ in document.occurrences
            if occ.symbol and not (occ.symbol_roles & DEFINITION_ROLE)
        )
        documents_report.append(
            {
                "relative_path": relative_path,
                "language": document.language,
                "occurrence_count": len(document.occurrences),
                "definition_count": definition_count,
                "reference_count": reference_count,
                "symbol_information_count": len(document.symbols),
            }
        )

    structural["edges"] = dedupe_edges(structural_edges)
    structural["edge_count"] = len(structural["edges"])
    if structural.get("project_node") and structural.get("file_nodes"):
        pn = ProjectNode.model_validate(structural["project_node"])
        fns = [FileNode.model_validate(f) for f in structural["file_nodes"]]
        cns = [CodeNode.model_validate(n) for n in structural["code_nodes"]]
        ens = [StructuralEdge.model_validate(extend_edge_for_model(e)) for e in structural["edges"]]
        nbrs = build_neighborhood_index(pn, fns, cns, ens)
        structural["neighborhoods"] = {k: v.model_dump() for k, v in nbrs.items()}

    write_json(structural_path, structural)

    edge_counts: dict[str, int] = {}
    for edge in structural["edges"]:
        et = str(edge["edge_type"])
        edge_counts[et] = edge_counts.get(et, 0) + 1

    scip_resolved_in_graph = sum(1 for n in structural["code_nodes"] if n.get("symbol_source") == "scip")
    total_nodes = len(structural["code_nodes"])
    scip_eligible_nodes = [
        n
        for n in structural["code_nodes"]
        if n.get("kind")
        in {
            "function",
            "class",
            "interface",
            "method",
            "variable",
            "react_hook",
            "config_object",
            "middleware",
            "service_boundary",
        }
    ]
    scip_eligible_resolved = sum(1 for n in scip_eligible_nodes if n.get("symbol_source") == "scip")
    addressable_orphaned_symbols = [
        item
        for item in orphaned_symbols
        if is_addressable_orphaned_symbol(item)
    ]
    report = {
        "metadata": {
            "project_root": index.metadata.project_root,
            "text_document_encoding": int(index.metadata.text_document_encoding),
            "tool_name": index.metadata.tool_info.name,
            "tool_version": index.metadata.tool_info.version,
            "document_count": len(index.documents),
            "external_symbol_count": len(index.external_symbols),
            "global_symbol_index_used": str(global_symbol_index_path) if global_symbol_index_path else None,
        },
        "resolution": {
            "resolved_code_nodes": resolved_definitions,
            "resolved_definition_occurrences": resolved_definitions,
            "nodes_with_scip_identity": scip_resolved_in_graph,
            "total_code_nodes": total_nodes,
            "scip_eligible_code_nodes": len(scip_eligible_nodes),
            "scip_eligible_nodes_with_scip_identity": scip_eligible_resolved,
            "unresolved_code_nodes": total_nodes - scip_resolved_in_graph,
            "unresolved_provisional_nodes": total_nodes - scip_resolved_in_graph,
            "identity_coverage": {
                "total": total_nodes,
                "with_scip_identity": scip_resolved_in_graph,
                "provisional_only": total_nodes - scip_resolved_in_graph,
            },
        },
        "reference_routing": {
            "code_to_code": reference_edges_code,
            "file_fallback": reference_edges_file,
            "cross_repo": cross_ref_edges,
        },
        "scip_backed_edge_counts": {
            "DEFINES": edge_counts.get("DEFINES", 0),
            "REFERENCES": edge_counts.get("REFERENCES", 0) + edge_counts.get("CROSS_REFERENCE", 0),
            "CROSS_REFERENCE": edge_counts.get("CROSS_REFERENCE", 0),
            "IMPLEMENTS": edge_counts.get("IMPLEMENTS", 0),
        },
        "structural_edge_counts": edge_counts,
        "documents": documents_report,
        "implementation_edges": implementation_edges,
        "orphaned_symbol_count": len(orphaned_symbols),
        "addressable_orphaned_symbol_count": len(addressable_orphaned_symbols),
    }
    if index.external_symbols:
        write_json(
            artifact_dir / "external-symbols.json",
            [
                {
                    "symbol": s.symbol,
                    "display_name": s.display_name,
                    "kind": scip_pb2.SymbolInformation.Kind.Name(s.kind) if s.kind else None,
                }
                for s in index.external_symbols
            ],
        )

    write_json(artifact_dir / "orphaned-symbols.json", orphaned_symbols)
    write_json(artifact_dir / "addressable-orphaned-symbols.json", addressable_orphaned_symbols)
    write_json(artifact_dir / "scip-consumed.json", report)
    return report


def extend_edge_for_model(edge: dict[str, Any]) -> dict[str, Any]:
    e = {**edge}
    if e.get("provenance") is None:
        e["provenance"] = None
    if e.get("target_repo") is None:
        e["target_repo"] = None
    return e


def build_symbol_info_map(index: scip_pb2.Index) -> dict[str, scip_pb2.SymbolInformation]:
    info: dict[str, scip_pb2.SymbolInformation] = {}
    for document in index.documents:
        for symbol in document.symbols:
            info[symbol.symbol] = symbol
    for symbol in index.external_symbols:
        info[symbol.symbol] = symbol
    return info


def load_document_text(repo_path: Path, document: scip_pb2.Document, normalized_relative_path: str) -> str:
    if document.text:
        return document.text
    return (repo_path / normalized_relative_path).read_text(encoding="utf-8", errors="ignore")


def find_containing_code_node(
    file_nodes: list[dict[str, Any]],
    ref_line: int,
    raw_range: list[int] | None,
) -> dict[str, Any] | None:
    if not file_nodes:
        return None
    if not raw_range:
        return min(
            file_nodes,
            key=lambda n: (n["range"]["end_line"] - n["range"]["start_line"], n["range"]["start_col"]),
        )
    in_span = [n for n in file_nodes if n["range"]["start_line"] <= ref_line <= n["range"]["end_line"]]
    if in_span:
        return min(
            in_span,
            key=lambda n: (n["range"]["end_line"] - n["range"]["start_line"], n["range"]["end_col"] - n["range"]["start_col"]),
        )
    return min(
        file_nodes,
        key=lambda n: (abs(n["range"]["start_line"] - ref_line) + abs(n["range"]["end_line"] - ref_line), n["range"]["start_col"]),
    )


def resolve_definition_occurrence(
    *,
    occurrence: scip_pb2.Occurrence,
    document: scip_pb2.Document,
    relative_path: str,
    file_text: str,
    file_nodes: list[dict[str, Any]],
    symbol_info: dict[str, scip_pb2.SymbolInformation],
) -> dict[str, Any]:
    token_text = extract_occurrence_text(file_text, occurrence.range, document.position_encoding).strip()
    info = symbol_info.get(occurrence.symbol)
    if not token_text:
        token_text = info.display_name if info and info.display_name else ""

    candidates = [node for node in file_nodes if node["name"] == token_text]
    if not candidates:
        return {
            "resolved_count": 0,
            "matched_node": None,
            "orphaned_symbol": build_orphaned_symbol_record(
                relative_path=relative_path,
                occurrence_symbol=occurrence.symbol,
                token_text=token_text,
                reason="no_matching_tree_sitter_node",
                symbol_info=info,
            ),
        }

    occurrence_start_line = occurrence.range[0] + 1 if occurrence.range else 1
    containing = [
        node
        for node in candidates
        if node["range"]["start_line"] <= occurrence_start_line <= node["range"]["end_line"]
    ]
    if not containing:
        containing = candidates

    best = min(
        containing,
        key=lambda node: (
            node["range"]["end_line"] - node["range"]["start_line"],
            node["range"]["start_col"],
        ),
    )

    best["provisional_scip_id"] = best.get("provisional_scip_id") or best["scip_id"]
    old_target_id = best["scip_id"]
    if not best.get("original_provisional_id"):
        best["original_provisional_id"] = old_target_id
    best["scip_id"] = occurrence.symbol
    best["symbol_source"] = "scip"
    if info and info.kind:
        best["scip_kind"] = scip_pb2.SymbolInformation.Kind.Name(info.kind)
    return {
        "resolved_count": 1,
        "matched_node": best,
        "old_target_ids": [c for c in {old_target_id, best.get("provisional_scip_id")} if c],
        "orphaned_symbol": None,
    }


def build_orphaned_symbol_record(
    *,
    relative_path: str,
    occurrence_symbol: str,
    token_text: str,
    reason: str,
    symbol_info: scip_pb2.SymbolInformation | None,
) -> dict[str, Any]:
    return {
        "relative_path": relative_path,
        "symbol": occurrence_symbol,
        "display_name": symbol_info.display_name if symbol_info and symbol_info.display_name else token_text,
        "kind": scip_pb2.SymbolInformation.Kind.Name(symbol_info.kind) if symbol_info and symbol_info.kind else None,
        "reason": reason,
    }


def is_addressable_orphaned_symbol(item: dict[str, Any]) -> bool:
    symbol = str(item.get("symbol", ""))
    display_name = str(item.get("display_name", ""))
    kind = item.get("kind")
    if symbol.startswith("local "):
        return False
    if not display_name:
        return False
    if kind not in ADDRESSABLE_SCIP_KINDS:
        return False
    return True


def reference_source_id(repo_name: str, relative_path: str) -> str:
    return build_file_uri(repo_name, relative_path)


def dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[object, ...], dict[str, Any]] = {}
    for edge in edges:
        key = (
            str(edge["source_id"]),
            str(edge["target_id"]),
            str(edge["edge_type"]),
            str(edge.get("repo_name", "")),
            str(edge.get("provenance", "")),
            str(edge.get("target_repo", "")),
        )
        unique[key] = edge
    return list(unique.values())


def rewrite_edge_targets(edges: list[dict[str, Any]], *, old_target_ids: list[str], new_target_id: str) -> None:
    for edge in edges:
        if str(edge["target_id"]) in old_target_ids:
            edge["target_id"] = new_target_id


def extract_occurrence_text(text: str, raw_range: list[int], position_encoding: int) -> str:
    if not raw_range:
        return ""
    lines = text.splitlines()
    start_line = raw_range[0]
    start_char = raw_range[1]
    if len(raw_range) == 3:
        end_line = start_line
        end_char = raw_range[2]
    else:
        end_line = raw_range[2]
        end_char = raw_range[3]

    if start_line >= len(lines) or end_line >= len(lines):
        return ""

    if start_line == end_line:
        return slice_by_encoding(lines[start_line], start_char, end_char, position_encoding)

    parts = [slice_by_encoding(lines[start_line], start_char, None, position_encoding)]
    if end_line - start_line > 1:
        parts.extend(lines[start_line + 1 : end_line])
    parts.append(slice_by_encoding(lines[end_line], 0, end_char, position_encoding))
    return "\n".join(parts)


def slice_by_encoding(line: str, start: int, end: int | None, position_encoding: int) -> str:
    if position_encoding == scip_pb2.UTF16CodeUnitOffsetFromLineStart:
        return slice_utf16(line, start, end)
    if position_encoding == scip_pb2.UTF32CodeUnitOffsetFromLineStart:
        return line[start:end]
    return slice_utf8(line, start, end)


def slice_utf8(line: str, start: int, end: int | None) -> str:
    encoded = line.encode("utf-8")
    segment = encoded[start:end]
    return segment.decode("utf-8", errors="ignore")


def slice_utf16(line: str, start: int, end: int | None) -> str:
    start_index = utf16_offset_to_index(line, start)
    end_index = utf16_offset_to_index(line, end) if end is not None else len(line)
    return line[start_index:end_index]


def utf16_offset_to_index(line: str, offset: int | None) -> int:
    if offset is None:
        return len(line)
    units = 0
    for index, char in enumerate(line):
        if units >= offset:
            return index
        units += len(char.encode("utf-16-le")) // 2
        if units > offset:
            return index + 1
    return len(line)
