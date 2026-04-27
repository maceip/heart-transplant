from __future__ import annotations

from pathlib import Path

from heart_transplant.multimodal.models import MultimodalNode


def collect_infra_nodes(root: Path) -> list[MultimodalNode]:
    root = root.resolve()
    nodes: list[MultimodalNode] = []
    for suffix in (".tf", ".yaml", ".yml"):
        for p in root.rglob(f"*{suffix}"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(root))
            if "node_modules" in rel or ".git" in rel:
                continue
            kind = "terraform" if suffix == ".tf" else "helm_yaml"
            nid = f"infra:{rel}"
            nodes.append(MultimodalNode(node_id=nid, kind=kind, path=rel, name=p.name))
    return nodes
