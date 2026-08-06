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

This repository is a seed. It contains architecture, schemas, examples, and a minimal importable Python package. It does not yet implement a production TORC runtime.

The first Codex task is deliberately narrow: build a local, deterministic, no-network vertical slice that proves authoritative lineage handoff between two synthetic execution substrates. See `docs/vertical-slice.md` and `docs/prompts/CODEX_BOOTSTRAP_PROMPT.md`.

## Baseline setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
python -m torc doctor --json
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m torc doctor --json
```

## Documents

- `docs/project-brief.md` - problem, hypothesis, constraints, and kill criteria
- `docs/architecture.md` - full plane boundary and component model
- `docs/domain-model.md` - identifiers, records, and invariants
- `docs/vertical-slice.md` - initial falsifiable implementation slice
- `docs/evaluation-plan.md` - comparison against simpler alternatives
- `docs/integration-boundaries.md` - ownership relative to existing Lugos modules
- `docs/roadmap.md` - evidence-gated sequence after the first slice
- `docs/prompts/CODEX_BOOTSTRAP_PROMPT.md` - implementation task for Codex
