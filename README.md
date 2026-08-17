# TORC Plane

TORC is the proposed lineage and continuity control plane for Lugos agents.

The project name is a working codename. `Transient Operations, Retained Continuity` is a useful mnemonic, not a requirement that should shape APIs or component boundaries.

## Core claim

An enduring agent is not a prompt, session, process, model, checkpoint, or host. It is the governed lineage connecting those temporary embodiments.

TORC preserves that lineage, compiles target-fit execution projections from it, controls which activation currently has authority, and records auditable succession when authority moves.

## Explanatory model

| Layer | Plain responsibility |
|---|---|
| Mind | Model inference, active reasoning, and immediate context |
| TORC Plane | Identity, lineage, authority, projection, succession, and provenance |
| Body | Harness, process, tools, workspace, credentials, host, and external actions |

This is explanatory language only. TORC does not need to proxy every model token or tool call, and it must not become a latency-critical middleware layer merely to satisfy the metaphor.

## What TORC owns

- Stable lineage identity and immutable lineage revisions
- The current authoritative lineage head
- Activation leases and duplicate-authority prevention
- Versioned self-model revisions
- Target-specific execution projections
- Fit decisions and their evidence
- Explicit handoff, acceptance, rejection, rollback, and branching records
- Provenance and integrity verification across the lineage

## What TORC does not own

- Model inference or provider routing
- General workflow execution
- Tool execution or sandbox enforcement
- Broad memory capture and semantic recall
- Cross-machine file synchronization
- Persona, skill, or source-pack custody
- Chat UI, HUD rendering, or operator messaging transport

Those concerns already belong to other Lugos components. See `docs/integration-boundaries.md`.

## Three representations

1. **Canonical lineage**: append-only, model-independent evidence and state history.
2. **Current self-model**: a versioned interpretation of role, goals, commitments, methods, assumptions, and active work.
3. **Execution projection**: an ephemeral representation shaped for a particular model, harness, capability set, policy envelope, and context budget.

The projection may change shape and size. The provenance chain may not be rewritten.

## Current status

P0 is implemented as a local Python and SQLite vertical slice. It demonstrates
append-only canonical revisions, deterministic fit and projection, exclusive
authority, immutable handoff preparation, separate acceptance, transactional
lease transfer, and tamper verification. It remains a research prototype, not
a production TORC runtime or a provider integration.

The evidence and remaining limits are recorded in `docs/p0-results.md`.

The bounded P2 pilot completed successfully on a real implementation-to-review
handoff. Its thin local operator surface reuses the P0 domain machinery, binds
a prepared handoff to one target activation, exports a clearly derived brief
and reconstruction template, fails closed on integrity errors, and retains the
same acceptance-gated lease transfer. See `docs/p2-pilot.md` for the completed
result and authority limits.

P3 now includes an operator-initiated failure-recovery path. It freezes failure
evidence and an assigned replacement without prematurely moving authority,
preserves the old lease on rejection, and atomically marks the old activation
failed when the bound replacement is accepted. See `docs/p3-recovery.md`.

P3 also includes explicit append-only rollback. An authoritative activation can
restore a strict ancestor's canonical state into a new revision while preserving
the full chain and retaining the same lease. See `docs/p3-rollback.md`.

P3 now also supports atomic creation of a new, independently authoritative
lineage whose immutable root pins and copies the current source head without
changing source authority. See `docs/p3-branch.md`.

P4 adds a read-only operator explanation contract. `torc lineage explain`
derives the current bearer, every authority change, handoff and fit rationale,
and rollback or branch context from one verified SQLite snapshot. The report is
explicitly non-canonical and fails closed instead of explaining invalid
provenance. See `docs/p4-visibility.md`.

TORC also includes the first provider-agnostic project snapshot artifact slice.
It collects manifest-bounded Git evidence, validates content-addressed
candidate projections, writes separate acceptance receipts, advances a
portable current pointer only after acceptance, and renders accepted snapshots
as standalone read-only HTML. It has no provider SDK dependency. See
`docs/artifacts/README.md`.

## Baseline setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
python -m torc doctor --json
python -m torc demo --state-dir .torc/demo --json
python -m torc inspect --state-dir .torc/demo --lineage demo-lineage --json
python -m torc lineage explain --state-dir .torc/demo --lineage demo-lineage --json
python -m torc verify --state-dir .torc/demo --lineage demo-lineage --json
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m torc doctor --json
python -m torc demo --state-dir .torc/demo --json
python -m torc inspect --state-dir .torc/demo --lineage demo-lineage --json
python -m torc lineage explain --state-dir .torc/demo --lineage demo-lineage --json
python -m torc verify --state-dir .torc/demo --lineage demo-lineage --json
```

The deterministic demo reports `activation-source` as the lease holder before
and after preparation, then `activation-target` after acceptance. Its projection
uses 65 of 70 estimated words, includes all required continuity sections, and
exports seven immutable JSON artifacts under `.torc/demo/artifacts/`.

## Documents

- `docs/project-brief.md` - problem, hypothesis, constraints, and kill criteria
- `docs/architecture.md` - full plane boundary and component model
- `docs/domain-model.md` - identifiers, records, and invariants
- `docs/vertical-slice.md` - initial falsifiable implementation slice
- `docs/evaluation-plan.md` - comparison against simpler alternatives
- `docs/p1a-experimental-readiness-spec.md` - apparatus required before comparison
- `docs/p1a-scope-envelope.json` - bounded P1a implementation authority and budgets
- `docs/plans/2026-08-06-p1a-experimental-readiness-implementation-plan.md` - ordered P1a implementation and verification work
- `docs/integration-boundaries.md` - ownership relative to existing Lugos modules
- `docs/roadmap.md` - evidence-gated sequence after the first slice
- `docs/p0-results.md` - P0 proof, observed scope, and remaining unknowns
- `docs/p2-pilot.md` - minimal real session-handoff dogfood workflow
- `docs/p2-pilot-scope-envelope.json` - bounded P2 pilot authority and budgets
- `docs/p3-recovery.md` - bounded operator-initiated failure-recovery workflow
- `docs/p3-recovery-scope-envelope.json` - failure-recovery authority and budgets
- `docs/p3-rollback.md` - explicit append-only canonical-state restoration
- `docs/p3-rollback-scope-envelope.json` - rollback authority and budgets
- `docs/p3-branch.md` - new-lineage branch creation and provenance
- `docs/p3-branch-scope-envelope.json` - branch-creation authority and budgets
- `docs/p4-visibility.md` - read-only authority and continuity explanation contract
- `docs/p4-visibility-scope-envelope.json` - bounded P4 visibility authority and budgets
- `docs/project-snapshot-artifacts.md` - three-record artifact architecture, reconnaissance, and Phase 2 boundary
- `docs/artifacts/README.md` - project snapshot schemas, CLI, retention, renderer, and cold-agent refresh index
- `docs/prompts/CODEX_BOOTSTRAP_PROMPT.md` - implementation task for Codex
