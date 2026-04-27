from __future__ import annotations

from collections import defaultdict

from typing import Any

from heart_transplant.models import CodeNode, FileNode, NeighborhoodRecord, ProjectNode, StructuralEdge
from heart_transplant.scip.path_normalization import build_file_uri


def get_neighborhood(structural: dict[str, Any], code_id: str) -> dict[str, Any] | None:
    """Return persisted neighborhood for a code node, or None."""
    nbrs = structural.get("neighborhoods")
    if not isinstance(nbrs, dict):
        return None
    rec = nbrs.get(code_id)
    return rec if isinstance(rec, dict) else None


def build_neighborhood_index(
    project_node: ProjectNode,
    file_nodes: list[FileNode],
    code_nodes: list[CodeNode],
    edges: list[StructuralEdge],
) -> dict[str, NeighborhoodRecord]:
    """Build ``scip_id`` -> one-hop metadata for code nodes."""
    by_file: dict[str, list[str]] = defaultdict(list)
    for n in code_nodes:
        by_file[n.file_path].append(n.scip_id)
    for fp, ids in by_file.items():
        by_file[fp] = sorted(set(ids))

    file_id_by_path: dict[str, str] = {f.file_path: f.node_id for f in file_nodes}
    id_to_path = {f.node_id: f.file_path for f in file_nodes}
    imports_by_file: dict[str, set[str]] = defaultdict(set)
    imported_by_id: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        if e.edge_type not in {"IMPORTS_MODULE", "DEPENDS_ON_FILE"}:
            continue
        src_fp = id_to_path.get(e.source_id)
        if not src_fp:
            continue
        imports_by_file[src_fp].add(e.target_id)
        tgt_fp = id_to_path.get(e.target_id) if e.edge_type == "DEPENDS_ON_FILE" else None
        if tgt_fp:
            imported_by_id[e.target_id].add(e.source_id)
    out: dict[str, NeighborhoodRecord] = {}
    for n in code_nodes:
        fp = n.file_path
        fid = file_id_by_path.get(fp, build_file_uri(project_node.repo_name, fp))
        out[n.scip_id] = NeighborhoodRecord(
            code_id=n.scip_id,
            file_path=fp,
            project_id=project_node.node_id,
            file_node_id=fid,
            imports=sorted(imports_by_file.get(fp, set())),
            imported_by=sorted(imported_by_id.get(fid, set())),
            same_file=[x for x in by_file.get(fp, []) if x != n.scip_id],
        )
    return out
