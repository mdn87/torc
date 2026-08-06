# Codex Task: Build the TORC P0 Lineage-Handoff Vertical Slice

You are working in the root of the `mdn87/torc` repository, expected to live as a separate repository at `lugos/torc`.

Build the first falsifiable TORC vertical slice. Do not build the whole future plane.

## Read first

Read these files in order before editing:

1. `AGENTS.md`
2. `README.md`
3. `docs/project-brief.md`
4. `docs/architecture.md`
5. `docs/domain-model.md`
6. `docs/vertical-slice.md`
7. `docs/integration-boundaries.md`
8. `docs/evaluation-plan.md`
9. `docs/scope-envelope.json`
10. every file under `schemas/`

When `../AGENTS.md` and `../config/agent-governance/README.md` exist, read them and treat them as higher-level constraints. Recompute or verify the current parent scope-policy hash before relying on the seed's recorded hash.

## Objective

Implement a local Python and SQLite demonstration of one lineage moving from one synthetic execution substrate to another through:

- append-only canonical lineage revisions
- a versioned self-model
- deterministic target-fit projection
- one authoritative activation lease
- an immutable reason-coded handoff snapshot
- a separate target reconstruction and acceptance result
- transactional authority transfer only after acceptance
- provenance and tamper verification

The implementation must make the core claim testable without calling a real model.

## Scope envelope

Stay inside the accepted P0 envelope:

- no daemon, server, watcher, or background process
- no network or provider API calls
- no edits outside this repository
- no parent Lugos submodule update
- no custom protocol
- no custom cryptography
- no automatic branch merge
- no attempt to replace Autowork, Sulis, agent-continuity, Omniroute, Bran, or agent-mail

Use Python 3.11+ and the standard library wherever practical. SQLite through `sqlite3` is the required durable store for this slice. Keep runtime dependencies at zero unless a concrete requirement makes that impossible. Development-only dependencies already exist in `pyproject.toml`.

## Required architecture

Keep domain logic separate from CLI presentation. A reasonable package decomposition is:

```text
src/torc/
  cli.py
  ids.py
  canonical.py
  models.py
  store.py
  projections.py
  fit.py
  leases.py
  handoffs.py
  verify.py
  demo.py
```

You may adjust names or combine small modules, but preserve the domain boundaries. Do not create a monolithic `cli.py` or one generic manager object.

Implement explicit schema migration from version 0 to version 1. The database must have enough relational constraints and transactions to enforce the P0 authority rules. Do not rely only on Python checks for exclusive lease ownership.

Use deterministic canonical JSON with sorted keys and stable separators for content hashing. SHA-256 provides tamper evidence only. State this clearly in code and docs.

## Required records and behavior

Implement, at minimum:

- lineage
- immutable lineage revision
- structured self-model within or referenced by a revision
- substrate descriptor
- fit decision
- execution projection
- activation
- authoritative lease
- immutable handoff snapshot
- separate handoff result
- exported immutable JSON artifact metadata

Use the seed schemas as the contract. Tighten them only when implementation evidence requires it. If you change a schema, update its example and tests in the same change.

The source revision must remain byte-for-byte and hash-for-hash stable when compiling projections for different targets or budgets.

A projection must record:

- source lineage and revision
- target substrate
- compiler and policy versions
- budget and estimate unit
- included sections and canonical source references
- omitted sections and reasons
- redactions
- content hash

Required continuity sections cannot be dropped to satisfy a target budget. Projection must fail with a specific domain error when the required material cannot fit.

## Fit behavior

Use the synthetic candidates in `examples/substrates.example.json` or replace them with equivalent fixtures.

The P0 fit evaluator must be deterministic and explainable. Apply hard eligibility checks before scoring. Record every factor and evidence value. Do not claim that the result is an objectively best frontier model.

Use a task-phase transition from implementation to independent review as the successful demo handoff reason.

## Handoff behavior

Preparation must:

1. Confirm the source activation holds the current lineage lease.
2. Freeze the source revision and authority state.
3. Link the fit decision and target projection.
4. Record the controlled reason code and rationale.
5. Store continuity requirements.
6. Write an immutable handoff snapshot.
7. Leave authority unchanged.

Resolution must:

1. Store a structured target reconstruction separately from the snapshot.
2. Evaluate each required continuity field.
3. Record accepted or rejected disposition.
4. On rejection, leave source authority unchanged.
5. On acceptance, create or activate the target bearer and transfer the lease in one SQLite transaction.
6. Append the corresponding canonical lineage revision and provenance links.

Do not mutate the handoff snapshot after resolution.

## CLI requirements

Preserve the existing `about` and `doctor` commands. Replace the seed implementation status when P0 is complete.

Add:

```text
torc demo --state-dir <path> --json
torc inspect --state-dir <path> --lineage <id> --json
torc verify --state-dir <path> [--lineage <id>] --json
```

`demo` should create its own deterministic scenario using synthetic substrates, execute one accepted handoff, and export inspectable JSON artifacts under the state directory. It should report identifiers, projection choices, lease holder before and after, artifact paths, and verification result.

`inspect` should return the lineage head, revision history, current authority, activations, projections, handoffs, and integrity status without mutating state.

`verify` should fail nonzero and return structured errors when any record, hash, parent link, projection source, handoff link, or authority transition is invalid.

## Test requirements

Implement all tests listed in `docs/vertical-slice.md`. At minimum, prove:

1. Accepted handoff transfers authority and verifies.
2. A duplicate active lease is rejected transactionally.
3. Preparation alone does not transfer authority.
4. Rejected acceptance preserves source authority.
5. Different target budgets produce different projections from an unchanged canonical revision.
6. Required continuity fields cannot be omitted for budget.
7. Tampering with a revision, projection, snapshot, or result is detected.
8. A result cannot resolve a missing or mismatched snapshot.
9. Authority cannot transfer to an unrelated activation.
10. The demo produces inspectable artifacts and passes verification.
11. Schema examples remain valid.
12. Migration from an empty database is repeatable and idempotent.

Use temporary directories and isolated SQLite files in tests. Do not depend on wall-clock sleeps or network access.

## Documentation updates

After implementation:

- Update `README.md` current status and quick-start output.
- Update `docs/vertical-slice.md` with the exact implemented commands and evidence paths.
- Add a short `docs/p0-results.md` containing what was proven, what remains unproven, observed scope, and any divergence from the seed.
- Update `docs/scope-envelope.json` observed values and vertical-slice evidence.
- Do not expand the roadmap based only on passing unit tests.

## Verification

Run from the repository root in the project virtual environment:

```text
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m torc doctor --json
python -m torc demo --state-dir .torc/demo --json
python -m torc inspect --state-dir .torc/demo --lineage demo-lineage --json
python -m torc verify --state-dir .torc/demo --lineage demo-lineage --json
```

If generated identifiers make the demo lineage ID different, use the ID returned by `demo` for the following commands.

Inspect `git diff` after verification. Do not push or modify the parent Lugos repository. Stop and report a scope-change request if the implementation requires any forbidden architecture trigger.

## Completion report

Report:

- files changed
- implemented domain and storage boundaries
- exact verification commands and results
- demo lineage, source activation, target activation, handoff, and result identifiers
- lease holder before and after
- projection budget, included sections, and omitted sections
- any accepted operational risk
- any part of the full TORC Plane intentionally left unimplemented
