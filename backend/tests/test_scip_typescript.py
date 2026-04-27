from __future__ import annotations

from pathlib import Path

from heart_transplant.scip_typescript import build_install_command, detect_package_manager


def test_detect_package_manager_prefers_bun_lock(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name":"sample"}', encoding="utf-8")
    (tmp_path / "bun.lock").write_text("", encoding="utf-8")
    assert detect_package_manager(tmp_path) == "bun"


def test_detect_package_manager_falls_back_to_npm_for_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"name":"sample"}', encoding="utf-8")
    assert detect_package_manager(tmp_path) == "npm"


def test_build_install_command_returns_none_for_unknown() -> None:
    assert build_install_command(None) is None

