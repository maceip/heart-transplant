from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from heart_transplant.models import StructuralEdge
from heart_transplant.scip.path_normalization import build_external_module_id, build_file_uri, normalize_relative_path

if TYPE_CHECKING:
    from tree_sitter import Node


def _walk(n: "Node") -> list["Node"]:
    out: list = [n]
    for c in n.children:
        out.extend(_walk(c))
    return out


def _decode_string(n: "Node") -> str:
    raw = n.text
    if not raw:
        return ""
    s = raw.decode("utf-8", errors="ignore").strip()
    if len(s) >= 2 and s[0] in "'\"`" and s[-1] == s[0]:
        s = s[1:-1]
    return s


def _resolve_local_to_existing(
    importer_rel: str,
    spec: str,
    existing_files: set[str],
) -> str | None:
    if not spec.startswith("."):
        return None
    imp_dir = str(PurePosixPath(importer_rel).parent)
    if imp_dir == ".":
        imp_dir = ""
    target = (PurePosixPath(imp_dir) / spec) if imp_dir else PurePosixPath(spec)
    base = normalize_relative_path(str(target))
    for candidate in (
        base,
        base + ".ts",
        base + ".tsx",
        base + ".js",
        base + ".jsx",
        base + ".mjs",
        base + ".cjs",
        base + ".py",
        base + ".go",
    ):
        if candidate in existing_files:
            return candidate
    for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
        alt = normalize_relative_path(str((PurePosixPath(imp_dir) / spec) if imp_dir else PurePosixPath(spec) / f"index{ext}"))
        if alt in existing_files:
            return alt
    for f in existing_files:
        if f == base or f.startswith(base + "/"):
            return f
    return None


def _ts_js_import_spec(n: "Node") -> str | None:
    """`import` / `export ... from` source string (tree-sitter TS/JS)."""
    strings: list[str] = []
    seen_from = b"from" in (n.text or b"")
    for t in _walk(n):
        if t.type in {"string", "string_fragment", "string_literal"} and (d := _decode_string(t)) and d:
            strings.append(d)
    if not strings:
        return None
    if seen_from:
        return strings[-1]
    for s in strings:
        st = s
        if st.startswith("type "):
            st = st[5:].strip()
        if st:
            return st
    return strings[0]


def extract_js_ts_import_edges(
    repo_name: str,
    rel_path: str,
    root: "Node",
    existing_files: set[str],
) -> list[StructuralEdge]:
    out: list[StructuralEdge] = []
    source_id = build_file_uri(repo_name, rel_path)
    seen: set[tuple[str, str, str]] = set()

    def emit(target: str, et: str) -> None:
        k = (source_id, target, et)
        if k in seen:
            return
        seen.add(k)
        out.append(
            StructuralEdge(
                source_id=source_id,
                target_id=target,
                edge_type=et,  # type: ignore[arg-type]
                repo_name=repo_name,
            )
        )

    for n in _walk(root):
        if n.type == "import_statement" or (n.type == "export_statement" and b"from" in (n.text or b"")):
            spec = _ts_js_import_spec(n)
            if not spec or spec == "type":
                continue
            if spec.startswith("type "):
                spec = spec[5:].strip()
            res = _resolve_local_to_existing(rel_path, spec, existing_files)
            if res is not None:
                emit(build_file_uri(repo_name, res), "DEPENDS_ON_FILE")
            else:
                emit(build_external_module_id(spec), "IMPORTS_MODULE")
        elif n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn and fn.type == "identifier" and fn.text == b"require":
                args = n.child_by_field_name("arguments")
                if args and args.named_child_count and args.named_children[0].type in {"string", "string_fragment", "string_literal"} and (
                    s := _decode_string(args.named_children[0])
                ):
                    res = _resolve_local_to_existing(rel_path, s, existing_files)
                    if res is not None:
                        emit(build_file_uri(repo_name, res), "DEPENDS_ON_FILE")
                    else:
                        emit(build_external_module_id(s), "IMPORTS_MODULE")
    return out


def extract_go_import_edges(
    repo_name: str,
    rel_path: str,
    root: "Node",
    existing_files: set[str],
) -> list[StructuralEdge]:
    out: list[StructuralEdge] = []
    source_id = build_file_uri(repo_name, rel_path)
    seen: set[tuple[str, str, str]] = set()

    def emit(target: str, et: str) -> None:
        k = (source_id, target, et)
        if k in seen:
            return
        seen.add(k)
        out.append(
            StructuralEdge(
                source_id=source_id,
                target_id=target,
                edge_type=et,  # type: ignore[arg-type]
                repo_name=repo_name,
            )
        )

    for n in _walk(root):
        if n.type == "import_spec" and n.named_child_count:
            for c in n.children:
                if c.type in {"interpreted_string_literal", "raw_string_literal"} and c.text:
                    s = c.text.decode("utf-8", errors="ignore").strip('"').strip("`")
                    if s.startswith("."):
                        if res := _resolve_local_to_existing(rel_path, s, existing_files):
                            emit(build_file_uri(repo_name, res), "DEPENDS_ON_FILE")
                    else:
                        emit(build_external_module_id(s), "IMPORTS_MODULE")
    return out


def extract_python_import_edges(
    repo_name: str,
    rel_path: str,
    root: "Node",
    existing_files: set[str],
) -> list[StructuralEdge]:
    out: list[StructuralEdge] = []
    source_id = build_file_uri(repo_name, rel_path)
    seen: set[tuple[str, str, str]] = set()

    def emit(target: str, et: str) -> None:
        k = (source_id, target, et)
        if k in seen:
            return
        seen.add(k)
        out.append(
            StructuralEdge(
                source_id=source_id,
                target_id=target,
                edge_type=et,  # type: ignore[arg-type]
                repo_name=repo_name,
            )
        )

    for n in _walk(root):
        if n.type == "import_from_statement":
            mod: str | None = None
            for c in n.children:
                if c.type in {"dotted_name", "relative_import"} and c.text:
                    mod = c.text.decode("utf-8", errors="ignore")
                    break
            if not mod:
                continue
            if mod.startswith(".") and (res := _resolve_local_to_existing(rel_path, mod.replace(".", "/"), existing_files)):
                emit(build_file_uri(repo_name, res), "DEPENDS_ON_FILE")
            else:
                emit(build_external_module_id(mod), "IMPORTS_MODULE")
        if n.type == "import_statement":
            for c in n.children:
                if c.type == "dotted_name" and c.text and (mod := c.text.decode("utf-8", errors="ignore")):
                    emit(build_external_module_id(mod), "IMPORTS_MODULE")
    return out


def extract_import_edges(
    repo_name: str,
    rel_path: str,
    root: "Node",
    language: str,
    existing_files: set[str],
) -> list[StructuralEdge]:
    if language in {"javascript", "typescript", "tsx"}:
        return extract_js_ts_import_edges(repo_name, rel_path, root, existing_files)
    if language == "go":
        return extract_go_import_edges(repo_name, rel_path, root, existing_files)
    if language == "python":
        return extract_python_import_edges(repo_name, rel_path, root, existing_files)
    return []
