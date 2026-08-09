# P4 Operator Visibility

Status: bounded local CLI contract.

## Purpose

TORC can derive one operator-facing explanation of a lineage from the local
canonical store. The explanation identifies the current bearer, accounts for
every authority change, distinguishes pending or rejected handoffs from
accepted succession, and annotates recovery, rollback, and branch events.

The report is explicitly derived and non-canonical. It does not create a
revision, artifact, lease, transition, or other durable record, and it cannot
grant or transfer authority.

## Operator command

```powershell
python -m torc lineage explain `
  --state-dir .torc/pilot `
  --lineage torc-dev `
  --json
```

The JSON response conforms to `schemas/operator-view.schema.json`. Its stable
top-level fields are:

- `lineage` and `current_authority`: the requested identity, verified head, and
  current activation, substrate, and lease;
- `authority_changes`: the chronological explanation of initial authority,
  branch authority, accepted handoffs, and recovery transfers;
- `handoffs`: prepared, accepted, and rejected handoffs, including the fact
  that pending or rejected records did not transfer authority;
- `fit_decisions`: the recorded target requirements, candidate evidence, and
  selected substrate for the handoffs in view;
- `continuity_events`: append-only rollback and branch annotations that are
  important to continuity but are not ordinary authority transfers;
- `relationships`: immutable record identifiers connecting the explanation to
  revisions, activations, leases, handoffs, results, fit decisions, and related
  lineages;
- `verification`, `trusted`, `explanation_complete`, and `warnings`: whether
  the asserted explanation is supported by a valid, complete provenance chain.

`derived` is always `true`, `canonical` is always `false`, and `report_kind`
is always `lineage_explanation`.

## Trust behavior

The explanation and verification are read from one SQLite snapshot so the
output cannot combine records from different moments. A trusted explanation
must account for the complete authority-transition ledger and end at the same
activation, lease, and revision reported by current authority.

If integrity or explanation checks fail, the command returns a nonzero exit
status with `trusted: false`, `explanation_complete: false`, no asserted
authority timeline, and warnings identifying the failure. The ordinary
`torc verify` command remains the detailed integrity diagnostic.

Pending and rejected handoffs are visible but never represented as authority
changes. Rollback is shown as an append-only canonical-state restoration with
the same bearer. A branch is shown as a new lineage rooted in a pinned source
revision; it does not suspend or transfer the source lineage's authority.
Failure recovery is labeled from the immutable handoff recovery context rather
than inferred only from mutable activation state.

## Boundaries

This slice is a local Python and SQLite query plus CLI presentation. It adds no
database migration, daemon, watcher, network dependency, provider call, live
model integration, HUD, MCP server, or parent-repository change.

A future `lugos-mcp` adapter may expose the same public read contract, and a HUD
may render it. Those consumers must not duplicate TORC's provenance logic,
open the SQLite database as an independent authority surface, or add mutation
controls to the read view. Autowork, Sulis, Bran, and other Lugos identifiers
remain opaque references owned by their respective systems.
