# heart-transplant

Clean-room repo extracted from the recent migration work without reusing older `jules-chop` files.

## Layout

- `backend`: ingest, fact extraction, rule engine, and scan server
- `frontend`: repo scan UI and icon/wasm assets
- `cli`: scaffold for a future command-line entrypoint
- `docs/audit`: separation manifests from the `jules-chop` extraction

## Guardrail

This repo is intended to contain only files created during the recent work window, plus new scaffolding added here to replace older mixed-in root files.
