from __future__ import annotations

import json
from pathlib import Path
from heart_transplant.multimodal.models import MultimodalNode


def collect_openapi_nodes(root: Path) -> list[MultimodalNode]:
    root = root.resolve()
    nodes: list[MultimodalNode] = []
    for candidate in root.rglob("openapi.json"):
        if not candidate.is_file():
            continue
        rel = str(candidate.relative_to(root))
        nid = f"spec:{rel}"
        nodes.append(MultimodalNode(node_id=nid, kind="openapi", path=rel, name=candidate.name))
    return nodes


def extract_paths(openapi_path: Path) -> list[tuple[str, str, str]]:
    """Return (method, path_template, operation_id_or_empty)."""
    data = json.loads(openapi_path.read_text(encoding="utf-8"))
    out: list[tuple[str, str, str]] = []
    paths = data.get("paths") or {}
    if not isinstance(paths, dict):
        return out
    for pth, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, op in methods.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                continue
            oid = ""
            if isinstance(op, dict):
                oid = str(op.get("operationId", "") or "")
            out.append((method.upper(), str(pth), oid))
    return out
