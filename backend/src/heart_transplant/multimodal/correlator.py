from __future__ import annotations

from pathlib import Path

from heart_transplant.multimodal.models import MultimodalEdge, MultimodalNode


def _rel_id(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def correlate_tests_to_sources(test_nodes: list[MultimodalNode], root: Path) -> list[MultimodalEdge]:
    root = root.resolve()
    edges: list[MultimodalEdge] = []
    for tn in test_nodes:
        p = root / tn.path
        stem = p.stem.replace(".test", "").replace(".spec", "").replace("_test", "")
        candidates = [
            root / tn.path.replace(".test.ts", ".ts").replace(".spec.ts", ".ts"),
            root / tn.path.replace(".test.tsx", ".tsx").replace(".spec.tsx", ".tsx"),
        ]
        for c in candidates:
            if c.is_file():
                rel = _rel_id(c, root)
                edges.append(
                    MultimodalEdge(
                        source_id=tn.node_id,
                        target_id=f"codefile:{rel}",
                        edge_kind="TESTS",
                    )
                )
                break
        if not any(e.source_id == tn.node_id for e in edges):
            for src in root.rglob(f"{stem}.ts"):
                if "node_modules" in str(src):
                    continue
                rel = _rel_id(src, root)
                if ".test." in rel or ".spec." in rel:
                    continue
                edges.append(
                    MultimodalEdge(
                        source_id=tn.node_id,
                        target_id=f"codefile:{rel}",
                        edge_kind="TESTS_HEURISTIC",
                    )
                )
                break
    return edges


def correlate_openapi_to_routes(
    openapi_path: Path,
    root: Path,
    route_globs: tuple[str, ...] = ("**/routes/**/*.ts", "**/*route*.ts"),
) -> list[MultimodalEdge]:
    from heart_transplant.multimodal.parsers.openapi_parser import extract_paths

    root = root.resolve()
    edges: list[MultimodalEdge] = []
    spec_id = f"spec:{str(openapi_path.relative_to(root))}"
    route_files: list[Path] = []
    for g in route_globs:
        route_files.extend(p for p in root.glob(g) if p.is_file())
    for method, tmpl, _oid in extract_paths(openapi_path):
        slug = tmpl.strip("/").replace("{", "").replace("}", "").replace("/", " ")
        keys = [k for k in slug.split() if len(k) > 2]
        for rf in route_files[:80]:
            text = rf.read_text(encoding="utf-8", errors="replace").lower()
            if any(k.lower() in text for k in keys[:3]) or tmpl.lower() in text:
                rel = _rel_id(rf, root)
                edges.append(
                    MultimodalEdge(
                        source_id=spec_id,
                        target_id=f"codefile:{rel}",
                        edge_kind=f"OPENAPI_{method}",
                    )
                )
                break
    return edges
