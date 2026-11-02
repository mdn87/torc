# ADR 0006: Tuan correlation sidecar for projections

**Status:** Proposed
**Date:** 2026-11-02

## Context

Tuan (agent-work measurement) wants to reference the projection a task consumed
by lineage id and sealed payload digest, without reading projection content.
Projections are sealed records whose schema is closed (`additionalProperties:
false`), so a new field would change every digest and break validation, and
`projections` has no index other than its primary key. Autowork now exports
`TUAN_CORRELATION_ID` into the environment of the processes it launches; that is
the only join key available that is not derived from content.

## Decision

When `Store.insert_hashed_record` inserts a projection in a process whose
environment carries a non-empty `TUAN_CORRELATION_ID`, Torc appends one JSON line
`{"correlation_id", "projection_id", "lineage_id", "record_sha256", "recorded_at"}`
to `tuan-correlations.jsonl` in the state directory, after the insert commits.
The sealed record, its digest, the schema and the SQLite schema version are
unchanged; read-only opens of existing databases are unaffected. Without the
variable nothing is written. A failure to append never fails the insert.

Tuan reads only the sidecar, by correlation id, through the state directory it is
told about; it never opens `torc.sqlite3`.

## Consequences

Projections compiled by Autowork-launched work (`torc lineage carry`, `torc
handoff prepare` inside a dispatched child) become referenceable by task
identity. The sidecar is append-only and identifier-only; it is not covered by
the database's immutability triggers and is not part of `torc verify`. The
exact-prefix capture manifest has no live producer today; when one exists, the
analogous change belongs in its `bindings`.
