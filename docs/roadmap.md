# Evidence-Gated Roadmap

## Seed

- Architecture and boundaries
- Domain vocabulary and JSON schemas
- Minimal importable package and seed doctor
- Codex implementation prompt

## P0: local deterministic handoff

- SQLite append-only lineage store
- Synthetic substrate catalog and fit decision
- Deterministic projection compiler
- Activation leases
- Immutable handoff snapshot and separate result
- Demo, inspection, verification, and tests

Gate: all P0 invariants pass without a service process or network dependency.

## P1a: experimental readiness

- One versioned experiment fixture and scoring oracle
- Adapter-neutral run and artifact contracts
- One source harness adapter
- One target harness adapter
- Compiled-prompt, native-persistence, and TORC lane materializers
- Deterministic replay, scoring, retry, inspection, and verification
- One unscored real two-agent smoke transition

Gate: all lanes are repeatable and comparable; compiled-prompt and TORC complete
one real smoke transition; native persistence is completed or evidenced as
unavailable. See `docs/p1a-experimental-readiness-spec.md`.

## P1b: real two-agent comparison

- Real task-phase transition
- Comparison against compiled-prompt and native-persistence when available
- Measured continuity and overhead

Gate: TORC beats or materially complements the simpler baseline.

## P2: Lugos contract integration

- Link Autowork assignment and outcome identifiers
- Express substrate requirements without selecting unauthorized routes
- Reference Sulis memory and Bran custody records
- Export operator-facing continuity artifacts

Gate: no duplicate ownership and no authority bypass.

## P3: succession and recovery

- Failure recovery
- Model or harness succession
- Explicit rollback
- Branch creation with new lineage identity

Automatic merge remains deferred.

## P4: operator visibility

- Read-only MCP or CLI contract
- HUD or mission-control lineage view
- Active bearer, pending handoff, fit rationale, and provenance graph

Gate: the operator can explain every authority change without reading raw database tables.

## Deferred until evidence requires it

- Always-on TORC daemon
- Cross-host authoritative store
- Automated frontier-model availability probing
- Learned fit scoring
- Automatic lineage merging
- Autonomous policy or invariant revision
