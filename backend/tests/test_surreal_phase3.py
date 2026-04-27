from __future__ import annotations

import json
from pathlib import Path

from heart_transplant.db.schema import apply_schema
from heart_transplant.db.surreal_loader import load_artifact
from heart_transplant.db.verify import verify_artifact_in_db
from heart_transplant.ingest.treesitter_ingest import ingest_repository


def test_surreal_load_and_verify_in_memory(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "a.ts").write_text("export function secretAuth() { return 1; }\n", encoding="utf-8")
    a = ingest_repository(repo, "demo/phase3")
    d = a.model_dump(mode="json")
    ad = tmp_path / "art"
    ad.mkdir()
    (ad / "structural-artifact.json").write_text(json.dumps(d), encoding="utf-8")
    from surrealdb import Surreal  # type: ignore[import-not-found]

    with Surreal("mem://") as db:  # noqa: SIM117
        db.use("htp3", "g3")
        apply_schema(db)
        load_artifact(ad, db=db)
        v = verify_artifact_in_db(ad, db=db)
        assert v["pass"] is True
