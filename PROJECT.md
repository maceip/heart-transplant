# heart-transplant — Master Project Document

**Last Updated**: 2026-04-28
**Current Phase**: **Phase 8.5 proof-tightening**, **Phase 9 practical temporal replay**, and the first LogicLens evidence-contract surfaces are in `main`. **Phases 10–13** have first-pass implementations, but their roadmap gates are not launch claims yet. The repo-root launch gate and `paper-checklist` are the source of truth for beta readiness and paper-alignment status.

## Current State

We have a real foundation across the original Phase 0-8 roadmap, with explicit launch caveats:

- `run-hard-gates.cmd` / `run-hard-gates.ps1` are the reproducible repo-local beta gate. A phase is not launch-green unless that script reports pass on the artifact being shipped.
- Current review found the previous hard-gate shortcut depended on a private harness and the latest local gate run was not fully green. Treat older claims that phases 0-5, 7, and 8 “pass protected hard gates” as stale until regenerated with the in-repo shortcut.
- Phase 6 has a real Continue-facing integration module, but the local operator proof is not complete because `cn` / Continue CLI is not currently on PATH.

Current paper-alignment status from `heart-transplant paper-checklist`: 8 tracked LogicLens-style features, 1 implemented, 7 partial, 0 missing. The implemented feature is repository program graph construction. The partial features are symbol identity/reference completeness, semantic blocks, evidence retrieval, graph persistence, temporal reasoning, cross-layer reasoning, and regret planning.

### What Has Been Built (Real & Solid)
- Clean, well-architected Python backend (`backend/src/heart_transplant/`)
- High-quality structural ingestion using Tree-sitter + real SCIP symbol resolution
- First-class file-surface nodes, SCIP-only orphan promotion, and parser coverage for TypeScript/TSX/JavaScript/Python/Go/Prisma/Rust/Java/C/C++
- 24-block semantic ontology with neighborhood-aware classification
- Full SurrealDB persistence, schema, indexing, and query layer
- Production-grade MCP server with useful graph tools (`get_node`, `get_neighbors`, `trace_symbol_path`, `find_block_nodes`, `get_impact_radius`, etc.)
- Intelligent blast radius computation with pruning logic
- Working evaluation harness (Phase 7) with gold benchmark
- Strong validation infrastructure (`phase_metrics.py`, `validation_gates.py`, non-gamable gates)
- **Phase 8.5 (implemented, proof surface tightening)**: `maximize-audit`, `maximize-report`, `maximize-gates`, expanded `gold_block_benchmark.json` + holdout file, `build-gold` holdout/main splits
- **Phase 9 (implemented, not paper-grade yet)**: `temporal-scan`, `temporal-diff`, `temporal-gates`, and optional `temporal-scan --replay-snapshots` are real. Historical replay now runs Tree-sitter ingest for selected commits; SCIP + semantic replay across full histories is still future work.
- **LogicLens evidence surfaces (partial)**: `canonical-graph`, `explain-node`, `explain-file`, `trace-dependency`, `find-architectural-block`, `answer-with-evidence`, `evidence-benchmark`, and `paper-checklist` exist as CLI surfaces, with tests covering the current evidence contract.
- **Artifact receipts (partial, useful)**: `ingest-local` now writes `artifact-manifest.json`, `run-manifest` can regenerate it for older artifacts, and `graph-integrity` checks structural, SCIP, semantic, and manifest layers separately.
- **50-repo corpus rail (partial, useful)**: the first EC2 synthesis is preserved under `docs/evals/`; the three crash failures and six zero-node successes are documented, with landed fixes for deep traversal and Rust/Java/C/C++ parser coverage. The full corpus still needs rerun before replacing the historical baseline.

### After 8.5 / 9 — What’s Next

The next build target is not “more pages.” It is making the LogicLens-style behavior measurable: run the 50-repo corpus again after the parser fixes, raise the block benchmark, and turn evidence retrieval into a scored question-answer harness. **Phase 14** (`program-surface`) remains the cross-phase readiness index so stubs cannot masquerade as shipped gates.

**Phase 8.5 (current deliverable):** static graph system audited, benchmark broadened, and proof surface being tightened; use `maximize-gates` with a real artifact **and a holdout artifact** for evidence.

### Key Documents

- **PROJECT.md** — This file (single source of truth)
- `docs/roadmaps/logiclens-paper-grade-roadmap.md` — Full roadmap, including the Phase 8.5 checkpoint before Phase 9
- `backend/src/heart_transplant/` — Main codebase
- `docs/evals/gold_block_benchmark.json` — Gate benchmark (25+ items, 4+ repos, 8+ blocks; main split excludes holdout repo `clean-elysia`)
- `docs/evals/gold_block_benchmark_holdout.json` — Holdout split for `clean-elysia` only
- `docs/evals/gold_block_benchmark_broad.json` — Broader exploratory benchmark used to expose classifier weaknesses
- `docs/evals/gold-standards.md` — Gold row schema, audit command, and holdout policy
- `docs/evals/evidence_questions.json` — First evidence-QA benchmark seed set
- `docs/evals/block-classification-benchmark-2026-04-27.md` — Latest measured block-classification benchmark readout
- `docs/evals/trending-repos-2026-04-27.json` and `docs/evals/trending-repos-top50-2026-04-27.json` — Dated daily-trending input manifests for private beta corpus refreshes
- `docs/evals/trending-top50-ec2-first-synthesis-2026-04-27.md` — First 50-repo EC2 synthesis with landed fix notes for the nine first-run complications
- `docs/roadmaps/alignment-and-trajectory-2026-04-27.md` — Current alignment doc for LogicLens-backend and Regret SDK trajectory
- `docs/roadmaps/logiclens-next-tranche-2026-04-27.md` — Outcome-gated next tranche to reach a respectable LogicLens backend and Regret SDK baseline

### Useful Commands

```powershell
cd backend

.\.venv-win\Scripts\python.exe -m heart_transplant.cli phase-metrics --artifact-dir <artifact-directory> --gold-set ..\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli gold-audit ..\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli gold-audit ..\docs\evals\gold_block_benchmark_holdout.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli run-manifest <artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli graph-integrity <artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli evidence-benchmark <artifact-directory> --questions ..\docs\evals\evidence_questions.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli validate-gates --artifact-dir <artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli test-graph <artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli maximize-audit --artifact-dir <artifact-directory> --gold-set ..\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli maximize-report <artifact-directory> --gold-set ..\docs\evals\gold_block_benchmark.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli maximize-gates <artifact-directory> --gold-set ..\docs\evals\gold_block_benchmark.json --holdout-artifact-dir <holdout-artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli maximize-gates <artifact-directory> --gold-set ..\docs\evals\gold_block_benchmark.json --holdout-artifact-dir <holdout-artifact-directory> --holdout-gold-set ..\docs\evals\gold_block_benchmark_holdout.json
.\.venv-win\Scripts\python.exe -m heart_transplant.cli corpus-gate ..\docs\evals\trending-top50-ec2-results-2026-04-27.jsonl
.\.venv-win\Scripts\python.exe -m heart_transplant.cli temporal-scan C:\path\to\git\repo --max-commits 25
.\.venv-win\Scripts\python.exe -m heart_transplant.cli temporal-scan C:\path\to\git\repo --max-commits 25 --replay-snapshots --replay-limit 5
.\.venv-win\Scripts\python.exe -m heart_transplant.cli program-surface
.\.venv-win\Scripts\python.exe -m heart_transplant.cli paper-checklist
.\.venv-win\Scripts\python.exe -m heart_transplant.cli canonical-graph <artifact-directory>
.\.venv-win\Scripts\python.exe -m heart_transplant.cli answer-with-evidence "Which files own authentication?" --artifact-dir <artifact-directory>
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
.\run-hard-gates.cmd --artifact-dir <artifact-directory> --gold-set docs\evals\gold_block_benchmark.json
.\run-hard-gates.cmd --artifact-dir <artifact-directory> --gold-set docs\evals\gold_block_benchmark.json --holdout-artifact-dir <holdout-artifact-directory> --holdout-gold-set docs\evals\gold_block_benchmark_holdout.json
```

### Next Engineer Instructions

Use `maximize-gates` on a full reference artifact plus a real holdout artifact when you need a single JSON answer for Phase 8.5 exit criteria. Use `program-surface` before a release to confirm which phase entrypoints are still stubs.

---
**Status**: Structural graph construction is the only LogicLens checklist item marked implemented. The other seven paper-shaped capabilities are partial and need scored gates before they become product claims. Phase 9 has Tree-sitter replay for selected commits, but not full SCIP + semantic historical replay. Phase 6 still needs Continue CLI operator proof.
**Decision**: Near-term work should prioritize rerunning the 50-repo corpus after parser fixes, raising the holdout block benchmark, and scoring evidence-backed architecture answers. Keep `program-surface` and `paper-checklist` accurate as entrypoints grow.
