# TORC Agent Rules

## Project

- **Type**: Python research prototype and Lugos subproject
- **Primary language**: Python 3.11+
- **Repository root**: this repository; never hardcode one host-specific absolute path in shared files
- **Expected parent**: the Lugos superproject, normally at `../`

## Purpose

TORC is the lineage and continuity control plane for Lugos agents. It governs durable lineage identity, authoritative activation, target-fit projection, succession, branching, and provenance across transient agent executions.

The full architecture is broader than the first implementation slice. Do not mistake the initial handoff experiment for the permanent boundary of the plane.

## Read order

Before substantive work, read:

1. `README.md`
2. `docs/project-brief.md`
3. `docs/architecture.md`
4. `docs/domain-model.md`
5. `docs/vertical-slice.md`
6. `docs/integration-boundaries.md`
7. `docs/scope-envelope.json`

When the parent Lugos repository is available, also read `../AGENTS.md` and `../config/agent-governance/README.md`. Parent scope and safety rules narrow this repository's rules.

## Architectural invariants

- The lineage is durable. Activations are transient.
- Canonical history is append-only. Corrections are new records, not history edits.
- The self-model may be revised, but each revision is attributable and reversible.
- Execution projections are derived artifacts, never canonical truth.
- Exactly one activation may hold the authoritative lease for a lineage head.
- A target does not gain authority merely by receiving a projection.
- Handoff preparation and handoff acceptance are separate immutable records.
- Rejected or failed acceptance leaves the prior authority unchanged.
- Every selection, projection, checkpoint, handoff, and authority change has provenance.
- TORC may reinterpret history. It may not alter the history being interpreted.

## Scope boundaries

TORC must not become another general agent framework. Do not implement model inference, tool execution, workflow orchestration, semantic memory, synchronization, identity personas, or provider routing inside TORC when an existing Lugos component owns it.

Use adapters and references at those boundaries. `docs/integration-boundaries.md` is authoritative.

## Initial slice constraints

For the first vertical slice:

- Use local Python and SQLite only.
- Add no daemon, web server, background worker, watcher, or network dependency.
- Use synthetic substrate descriptors and deterministic fit rules.
- Do not call provider APIs or attempt live frontier-model routing.
- Do not edit the parent Lugos repository.
- Do not add a custom cryptographic algorithm. Standard SHA-256 is integrity evidence, not access control.
- Implement the smallest production-shaped path that can prove or falsify the core continuity claim.

## Terminology

Prefer plain domain terms in code and records:

`lineage`, `revision`, `head`, `self_model`, `activation`, `lease`, `substrate`, `projection`, `fit_decision`, `handoff`, `acceptance`, `branch`, `artifact_ref`, and `evidence_ref`.

The torc, mind, and body imagery may explain the project. It must not determine class names, storage layout, or runtime topology.

## Coding conventions

- Use a `src/` package layout.
- Keep core domain logic independent of CLI presentation.
- Prefer immutable dataclasses or frozen value objects for records.
- Use UTC RFC 3339 timestamps.
- Use UUIDs or content-derived identifiers consistently and document the choice.
- Serialize deterministic JSON with sorted keys where hashes depend on content.
- Keep SQLite migrations explicit and versioned from the first durable schema.
- Keep adapter interfaces narrow. Do not design hypothetical provider integrations beyond the current slice.
- Do not silently recover from integrity or authority errors.

## Verification

The minimum completion gate is:

```text
python -m pytest
python -m torc doctor --json
python -m torc demo --state-dir <temporary-directory> --json
python -m torc verify --state-dir <temporary-directory> --json
```

The last two commands are targets for the first implementation and do not exist in the seed.

Tests must cover the invariants in `docs/vertical-slice.md`, including rejected acceptance, duplicate lease prevention, projection derivation, and tamper detection.

## Git and repository boundaries

- Keep changes inside this repository unless the operator explicitly expands scope.
- Do not add or update the parent Lugos submodule pointer during implementation.
- Do not push, force-push, rewrite history, or change repository settings unless the operator's current instruction authorizes it.
- Prefer one coherent implementation batch and one verification pass over repeated speculative rewrites.
