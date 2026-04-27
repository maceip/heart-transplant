from __future__ import annotations

import json
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import persist_structural_artifact, write_json
from heart_transplant.ingest.treesitter_ingest import ingest_repository


@dataclass
class IngestResult:
    repo_name: str
    repo_path: str
    status: str
    error_category: str | None = None
    detail: str | None = None
    node_count: int = 0
    edge_count: int = 0
    file_node_count: int = 0
    parser_backends: list[str] | None = None
    artifact_dir: str | None = None


def ingest_vendors(
    root: Path,
    output_report: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Not a directory: {root}")
    results: list[IngestResult] = []
    for sub in sorted(root.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        repo_name = f"vendor/{sub.name}"
        r = IngestResult(repo_name=repo_name, repo_path=str(sub), status="unknown")
        try:
            if not any(sub.iterdir()):
                r.status = "skipped"
                r.error_category = "empty"
                r.detail = "Directory has no children"
                results.append(r)
                continue
            artifact = ingest_repository(sub, repo_name)
            target = persist_structural_artifact(artifact)
            r.status = "ok"
            r.node_count = artifact.node_count
            r.edge_count = artifact.edge_count
            r.file_node_count = len(artifact.file_nodes)
            r.parser_backends = artifact.parser_backends
            r.artifact_dir = str(target)
        except Exception as e:  # noqa: BLE001 — corpus sweep must not abort on one repo
            r.status = "fail"
            r.error_category = type(e).__name__
            r.detail = f"{e}\n{traceback.format_exc()}"
        results.append(r)

    summary = {
        "vendor_root": str(root),
        "total": len(results),
        "ok": sum(1 for x in results if x.status == "ok"),
        "failed": sum(1 for x in results if x.status == "fail"),
        "skipped": sum(1 for x in results if x.status == "skipped"),
        "results": [asdict(x) for x in results],
    }
    if output_report is not None:
        output_report.parent.mkdir(parents=True, exist_ok=True)
        write_json(output_report, summary)
    return summary
