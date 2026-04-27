from __future__ import annotations

import json
from pathlib import Path
from collections import Counter, defaultdict
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
            got_blocks = [got.primary_block, *[secondary.block for secondary in got.secondary_blocks]]
            classified.append(
                {
                    "node_id": node.scip_id,
                    "file_path": node.file_path,
                    "got_block": got.primary_block,
                    "secondary_blocks": [secondary.model_dump(mode="json") for secondary in got.secondary_blocks],
                }
            )
            ok = ok or expected in {str(block) for block in got_blocks}
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


def build_block_benchmark_report(
    structural: dict[str, Any],
    gold_items: list[dict[str, Any]],
    *,
    artifact_dir: Path | None = None,
    gold_set_path: Path | None = None,
) -> dict[str, Any]:
    """Return beta-facing block benchmark metrics separated by coverage and classifier quality."""

    raw = run_benchmark(structural, gold_items)
    rows = raw["rows"]
    missing_rows = [row for row in rows if row.get("error") == "missing node"]
    scorable_rows = [row for row in rows if row.get("error") != "missing node"]
    correct_rows = [row for row in rows if row.get("match") is True]
    scorable_correct_rows = [row for row in scorable_rows if row.get("match") is True]
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_block: dict[str, Counter[str]] = defaultdict(Counter)

    for row in missing_rows:
        confusion[str(row.get("expected_block") or "")]["__missing_node__"] += 1

    for row in scorable_rows:
        expected = str(row.get("expected_block") or "")
        got_values = {
            str(item.get("got_block"))
            for item in row.get("classified", [])
            if isinstance(item, dict) and item.get("got_block")
        }
        if not got_values:
            got_values = {"<none>"}
        for got in got_values:
            confusion[expected][got] += 1
        per_block[expected]["total"] += 1
        if row.get("match"):
            per_block[expected]["correct"] += 1

    duplicate_gold_keys = [
        key
        for key, count in Counter(
            (
                str(item.get("repo_name", "")),
                str(item.get("node_id", "")),
                str(item.get("file_path", "")),
                str(item.get("file_glob", "")),
                str(item.get("expected_block", "")),
            )
            for item in gold_items
        ).items()
        if count > 1
    ]

    total = int(raw["total"])
    scorable_total = len(scorable_rows)
    return {
        "report_type": "block_benchmark",
        "artifact_dir": str(artifact_dir) if artifact_dir else None,
        "gold_set": str(gold_set_path) if gold_set_path else None,
        "summary": {
            "input_gold_rows": raw["input_total"],
            "scored_gold_rows": total,
            "skipped_repo_scope": raw["skipped_repo_scope"],
            "end_to_end_correct": len(correct_rows),
            "end_to_end_accuracy": len(correct_rows) / max(total, 1),
            "missing_node_count": len(missing_rows),
            "missing_node_rate": len(missing_rows) / max(total, 1),
            "scorable_gold_rows": scorable_total,
            "scorable_correct": len(scorable_correct_rows),
            "scorable_accuracy": len(scorable_correct_rows) / max(scorable_total, 1),
            "duplicate_gold_key_count": len(duplicate_gold_keys),
        },
        "per_block": {
            block: {
                "total": counts["total"],
                "correct": counts["correct"],
                "accuracy": counts["correct"] / max(counts["total"], 1),
            }
            for block, counts in sorted(per_block.items())
        },
        "confusion": {expected: dict(sorted(got_counts.items())) for expected, got_counts in sorted(confusion.items())},
        "missing_rows": missing_rows,
        "duplicate_gold_keys": duplicate_gold_keys,
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
