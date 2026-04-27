from __future__ import annotations

from pathlib import Path

from heart_transplant.multimodal.models import MultimodalNode


def collect_test_nodes(root: Path) -> list[MultimodalNode]:
    root = root.resolve()
    nodes: list[MultimodalNode] = []
    patterns = ("**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/*.spec.tsx", "**/*_test.go", "**/*.test.mjs")
    seen: set[Path] = set()
    for pat in patterns:
        for p in root.glob(pat):
            if p in seen or not p.is_file():
                continue
            seen.add(p)
            rel = str(p.relative_to(root))
            nid = f"test:{rel}"
            nodes.append(MultimodalNode(node_id=nid, kind="test", path=rel, name=p.name))
    return nodes
