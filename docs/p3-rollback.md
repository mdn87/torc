# P3 Explicit Rollback

Status: implemented bounded slice.

## Meaning

TORC rollback is an append-only restoration of an earlier canonical state. It
does not move the lineage head backward or erase the decisions that followed
the selected revision. Instead, it appends a `rollback_applied` revision whose
parent is the current head and whose canonical state exactly matches a strict
ancestor.

The same activation and lease remain authoritative and advance to the new
revision. No handoff or authority transition occurs because no bearer changes.
If the authoritative activation is unavailable, failure recovery must happen
first.

The rollback revision freezes:

- the earlier target revision and its content hash;
- the operator rationale and decision reference;
- external evidence references; and
- the exact head, activation, and lease observed before rollback.

`--expected-head` is mandatory. If the lineage advanced after the operator
inspected it, rollback fails closed rather than discarding unseen canonical
work. A rollback also makes any handoff prepared from the former head stale;
the existing handoff guard prevents that snapshot from transferring authority.

## Operator flow

First inspect the lineage and choose a strict ancestor revision:

```powershell
python -m torc inspect `
  --state-dir .torc/pilot `
  --lineage torc-dev `
  --json
```

Then append the restoration:

```powershell
python -m torc lineage rollback `
  --state-dir .torc/pilot `
  --lineage torc-dev `
  --activation activation-current `
  --expected-head revision-current `
  --target-revision revision-earlier `
  --operator-ref operator-rollback-decision `
  --rationale "Restore the last accepted canonical direction." `
  --evidence-ref review-finding-rollback `
  --json
```

Optionally inspect the unchanged bearer, then run the required verification:

```powershell
python -m torc lineage status --state-dir .torc/pilot --lineage torc-dev --json
python -m torc verify --state-dir .torc/pilot --lineage torc-dev --json
```

## Boundaries

Rollback changes only TORC's canonical state. It cannot undo filesystem edits,
tool calls, deployments, provider actions, database changes, workflow effects,
or uncheckpointed session state. This slice adds no database migration, service,
automatic rollback policy, authority transfer, branch, merge, provider call, or
parent-repository integration.
