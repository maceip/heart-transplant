from __future__ import annotations

import json
from pathlib import Path
from fnmatch import fnmatch
from typing import Any

from heart_transplant.classify.heuristic import classify_node_heuristic
from heart_transplant.models import CodeNode, NeighborhoodRecord, StructuralArtifact


def load_gold_set(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_benchmark(structural: dict[str, Any], gold_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare heuristic labels to gold ``expected_block`` for listed ``node_id``s."""
    art = StructuralArtifact.model_validate(structural)
    scoped_items = [item for item in gold_items if gold_item_applies_to_artifact(item, art)]
    nbrs = structural.get("neighborhoods", {})
    by_id = {c.scip_id: c for c in art.code_nodes}
    by_id.update({c.original_provisional_id: c for c in art.code_nodes if c.original_provisional_id})
    correct = 0
    rows: list[dict[str, Any]] = []
    for g in scoped_items:
        expected = str(g.get("expected_block"))
        candidates = nodes_for_gold_item(g, art, by_id)
        if not candidates:
            rows.append({**g, "got": None, "match": False, "error": "missing node"})
            continue
        classified: list[dict[str, Any]] = []
        ok = False
        for node in candidates:
            raw = nbrs.get(node.scip_id) or nbrs.get(str(node.scip_id))
            nb = NeighborhoodRecord.model_validate(raw) if raw else None
            got = classify_node_heuristic(node, nb)
            classified.append(
                {
                    "node_id": node.scip_id,
                    "file_path": node.file_path,
                    "got_block": got.primary_block,
                }
            )
            ok = ok or str(got.primary_block) == expected
        if ok:
            correct += 1
        rows.append(
            {
                **g,
                "expected_block": expected,
                "classified": classified,
                "match": ok,
            }
        )
    return {
        "total": len(scoped_items),
        "input_total": len(gold_items),
        "skipped_repo_scope": len(gold_items) - len(scoped_items),
        "correct": correct,
        "accuracy": correct / max(len(scoped_items), 1),
        "rows": rows,
    }


def gold_item_applies_to_artifact(item: dict[str, Any], artifact: StructuralArtifact) -> bool:
    """Return whether a gold row should be scored against this single-repo artifact."""
    repo_name = str(item.get("repo_name", "")).strip()
    if not repo_name:
        return True
    artifact_repo = artifact.repo_name.strip()
    artifact_short = artifact_repo.rsplit("/", 1)[-1]
    return repo_name in {artifact_repo, artifact_short} or artifact_repo.endswith(f"/{repo_name}")


def nodes_for_gold_item(
    item: dict[str, Any],
    artifact: StructuralArtifact,
    by_id: dict[str, CodeNode],
) -> list[CodeNode]:
    if item.get("node_id"):
        node = by_id.get(str(item["node_id"]))
        return [node] if node else []
    if item.get("file_path"):
        return [node for node in artifact.code_nodes if node.file_path == str(item["file_path"])]
    if item.get("file_glob"):
        pattern = str(item["file_glob"])
        return [node for node in artifact.code_nodes if fnmatch(node.file_path, pattern)]
    return []
