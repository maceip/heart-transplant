from __future__ import annotations

from pathlib import Path

from heart_transplant.temporal.diff import architecture_diff
from heart_transplant.temporal.models import DriftFinding, DriftReport, FileArchitectureChange


def detect_architectural_drift(
    repo_path: Path,
    before_ref: str,
    after_ref: str,
    *,
    expected_paths: set[str] | None = None,
) -> DriftReport:
    """Detect files whose inferred block membership changed across two commits.

    This is an intentionally conservative Phase 9 detector. It claims drift
    when a changed path has different before/after block labels, and it also
    handles simple move/rename cases represented as delete+add pairs. Optional
    ``expected_paths`` is used only for gate scoring.
    """
    diff = architecture_diff(repo_path, before_ref, after_ref)
    findings: list[DriftFinding] = []
    for change in diff.file_changes:
        before = set(change.before_blocks)
        after = set(change.after_blocks)
        if not before or not after or before == after:
            continue
        findings.append(
            DriftFinding(
                path=change.path,
                before_blocks=sorted(before),
                after_blocks=sorted(after),
                first_seen_commit=diff.after_sha,
                confidence=0.9,
                reason="File changed and inferred architectural block membership changed between commits.",
            )
        )

    direct_paths = {finding.path for finding in findings}
    deletes = [change for change in diff.file_changes if change.status == "D" and change.before_blocks]
    adds = [change for change in diff.file_changes if change.status == "A" and change.after_blocks]
    paired_deletes: set[str] = set()
    for added in adds:
        if added.path in direct_paths:
            continue
        deleted = best_move_candidate(added, deletes, paired_deletes)
        if deleted is None:
            continue
        before = set(deleted.before_blocks)
        after = set(added.after_blocks)
        if before == after:
            continue
        paired_deletes.add(deleted.path)
        findings.append(
            DriftFinding(
                path=added.path,
                before_blocks=sorted(before),
                after_blocks=sorted(after),
                first_seen_commit=diff.after_sha,
                confidence=0.82,
                reason="File moved or was recreated at a new path and inferred architectural block membership changed.",
            )
        )

    precision = recall = None
    if expected_paths is not None:
        predicted = {finding.path for finding in findings}
        true_positive = len(predicted & expected_paths)
        precision = true_positive / max(len(predicted), 1)
        recall = true_positive / max(len(expected_paths), 1)

    return DriftReport(
        repo_path=str(Path(repo_path).resolve()),
        before_ref=before_ref,
        after_ref=after_ref,
        before_sha=diff.before_sha,
        after_sha=diff.after_sha,
        findings=findings,
        precision=precision,
        recall=recall,
        limitations=[
            "Phase 9 drift detection detects file-level block-membership drift and simple move/rename drift, not semantic intent drift inside unchanged paths.",
        ],
    )


def best_move_candidate(
    added: FileArchitectureChange,
    deletes: list[FileArchitectureChange],
    paired_deletes: set[str],
) -> FileArchitectureChange | None:
    """Find the most plausible deleted path for an added file without reading blobs."""
    added_path = Path(added.path)
    ranked: list[tuple[int, FileArchitectureChange]] = []
    for deleted in deletes:
        if deleted.path in paired_deletes:
            continue
        deleted_path = Path(deleted.path)
        score = 0
        if deleted_path.name == added_path.name:
            score += 3
        if deleted_path.stem == added_path.stem:
            score += 2
        if set(deleted.before_blocks) & set(added.after_blocks):
            score += 1
        if score:
            ranked.append((score, deleted))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1].path))
    return ranked[0][1]
