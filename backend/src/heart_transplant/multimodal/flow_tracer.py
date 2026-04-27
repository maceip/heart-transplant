from __future__ import annotations

from pathlib import Path

from heart_transplant.multimodal.models import FlowHint
from heart_transplant.multimodal.parsers.openapi_parser import extract_paths


def build_flow_hints(openapi_files: list[Path], root: Path) -> list[FlowHint]:
    root = root.resolve()
    hints: list[FlowHint] = []
    for oa in openapi_files:
        rel_dir = oa.parent.relative_to(root)
        guess = ""
        for rf in root.glob("**/routes/**/*.ts"):
            if rf.is_file() and str(rel_dir) in str(rf.parent):
                guess = str(rf.relative_to(root))
                break
        for method, tmpl, oid in extract_paths(oa)[:40]:
            hints.append(
                FlowHint(
                    summary=f"{method} {tmpl}" + (f" ({oid})" if oid else ""),
                    path_template=tmpl,
                    method=method,
                    code_file_guess=guess,
                )
            )
    return hints
