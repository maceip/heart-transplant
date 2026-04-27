from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from heart_transplant.ingest.import_extractor import extract_import_edges
from heart_transplant.ingest.neighborhoods import build_neighborhood_index
from heart_transplant.models import (
    CodeNode,
    FileNode,
    ProjectNode,
    SourceRange,
    StructuralArtifact,
    StructuralEdge,
    SymbolKind,
)
from heart_transplant.scip.path_normalization import (
    build_file_uri,
    build_project_node_id,
    build_provisional_symbol_uri,
)

TREE_SITTER_LANGUAGES = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".py": "python",
    ".go": "go",
}
CUSTOM_LANGUAGES = {
    ".prisma": "prisma",
}
SUPPORTED_SOURCE_SUFFIXES = set(TREE_SITTER_LANGUAGES) | set(CUSTOM_LANGUAGES)

ROUTE_VERBS = frozenset({"get", "post", "put", "delete", "patch", "all", "use", "head", "options"})
SCIP_ELIGIBLE_SYMBOL_KINDS = frozenset(
    {
        SymbolKind.FUNCTION,
        SymbolKind.CLASS,
        SymbolKind.INTERFACE,
        SymbolKind.METHOD,
        SymbolKind.VARIABLE,
        SymbolKind.REACT_HOOK,
        SymbolKind.CONFIG_OBJECT,
        SymbolKind.MIDDLEWARE,
        SymbolKind.SERVICE_BOUNDARY,
    }
)


@dataclass(frozen=True)
class NodeRule:
    node_type: str
    kind: SymbolKind
    name_field: str | None = "name"


LANGUAGE_RULES: dict[str, list[NodeRule]] = {
    "javascript": [
        NodeRule("function_declaration", SymbolKind.FUNCTION),
        NodeRule("variable_declarator", SymbolKind.FUNCTION),
        NodeRule("class_declaration", SymbolKind.CLASS),
        NodeRule("method_definition", SymbolKind.METHOD, "name"),
    ],
    "typescript": [
        NodeRule("function_declaration", SymbolKind.FUNCTION),
        NodeRule("variable_declarator", SymbolKind.FUNCTION),
        NodeRule("class_declaration", SymbolKind.CLASS),
        NodeRule("interface_declaration", SymbolKind.INTERFACE),
        NodeRule("method_definition", SymbolKind.METHOD, "name"),
    ],
    "tsx": [
        NodeRule("function_declaration", SymbolKind.FUNCTION),
        NodeRule("variable_declarator", SymbolKind.FUNCTION),
        NodeRule("class_declaration", SymbolKind.CLASS),
        NodeRule("interface_declaration", SymbolKind.INTERFACE),
        NodeRule("method_definition", SymbolKind.METHOD, "name"),
    ],
    "python": [
        NodeRule("function_definition", SymbolKind.FUNCTION),
        NodeRule("class_definition", SymbolKind.CLASS),
    ],
    "go": [
        NodeRule("function_declaration", SymbolKind.FUNCTION),
        NodeRule("method_declaration", SymbolKind.METHOD),
        NodeRule("interface_type", SymbolKind.INTERFACE, None),
    ],
}


def ingest_repository(repo_path: Path, repo_name: str) -> StructuralArtifact:
    repo_path = repo_path.resolve()
    code_nodes: list[CodeNode] = []
    edges: list[StructuralEdge] = []
    parsers_used: set[str] = set()
    file_nodes: list[FileNode] = []
    project_id = build_project_node_id(repo_name)
    project_node = ProjectNode(
        node_id=project_id,
        name=repo_name.rsplit("/", 1)[-1] if "/" in repo_name else repo_name,
        repo_name=repo_name,
    )

    files_by_rel_path: dict[str, Path] = {}
    for path in walk_source_files(repo_path):
        rel = path.relative_to(repo_path).as_posix()
        files_by_rel_path[rel] = path

    existing_rel_paths = set(files_by_rel_path.keys())

    for rel_path, abs_path in sorted(files_by_rel_path.items()):
        language = TREE_SITTER_LANGUAGES.get(abs_path.suffix.lower()) or CUSTOM_LANGUAGES.get(abs_path.suffix.lower())
        if not language:
            continue
        parsers_used.add(language)
        content = abs_path.read_text(encoding="utf-8", errors="ignore")
        surface_node = build_file_surface_node(
            repo_name=repo_name,
            project_id=project_id,
            rel_path=rel_path,
            content=content,
            language=language,
        )
        code_nodes.append(surface_node)
        file_nodes.append(
            FileNode(
                node_id=build_file_uri(repo_name, rel_path),
                file_path=rel_path,
                repo_name=repo_name,
                language=language,
                project_id=project_id,
            )
        )
        if language == "prisma":
            file_nodes_chunk = extract_prisma_model_nodes(
                repo_name=repo_name,
                project_id=project_id,
                rel_path=rel_path,
                content=content,
            )
            code_nodes.extend(file_nodes_chunk)
            edges.extend(build_contains_edges(repo_name, rel_path, [surface_node, *file_nodes_chunk]))
        else:
            parser = get_parser(language)
            tree = parser.parse(content.encode("utf-8"))
            file_nodes_chunk = extract_code_nodes(
                repo_name=repo_name,
                project_id=project_id,
                rel_path=rel_path,
                content=content,
                root=tree.root_node,
                language=language,
            )
            code_nodes.extend(file_nodes_chunk)
            edges.extend(build_contains_edges(repo_name, rel_path, [surface_node, *file_nodes_chunk]))
            edges.extend(
                extract_import_edges(
                    repo_name,
                    rel_path,
                    tree.root_node,
                    language,
                    existing_rel_paths,
                )
            )

    pr_id = project_node.node_id
    for fn in file_nodes:
        edges.append(
            StructuralEdge(
                source_id=pr_id,
                target_id=fn.node_id,
                edge_type="CONTAINS",
                repo_name=repo_name,
            )
        )

    nbrs = build_neighborhood_index(project_node, file_nodes, code_nodes, edges)
    artifact_id = build_artifact_id(repo_name)
    return StructuralArtifact(
        artifact_id=artifact_id,
        repo_name=repo_name,
        repo_path=str(repo_path),
        project_id=project_id,
        node_count=len(code_nodes),
        edge_count=len(edges),
        parser_backends=sorted(parsers_used),
        project_node=project_node,
        file_nodes=file_nodes,
        code_nodes=code_nodes,
        edges=edges,
        neighborhoods=nbrs,
    )


def build_file_surface_node(
    *,
    repo_name: str,
    project_id: str,
    rel_path: str,
    content: str,
    language: str,
) -> CodeNode:
    """Materialize the file as an architectural surface, not only as a symbol container."""

    line_count = max(content.count("\n") + 1, 1)
    return CodeNode(
        scip_id=f"codefile:{rel_path}",
        name=Path(rel_path).name,
        kind=SymbolKind.FILE_SURFACE,
        file_path=rel_path,
        range=SourceRange(start_line=1, start_col=0, end_line=line_count, end_col=0),
        content=content[:4000],
        repo_name=repo_name,
        language=language,
        project_id=project_id,
        original_provisional_id=f"codefile:{rel_path}",
        symbol_source="file_surface",
    )


def walk_source_files(root: Path) -> Iterable[Path]:
    ignored_dirs = {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".turbo",
        ".cache",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        ".venv",
        ".venv-win",
        "venv",
        "env",
        "ENV",
        ".tox",
        ".nox",
    }
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path.suffix.lower() in SUPPORTED_SOURCE_SUFFIXES:
            yield path


def _python_function_kind(node: Node) -> SymbolKind:
    p = node.parent
    while p:
        if p.type == "class_definition":
            return SymbolKind.METHOD
        if p.type == "function_definition":
            return SymbolKind.FUNCTION
        p = p.parent
    return SymbolKind.FUNCTION


def _decode_js_string(n: Node) -> str:
    t = n.text
    if not t:
        return ""
    s = t.decode("utf-8", errors="ignore").strip()
    if len(s) >= 2 and s[0] in "'\"`" and s[-1] == s[0]:
        s = s[1:-1]
    return s


def _route_handler_label(node: Node) -> str:
    args = node.child_by_field_name("arguments")
    if not args or not args.named_child_count:
        return f"route_L{node.start_point[0] + 1}"
    a0 = args.named_children[0]
    if a0.type in {"string", "string_fragment", "string_literal"} and (s := _decode_js_string(a0)):
        sub = s.strip().strip("/").replace("/", "_")
        return f"route_{sub or 'root'}"[:100]
    return f"route_L{node.start_point[0] + 1}"


def is_route_handler_call(node: Node) -> bool:
    if node.type != "call_expression":
        return False
    fn = node.child_by_field_name("function")
    if not fn or fn.type != "member_expression":
        return False
    prop = fn.child_by_field_name("property")
    if not prop or not prop.text:
        return False
    name = prop.text.decode("utf-8", errors="ignore")
    if name not in ROUTE_VERBS:
        return False
    args = node.child_by_field_name("arguments")
    if not args or args.named_child_count < 2:
        return False
    a1 = args.named_children[1]
    return a1.type in {
        "arrow_function",
        "function_expression",
        "function_declaration",
    }


def extract_code_nodes(
    repo_name: str,
    project_id: str,
    rel_path: str,
    content: str,
    root: Node,
    language: str,
) -> list[CodeNode]:
    rules = LANGUAGE_RULES.get(language, [])
    lines = content.splitlines()
    code_nodes: list[CodeNode] = []

    def add_node(*, name: str, kind: SymbolKind, node: Node) -> None:
        source_range = SourceRange(
            start_line=node.start_point[0] + 1,
            start_col=node.start_point[1] + 1,
            end_line=node.end_point[0] + 1,
            end_col=node.end_point[1] + 1,
        )
        body = extract_source_slice(lines, source_range)
        pid = make_provisional_scip_id(repo_name, rel_path, name, kind, source_range.start_line)
        code_nodes.append(
            CodeNode(
                scip_id=pid,
                name=name,
                kind=kind,
                file_path=rel_path,
                range=source_range,
                content=body,
                repo_name=repo_name,
                language=language,
                project_id=project_id,
                original_provisional_id=pid,
                provisional_scip_id=pid,
                symbol_source="provisional",
            )
        )

    def visit(n: Node) -> None:
        for rule in rules:
            if n.type != rule.node_type:
                continue
            kind = rule.kind
            if language == "python" and n.type == "function_definition":
                kind = _python_function_kind(n)
            if language == "go" and n.type == "function_declaration" and n.child_by_field_name("receiver") is not None:
                kind = SymbolKind.METHOD
            name = extract_node_name(n, lines, rule)
            if not name and n.type != "interface_type":
                break
            if n.type == "interface_type" and not name:
                break
            if not name:
                break
            if n.type == "variable_declarator" and kind == SymbolKind.FUNCTION:
                value_node = n.child_by_field_name("value")
                if value_node is not None and value_node.type not in {"arrow_function", "function_expression"}:
                    if not is_addressable_variable_declarator(n):
                        break
                    kind = SymbolKind.VARIABLE
            kind = refine_architectural_kind(name=name, kind=kind, node=n, rel_path=rel_path)
            add_node(name=name, kind=kind, node=n)
            break

        if language in {"javascript", "typescript", "tsx"} and is_route_handler_call(n):
            add_node(name=_route_handler_label(n), kind=SymbolKind.ROUTE_HANDLER, node=n)

    stack = [root]
    while stack:
        node = stack.pop()
        visit(node)
        stack.extend(reversed(node.children))

    if not code_nodes and is_file_level_config_boundary(rel_path, content):
        add_node(name=file_level_boundary_name(rel_path), kind=SymbolKind.CONFIG_OBJECT, node=root)

    return code_nodes


def extract_prisma_model_nodes(
    *,
    repo_name: str,
    project_id: str,
    rel_path: str,
    content: str,
) -> list[CodeNode]:
    """Extract durable Prisma model boundaries without treating fields as graph nodes."""
    nodes: list[CodeNode] = []
    lines = content.splitlines()
    for match in re.finditer(r"(?m)^model\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", content):
        name = match.group(1)
        start_line = content[: match.start()].count("\n") + 1
        end_line = find_matching_prisma_block_end(lines, start_line)
        source_range = SourceRange(
            start_line=start_line,
            start_col=1,
            end_line=end_line,
            end_col=max(1, len(lines[end_line - 1]) + 1 if end_line - 1 < len(lines) else 1),
        )
        pid = make_provisional_scip_id(repo_name, rel_path, name, SymbolKind.DB_MODEL, start_line)
        nodes.append(
            CodeNode(
                scip_id=pid,
                name=name,
                kind=SymbolKind.DB_MODEL,
                file_path=rel_path,
                range=source_range,
                content=extract_source_slice(lines, source_range),
                repo_name=repo_name,
                language="prisma",
                project_id=project_id,
                original_provisional_id=pid,
                provisional_scip_id=pid,
                symbol_source="provisional",
            )
        )
    return nodes


def find_matching_prisma_block_end(lines: list[str], start_line: int) -> int:
    depth = 0
    for idx in range(start_line - 1, len(lines)):
        line = lines[idx]
        depth += line.count("{")
        depth -= line.count("}")
        if depth <= 0 and idx >= start_line - 1:
            return idx + 1
    return len(lines)


def refine_architectural_kind(name: str, kind: SymbolKind, node: Node, rel_path: str) -> SymbolKind:
    """Stamp architecturally useful seams while preserving SCIP-addressable boundaries."""
    if kind not in SCIP_ELIGIBLE_SYMBOL_KINDS:
        return kind
    lowered_name = name.lower()
    lowered_path = rel_path.lower()
    value_node = node.child_by_field_name("value") if node.type == "variable_declarator" else None
    value_type = value_node.type if value_node is not None else ""
    content = (node.text or b"").decode("utf-8", errors="ignore")
    lowered_content = content.lower()

    if re.match(r"^use[A-Z0-9_]", name) and rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
        return SymbolKind.REACT_HOOK
    if "middleware" in lowered_name or lowered_name.endswith(("guard", "handler")) and "middleware" in lowered_path:
        return SymbolKind.MIDDLEWARE
    if re.search(r"(middleware|guard)s?/", lowered_path) and kind in {SymbolKind.FUNCTION, SymbolKind.VARIABLE}:
        return SymbolKind.MIDDLEWARE
    if "config" in lowered_name or "env" in lowered_name or "schema" in lowered_name:
        if value_type in {"object", "object_pattern", "object_expression", "call_expression"} or kind == SymbolKind.FUNCTION:
            return SymbolKind.CONFIG_OBJECT
    if any(part in lowered_path for part in ("/config", "/env", "/schema")) and kind in {SymbolKind.FUNCTION, SymbolKind.VARIABLE}:
        return SymbolKind.CONFIG_OBJECT
    if lowered_name.endswith(("service", "repository", "repo", "client", "adapter", "provider")):
        return SymbolKind.SERVICE_BOUNDARY
    if re.search(r"/(services?|repositories|adapters|providers)/", lowered_path):
        return SymbolKind.SERVICE_BOUNDARY
    if any(token in lowered_content for token in ("new elysia(", "new express(", "hono<", "router(")):
        return SymbolKind.SERVICE_BOUNDARY
    return kind


def is_file_level_config_boundary(rel_path: str, content: str) -> bool:
    lowered_path = rel_path.lower()
    lowered_content = content.lower()
    return (
        ("config" in lowered_path or lowered_path.endswith((".config.ts", ".config.js", ".config.mjs")))
        and "export default" in lowered_content
        and re.search(r"\b(defineconfig|config|env|schema|database|datasource)\b", lowered_content) is not None
    )


def file_level_boundary_name(rel_path: str) -> str:
    stem = rel_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_")
    return cleaned or "file_config"


def build_contains_edges(repo_name: str, rel_path: str, code_nodes: list[CodeNode]) -> list[StructuralEdge]:
    file_node_id = build_file_uri(repo_name, rel_path)
    return [
        StructuralEdge(
            source_id=file_node_id,
            target_id=code_node.scip_id,
            edge_type="CONTAINS",
            repo_name=repo_name,
        )
        for code_node in code_nodes
    ]


def extract_node_name(node: Node, lines: list[str], rule: NodeRule) -> str | None:
    if node.type == "interface_type":
        type_node = node.parent.child_by_field_name("name") if node.parent else None
        return decode_node_text(type_node, lines)

    if node.type == "variable_declarator":
        value_node = node.child_by_field_name("value")
        if (
            value_node is None
            or (
                value_node.type not in {"arrow_function", "function_expression"}
                and not is_addressable_variable_declarator(node)
            )
        ):
            return None
        name_node = node.child_by_field_name("name")
        if name_node is not None and name_node.type != "identifier":
            return None
        return decode_node_text(name_node, lines)

    if rule.name_field:
        named = node.child_by_field_name(rule.name_field)
        if named is not None:
            return decode_node_text(named, lines)

    for child in node.children:
        if child.type == "identifier":
            return decode_node_text(child, lines)
    return None


def is_addressable_variable_declarator(node: Node) -> bool:
    """Promote exported/top-level bindings, but not local variables inside functions."""
    if node.type != "variable_declarator":
        return False
    parent = node.parent
    while parent is not None:
        if parent.type in {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_definition",
            "statement_block",
        }:
            return False
        if parent.type == "export_statement":
            return True
        if parent.type == "program":
            return True
        parent = parent.parent
    return False


def decode_node_text(node: Node | None, lines: list[str]) -> str | None:
    if node is None:
        return None
    source_range = SourceRange(
        start_line=node.start_point[0] + 1,
        start_col=node.start_point[1] + 1,
        end_line=node.end_point[0] + 1,
        end_col=node.end_point[1] + 1,
    )
    return extract_source_slice(lines, source_range).strip() or None


def extract_source_slice(lines: list[str], source_range: SourceRange) -> str:
    start_index = source_range.start_line - 1
    end_index = source_range.end_line - 1
    if start_index < 0 or end_index >= len(lines):
        return ""
    if start_index == end_index:
        return lines[start_index][source_range.start_col - 1 : source_range.end_col - 1]

    pieces = [lines[start_index][source_range.start_col - 1 :]]
    if end_index - start_index > 1:
        pieces.extend(lines[start_index + 1 : end_index])
    pieces.append(lines[end_index][: source_range.end_col - 1])
    return "\n".join(pieces)


def make_provisional_scip_id(repo_name: str, rel_path: str, name: str, kind: SymbolKind, start_line: int) -> str:
    return build_provisional_symbol_uri(repo_name, rel_path, name, kind.value, start_line)


def build_artifact_id(repo_name: str) -> str:
    return repo_name.replace("/", "__")
