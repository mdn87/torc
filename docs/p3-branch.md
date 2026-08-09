# P3 Lineage Branch Creation

Status: implemented bounded slice.

## Meaning

A TORC branch is a genuinely new lineage identity, not two activations claiming
the same lineage. Its first `branch_created` revision starts a new local hash
chain with no parent and exactly copies the frozen source head's canonical state.
Immutable `branch_origin` provenance pins the source lineage, revision and hash,
source activation and lease, operator decision, external assignment reference,
and initial child authority.

Branch creation does not transfer or suspend source authority. The source keeps
its head, activation, and lease; the child receives its own activation and lease
in one atomic transaction. Each lineage can then checkpoint, hand off, recover,
or roll back independently.

The external assignment reference is required because TORC authority does not
grant filesystem, harness, model, provider, workflow, or tool permissions. It
records the independently authorized assignment but does not validate it.

## Operator flow

Inspect and freeze the exact source head, then create the child:

```powershell
python -m torc lineage status `
  --state-dir .torc/pilot `
  --lineage torc-dev `
  --json

python -m torc lineage branch `
  --state-dir .torc/pilot `
  --source-lineage torc-dev `
  --source-activation activation-current `
  --expected-head revision-current `
  --child-lineage torc-dev-experimental `
  --child-activation activation-branch `
  --substrate-file examples/p3-branch-child-substrate.json `
  --operator-ref operator-branch-decision `
  --target-assignment-ref assignment-branch-work `
  --rationale "Explore an independent implementation direction." `
  --evidence-ref design-finding-branch `
  --json
```

Verify both independent chains:

```powershell
python -m torc verify --state-dir .torc/pilot --lineage torc-dev --json
python -m torc verify --state-dir .torc/pilot --lineage torc-dev-experimental --json
```

## Boundaries

The child always begins as an exact canonical copy. Custom initial state should
be an explicit later checkpoint. This slice adds no merge, reconciliation,
conflict resolution, automatic branch policy, branch retirement, database
migration, service, provider call, or parent-repository integration.
