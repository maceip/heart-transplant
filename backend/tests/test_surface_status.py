from __future__ import annotations

from heart_transplant.surface.status import program_surface_status


def test_program_surface_lists_phases() -> None:
    report = program_surface_status()
    assert report["report_type"] == "phase_14_program_surface"
    phases = report["phases"]
    assert len(phases) >= 6
    assert all(p.get("import_ok") for p in phases)
