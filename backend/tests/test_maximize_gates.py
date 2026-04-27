from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import heart_transplant.maximize.gates as maximize_gates
from heart_transplant.ingest.treesitter_ingest import ingest_repository


def _write_structural_artifact(artifact_dir: Path, repo_path: Path, repo_name: str = "demo/repo") -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "structural-artifact.json").write_text(
        json.dumps({"repo_path": str(repo_path), "repo_name": repo_name}),
        encoding="utf-8",
    )


def _write_gold_set(path: Path) -> None:
    blocks = [
        "Access Control",
        "Data Persistence",
        "Network Edge",
        "System Telemetry",
        "Core Rendering",
        "Connectivity Layer",
        "Background Processing",
        "Security Ops",
    ]
    repos = ["repo-a", "repo-b", "repo-c", "repo-d"]
    items = []
    for index in range(25):
        items.append(
            {
                "id": f"item-{index}",
                "repo_name": repos[index % len(repos)],
                "file_path": f"src/file-{index}.ts",
                "expected_block": blocks[index % len(blocks)],
            }
        )
    path.write_text(json.dumps(items), encoding="utf-8")


def _make_package_root(tmp_path: Path) -> Path:
    package_root = tmp_path / "repo" / "backend" / "src" / "heart_transplant"
    package_root.mkdir(parents=True, exist_ok=True)
    return package_root


def test_maximize_gates_requires_holdout_evidence(tmp_path: Path, monkeypatch) -> None:
    repo_path = tmp_path / "repo-source"
    repo_path.mkdir()
    artifact_dir = tmp_path / "artifact"
    gold_set = tmp_path / "gold.json"
    package_root = _make_package_root(tmp_path)
    _write_structural_artifact(artifact_dir, repo_path)
    _write_gold_set(gold_set)

    monkeypatch.setattr(
        maximize_gates,
        "run_validation_gates",
        lambda repo_path, artifact_dir: {"summary": {"overall_status": "pass"}},
    )

    report = maximize_gates.run_maximize_gates(
        artifact_dir,
        gold_set,
        package_root=package_root,
        run_demos=False,
    )

    generalization_gate = next(g for g in report["gates"] if g["gate_id"] == "maximize_gate_generalization")
    assert generalization_gate["status"] == "fail"
    assert "holdout" in generalization_gate["outputs"]["note"].lower()


def test_maximize_gates_scores_holdout_semantic_benchmark(tmp_path: Path, monkeypatch) -> None:
    repo_path = tmp_path / "repo-source"
    repo_path.mkdir()
    artifact_dir = tmp_path / "artifact"
    gold_set = tmp_path / "gold.json"
    package_root = _make_package_root(tmp_path)
    _write_structural_artifact(artifact_dir, repo_path)

    holdout_repo = tmp_path / "holdout-repo"
    holdout_repo.mkdir()
    (holdout_repo / "auth.ts").write_text("export function login() { return true; }\n", encoding="utf-8")
    holdout_artifact = ingest_repository(holdout_repo, "holdout-repo")
    holdout_artifact_dir = tmp_path / "holdout-artifact"
    holdout_artifact_dir.mkdir()
    (holdout_artifact_dir / "structural-artifact.json").write_text(
        json.dumps(holdout_artifact.model_dump(mode="json")),
        encoding="utf-8",
    )
    gold_set.write_text(
        json.dumps(
            [
                {
                    "id": "holdout-auth",
                    "repo_name": "holdout-repo",
                    "file_path": "auth.ts",
                    "expected_block": "Access Control",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        maximize_gates,
        "run_validation_gates",
        lambda repo_path, artifact_dir: {"summary": {"overall_status": "pass"}},
    )

    report = maximize_gates.run_maximize_gates(
        artifact_dir,
        gold_set,
        holdout_artifact_dir=holdout_artifact_dir,
        package_root=package_root,
        run_demos=False,
    )

    generalization_gate = next(g for g in report["gates"] if g["gate_id"] == "maximize_gate_generalization")
    assert generalization_gate["status"] == "pass"
    assert generalization_gate["outputs"]["holdout_semantic_summary"]["total"] == 1
    assert generalization_gate["outputs"]["holdout_semantic_summary"]["accuracy"] == 1.0
    assert generalization_gate["outputs"]["holdout_block_benchmark_summary"]["scorable_accuracy"] == 1.0


def test_maximize_gates_accepts_separate_holdout_gold_set(tmp_path: Path, monkeypatch) -> None:
    repo_path = tmp_path / "repo-source"
    repo_path.mkdir()
    artifact_dir = tmp_path / "artifact"
    reference_gold = tmp_path / "reference-gold.json"
    holdout_gold = tmp_path / "holdout-gold.json"
    package_root = _make_package_root(tmp_path)
    _write_structural_artifact(artifact_dir, repo_path)
    _write_gold_set(reference_gold)

    holdout_repo = tmp_path / "holdout-repo"
    holdout_repo.mkdir()
    (holdout_repo / "auth.ts").write_text("export function login() { return true; }\n", encoding="utf-8")
    holdout_artifact = ingest_repository(holdout_repo, "holdout-repo")
    holdout_artifact_dir = tmp_path / "holdout-artifact"
    holdout_artifact_dir.mkdir()
    (holdout_artifact_dir / "structural-artifact.json").write_text(
        json.dumps(holdout_artifact.model_dump(mode="json")),
        encoding="utf-8",
    )
    holdout_gold.write_text(
        json.dumps(
            [
                {
                    "id": "holdout-auth",
                    "repo_name": "holdout-repo",
                    "file_path": "auth.ts",
                    "expected_block": "Access Control",
                }
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        maximize_gates,
        "run_validation_gates",
        lambda repo_path, artifact_dir: {"summary": {"overall_status": "pass"}},
    )

    report = maximize_gates.run_maximize_gates(
        artifact_dir,
        reference_gold,
        holdout_artifact_dir=holdout_artifact_dir,
        holdout_gold_set_path=holdout_gold,
        package_root=package_root,
        run_demos=False,
    )

    generalization_gate = next(g for g in report["gates"] if g["gate_id"] == "maximize_gate_generalization")
    assert generalization_gate["status"] == "pass"
    assert generalization_gate["outputs"]["holdout_gold_set_path"] == str(holdout_gold.resolve())
    assert generalization_gate["outputs"]["holdout_semantic_summary"]["total"] == 1


def test_scan_for_scaffold_markers_uses_dynamic_vendor_repo_names(tmp_path: Path) -> None:
    package_root = _make_package_root(tmp_path)
    repo_root = package_root.parents[3]
    vendored_repo = repo_root / "vendor" / "github-repos" / "holdout-repo"
    vendored_repo.mkdir(parents=True, exist_ok=True)
    flagged = package_root / "sample.py"
    flagged.write_text('REPO_TOKEN = "holdout-repo"\n', encoding="utf-8")

    hits = maximize_gates._scan_for_scaffold_markers(package_root)

    assert any("holdout-repo" in hit for hit in hits)


def test_run_cli_demos_uses_positional_artifact_for_maximize_report(monkeypatch, tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run(cmd: list[str], **_: object) -> SimpleNamespace:
        commands.append(cmd)
        return SimpleNamespace(returncode=0, stdout="{}\n", stderr="")

    monkeypatch.setattr(maximize_gates.subprocess, "run", fake_run)

    maximize_gates._run_cli_demos(tmp_path / "artifact", tmp_path / "gold.json")

    maximize_report = next(cmd for cmd in commands if "maximize-report" in cmd)
    assert "--artifact-dir" not in maximize_report
    assert maximize_report[3] == "maximize-report"
    assert maximize_report[4] == str((tmp_path / "artifact"))

