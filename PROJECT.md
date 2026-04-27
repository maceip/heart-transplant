# heart-transplant — Master Project Document

**Last Updated**: 2026-04-26  
**Current Phase**: **Phase 8.5 proof-tightening** and **Phase 9 practical temporal layer** are in `main`. **Phases 10–13** now have first-pass implementations (structural Monte Carlo impact, heuristic regret + surgery JSON, transplant planner + ledger + compileall validation hook, multimodal test/OpenAPI/infra correlation). Roadmap **non-gamable gates** for 10–13 are **not** claimed yet; **Phase 14** `program-surface` tracks import health for these entrypoints.

## Current Honest State

We have a real, working foundation across the original Phase 0-8 roadmap, with one explicit caveat:

- Phases 0-5, 7, and 8 currently pass the protected hard gates on the latest reference artifact.
- Phase 6 has a real Continue-facing integration module, but the local operator proof is not complete because `cn` / Continue CLI is not currently on PATH.

So the honest status is: the graph, semantic, persistence, MCP, blast-radius, and evaluation foundation is real; the Continue operator surface still needs local end-to-end proof.

### What Has Been Built (Real & Solid)
- Clean, well-architected Python backend (`backend/src/heart_transplant/`)
- High-quality structural ingestion using Tree-sitter + real SCIP symbol resolution
- 24-block semantic ontology with neighborhood-aware classification
- Full SurrealDB persistence, schema, indexing, and query layer
- Production-grade MCP server with useful graph tools (`get_node`, `get_neighbors`, `trace_symbol_path`, `find_block_nodes`, `get_impact_radius`, etc.)
- Intelligent blast radius computation with pruning logic
- Working evaluation harness (Phase 7) with gold benchmark
- Strong truthfulness infrastructure (`phase_metrics.py`, `validation_gates.py`, non-gamable gates)
- **Phase 8.5 (implemented, proof surface tightening)**: `maximize-audit`, `maximize-report`, `maximize-gates`, expanded `gold_block_benchmark.json` + holdout file, `build-gold` holdout/main splits
- **Phase 9 (implemented, not paper-grade yet)**: `temporal-scan` and related temporal commands are real, but historical snapshots still infer blocks from versioned file paths instead of replaying full historical Tree-sitter + SCIP ingest

### After 8.5 / 9 — What’s Next

The roadmap’s **Phases 10–13** are the next build targets. **Phase 14** (`program-surface`) is the cross-phase readiness index so stubs cannot masquerade as shipped gates.

**Phase 8.5 (current deliverable):** static graph system audited, benchmark broadened, and proof surface being tightened; use `maximize-gates` with a real artifact **and a holdout artifact** for evidence.

### Key Documents

- **PROJECT.md** — This file (single source of truth)
- `docs/roadmaps/logiclens-paper-grade-roadmap.md` — Full roadmap, including the Phase 8.5 checkpoint before Phase 9
- `backend/src/heart_transplant/` — Main codebase
- `docs/evals/gold_block_benchmark.json` — Gate benchmark (25+ items, 4+ repos, 8+ blocks; main split excludes holdout repo `clean-elysia`)
- `docs/evals/gold_block_benchmark_holdout.json` — Holdout split for `clean-elysia` only
- `docs/evals/gold_block_benchmark_broad.json` — Broader exploratory benchmark used to expose classifier weaknesses
- `docs/evals/trending-repos-2026-04-27.json` — Dated daily-trending input manifest for private beta corpus refreshes

### Useful Commands

```powershell
cd backend

.\.venv-win\Scripts\python.exe -m heart_transplant.cli phase-metrics --artifact-dir <artifact-directory> --gold-set C:\Users\mac\heart-transplant\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli validate-gates --artifact-dir <artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli test-graph <artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli maximize-audit --artifact-dir <artifact-directory> --gold-set C:\Users\mac\heart-transplant\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli maximize-report <artifact-directory> --gold-set C:\Users\mac\heart-transplant\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli maximize-gates <artifact-directory> --gold-set C:\Users\mac\heart-transplant\docs\evals\gold_block_benchmark.json --holdout-artifact-dir <holdout-artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli temporal-scan C:\path\to\git\repo --max-commits 25
.\.venv-win\Scripts\python.exe -m heart_transplant.cli program-surface
.\.venv-win\Scripts\python.exe -m heart_transplant.cli simulate-change "refactor auth middleware" --artifact-dir <artifact-directory> --temporal-report <optional-phase-9-report.json>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli regret-scan --artifact-dir <artifact-directory> --output .heart-transplant\reports\regret-plan.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli execute-transplant <regret_id> --artifact-dir <artifact-directory> --plan .heart-transplant\reports\regret-plan.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli multimodal-ingest C:\path\to\repo --out .heart-transplant\reports\multimodal.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli mcp-serve
```

Refresh the local beta corpus from the dated trending manifest:

```powershell
.\scripts\vendor-trending-inputs.ps1
cd backend
.\.venv-win\Scripts\python.exe -m heart_transplant.cli ingest-vendor-corpus ..\vendor\github-repos
```

Regenerate gate gold from `vendored-ground-truth.json` after editing ground truth:

```powershell
.\.venv-win\Scripts\python.exe -m heart_transplant.cli build-gold ..\docs\evals\vendored-ground-truth.json --out ..\docs\evals\gold_block_benchmark.json --max-items 55 --exclude-repo clean-elysia --include-medium
.\.venv-win\Scripts\python.exe -m heart_transplant.cli build-gold ..\docs\evals\vendored-ground-truth.json --out ..\docs\evals\gold_block_benchmark_holdout.json --max-items 20 --only-repo clean-elysia --include-medium
```

Shortcut from repo root:

```powershell
.\run-hard-gates.cmd --artifact-dir <artifact-directory> --gold-set C:\Users\mac\heart-transplant\docs\evals\gold_block_benchmark.json
```

### Next Engineer Instructions

Use `maximize-gates` on a full reference artifact plus a real holdout artifact when you need a single JSON answer for Phase 8.5 exit criteria. Use `program-surface` before a release to confirm which phase entrypoints are still stubs.

---
**Status**: Phase 8.5 is implemented but still tightening its proof surface. Phase 9 is real and gated, but it is not yet the full historical graph replay system described by the paper-grade target. Phases 10–13 are CLI stubs pending real implementations and gates. Phase 6 still needs Continue CLI operator proof.
**Decision**: Phase 10+ work proceeds only against implementations that can pass the phase-specific non-gamable gates in the roadmap; keep `program-surface` accurate as entrypoints grow.
