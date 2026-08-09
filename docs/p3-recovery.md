# P3 Failure Recovery

Status: implemented bounded slice.

## What recovery means

TORC can recover the last verified canonical lineage head when the operator
declares its authoritative activation unavailable. Recovery is an exceptional
acceptance-gated handoff, not automatic liveness detection and not restoration
of uncheckpointed model, process, tool, or workspace state.

Preparation freezes the current lineage head, source activation and lease,
operator declaration, failure evidence, assigned replacement, target-fit
projection, and continuity requirements. It creates a pending replacement but
does not transfer authority. The unavailable source remains the formally fenced
lease holder so no second activation can act with TORC authority before the
replacement reconstructs the required state.

Resolution has three outcomes:

- Rejection records the failed reconstruction and leaves source authority intact.
- Acceptance atomically marks the source activation `failed`, closes its lease,
  appends a linked `handoff_accepted` revision, activates the bound replacement,
  and grants exactly one new lease.
- If the source authority or head changed after preparation, resolution fails
  closed. The operator must prepare a new recovery from the current head.

## Operator flow

The trusted operator must first gather at least one opaque evidence reference
and provide an external assignment reference in the plan. TORC records those
references; it does not inspect the process or authorize the external worker.

```powershell
python -m torc recovery prepare `
  --state-dir .torc/pilot `
  --lineage torc-dev `
  --failed-activation activation-current `
  --plan-file examples/p3-recovery-plan.json `
  --evidence-ref process-probe-001 `
  --json
```

The command exports a derived markdown brief and reconstruction template. Give
those artifacts to the bound replacement activation, then resolve its completed
reconstruction:

```powershell
python -m torc recovery resolve `
  --state-dir .torc/pilot `
  --handoff <handoff-id> `
  --target-activation activation-p3-recovery `
  --reconstruction-file <reconstruction-template-or-completed-file> `
  --json
```

Finally, inspect the bearer and verify the store:

```powershell
python -m torc lineage status --state-dir .torc/pilot --lineage torc-dev --json
python -m torc verify --state-dir .torc/pilot --lineage torc-dev --json
```

## Boundaries

This slice adds no schema migration, daemon, watcher, lease expiry, provider
call, harness control, network dependency, or parent-repository integration.
It relies on existing immutable handoff, activation, lease, revision, artifact,
and authority-transition records. Rollback and lineage branching remain separate
P3 work because they change canonical history semantics rather than replace an
unavailable bearer.
