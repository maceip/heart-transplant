from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import artifact_root


def ledger_path_default() -> Path:
    return artifact_root().parent / "transplant_ledger.jsonl"


def append_ledger_event(event: dict[str, Any], path: Path | None = None) -> Path:
    p = path or ledger_path_default()
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(UTC).isoformat(), "id": str(uuid.uuid4()), **event}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return p
