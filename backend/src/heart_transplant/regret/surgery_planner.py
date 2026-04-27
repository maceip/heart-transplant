from __future__ import annotations

from heart_transplant.regret.models import RegretItem, SurgeryPlan, SurgeryStep


def plan_for_regret(item: RegretItem) -> SurgeryPlan:
    pid = item.pattern_id
    if pid == "scattered_auth":
        steps = [
            SurgeryStep(
                order=1,
                action="Inventory auth entrypoints and shared session utilities.",
                rationale="Reduce duplicate middleware and guards.",
                risk="medium",
                verification="Run auth integration tests; grep for duplicate session checks.",
            ),
            SurgeryStep(
                order=2,
                action="Extract a single auth service/facade and route adapters through it.",
                rationale="Centralize policy and token validation.",
                risk="high",
                verification="Contract tests for the facade; staged rollout per route module.",
            ),
        ]
    elif pid == "database_sprawl":
        steps = [
            SurgeryStep(
                order=1,
                action="Define a narrow repository or data-access module boundary.",
                rationale=f"Address {item.title.lower()} by constraining imports.",
                risk="medium",
                verification="Module graph check: no new cross-layer imports.",
            ),
            SurgeryStep(
                order=2,
                action="Migrate highest-churn call sites first (see temporal hotspots if available).",
                rationale="Maximize payoff while limiting blast radius.",
                risk="medium",
                verification="Unit tests for migrated modules.",
            ),
        ]
    elif pid == "logging_inconsistency":
        steps = [
            SurgeryStep(
                order=1,
                action="Inventory logging call sites, logger factories, and telemetry sinks by runtime boundary.",
                rationale="Identify incompatible log formats, missing context fields, and direct console usage before changing behavior.",
                risk="low",
                verification="Search for direct console/logging calls and compare emitted fields against the telemetry schema.",
            ),
            SurgeryStep(
                order=2,
                action="Introduce one structured logging facade with required context fields and adapters for existing sinks.",
                rationale="Make telemetry consistent without forcing a persistence-layer migration.",
                risk="medium",
                verification="Unit tests for formatter/adapters plus a smoke run that asserts request/job identifiers appear in logs.",
            ),
            SurgeryStep(
                order=3,
                action="Migrate the highest-volume or incident-relevant logging call sites first.",
                rationale="Improve operator signal quickly while limiting churn.",
                risk="medium",
                verification="Golden log snapshots or telemetry query checks for migrated paths.",
            ),
        ]
    elif pid == "fat_route_file":
        steps = [
            SurgeryStep(
                order=1,
                action="Split handlers by domain subdirectory or controller modules.",
                rationale="Lower coupling and file size.",
                risk="low",
                verification="Router registration smoke test.",
            ),
        ]
    else:
        steps = [
            SurgeryStep(
                order=1,
                action="Triage evidence lines and confirm pattern with owners.",
                rationale="Avoid false positives before refactor.",
                risk="low",
                verification="Manual review checklist.",
            ),
        ]

    return SurgeryPlan(regret_id=item.regret_id, title=item.title, steps=steps)
