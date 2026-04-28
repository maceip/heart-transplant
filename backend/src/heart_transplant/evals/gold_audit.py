from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json


GOLD_CONFIDENCE_VALUES = {"high", "medium", "low"}
GOLD_STATUS_VALUES = {"active", "needs_review", "deprecated"}
REQUIRED_FIELDS = {
    "id",
    "repo_name",
    "accepted_blocks",
    "primary_block",
    "confidence",
    "source",
    "status",
}
TARGET_FIELDS = ("node_id", "file_path", "file_glob")


def load_gold_rows(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Gold set must be a JSON list: {path}")
    return [row for row in data if isinstance(row, dict)]


def audit_gold_file(path: Path) -> dict[str, Any]:
    return audit_gold_rows(load_gold_rows(path), gold_set_path=path)


def audit_gold_rows(rows: list[dict[str, Any]], *, gold_set_path: Path | None = None) -> dict[str, Any]:
    normalized = [normalize_gold_row(row, index=index) for index, row in enumerate(rows)]
    duplicate_rows = find_duplicate_rows(normalized)
    missing_required_fields = find_missing_required_fields(normalized)
    invalid_rows = find_invalid_rows(normalized)
    contradictions = find_contradictory_labels(normalized)
    multi_label_rows = [row for row in normalized if len(row["accepted_blocks"]) > 1 and row["status"] != "deprecated"]
    rows_needing_multi_label_treatment = [
        row
        for row in normalized
        if row["status"] != "deprecated"
        and (
            len(row["accepted_blocks"]) > 1
            or "multi-label" in str(row.get("notes", "")).lower()
            or "ambiguous" in str(row.get("notes", "")).lower()
        )
    ]

    status_counts = Counter(row["status"] for row in normalized)
    confidence_distribution = Counter(row["confidence"] for row in normalized)
    repo_coverage = Counter(row["repo_name"] for row in normalized if row["repo_name"])
    block_coverage: Counter[str] = Counter()
    for row in normalized:
        if row["status"] == "deprecated":
            continue
        block_coverage.update(row["accepted_blocks"])

    blocking_issue_count = (
        len(duplicate_rows)
        + len(missing_required_fields)
        + len(invalid_rows)
        + len([item for item in contradictions if item["status"] == "active"])
    )
    return {
        "report_type": "gold_audit",
        "gold_set": str(gold_set_path) if gold_set_path else None,
        "summary": {
            "total_rows": len(normalized),
            "active_rows": status_counts.get("active", 0),
            "needs_review_rows": status_counts.get("needs_review", 0),
            "deprecated_rows": status_counts.get("deprecated", 0),
            "duplicate_row_count": len(duplicate_rows),
            "contradictory_target_count": len(contradictions),
            "active_contradictory_target_count": len([item for item in contradictions if item["status"] == "active"]),
            "missing_required_field_count": len(missing_required_fields),
            "invalid_row_count": len(invalid_rows),
            "repo_count": len(repo_coverage),
            "block_count": len(block_coverage),
            "multi_label_row_count": len(multi_label_rows),
            "rows_needing_multi_label_treatment": len(rows_needing_multi_label_treatment),
            "overall_status": "pass" if blocking_issue_count == 0 else "fail",
        },
        "confidence_distribution": dict(sorted(confidence_distribution.items())),
        "status_distribution": dict(sorted(status_counts.items())),
        "repo_coverage": dict(sorted(repo_coverage.items())),
        "block_coverage": dict(sorted(block_coverage.items())),
        "duplicate_rows": duplicate_rows,
        "contradictory_labels": contradictions,
        "missing_required_fields": missing_required_fields,
        "invalid_rows": invalid_rows,
        "rows_needing_multi_label_treatment": compact_rows(rows_needing_multi_label_treatment),
    }


def normalize_gold_row(row: dict[str, Any], *, index: int = 0) -> dict[str, Any]:
    present_fields = set(row.keys())
    accepted_blocks = row.get("accepted_blocks")
    if not isinstance(accepted_blocks, list) or not accepted_blocks:
        expected = row.get("expected_block")
        accepted_blocks = [expected] if expected else []
    accepted = [str(block) for block in accepted_blocks if str(block or "").strip()]
    primary = str(row.get("primary_block") or row.get("expected_block") or (accepted[0] if accepted else ""))
    status = str(row.get("status") or "active")
    confidence = str(row.get("confidence") or "")
    return {
        **row,
        "_index": index,
        "_present_fields": present_fields,
        "id": str(row.get("id") or ""),
        "repo_name": str(row.get("repo_name") or ""),
        "node_id": str(row.get("node_id") or ""),
        "file_path": str(row.get("file_path") or ""),
        "file_glob": str(row.get("file_glob") or ""),
        "accepted_blocks": accepted,
        "primary_block": primary,
        "expected_block": primary,
        "confidence": confidence,
        "source": str(row.get("source") or ""),
        "notes": str(row.get("notes") or ""),
        "status": status,
    }


def active_gold_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        public_gold_row(row)
        for row in (normalize_gold_row(item, index=index) for index, item in enumerate(rows))
        if row["status"] == "active"
    ]


def accepted_blocks_for_row(row: dict[str, Any]) -> list[str]:
    normalized = normalize_gold_row(row)
    return normalized["accepted_blocks"] or [normalized["primary_block"]]


def find_duplicate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_semantic_key: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["id"]:
            by_id[row["id"]].append(row)
        by_semantic_key[(row["repo_name"], target_kind(row), target_value(row), row["primary_block"], row["status"])].append(row)
    duplicates: list[dict[str, Any]] = []
    for key, grouped in sorted(by_id.items()):
        if len(grouped) > 1:
            duplicates.append({"kind": "id", "key": key, "rows": compact_rows(grouped)})
    for key, grouped in sorted(by_semantic_key.items()):
        if len(grouped) > 1:
            duplicates.append({"kind": "semantic", "key": list(key), "rows": compact_rows(grouped)})
    return duplicates


def find_missing_required_fields(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for row in rows:
        present_fields = row.get("_present_fields", set())
        row_missing = sorted(field for field in REQUIRED_FIELDS if field not in present_fields or not row.get(field))
        if not any(field in present_fields and row.get(field) for field in TARGET_FIELDS):
            row_missing.append("node_id|file_path|file_glob")
        if row_missing:
            missing.append({"row": compact_row(row), "missing": row_missing})
    return missing


def find_invalid_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    invalid: list[dict[str, Any]] = []
    for row in rows:
        problems: list[str] = []
        if row["status"] and row["status"] not in GOLD_STATUS_VALUES:
            problems.append(f"invalid status: {row['status']}")
        if row["confidence"] and row["confidence"] not in GOLD_CONFIDENCE_VALUES:
            problems.append(f"invalid confidence: {row['confidence']}")
        if row["primary_block"] and row["accepted_blocks"] and row["primary_block"] not in row["accepted_blocks"]:
            problems.append("primary_block is not in accepted_blocks")
        if problems:
            invalid.append({"row": compact_row(row), "problems": problems})
    return invalid


def find_contradictory_labels(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["status"] == "deprecated":
            continue
        grouped[(row["repo_name"], target_kind(row), target_value(row))].append(row)

    contradictions: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        active_items = [row for row in items if row["status"] == "active"]
        if len(items) <= 1:
            continue
        active_blocks = {block for row in active_items for block in row["accepted_blocks"]}
        active_primaries = {row["primary_block"] for row in active_items if row["primary_block"]}
        review_only = not active_items or all(row["status"] == "needs_review" for row in items)
        unresolved_active_conflict = len(active_items) > 1 and len(active_primaries) > 1
        if review_only or unresolved_active_conflict:
            contradictions.append(
                {
                    "target": {"repo_name": key[0], "target_kind": key[1], "target": key[2]},
                    "status": "needs_review" if review_only else "active",
                    "accepted_blocks": sorted(active_blocks),
                    "rows": compact_rows(items),
                }
            )
    return contradictions


def target_kind(row: dict[str, Any]) -> str:
    for field in TARGET_FIELDS:
        if row.get(field):
            return field
    return "<missing>"


def target_value(row: dict[str, Any]) -> str:
    for field in TARGET_FIELDS:
        if row.get(field):
            return str(row[field])
    return ""


def compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [compact_row(row) for row in rows]


def public_gold_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": row.get("_index"),
        "id": row.get("id"),
        "repo_name": row.get("repo_name"),
        "node_id": row.get("node_id") or None,
        "file_path": row.get("file_path") or None,
        "file_glob": row.get("file_glob") or None,
        "primary_block": row.get("primary_block"),
        "accepted_blocks": row.get("accepted_blocks"),
        "confidence": row.get("confidence"),
        "status": row.get("status"),
        "notes": row.get("notes") or None,
    }
