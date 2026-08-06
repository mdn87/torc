# P0 Vertical Slice: Local Lineage Handoff

## Question

Can TORC preserve an authoritative, auditable lineage across a change of execution substrate without reducing continuity to a mutable prompt summary?

## Scope

Build one local process and one SQLite database. Use two synthetic substrate descriptors. No provider, network, background process, or parent-repository integration is permitted.

## Scenario

1. Create lineage `demo-lineage` from a canonical seed containing identity, goals, constraints, commitments, open work, evidence references, and optional context.
2. Register `substrate-a` with a larger context budget and implementation capabilities.
3. Register `substrate-b` with a smaller context budget and review capabilities.
4. Activate `substrate-a` and acquire the lineage lease.
5. Append a checkpoint and a revised self-model.
6. Evaluate a task-phase transition from implementation to independent review.
7. Compile a projection for `substrate-b` that preserves all required continuity fields while omitting lower-priority context within budget.
8. Prepare an immutable handoff snapshot.
9. Produce a structured target reconstruction.
10. Run acceptance checks.
11. Transfer the authoritative lease only after acceptance.
12. Append the accepted handoff to the lineage and verify the full chain.

## Required library behavior

- Initialize and migrate a local SQLite store.
- Serialize deterministic canonical JSON for hash input.
- Append lineage revisions without update or delete paths.
- Acquire one active authoritative lease transactionally.
- Reject duplicate authority acquisition.
- Compile projections from source-linked sections under a deterministic budget.
- Store projection inclusion and omission provenance.
- Prepare a handoff without changing authority.
- Store target reconstruction and acceptance as a separate record.
- Transfer authority in one transaction after successful acceptance.
- Verify revision links, artifact hashes, projection sources, and authority transitions.

## Acceptance requirements

At minimum, the target reconstruction must correctly identify:

- lineage identity
- current responsibility
- settled decisions
- active commitments
- hard constraints and prohibitions
- unresolved work
- known uncertainties
- reason for handoff
- canonical source revision

A target may add a new inference, but it must label that inference as new rather than inherited.

## Projection rules for P0

Required sections:

1. identity and role
2. hard constraints
3. active commitments
4. open work
5. handoff reason and expected target responsibility

Optional sections are selected by priority until the target budget is reached. Every omitted section records a reason such as `budget`, `capability_irrelevant`, `policy_redaction`, or `superseded`.

Use a deterministic word or character estimate. Do not add a tokenizer dependency during P0.

## CLI surface

Codex should implement these stable demonstration commands:

```text
torc demo --state-dir <path> --json
torc inspect --state-dir <path> --lineage <id> --json
torc verify --state-dir <path> [--lineage <id>] --json
```

`demo` may orchestrate internal service calls directly. P0 does not need a complete operator CRUD CLI.

## Required tests

1. End-to-end accepted handoff transfers authority and produces a valid chain.
2. Duplicate active lease acquisition fails.
3. Preparing a handoff does not transfer authority.
4. Rejected acceptance preserves source authority.
5. Two projections from the same revision with different budgets differ, while the canonical revision hash remains unchanged.
6. Required continuity fields cannot be omitted to satisfy budget. Compilation fails instead.
7. Tampering with a revision, projection, snapshot, or result is detected.
8. A handoff result cannot reference a missing or different snapshot.
9. Authority cannot transfer to a target activation outside the accepted handoff.
10. The demo is deterministic apart from generated identifiers and timestamps.

## Evidence produced

The demo output should report:

- lineage and revision identifiers
- source and target activation identifiers
- source and target substrate identifiers
- fit decision and reason
- projection size, included sections, and omitted sections
- handoff snapshot and result identifiers
- lease holder before and after acceptance
- verification status
- paths of inspectable exported JSON artifacts

## Stop conditions

Stop and record a scope-change request instead of implementing any of the following:

- new daemon or service process
- network or provider integration
- cross-host production dependency
- custom protocol
- custom cryptography
- automatic lineage merge
- modifications outside the TORC repository
- replacement or modification of Autowork assignment authority
