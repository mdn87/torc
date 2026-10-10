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

Status: closed. The controlled synthetic series did not pass its comparative
gate, so the operator declined to repeat it and authorized a bounded real-work
P2 pilot instead. That pilot succeeded; see `docs/p1b-results.md` and
`docs/p2-pilot.md`.

- Real task-phase transition
- Comparison against compiled-prompt and native-persistence when available
- Measured continuity and overhead

Gate: TORC beats or materially complements the simpler baseline.

## P2: Lugos contract integration

Status: successful for the bounded real-work slice and closed. TORC governed a
real Codex-to-Claude implementation-review transition, exported operator-facing
continuity artifacts, prevented authority bypass, and preserved external
ownership boundaries. Broader Autowork, Sulis, and Bran identifier adapters are
integration-on-demand work, not remaining P2 exit criteria.

Completed in the bounded slice:

- Express substrate requirements without selecting unauthorized routes
- Export operator-facing continuity artifacts

Deferred until a consuming workflow requires them:

- Link Autowork assignment and outcome identifiers
- Reference Sulis memory and Bran custody records

Gate: no duplicate ownership and no authority bypass.

## P3: succession and recovery

Status: complete for the bounded local P3 slices. Operator-initiated failure
recovery, explicit append-only rollback, and new-lineage branch creation are
implemented without a daemon or database migration. Model or harness succession
uses the ordinary handoff path when the source is available and recovery when it
is not.

- Failure recovery (bounded operator-declared slice complete)
- Model or harness succession (covered by handoff plus recovery semantics)
- Explicit rollback (bounded append-only restore slice complete)
- Branch creation with new lineage identity (bounded local slice complete)

Automatic merge remains deferred.

## P4: operator visibility

Status: bounded local CLI slice implemented. `torc lineage explain` derives a
non-canonical explanation from one verified SQLite snapshot. MCP and HUD
rendering remain integration-on-demand work outside this repository.

- Read-only CLI contract (`lineage explain`)
- Active bearer, pending handoff, fit rationale, and authority-change history
- Recovery, rollback, and branch continuity annotations
- Deferred: thin MCP exposure and HUD or mission-control rendering

Gate: the operator can explain every authority change without reading raw database tables.

## P5: receiver-fitted carry

Status: bounded local slice implemented. ADR 0004 made the carried self TORC's
own responsibility after a review found that no phase since P0 had returned to
it. Compiler `p5-1` derives the budget from the receiver's descriptor, fits
optional state item by item, applies one capability rule, and reads the lineage
history for continuity that was dropped without a resolution. The boundary asks
are advisory. See `docs/p5-receiver-carry.md`.

- Receiver-derived sizing and item-level shaping
- History reading with unaccounted drops and changes since the receiver last bore the lineage
- Revision resolutions (`completed`, `superseded`, `withdrawn`)
- Non-blocking boundary asks in checkpoint and status responses
- `torc lineage carry` at session start; handoffs use the same compiler
- Deferred: a live comparison of the shaped carry against a compiled prompt,
  blocking enforcement of the asks, and history across a branch point

Gate: from unchanged canonical history, the carry differs by receiver and an
omission by the last bearer still reaches the next one.

## Deferred until evidence requires it

- Always-on TORC daemon
- Cross-host authoritative store
- Automated frontier-model availability probing
- Learned fit scoring
- Automatic lineage merging
- Autonomous policy or invariant revision
- Durable-workspace and per-operation backend descriptors, workspace-shaped
  projections, and explicit reconciliation stages. See
  `docs/decisions/cloudflare-computer-borrow-boundary.md`.
