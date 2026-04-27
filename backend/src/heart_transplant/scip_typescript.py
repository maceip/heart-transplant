from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from heart_transplant.models import ScipIndexMetadata


def run_scip_typescript_index(
    repo_path: Path,
    repo_name: str,
    artifact_dir: Path,
    *,
    install_deps: bool = False,
) -> ScipIndexMetadata:
    repo_path = repo_path.resolve()
    artifact_dir = artifact_dir.resolve()
    package_manager = detect_package_manager(repo_path)

    if package_manager and not dependencies_installed(repo_path):
        if not install_deps:
            raise RuntimeError(
                f"Dependencies are not installed for {repo_path}. Run with --install-deps or install them manually first."
            )
        install_command = build_install_command(package_manager)
        if install_command is None:
            raise RuntimeError(
                f"Could not find a usable package manager for {repo_path}. Needed one of bun, pnpm, yarn, or npm."
            )
        subprocess.run(install_command, cwd=repo_path, check=True)
        install_performed = True
    else:
        install_command = build_install_command(package_manager) if install_deps and package_manager else None
        install_performed = False

    npx_command = resolve_command("npx")
    output_path = artifact_dir / "index.scip"
    index_command = [
        npx_command,
        "-y",
        "@sourcegraph/scip-typescript",
        "index",
        "--cwd",
        str(repo_path),
        "--output",
        str(output_path),
        "--no-progress-bar",
    ]

    if package_manager == "pnpm":
        index_command.append("--pnpm-workspaces")
    elif package_manager == "yarn":
        index_command.append("--yarn-workspaces")
    elif not (repo_path / "tsconfig.json").exists():
        index_command.append("--infer-tsconfig")

    subprocess.run(index_command, check=True)

    version = subprocess.run(
        [npx_command, "-y", "@sourcegraph/scip-typescript", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip() or None

    return ScipIndexMetadata(
        repo_name=repo_name,
        repo_path=str(repo_path),
        indexer="scip-typescript",
        version=version,
        output_path=str(output_path),
        detected_package_manager=package_manager,
        install_command=install_command,
        install_performed=install_performed,
        index_command=index_command,
    )


def detect_package_manager(repo_path: Path) -> str | None:
    if (repo_path / "bun.lock").exists() or (repo_path / "bun.lockb").exists():
        return "bun"
    if (repo_path / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_path / "yarn.lock").exists():
        return "yarn"
    if (repo_path / "package-lock.json").exists():
        return "npm"
    if (repo_path / "package.json").exists():
        return "npm"
    return None


def build_install_command(package_manager: str | None) -> list[str] | None:
    if package_manager == "bun":
        bun = shutil.which("bun")
        if bun:
            return [bun, "install"]
        npm = shutil.which("npm")
        if npm:
            return [npm, "install"]
        return None

    if package_manager == "pnpm":
        pnpm = shutil.which("pnpm")
        return [pnpm, "install"] if pnpm else None

    if package_manager == "yarn":
        yarn = shutil.which("yarn")
        return [yarn, "install"] if yarn else None

    if package_manager == "npm":
        npm = shutil.which("npm")
        return [npm, "install"] if npm else None

    return None


def dependencies_installed(repo_path: Path) -> bool:
    return (repo_path / "node_modules").exists()


def resolve_command(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"Required command not found on PATH: {name}")
    return resolved
