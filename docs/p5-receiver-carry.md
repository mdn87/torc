# P5 Receiver-Fitted Carry

Status: bounded local slice implemented.

## Purpose

ADR 0004 rules that TORC owns what a lineage carries to its next bearer. The P0
compiler does not do that job. It copies fixed sections of the head
revision, ignores the receiving substrate's descriptor, and never consults
history, so whatever the last bearer left out of its summary is gone for good.

P5 builds the center described in `docs/concepts/0001-torc-original-concept.md`
as four bounded parts:

1. a compiler that uses the receiver's descriptor and reads the lineage history;
2. a boundary step that asks the bearer to account for what it dropped and to
   restate the self-model when the bearer has changed;
3. a carry call at session start as well as at handoff;
4. a fixture where the last summary dropped something the history kept.

TORC still performs no inference. Every rule below is deterministic. The
bearing agent does the thinking; TORC notices, asks, shapes, and records.

## What a carry is

A carry is an execution projection compiled by compiler `p5-1` for one
receiving substrate. It uses the existing projection record shape
(`schemas/execution-projection.schema.json`), is stored as an immutable
projection, and stays a derived, non-canonical artifact. Receiving a carry
grants no authority.

The P0 compiler (`p0-1`) is unchanged. The demo and the frozen P1 experiment
lanes keep using it so their recorded evidence stays replayable.

## Sizing

The budget comes from the receiver, not from the operator's plan.

- The unit is the descriptor's `context_budget.unit` (`words` or `characters`).
- The budget is `context_budget.carry_limit` when the descriptor declares one.
  Otherwise it is 5 percent of `context_budget.limit`, with a floor of 200 words
  or 1,200 characters and never more than the limit itself.
- An operator cap (`budget_limit` in a handoff plan, `--budget-cap` on the
  carry command) can only lower the budget.
- Required sections must fit. If they cannot, compilation fails with
  `ProjectionBudgetError` and nothing is stored.

## Shaping

Sections are considered in this order.

| Tier | Sections |
|---|---|
| Required | `identity-role`, `constraints`, `commitments`, `open-work`, the purpose section, `receiver-fit`, `self-model-provenance` |
| History | one `unaccounted-*` section per unaccounted drop (priority 90), then `changes-since-receiver` (priority 85) |
| Optional head state | `goals` 80, `settled-decisions` 70, `uncertainties` 60, `methods` 50, `artifact-refs` 40, `memory-refs` 30 |

- The purpose section is `handoff-purpose` for a handoff and `session-purpose`
  for a session start. `session-purpose` states who holds authority and whether
  the receiver is that bearer's substrate.
- `receiver-fit` records how the budget was derived and how many revisions were
  read.
- Optional list sections are fitted item by item. When only part of a section
  fits, the included items are kept and `<section>.remainder` is recorded as
  omitted for `budget`.
- `artifact-refs` is omitted with reason `capability_irrelevant` when the
  receiver lacks `repository_read`. It cannot open what the refs point to.
- `changes-since-receiver` reports what changed since the receiving substrate
  last authored a revision. Authored revisions define that baseline: revisions
  TORC writes on the substrate's behalf, such as the `handoff_accepted` revision
  of a hand-back, do not count, and neither does an interval during which the
  substrate held the lease without checkpointing. `added` is the net addition
  between the baseline and the head. `removed` lists every tracked item that is
  absent from the head and whose latest removal happened, or was accounted for,
  after the baseline, with that removal's disposition (`completed`,
  `superseded`, `withdrawn`, `rolled_back`, or `unaccounted`). An item added
  and resolved while the receiver was away is therefore reported, and a
  disposition recorded for an earlier removal never describes a later one. The
  section is absent when the receiver has never authored a revision or nothing
  has changed since its baseline.

## Reading history

The history is the source revision and its ancestors inside the lineage,
followed through parent links. Three sections are tracked: `constraints`,
`commitments`, and `open_work`. Items are compared as exact strings.

A removal is accounted for when:

- the removing revision, or any later one, carries a resolution for the item;
- the removing revision is a `rollback_applied` event; or
- the item is present in the head again.

Every other removal is an **unaccounted drop**. It is reported with the
revision that last held it, the revision that dropped it, and the substrate
that dropped it. A reworded item appears as one drop and one addition. TORC
does not guess that two strings mean the same thing; a `superseded` resolution
is how a bearer says so.

History before a branch point is not read. A branch's first revision holds the
full state at branch time.

## Resolutions

A revision may carry an optional `resolutions` list:

```json
{"section": "open_work", "item": "Write the rollback test", "disposition": "completed", "note": "merged"}
```

`disposition` is `completed`, `superseded`, or `withdrawn`. Each resolution
must name an item that this revision removes or that is currently an
unaccounted drop. Anything else is rejected before any write. That check runs
inside the store's append transaction, so it holds for every caller, not only
the operator command. A resolution accounts for the latest open removal of its
item: if the item is restored and dropped again, the new drop is unaccounted
until it is resolved in turn. The field is absent when empty, so existing
records and their hashes are unchanged.

The store accepts only `checkpoint` and `self_model_revised` through the
ordinary append path. Rollback, branch, and handoff revisions are written by
their own workflows, which supply the context the verifier checks; a reserved
event type is refused before any write.

## Boundary asks

Every checkpoint response and `lineage status` include a `boundary` block:

- `unaccounted`: the open unaccounted drops, including any this checkpoint just
  created;
- `self_model`: the revision, activation, and substrate that last authored the
  self-model (`authored_*`, keyed on a change to its content), the revision,
  activation, and substrate that last restated it (`restated_*`), and
  `restatement_due`, which is true when the last restating substrate differs
  from the current bearer's. A `self_model_revised` checkpoint restates the
  self-model even when its text is confirmed verbatim, so a confirmation is
  visible as a confirmation rather than as a change. A plain checkpoint of
  unchanged text restates nothing. An accepted handoff copies the recipient's
  responsibility into the role; that is TORC's bookkeeping and changes neither
  authorship nor restatement. The carry's `self-model-provenance` section
  includes the `restated_*` fields only when they differ from `authored_*`.

The asks do not block. TORC accepts the checkpoint, records it, and repeats the
ask in every carry until the bearer restores the item, resolves it, or restates
the self-model through a `self_model_revised` checkpoint. Blocking enforcement
waits for evidence from use. The asks persist in every carry that has budget
for them; the history tier is fitted after the required tier, so a very small
receiver may receive the asks only through the checkpoint response and
`lineage status`.

A `handoff prepare` runs in one immediate transaction. Its two exported
artifacts are created last, with exclusive create, and removed again if
anything fails, so a preparation that cannot fit the receiver stores neither
the target descriptor nor the fit decision and a retry does not trip over a
half-finished export.

## Commands

Session start, for any registered or supplied receiver:

```text
python -m torc lineage carry --state-dir <dir> --lineage <id> --substrate-file <descriptor.json> [--budget-cap <n>] [--json]
```

Checkpoint with resolutions:

```text
python -m torc lineage checkpoint --state-dir <dir> --lineage <id> --activation <id> --state-file <state.json> [--resolutions-file <resolutions.json>] [--json]
```

`handoff prepare` and `recovery prepare` compile their projection with `p5-1`.
`budget_limit` in a plan becomes an optional cap.

The carry command registers the receiver's descriptor, because a stored
projection must reference a registered substrate. The operator handoff
therefore evaluates fit for the source and the operator-named target only.
Before this change fit scored every registered descriptor, so an observer that
had only asked for a carry could out-rank the named target and block the
handoff. Fit scoring itself is unchanged, and the demo and experiment lanes
still evaluate every registered substrate.

## Verification

`torc verify` accepts a `p5-1` section whose source reference points at the
source revision or one of its ancestors in the same lineage. `p0-1` projections
keep the stricter rule that every reference points at the source revision.

The verifier also replays each revision's `resolutions` against the history
before it and reports `resolution_invalid` for one that is malformed or names
an item that was never dropped; a malformed entry stops the replay rather than
crashing a later carry. It reports `event_type_unknown` for a revision whose
event type is outside the revision schema's vocabulary. Because checkpoint and
carry verify the lineage first, a record stored around the append rules is
refused as an integrity failure instead of silencing a real drop.

## Fixture

`examples/p5-dropped-work/` holds a four-revision lineage in which the last
bearer completed one item with a resolution and silently dropped an open work
item and a hard constraint, plus a small and a large receiver. The P0 compiler
loses both dropped items. The P5 compiler carries them to both receivers from
unchanged canonical history.

To replay it, run `lineage create` with `state-1-created.json` and
`source-substrate.json`, then `lineage checkpoint` with states 2, 3 (adding
`--resolutions-file resolutions-3.json`), and 4. The last checkpoint is accepted
and its response asks about both drops. `lineage carry` with
`receiver-small.json` then uses 99 of its 100 declared words: both drops are
carried ahead of any optional state, one settled decision fits and the rest is
recorded as `settled-decisions.remainder`, `uncertainties` and `methods` are
omitted for budget, and `artifact-refs` is omitted as `capability_irrelevant`.
`receiver-large.json` derives a 10,000-word budget from its descriptor and
omits nothing. `tests/test_carry.py` covers the same sequence.

## Boundaries

This slice is local Python and SQLite. It adds no database migration, daemon,
watcher, network dependency, provider call, or parent-repository change. It
does not change who selects the next agent or how fit is scored, does not match
reworded items, and does not alter LIR, lugos-mcp, or any other consumer.

## What this does not prove

P5 proves a mechanism: an omission by one bearer no longer becomes permanent,
and the carry differs by receiver while canonical history stays byte-identical.
It does not show that a receiving agent performs better. The hypothesis and
kill criteria in `docs/project-brief.md` still apply. The next evidence step is
a live comparison on a task with a real omission, which needs its own approval.
