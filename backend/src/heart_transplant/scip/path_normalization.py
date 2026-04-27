from __future__ import annotations

import re
from pathlib import PurePosixPath


def normalize_repo_name(repo_name: str) -> str:
    return repo_name.replace("\\", "/").strip("/")


def normalize_relative_path(path: str) -> str:
    """Normalize to a stable POSIX path key for Tree-sitter / SCIP matching."""
    normalized = path.replace("\\", "/")
    normalized = str(PurePosixPath(normalized))
    return normalized.lstrip("./")


def build_file_uri(repo_name: str, relative_path: str) -> str:
    """Strict canonical URI for a file: ``repo://<repo>/<posix-path>``."""
    normalized_repo = normalize_repo_name(repo_name)
    normalized_path = normalize_relative_path(relative_path)
    return f"repo://{normalized_repo}/{normalized_path}"


def build_project_node_id(repo_name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", normalize_repo_name(repo_name))
    return f"project:{slug}"


def build_external_module_id(package_name: str) -> str:
    return f"module:{normalize_module_spec(package_name)}"


def normalize_module_spec(name: str) -> str:
    s = name.strip().strip("'\"").split("?")[0]
    if s.startswith("@"):
        parts = s.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
    return s.split("/")[0] if s else s


def build_provisional_symbol_uri(
    repo_name: str,
    relative_path: str,
    symbol_name: str,
    symbol_kind: str,
    start_line: int,
) -> str:
    file_uri = build_file_uri(repo_name, relative_path)
    return f"{file_uri}#{symbol_name}:{symbol_kind}:{start_line}"

