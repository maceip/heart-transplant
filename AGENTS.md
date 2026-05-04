# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

heart-transplant is a Python backend that ingests source code repositories, builds a multi-layer program graph (structural, semantic, temporal, causal), and exposes architecture intelligence through a CLI and an MCP server. The single Python package lives under `backend/`.

### Python version

The project requires **Python >= 3.13** (`pyproject.toml`). The VM uses `uv` to manage the Python installation (`uv python install 3.13`). The binary lands in `/root/.local/bin`.

### Virtual environment & dependencies

```bash
cd backend
source .venv/bin/activate
```

All dependencies (including dev) are declared in `backend/pyproject.toml`. Install with `pip install -e ".[dev]"` from inside the venv.

### Running tests

```bash
cd backend && source .venv/bin/activate
python -m pytest          # 90 tests, ~3 s, all use in-memory SurrealDB
```

Tests do **not** require a running SurrealDB server — they use `mem://` in-process.

### Running the CLI

```bash
heart-transplant --help                       # list all commands
heart-transplant ingest-local /path/to/repo   # core structural ingest
heart-transplant classify <artifact-dir>      # semantic block classification
heart-transplant paper-checklist              # LogicLens feature status
```

Artifact directories are auto-created under `.heart-transplant/artifacts/`.

### SurrealDB (optional, not needed for tests)

Only needed for `load-surreal`, `verify-surreal`, `mcp-serve`, and the `persist-*-surreal` commands. Tests bypass it via in-memory mode.

### SCIP indexing (optional)

The `--with-scip` flag on `ingest-local` requires Node.js (`npx @sourcegraph/scip-typescript`). Not needed for standard development or testing.

### Lint

No dedicated linter configuration is committed. `pyright` or `mypy` can be used for type checking but are not in the dev dependencies.

### Key caveats

- The README and PROJECT.md show Windows PowerShell paths (`.venv-win`). On Linux, use `backend/.venv/bin/python` instead.
- The `CanonicalGraph` model emits a Pydantic `UserWarning` about shadowing `schema` — this is expected and harmless.
