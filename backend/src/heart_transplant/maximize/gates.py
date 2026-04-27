from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from heart_transplant.evals.gold_benchmark import build_block_benchmark_report, load_gold_set, run_benchmark
from heart_transplant.validation_gates import run_validation_gates


def run_maximize_gates(
    artifact_dir: Path,
    gold_set_path: Path,
    *,
    holdout_artifact_dir: Path | None = None,
    holdout_gold_set_path: Path | None = None,
    package_root: Path | None = None,
    run_demos: bool = True,
) -> dict[str, Any]:
    """Phase 8.5 non-gamable gates from the roadmap (machine-readable results)."""

    artifact_dir = artifact_dir.resolve()
    gold_set_path = gold_set_path.resolve()
    holdout_gold_set_path = holdout_gold_set_path.resolve() if holdout_gold_set_path else gold_set_path
    pkg = (package_root or _infer_package_root()).resolve()

    gates: list[dict[str, Any]] = []

    structural = json.loads((artifact_dir / "structural-artifact.json").read_text(encoding="utf-8"))
    repo_path = Path(str(structural["repo_path"])).resolve()
    validation = run_validation_gates(repo_path, artifact_dir)
    ref_ok = validation.get("summary", {}).get("overall_status") == "pass"
    gates.append(
        {
            "gate_id": "maximize_gate_reference_reproducible",
            "status": "pass" if ref_ok else "fail",
            "outputs": {"validation_summary": validation.get("summary")},
        }
    )

    gold_items = load_gold_set(gold_set_path)
    repos = {str(i.get("repo_name", "")) for i in gold_items if i.get("repo_name")}
    blocks = {str(i.get("expected_block", "")) for i in gold_items if i.get("expected_block")}
    breadth_ok = len(gold_items) >= 25 and len(repos) >= 4 and len(blocks) >= 8
    gates.append(
        {
            "gate_id": "maximize_gate_benchmark_breadth",
            "status": "pass" if breadth_ok else "fail",
            "outputs": {
                "item_count": len(gold_items),
                "repo_count": len(repos),
                "distinct_blocks": len(blocks),
                "thresholds": {"items": 25, "repos": 4, "blocks": 8},
            },
        }
    )

    demo_results: list[dict[str, Any]] = []
    demo_ok = True
    if run_demos:
        demo_results = _run_cli_demos(artifact_dir, gold_set_path)
        demo_ok = all(r.get("ok") for r in demo_results)
    gates.append(
        {
            "gate_id": "maximize_gate_demo_replay",
            "status": "pass" if demo_ok else "fail",
            "outputs": {"demos": demo_results},
        }
    )

    holdout_report: dict[str, Any] | None = None
    holdout_semantic_report: dict[str, Any] | None = None
    holdout_block_report: dict[str, Any] | None = None
    holdout_semantic_threshold = 0.5
    if holdout_artifact_dir is not None:
        h = holdout_artifact_dir.resolve()
        h_struct = json.loads((h / "structural-artifact.json").read_text(encoding="utf-8"))
        h_repo = Path(str(h_struct["repo_path"])).resolve()
        holdout_report = run_validation_gates(h_repo, h)
        holdout_gold_items = load_gold_set(holdout_gold_set_path)
        holdout_semantic_report = run_benchmark(h_struct, holdout_gold_items)
        holdout_block_report = build_block_benchmark_report(
            h_struct,
            holdout_gold_items,
            artifact_dir=h,
            gold_set_path=holdout_gold_set_path,
        )
        validation_ok = holdout_report.get("summary", {}).get("overall_status") == "pass"
        semantic_total = int(holdout_semantic_report.get("total", 0))
        semantic_accuracy = float(holdout_semantic_report.get("accuracy", 0.0))
        hold_ok = validation_ok and semantic_total > 0 and semantic_accuracy >= holdout_semantic_threshold
    else:
        hold_ok = False

    gates.append(
        {
            "gate_id": "maximize_gate_generalization",
            "status": "pass" if hold_ok else "fail",
            "outputs": {
                "holdout_artifact_dir": str(holdout_artifact_dir) if holdout_artifact_dir else None,
                "holdout_gold_set_path": str(holdout_gold_set_path) if holdout_artifact_dir else None,
                "holdout_validation_summary": holdout_report.get("summary") if holdout_report else None,
                "holdout_semantic_summary": (
                    {
                        "total": holdout_semantic_report.get("total", 0),
                        "correct": holdout_semantic_report.get("correct", 0),
                        "accuracy": holdout_semantic_report.get("accuracy", 0.0),
                        "threshold": holdout_semantic_threshold,
                    }
                    if holdout_semantic_report
                    else None
                ),
                "holdout_block_benchmark_summary": (
                    holdout_block_report.get("summary") if holdout_block_report else None
                ),
                "note": (
                    None
                    if hold_ok
                    else (
                        "A holdout artifact is required for generalization proof."
                        if holdout_artifact_dir is None
                        else "Holdout generalization requires structural validation plus semantic benchmark rows for the holdout artifact meeting the accuracy threshold."
                    )
                ),
            },
        }
    )

    hits = _scan_for_scaffold_markers(pkg)
    scaffold_ok = len(hits) == 0
    gates.append(
        {
            "gate_id": "maximize_gate_no_scaffolding",
            "status": "pass" if scaffold_ok else "fail",
            "outputs": {"forbidden_hits": hits},
        }
    )

    failed = sum(1 for g in gates if g["status"] == "fail")
    return {
        "report_type": "phase_8_5_maximize_gates",
        "artifact_dir": str(artifact_dir),
        "gold_set_path": str(gold_set_path),
        "summary": {
            "total_gates": len(gates),
            "failed": failed,
            "overall_status": "pass" if failed == 0 else "fail",
        },
        "gates": gates,
    }


def _infer_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _scan_for_scaffold_markers(package_root: Path) -> list[str]:
    markers = _dynamic_scaffold_markers(package_root)
    hits: list[str] = []
    for path in sorted(package_root.rglob("*.py")):
        rel = path.relative_to(package_root)
        if rel.parts[:1] == ("generated",) or "test" in rel.parts:
            continue
        lowered = path.read_text(encoding="utf-8", errors="replace").lower()
        for needle in markers:
            if needle and needle in lowered:
                hits.append(f"{path}:{needle}")
    return hits


def _dynamic_scaffold_markers(package_root: Path) -> set[str]:
    repo_root = package_root.resolve().parents[3]
    vendored_root = repo_root / "vendor" / "github-repos"
    if not vendored_root.is_dir():
        return set()
    return {path.name.lower() for path in vendored_root.iterdir() if path.is_dir() and path.name}


def _run_cli_demos(artifact_dir: Path, gold_set_path: Path) -> list[dict[str, Any]]:
    """Five CLI demos that must exit 0 and emit parseable JSON on stdout (last line or full)."""

    art = str(artifact_dir)
    gold = str(gold_set_path)
    specs: list[tuple[str, list[str]]] = [
        ("test-graph", [art]),
        ("phase-metrics", ["--artifact-dir", art, "--gold-set", gold]),
        ("validate-gates", ["--artifact-dir", art]),
        ("maximize-report", [art, "--gold-set", gold]),
        ("classify", ["--no-use-openai", art]),
    ]
    out: list[dict[str, Any]] = []
    for name, args in specs:
        cmd = [sys.executable, "-m", "heart_transplant.cli", name, *args]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        combined = (proc.stdout or "") + (proc.stderr or "")
        json_ok = _stdout_contains_json_object(combined)
        ok = proc.returncode == 0 and json_ok
        out.append(
            {
                "demo_id": name,
                "command": cmd,
                "exit_code": proc.returncode,
                "json_stdout": json_ok,
                "ok": ok,
                "tail": combined[-400:] if combined else "",
            }
        )
    return out


def _stdout_contains_json_object(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    for chunk in _json_candidates(s):
        try:
            json.loads(chunk)
            return True
        except json.JSONDecodeError:
            continue
    return False


def _json_candidates(s: str) -> list[str]:
    """Try whole string, then last line (typer sometimes prints warnings first)."""

    lines = [ln for ln in s.splitlines() if ln.strip()]
    candidates = [s]
    if lines:
        candidates.append(lines[-1])
        # Multi-line pretty JSON: find first `{` to end
        start = s.find("{")
        if start != -1:
            candidates.append(s[start:])
    return candidates
