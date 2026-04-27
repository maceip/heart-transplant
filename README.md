# heart-transplant

Canonical restart of the project around a verified stack:

- Tree-sitter
- SCIP
- SurrealDB
- Pydantic-AI
- MCP Python SDK
- Continue CLI

## What We Kept

- `vendor/`
  - local vendored GitHub repos for evaluation
- `docs/`
  - evaluation notes and architecture comparisons
- the 24 universal semantic blocks

## What We Archived

This clean-room restart intentionally does not include the previous exploratory
prototype in the checkout. The canonical backend path is `backend/src/heart_transplant/`;
legacy code was excluded during the transplant rather than preserved under an
`archive/` directory in this repository.

## First Milestone

The active milestone is **structural ingestion**:

1. parse local repos with Tree-sitter
2. emit `CodeNode` records using the verified schema direction
3. persist durable structural artifacts

Current command:

```powershell
python -m heart_transplant.cli ingest-local C:\path\to\repo
```

or, once installed from `backend/`:

```powershell
heart-transplant ingest-local C:\path\to\repo
```

To also generate a real SCIP index for TypeScript or JavaScript repos:

```powershell
heart-transplant ingest-local C:\path\to\repo --with-scip
```

If dependencies are not installed yet:

```powershell
heart-transplant ingest-local C:\path\to\repo --with-scip --install-deps
```

## Current Honest State

Real now:

- clean canonical Python backend package
- 24-block ontology in Python
- Tree-sitter-backed local structural ingest
- durable JSON structural artifacts
- real `scip-typescript` indexing into the artifact directory for TS/JS repos
- SCIP→artifact consumption, optional corpus symbol index, and SurrealDB load/verify
- block classification and optional persistence of semantics to Surreal
- **MCP stdio server** (`heart-transplant mcp-serve` or `python -m heart_transplant.mcp_server`) exposing graph tools when Surreal is running and loaded
- dated trending-repo input manifests for beta corpus refreshes (`docs/evals/trending-repos-2026-04-27.json`)

Deferred / in progress (see [docs/roadmaps/logiclens-paper-grade-roadmap.md](docs/roadmaps/logiclens-paper-grade-roadmap.md)):

- end-to-end **Continue** operator session proof on your machine
- full paper-style eval harness and scoring (starter gold file: [docs/evals/gold_block_benchmark.json](docs/evals/gold_block_benchmark.json))

## Beta Corpus

Trending repos are vendored locally, not committed:

```powershell
.\scripts\vendor-trending-inputs.ps1
cd backend
.\.venv-win\Scripts\python.exe -m heart_transplant.cli ingest-vendor-corpus ..\vendor\github-repos
```
