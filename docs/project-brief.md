# Project Brief

## One-paragraph summary

TORC is the Lugos lineage and continuity control plane. It treats a persistent agent as a governed lineage that can be successively embodied by different models, harnesses, processes, workspaces, and hosts. TORC maintains canonical lineage history, a versioned self-model, target-fit execution projections, activation authority, explicit succession, and provenance. It does not perform model inference or domain work.

## Hypothesis

A frontier agent can retain materially better operational continuity across model or runtime changes when it receives a target-fit projection backed by an immutable canonical lineage and controlled authority transfer, rather than a free-form prompt summary alone.

This is a hypothesis, not a justification for a permanent subsystem.

## Operator and consumers

- **Operator**: the Lugos owner
- **Primary consumers**: Lugos orchestration surfaces and agent harness adapters
- **Initial consumer**: a deterministic local demo used to test the continuity model before any provider integration

## Core capabilities

- Create and identify an enduring lineage
- Append immutable lineage revisions
- Maintain a versioned self-model without rewriting evidence
- Register execution-substrate descriptors
- Evaluate substrate fit from declared requirements and evidence
- Compile an execution projection within a target budget
- Acquire and release authoritative activation leases
- Prepare a reason-coded handoff snapshot
- Validate target reconstruction before authority transfer
- Record acceptance, rejection, rollback, and branch provenance
- Verify the lineage and artifact hash chain

## Constraints and unknowns

- It is not yet proven that TORC preserves more useful continuity than a carefully compiled prompt.
- It is not yet proven that an existing framework cannot provide these semantics with a thin adapter.
- "Best available frontier agent" is underspecified until capability, policy, environment, reliability, cost, and context evidence are defined.
- Context sizing in the first slice will use a deterministic approximation, not a provider tokenizer.
- Automated fit evaluation may become a false precision layer if its evidence is weak.
- Lineage transfer must not allow a recipient to silently broaden authority or rewrite prior commitments.
- Branching and merging semantics are likely harder than linear succession and are deferred from the first slice.

## First vertical slice

Build a local Python and SQLite path that:

1. Creates one lineage and two synthetic execution substrates.
2. Activates the first substrate under an exclusive lease.
3. Appends a checkpoint and self-model revision.
4. Produces a constrained projection for the second substrate.
5. Freezes an immutable handoff snapshot with an explicit reason.
6. Validates a structured reconstruction from the target.
7. Transfers authority only after acceptance.
8. Verifies the resulting provenance chain and demonstrates tamper detection.

No live model or provider is required.

## Success checks

- Canonical revisions remain unchanged when projections vary by target or budget.
- A second authoritative activation cannot be created while the first lease is valid.
- Handoff preparation alone does not change authority.
- Rejected acceptance leaves the source activation authoritative.
- Accepted handoff creates a new authority record and closes the source lease.
- Every authority transition references its reason, source revision, target projection, and acceptance evidence.
- Editing a stored immutable artifact causes verification to fail.
- The demo and test suite run on Windows and macOS without a service process.

## Kill or narrow criteria

Narrow TORC to adapters or delete it if the experiment shows any of the following:

- A compiled prompt plus existing Lugos records preserves the same required continuity with less operational burden.
- An existing agent runtime already supplies canonical lineage, exclusive authority, target-fit projection, acceptance-gated succession, and provenance with an acceptable adapter surface.
- Fit scoring cannot outperform explicit operator or Autowork routing decisions.
- Projection and handoff overhead exceed their measured continuity benefit.
- The only remaining value is renaming facilities that already exist in Sulis, Autowork, or agent-continuity.
