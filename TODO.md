# TODO

Active backlog only. Historical TODO content is preserved at `docs/archive/2026-02-doc-refresh/TODO.original.md`.

## Docs

- [ ] Align remaining legacy design docs with current `/api/v1` routes or mark them explicitly historical.
- [ ] Add a lightweight docs validation script for markdown links + `uv run` command references.

## Engineering

- [ ] Add smoke CI checks for `uv run test-smoke` and `uv run test-e2e` entry points.
- [ ] Evaluate whether Neon helper scripts should support additional secret rotation workflows.

## Ops

- [ ] Decide and document retention/archival job ownership (service vs platform).
- [ ] Define production rate-limit and security-header ownership (service vs gateway).
