from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from heart_transplant.evals.gold_benchmark import load_gold_set

REQUIRED_FIELDS = ("repo_name", "expected_block")


def audit_gold_set(path: Path) -> dict[str, Any]:
    rows = load_gold_set(path.resolve())
    missing_required: list[dict[str, Any]] = []
    target_blocks: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    exact_keys: Counter[tuple[str, str, str, str, str]] = Counter()
    repo_counts: Counter[str] = Counter()
    block_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()

    for index, row in enumerate(rows):
        missing = [field for field in REQUIRED_FIELDS if not row.get(field)]
        if not (row.get("node_id") or row.get("file_path") or row.get("file_glob")):
            missing.append("node_id|file_path|file_glob")
        if missing:
            missing_required.append({"index": index, "id": row.get("id"), "missing": missing})

        repo = str(row.get("repo_name", ""))
        node_id = str(row.get("node_id", ""))
        file_path = str(row.get("file_path", ""))
        file_glob = str(row.get("file_glob", ""))
        block = str(row.get("expected_block", ""))
        target = (repo, node_id, file_path, file_glob)
        target_blocks[target].add(block)
        exact_keys[(repo, node_id, file_path, file_glob, block)] += 1
        if repo:
            repo_counts[repo] += 1
        if block:
            block_counts[block] += 1
        confidence_counts[str(row.get("confidence", "unknown"))] += 1

    contradictions = [
        {
            "repo_name": repo,
            "node_id": node_id,
            "file_path": file_path,
            "file_glob": file_glob,
            "expected_blocks": sorted(blocks),
        }
        for (repo, node_id, file_path, file_glob), blocks in target_blocks.items()
        if len({block for block in blocks if block}) > 1
    ]
    duplicate_rows = [
        {
            "repo_name": repo,
            "node_id": node_id,
            "file_path": file_path,
            "file_glob": file_glob,
            "expected_block": block,
            "count": count,
        }
        for (repo, node_id, file_path, file_glob, block), count in exact_keys.items()
        if count > 1
    ]

    failed = bool(missing_required)
    needs_review = bool(contradictions or duplicate_rows)
    return {
        "report_type": "gold_audit",
        "gold_set": str(path.resolve()),
        "summary": {
            "row_count": len(rows),
            "repo_count": len(repo_counts),
            "block_count": len(block_counts),
            "missing_required_count": len(missing_required),
            "contradiction_count": len(contradictions),
            "contradictory_target_count": len(contradictions),
            "duplicate_row_count": len(duplicate_rows),
            "duplicate_key_count": len(duplicate_rows),
            "overall_status": "fail" if failed else "needs_review" if needs_review else "pass",
        },
        "repo_counts": dict(sorted(repo_counts.items())),
        "block_counts": dict(sorted(block_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "missing_required": missing_required,
        "contradictions": contradictions,
        "duplicate_rows": duplicate_rows,
    }
