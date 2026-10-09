<!-- LUGOS-ROUNDTABLE v1 -->
## CONTROL
technique: adversarial-refine
seq: 7
round: 4
turn: claude
phase: converge
status: halted
max_seq: 6
max_rounds: 12
clean_attacks: 1
converge_k: 1
lease_until: 
participants: codex:attacker:<<codex/>>, claude:defender:<<claude/>>
submitted_round: 
topic: Refine version 2 of torc/docs/pr-25-receiver-fitted-carry-assessment.md: Codex attacks the weakest remaining claims, Claude defends and revises
updated: 

## ARTIFACT
<!-- LUGOS-SECTION:BEGIN -->
# PR #25 assessment: receiver-fitted carry

Version 2, 2026-10-08. Local architectural, code, and measured assessment,
revised after a Codex-and-Claude cross-review campaign (see "Review
provenance" at the end). This is a review record, not an acceptance decision
or a change to TORC runtime policy. Version 1 is preserved at
[evidence/pr-25-assessment/v1-assessment.md](evidence/pr-25-assessment/v1-assessment.md);
every measurement below can be rerun from the scripts in that directory.

Reviewed [PR #25](https://github.com/mdn87/torc/pull/25) at commit
a056c61be4dddce8a71fd9cb31f585b70a3b510d, based on
bad615ca6303e88edae2e483b74d544657b8cb9e, which is still the head of master.
The PR is the local checkout, branch agent/p5-receiver-shaped-carry. It
contains two commits and changes 26 files (+1,953 / -60). The first commit
adds the concept record and ADR 0004; the second adds the P5 specification,
one new module, 734 production lines by its scope envelope, 615 test lines,
and a four-revision fixture. GitHub CI passed on all six OS and Python
combinations plus the host-identifier scan. The Codex reviewer on GitHub left
three P2 comments on the history module; all three reproduce here. The
companion [PR #26 assessment](pr-26-continuity-and-batching-assessment.md)
covers the other open branch.

## What changed in this version

Two Codex reviewers (gpt-5.6-sol on claims versus code, gpt-6-astra on
measurement and argument), one Claude reviewer (opus on concept fit, rollout,
and reasoning), and a three-model panel judged by a fourth model reviewed
version 1 against the PR sources and the project documents. Their accepted
findings changed the document as follows:

- The verdict now names the history reader as the demonstrated contribution
  and the receiver-fitted sizing and shaping as unvalidated and as where the
  cost sits. The compiled-prompt comparison favors P5 by construction,
  because that prompt was never given the history P5 reads; the kill
  criterion names exactly a compiled prompt plus existing records, so that
  baseline is still unrun. "More correct" is conditioned on the before-merge
  fixes: as submitted, the carry is more explicit about omissions but
  contradictory about their dispositions.
- Size ratios are reported one unit at a time on both sides. Version 1's
  "about three times" divided rendered words by an estimate; the like-for-
  like figures are 2.9 to 3.1 times in delivered words, 4.2 to 4.3 times in
  delivered bytes, and 1.5 to 1.7 times in the compiler's own estimate
  against P0. The P1b resemblance is labeled a different fixture and unit.
- Composition is measured on the rendered carry, not the stored record:
  TORC's three bookkeeping sections are 27 to 28 percent of delivered bytes
  and identifiers 13 percent. The stored-record figure (69 percent metadata)
  is kept only as a storage observation.
- The concept-fit section separates conformance against documents the PR
  does not author from an assessment of the rulings the PR itself introduces
  (the concept record and ADR 0004), and walks all five kill criteria. One
  of them, fit scoring against explicit routing, has been narrowed by the PR
  from a selector to a gate on the named target, and the gate's value is
  untested.
- Seven findings are now before-merge: the three provenance defects, the
  net-delta change summary, resolution validation at the store and verifier,
  the non-atomic handoff preparation whose correction must cover the
  filesystem, and the unrestricted event type on the Python checkpoint API,
  which can append an invalid canonical revision that poisons every later
  integrity-gated operation.
- New findings: the handoff template delivers optional head state in full
  and acceptance demands it, whatever the carry omitted; the sizing floor can
  hand a small receiver its whole
  context as carry budget; the verifier picks its strictness from a field
  inside the record it verifies; the P5 optional tier is ordered by list
  position rather than by the published priorities; artifact hashing in the
  verifier is unscoped by lineage; status returns the boundary block without
  any integrity check; the descriptor conflict surfaces as a bare
  `ValueError`.
- Corrections to version 1: the branch-root bullet had the wrong cause; the
  history tier degrades drop by drop rather than whole; the spec is
  internally inconsistent about the change-summary baseline rather than
  misquoted by the code; "count rendered units" is a design change, not a
  smallest correction; the "every call verifies" statement was wrong for
  status.
- The rollout adds an LIR boundary reconciliation step that ADR 0004 itself
  calls for, makes descriptor-by-id a precondition of exposing the carry,
  names operator approval as the entry condition of the live comparison,
  replaces "promote history to required" with a bounded preservation policy,
  and applies every evaluation-plan gate rather than retention alone.
- An adversarial-refine session followed the synthesis: Codex gpt-6-astra
  attacked this version in rounds, Claude defended and revised. Round one
  corrected six points (the unbounded rendered omission ledger, descriptor
  admission by ownership rather than id reuse, resolution eligibility inside
  the store transaction, the withdrawn unaccounted-override shortcut, the
  fit criterion as narrowed rather than met, and the floor wording). Round
  two added the lineage poisoning and the handoff-template bypass above.
- The replay, sweep, mutation, scaling, and reproduction scripts, their raw
  outputs, the reviewers' finding ledgers, the attack rounds, and the
  panel's judged analysis are committed under
  `docs/evidence/pr-25-assessment/`.

## Assessment in brief

The PR builds the part of TORC that every phase after P0 skipped: the carry
itself. Compiler `p5-1` derives the budget from the receiving substrate's
descriptor, fits optional state item by item, applies one capability rule,
and reads the lineage history behind the head, so work that a bearer dropped
from its summary still reaches the next bearer together with the revision
that last held it and the revision that dropped it. Revisions gain an
optional, hash-stable `resolutions` list. Checkpoint and status responses
gain a non-blocking `boundary` block that asks about unaccounted drops and
about restating a self-model that another substrate wrote. `torc lineage
carry` compiles the carry at session start; it creates no activation and
touches no lease, and it does register the receiver's descriptor and store
one projection.

Replayed here, the mechanism does what the PR says. From one head revision
the P5 carry delivers the two items the last bearer silently dropped; the
P0 projection and a compiled-prompt shape built from the same head deliver
neither, and canonical history stays byte-identical. Two qualifications
follow from the review. First, that is a property of the artifact, not of a
receiver's behavior, which the PR itself states. Second, it holds by
construction: both baselines read only the head, so the replay demonstrates
the history reader (`revision_chain` and `unaccounted_drops`), which is the
cheap and separable half of P5. Receiver-derived sizing and item-level
shaping are the half that carries the cost, and nothing here validates
them. The decision-relevant baseline, a compiled prompt given the same
history, has not been run.

The carry costs more to read than either baseline. Delivered to the large
receiver it is 3.1 times the compiled-prompt shape in words and 4.3 times in
bytes; the compiler's own estimate is 1.7 times the P0 projection. P1b
recorded 3.26 in words and 4.31 in bytes on a different, ceiling-saturated
fixture, so the resemblance is descriptive only. The kill criterion on
overhead against measured benefit stays open, and the PR makes it testable
on a fixture that finally contains a real omission. A second kill criterion,
that fit scoring cannot outperform explicit routing, has been narrowed by
this PR rather than decided: in the only non-synthetic path, fit no longer
selects among candidates and only gates the operator's named target, and
whether that gate beats plain requirement validation is untested.

As submitted, the carry is more explicit than a plain summary about what it
omits and why, and it is contradictory about dispositions under specific
succession patterns. After the before-merge fixes it would also be more
correct. Seven findings are before merge; they are local and have
reproduction scripts. None touches leases or authority; three can leave
durable state behind through supported paths: a fabricated or malformed
resolution appended through the store, a partially prepared handoff, and a
reserved-event revision that the verifier then rejects for the life of the
lineage. The last two are reachable from operator workflows, the first from
the store API. The
review campaign also showed that the measurements most likely to decide the
overhead criterion are contested: the P1b tie, the small receiver's budget
row, and the unbounded growth terms on long lineages each had a panelist's
vote. This version leads with the facts that threaten the hypothesis rather
than with the fixture table.

## Significant improvements

| Area | What changed | Why it matters |
|---|---|---|
| Receiver-derived sizing | [receiver_budget](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/projections.py#L48-L73) uses the descriptor's `carry_limit`, otherwise 5 percent of the context limit with a floor; an operator cap can only lower it. | The receiver, not the operator's plan, decides how much it can take, and the derivation is recorded in the carry's `receiver-fit` section. The descriptor is self-reported and unverified, and the floor is capped only by the whole context limit, with no fractional cap (finding below). |
| Shaping by item and capability | [compile_receiver_projection](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/projections.py#L226-L396) fits optional lists item by item, records a `.remainder` omission, and omits `artifact-refs` for a receiver without `repository_read`. | Partial sections survive instead of disappearing whole. Every omission has a reason the operator can read. The optional tier is ordered by list position; the recorded `priority` is descriptive. |
| History reading | [history.py](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py) follows parent links to the lineage root and reports tracked items removed without a resolution, a rollback, or a later restoration. | A head revision is one bearer's summary. Reading the chain is what makes "an omission is not permanent" true, and it is the whole of the content advantage measured here. |
| Resolutions | The revision schema adds an optional `resolutions` list; [append_revision](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/store.py#L466) writes it only when non-empty (the shape test `test_revision_without_resolutions_keeps_its_recorded_shape` backs this); [validate_resolutions](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L179-L199) rejects a name that is not a real removal before any write on the operator path. | Existing records keep their hashes. A bearer has a recorded way to say completed, superseded, or withdrawn. Validation is not yet enforced at the store or by the verifier (finding below). |
| Boundary asks | Checkpoint and status responses add a [boundary](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L755-L758) block. The asks never block. | The protocol now asks for the self-model revision that ADR 0004 describes and keeps asking, without turning TORC into an enforcement gate before use provides evidence. |
| Session-start carry | [carry_operator_lineage](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L257-L292) registers the receiver's descriptor and stores one projection in a single immediate transaction; a carry that cannot fit stores nothing. | Observers and returning bearers can be shaped for without a handoff. Verified here: the revision, lineage, activation, lease, and authority-transition tables are identical before and after a carry; the projection and substrate tables are not. |
| Handoff fit scope | [prepare_operator_handoff](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L336-L341) evaluates fit for the source and the operator-named target only. | An observer that only asked for a carry can no longer out-rank the named target and block a handoff. The PR reproduced that failure before fixing it. The same change turns fit into a confirmation of the operator's choice (see the kill-criteria walk). |
| Verification | [verify](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/verify.py#L471-L481) accepts a source reference to an ancestor of the source revision for any compiler version beginning `p5-`; `p0-1` keeps the strict rule. Tamper and misattribution tests pass. | History sections can cite the revision that held an item while the hash chain still checks them. The allowance is keyed on a field inside the record being verified (finding below). |

## What the replay measures

The fixture in `examples/p5-dropped-work` was replayed on macOS with Python
3.14 through the operator API
([replay.py](evidence/pr-25-assessment/scripts/replay.py)). From the same
head revision, the P0 compiler was run at the same budgets, and the P1
compiled-prompt shape (`experiment_lanes.materialize_compiled_prompt`) was
built the way the P1 source capture builds it. Word counts use the
compiler's regex on whatever text is delivered, so the two delivered columns
compare like with like; the P0 row is a compiler estimate because P0 is not
rendered on its own.

| Transport from the same head | Compiler estimate | Delivered words | Delivered bytes | Dropped work item | Dropped constraint |
|---|---:|---:|---:|---|---|
| P0 projection, budget 100 or 10,000 | 67 | not rendered | not rendered | lost | lost |
| P1 compiled-prompt shape | n/a | 60 | 580 | lost | lost |
| P5 carry, small receiver (`carry_limit` 100) | 99 of 100 | 174 | 2,435 | carried | carried |
| P5 carry, large receiver (5 percent of 200,000) | 116 of 10,000 | 184 | 2,519 | carried | carried |

Ratios, one unit at a time: against the compiled-prompt shape the carries
are 2.9 and 3.1 times in delivered words and 4.2 and 4.3 times in delivered
bytes; against the P0 projection, in the compiler's own estimate, 1.5 and
1.7 times. The small receiver's carry matches the PR text: both drops ahead
of optional state, one settled decision kept with the remainder recorded,
uncertainties and methods omitted for budget, artifact-refs omitted as
capability-irrelevant. The last checkpoint was accepted and asked about both
drops; status repeats the ask; a later checkpoint that restores the
constraint and withdraws the work item clears it.

What the table shows and what it does not. The compiler reads the chain
instead of the head, and the head is whatever the last bearer chose to keep;
reading history is the whole of the content advantage. The two baselines
were built from the head only, which is how P0 and the P1 lane work, but it
means the comparison cannot distinguish TORC's receiver-fitted carry from
any transport that is given the history. Claude opus on the panel, the
gpt-6-astra reviewer, and the Claude opus reviewer made the same point
independently. Until a compiled prompt with equivalent history access is
run, the table is a mechanism demonstration, not evidence against the kill
criterion that names exactly that baseline.

Composition of what the receiver reads, measured on the rendered carry
rather than the stored record: TORC's three bookkeeping sections
(`session-purpose`, `receiver-fit`, `self-model-provenance`) are 693 to 697
bytes and 33 words, 27 to 28 percent of delivered bytes; the history sections
are 630 bytes, 25 percent; nine revision and activation identifiers are 333
bytes, 13 percent; the fixed preamble is about 15 percent. The stored record
is 4.3 KB with 1.3 KB of section content, but the renderer emits only section
ids and content, so that 69 percent is a storage observation and does not
bound what a different presentation could save from the model-visible text.

Three further measurements qualify the sizing claim
([rank_sweep.py](evidence/pr-25-assessment/scripts/rank_sweep.py)):

- **Required floor.** The smallest `carry_limit` that compiles is 55 words,
  and 27 of those are TORC's own sections, so about half of the minimum
  viable budget is self-description. Each `unaccounted-*` section and
  `changes-since-receiver` is fitted whole or omitted, and the tier degrades
  drop by drop, newest first; the optional list sections below it keep a
  `.remainder` record, while `changes-since-receiver` disappears whole
  without one. Swept from 55 to 100 words: budgets of 55 to 68 carry TORC's
  bookkeeping plus `goals` and `uncertainties` and omit both drops with
  reason `budget`; 69 to 83 carry one drop; 84 is the first budget that
  carries both. The spec's packing order permits this, so the gap is in the
  choice of required tier, not in the fitting loop.
- **Floor against context.** The 200-word floor is capped only by the whole
  context limit, never by a fraction of it: a receiver declaring a 300-word
  context gets a 200-word carry budget (67 percent of its context) and one
  declaring 120 words gets all 120, and the suite asserts both as correct.
  The budget never exceeds the declared context; for the smallest receivers
  it consumes all of it, which is the opposite of fitted.
- **Unit fidelity.** The budget counts regex words over the canonical JSON of
  each section's content; the receiver reads rendered Markdown with headers
  and pretty-printed JSON, 174 words for a 100-word budget. Identifiers count
  as one word each because the regex admits hyphens, and each unaccounted
  section carries two of them. Provider tokens are not measured; the common
  estimate of roughly 20 tokens per 32-hex identifier is unverified, which is
  one reason a live run must retain provider usage. The brief accepts a
  deterministic approximation. Making the budget count rendered units is not
  a small correction: the renderer lives in the operator module that imports
  the compiler, sizing runs inside the per-item fitting loop, and the word
  estimator is shared with the frozen P0 compiler. The smallest honest change
  is to record the rendered size in `receiver-fit` as evidence and name the
  budget for what it counts.

## Fit with the project's commitments

Two of the documents version 1 scored the PR against, the
[concept record](concepts/0001-torc-original-concept.md) and
[ADR 0004](decisions/0004-torc-is-always-in-charge.md), land with this PR.
They are assessed below as proposals. Conformance is scored only against
documents the PR does not author: the [project brief](project-brief.md), the
[evaluation plan](evaluation-plan.md), the
[integration boundaries](integration-boundaries.md), ADR 0001 to 0003, and
the [P1b results](p1b-results.md).

| Existing commitment | PR contribution | Remaining work |
|---|---|---|
| Hypothesis: a target-fit projection backed by canonical lineage beats a free-form summary (brief) | The projection is now derived from the target descriptor and from history, so the hypothesis finally has a subject to test. | The live comparison the brief and evaluation plan describe, with the history-informed compiled prompt as a baseline. |
| Compile a projection within a target budget; context sizing is a deterministic approximation (brief) | Budget from the descriptor, item-level fitting, one capability rule, omissions with reasons. | The unit counts content rather than delivery; the 5 percent share and the floors are unmeasured constants; the floor can consume the whole context of a small receiver; the required tier is TORC's metadata while the history tier is optional; the descriptor is self-reported. |
| Fit scoring must outperform explicit routing or be narrowed (brief, kill criterion) | The operator handoff now scores only the source and the operator-named target, and rejects preparation when the target does not win; selection among candidates survives only in the demo and experiment lanes. | Narrowed from a selector to a gate on the named choice. Whether that gate adds anything over plain requirement validation (it can refuse an unsuitable choice, or wrongly refuse a suitable one) is untested, so the criterion is narrowed, not decided. Narrow fit to the requirements-expression surface that the integration boundaries already describe ("Routing and fit are different"), and let Autowork and Orca route. |
| Validate target reconstruction before authority transfer (brief, ADR 0003) | Handoff and recovery preparation compile with `p5-1`; the brief carries the drops; the verifier checks ancestor references. | [Acceptance](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/handoffs.py#L119-L141) compares head-state fields only, so a successor is accepted without acknowledging the unaccounted drops. Consistent with "asks never block"; the spec should say so, or add an optional continuity requirement. At the same time acceptance demands optional head state in full and the template delivers it in full, so the bundle a successor receives is not bounded by the carry (finding below). The verifier's ancestor check is about hash-chain validity, not disposition correctness. |
| TORC proposes substrate requirements; Autowork and Omniroute authorize routes; harness adapters load projections (integration boundaries) | A session-start carry a harness adapter can load; the P0 compiler, demo, and frozen experiment lanes are untouched. | The lugos-mcp TORC adapter only exposes `lineage explain`, so no consumer parses the new `boundary` block (nothing breaks) and nothing consumes the carry yet. |
| P1b outcome: a fixed packet tied a compiled prompt at three times the size (P1b results, ADR 0004 consequence) | The carry is no longer a fixed packet, so P1b counts neither for nor against it. | The overhead has not changed in kind; it has moved into provenance identifiers and bookkeeping sections. |

**The PR's own rulings.** The concept record quotes the operator's original
phrases and maps them to the seed design; it is a reference, not a
conformance target. ADR 0004 rules that TORC owns what a lineage carries to
its next bearer and that other components consume what TORC produces. Both
are reasonable readings of the brief, and the PR follows its own ruling.
Two things follow for the parent repository. The LIR boundary document still
describes the older split in which LIR renders the agent-facing resumption
view, and ADR 0004 itself says those documents must be brought into line once
the receiver-facing interface is defined; this PR defines it, so that follow-
up is now due and version 1 gave it no owner. And ADR 0004 assigns TORC the
duty to ask for, attribute, and record the self-model revision; the
attribution mechanism this PR implements is keyed on content, and the
correction proposed below would key it on a self-declared event, which is
weaker unless the event type is validated and the two facts are recorded
separately.

**Kill criteria walk.** The brief lists five kill-or-narrow criteria.
(1) A compiled prompt plus existing records preserves the same continuity
with less burden: open; the baseline it names has not been run. (2) An
existing runtime supplies the same semantics with an acceptable adapter:
not evaluated here; P1b preregistered native persistence as unavailable for
its pair. (3) Fit scoring cannot outperform explicit routing: narrowed, not
decided; after this PR fit gates the named target instead of selecting one,
and the gate's value over requirement validation is untested, as above.
(4) Projection and handoff overhead
exceed their measured benefit: open, and the measurements most likely to
decide it are contested. (5) The only remaining value is renaming facilities
that exist elsewhere: not evaluated here; the history reader has no
counterpart in Sulis, Autowork, or agent-continuity that the reviewers could
name, which is the strongest argument that something in P5 is new.

## Findings and disposition

Findings from version 1 are kept; those the review campaign added are marked
with the reviewer that found them. Three Codex findings were reproduced with
[adjudicate_codex_findings.py](evidence/pr-25-assessment/scripts/adjudicate_codex_findings.py).

| Priority | Finding and evidence | Smallest correction |
|---|---|---|
| **Before merge** | [changes_since_substrate](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L125-L146) collects every resolution since the receiver's base revision and reuses it for a later removal of the same item. Reproduced: an item completed, restored, then dropped again without a resolution appears in the carry as `completed` in `changes-since-receiver` and as `unaccounted-open_work-3` at the same time. | Scope each disposition to the removal it accounts for by tracking the latest removal of each item. Letting the current unaccounted state override a stale disposition is not enough on its own: after resolve, restore, and a genuine rollback that removes the item again, the rollback removal is exempt, so there is no unaccounted entry to override and the stale `completed` would still win. Add resolve-restore-drop and resolve-restore-rollback sequences to `tests/test_carry.py` (asserting `unaccounted` and `rolled_back` respectively), plus a plain unresolved removal asserted as `unaccounted`, since the fix edits exactly the expression those labels come from. |
| **Before merge** | [changes_since_substrate](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L114-L121) treats the `handoff_accepted` revision as work authored by the returning substrate. Reproduced: a successor completes an item with a resolution, hands the lineage back, and the returning bearer's carry has no `changes-since-receiver` section, although the same carry taken one step earlier reported two revisions of change. | Skip `handoff_accepted` revisions when finding the receiver's last authored revision, as `self_model_provenance` already does, and resolve the baseline contract (below) in the same change. |
| **Before merge** | [self_model_provenance](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L86-L90) assigns authorship by content change only. Reproduced: a successor that confirms the inherited self-model verbatim with a `self_model_revised` checkpoint stays at `restatement_due: true`; only a textual change clears it. | Treat a `self_model_revised` event as a restatement, keeping the `handoff_accepted` exclusion. This trades a content-derived signal for a self-declared label, so pair it with event-type validation and record `authored_by` (from content) and `last_restated_by` (from the event) separately, so a verbatim confirmation is visible as a confirmation. |
| **Before merge** (Codex gpt-5.6-sol) | The spec says `changes-since-receiver` "lists what was added, removed, and resolved" since the receiver last authored a revision. [The implementation](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L131-L148) is a net set difference between that base and the head. Reproduced: an item the successor added and then completed with a resolution before the original bearer returned is absent from `added`, `removed`, and the dispositions; the section reports only `self_model_changed`. | Either fold the revisions after the base and report additions, removal epochs, and resolutions as events, or redefine the section as a net delta in the spec and stop claiming it reports everything resolved. Add add-then-resolve and already-absent-then-resolve tests. |
| **Before merge** (Codex gpt-5.6-sol) | Resolution legality is enforced only on the operator checkpoint path. [append_revision](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/store.py#L466) stores any `resolutions` list, and `verify_store` never checks resolution shape or eligibility. Reproduced: a correctly sealed revision appended through the store with a fabricated `completed` resolution passes verification and silences the real drop; a malformed entry is stored and makes every later history read raise `KeyError`. | Validate both shape and eligibility inside the store's append transaction, before the revision, head, lease, and activation advance, so the spec's "rejected before any write" promise holds for every caller; keep eligibility replay in the verifier as an independent check, where a malformed record must be a verification error rather than a crash in the carry. Add direct-store tests for a nonexistent item, a wrong section, and a malformed entry, each asserting that nothing advanced. |
| **Before merge** (independent review; Codex gpt-5.6-sol and Claude opus on the filesystem) | The spec says a carry that cannot fit stores nothing, and the carry honors that in one transaction. [prepare_operator_handoff](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L330-L358) does not: when the receiver-derived budget cannot hold the required tier, the registered target descriptor and the fit decision remain stored. The two handoff artifacts are written with exclusive-create before their metadata rows, so a database transaction alone cannot make preparation atomic, a retry fails on the existing file, and `artifact_metadata`'s own `with store.connection:` would commit an enclosing transaction early. With the resolution and reserved-event poisonings above, this is one of three defects that leave durable state behind on a reachable path, and one of the two reachable from an operator workflow, which is why it moved up from version 1. | Render first, write both artifacts to temporary paths, do the database work in one immediate transaction with `prepare_handoff` and `artifact_metadata` joining it, finalize the files at the commit boundary, and clean up on every failure. Add an injected second-export failure test. |
| **Before merge** (Codex gpt-5.6-sol; Claude opus; Codex gpt-6-astra on the consequence) | The CLI restricts `--event-type` to `checkpoint` and `self_model_revised`, but [checkpoint_operator_lineage](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L84-L121) accepts any string, and `unaccounted_drops` exempts every removal made by a revision labeled `rollback_applied`. Reproduced: a plain checkpoint with that label removed an item without an ask and was persisted as the new head; verification then reports `rollback_context_invalid` for that revision, and because every later checkpoint and carry runs the integrity check first, both are refused with `IntegrityError` from then on. History is append-only, so the lineage stays poisoned. This is durable-state damage reachable from a supported Python path, comparable to the resolution poisoning above. | Enforce the ordinary checkpoint vocabulary (`checkpoint`, `self_model_revised`) in `Store.append_revision` itself, not only in the operator API, so that every caller is covered the way the resolution correction above demands; keep rollback, branch, and handoff events on their dedicated workflows, which supply the context the verifier checks. Add a direct-store regression that a reserved event type changes no records or heads, that verification stays valid, and that a subsequent ordinary checkpoint succeeds. |
| **Before small receivers are real** | The required tier is TORC's metadata; the history tier is optional and ranks below it in code order. Measured: budgets of 55 to 68 words carry bookkeeping plus goals and uncertainties and omit both drops; 84 is the first budget that carries both. The spec's packing order permits this, so the gap is in the choice of required tier, not in the fitting loop. | Decide a bounded preservation policy rather than promoting the history tier to required outright, because the required tier is all-or-nothing and the scaling probe already has 1,597 drops against a 903-drop budget: which drops are mandatory, what happens on overflow, and the minimum supported budget, tested on a lineage whose history exceeds the receiver budget. |
| **Before small receivers are real** (Claude opus) | [receiver_budget](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/projections.py#L48-L73) takes the larger of the 5 percent share and the floor, capped only by the context limit itself, and the suite asserts a 300-word context gets 200 and a 120-word context gets 120. | Cap the floor as a fraction of the context limit, or require small descriptors to declare `carry_limit`. Record the rendered size in `receiver-fit` as evidence; treat a rendered-unit budget as its own design slice. |
| **Before small receivers are real** (Codex gpt-6-astra) | The handoff bundle bypasses the sizing. Acceptance requires `settled_decisions` and `uncertainties` in full by default ([CONTINUITY_FIELDS](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/handoffs.py#L15-L25)), [expected_reconstruction](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/handoffs.py#L119-L141) copies the complete head lists into the reconstruction template, the brief tells the recipient to copy that template, and `p5-1` fits those same lists as optional content. Reproduced: a head with 60 settled decisions and a 120-word `carry_limit` compiles a projection that omits the settled-decisions remainder and methods, while the exported template carries all 60 (a 5.3 KB template beside a 2.6 KB brief). The successor therefore receives, and must reproduce to be accepted, content the carry was sized to leave out. The shape predates P5; receiver-derived budgets make it routine. | Define and measure the complete bundle a successor receives, template included. Either require everything acceptance demands to fit and reject preparation otherwise, or align the optional acceptance checks with the projection's selected content while keeping the mandatory continuity requirements. Add a regression with oversized optional head state. |
| **Before exposing the carry to observers** (Claude opus) | A session-start carry registers the receiver's descriptor, and `_register_substrate_once` raises on a later plan that names the same `substrate_id` with different content. The candidate restriction removed the fit veto; a carry exposed over lugos-mcp would make this the reachable way for an admitted observer to block a handoff. The conflict surfaces as a bare `ValueError` rather than a TORC error, so the structured CLI error contract is not established for it. | Referencing a registered descriptor by id is not enough: an observer could register the future target's id first with a different context limit or capabilities, and a plan that supplies only the id would then be sized from the observer's descriptor instead of detecting the substitution. Separate descriptor reuse from descriptor admission: restrict observer carries to owner-registered descriptors or give registration an ownership rule, and bind an authorized target to its expected descriptor content. Raise `InvalidInputError` on conflict. Add a test in which an observer registers a future target's id with different content. Make this a precondition of rollout step 4, not a documentation note. |
| **Before session-start carries run on long lineages** | Every carry stores a projection that every later checkpoint and carry re-verifies with a per-projection ancestor prefix walk, and both the checkpoint response and `lineage status` return every open drop. Measured below: superlinear verification after a few stored carries, and 347 KB responses at 1,600 revisions. The verifier also hashes every exported artifact file in the store regardless of the lineage argument, so write-path cost grows with handoff history independently of lineage length; that axis was not measured. The delivered carry is unbounded too: every drop that does not fit becomes an entry in the rendered "Omitted from this projection" list, about 40 bytes each, so a fixed receiver budget still permits arbitrarily long model-visible input as omitted drops accumulate (about 28 KB of unbudgeted text for the 694 omitted drops at 1,600 revisions). | Precompute the ancestor set once per verification and scope artifact hashing. Bound the drop list in both responses with a total count, and add a separate paginated drop query with cursor and limit; routing the remainder through the same unpaginated status call, as version 1 proposed, keeps the problem. Deliver a bounded omission summary (counts by section plus a retrieval reference) in the rendered carry and keep the full ledger in the stored projection; test a growing number of omitted drops against a fixed budget and assert the bound on delivered output. Stop building drops that cannot fit. |
| **Before integrating with PR #26** | Both open branches add a different decision numbered 0004. Git merges the two filenames cleanly (checked with merge-tree against c600c0bc), so the conflict is semantic only. The capsule builder takes already-fitted sections, so compacting a carry cannot recover drops that P5 omitted for budget; sizing must happen after rendering or the capsule must be sized on its own. | Give the capsule decision a distinct number, state how it implements the receiver-facing P5 decision, define the required-field mapping an actual successor must receive, and add a P5-projection-to-capsule contract test that covers sizing order. |
| **Low** (Codex gpt-5.6-sol; Claude opus) | The verifier's ancestor allowance is gated on `compiler_version.startswith("p5-")`, a field inside the record being verified, so a projection self-labeled `p5-anything` chooses its own strictness. No test exercises the version gate. | Gate on the exact supported version or an out-of-band policy table; add tests for a fabricated `p5-9` version, a `p5-1` descendant reference, and a `p0-1` ancestor reference. |
| **Low** (Claude opus) | [compile_receiver_projection](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/projections.py#L372) iterates `optional_specs` in list order, whereas the P0 compiler sorts by priority. The recorded `priority` is descriptive metadata in the P5 path, so a reorder of the literal list silently changes what a tight receiver gets. | Reuse the P0 sort and add one assertion that shaping is invariant to list order. |
| **Spec and docs** | The P5 spec says the asks persist "in every carry"; the carry omits them under budget pressure. The spec does not say that acceptance ignores history sections. The spec defines `changes-since-receiver` by the receiver's last authored revision but says it is absent when the receiver "has never borne" the lineage, so a bearer that held the lease from creation and never checkpointed falls under neither clause and gets no summary when it returns; the code keys on authorship. `unaccounted-*` section ids are stable across budgets but shift when an older drop is resolved, so a consumer must key on section and item. The carry command is state-mutating (descriptor and projection) although it grants no authority. | Decide whether bearing intervals or authored revisions define the baseline and state it; state the other four in `docs/p5-receiver-carry.md`. |

### Independent review

A second review of the diff by a native subagent, run without sight of the
Codex comments or the findings above, reached the same two top defects
(stale disposition in `changes-since-receiver`, authorship keyed on content
rather than on the `self_model_revised` event) and added the handoff-prepare
atomicity gap and the descriptor-conflict path. It also recorded behavior
that follows the spec but that a consumer should know:

- A rollback to a revision that itself silently dropped an item yields the
  same head state as the drop but an empty `boundary.unaccounted`. The ask is
  path-dependent, because a `rollback_applied` revision accounts for every
  removal it makes.
- A branch root is attributed to the source activation's substrate, so the
  child lineage's first bearer is asked to restate a self-model that the
  parent's substrate authored. That is intended. The separate case of a
  `lineage_created` root is operator-authored with a null substrate, and no
  ask is raised for it; the surviving mutation on `restatement_due` covers
  only that null case. Version 1 conflated the two.
- An observer carry computes `restatement_due` relative to the receiver, not
  the current bearer. That is the intended reading for an observer, and the
  `session-purpose` section says whether the receiver holds authority.

Everything else probed was found correct: the ancestor allowance rejects a
later revision, a branch parent's revision, and a `p0-1` ancestor reference;
resolution cycles, wrong-section and partly invalid resolution lists, and
wrong-activation checkpoints leave the head and the connection untouched;
partial fits in both units keep `estimated_used` equal to the sum of included
sections; the CLI error paths that were probed (a bad resolutions file, a
zero budget cap, a missing state directory) return structured errors and
create no state directory; the `boundary` field is not embedded in any
closed view schema; and a carry writes only the projection and substrate
tables.

### Test coverage under mutation

The PR reports that four deliberate mutations of the history logic were each
caught. A broader pass on a scratch copy of this checkout
([run_mutations.py](evidence/pr-25-assessment/scripts/mutation/run_mutations.py),
[results](evidence/pr-25-assessment/results/mutation-results.json)) applied
24 single edits across `history.py`, `projections.py`, `verify.py`,
`operator.py`, and `store.py` and ran the full suite after each (two full
runs, identical verdicts). Seventeen were caught, every one by
`tests/test_carry.py`. Seven survived; each was probed and changes observable
behavior, so none is an equivalent mutant.

| Surviving mutation | What the suite does not check |
|---|---|
| Rollback no longer restores the rolled-back revision's self-model authorship | No test rolls back across a self-model edit by a different substrate. |
| `restatement_due` no longer treats an operator-authored (null substrate) self-model as not due | No test asserts the operator-authored case; the mutant makes a freshly created lineage ask its own bearer to restate. |
| `changes-since-receiver` labels an unresolved removal `rolled_back` instead of `unaccounted` | The only assertion on removals covers a `completed` item. This is the expression the first before-merge fix edits. |
| History tier fitted oldest drop first instead of newest first | The fixture drops both items at one revision, so order is never exercised. With drops at different revisions and a 70-word budget, the mutant keeps the older drop. |
| `characters` budgets counted as words | No carry is compiled for a `characters` receiver; only `receiver_budget` is tested for that unit. The mutant counts 116 where 1,464 is correct. |
| Ancestor allowance in `verify` applied to `p0-1` projections too | No forged `p0-1` projection with an ancestor reference. |
| `verify` accepts any revision of the lineage as a `p5-1` source | The only forgery cites another lineage; a later revision of the same lineage is never forged, so the ancestor restriction itself is unverified. |

The before-merge defects sit exactly in the under-tested region
(`changes_since_substrate` dispositions and `self_model_provenance`
authorship). The tests to add are the probes: a rollback across a foreign
self-model edit, an operator-authored lineage, a plain unresolved removal
asserted as `unaccounted` and a genuine rollback removal asserted as
`rolled_back`, two drops at different revisions under a tight budget, one
`characters` carry, forged projections with a `p0-1` ancestor reference, a
`p5-1` descendant reference, and a fabricated `p5-9` version, a forged and a
malformed resolution, a reserved event type on the operator API (asserting
nothing stored, verification still valid, and a later checkpoint accepted),
a transient add-then-resolve while the receiver is away, and a handoff with
oversized optional head state (asserting what the template and brief
deliver against what the projection selected).

### Cost against lineage length

A synthetic probe ([probe.py](evidence/pr-25-assessment/scripts/scaling/probe.py),
[results](evidence/pr-25-assessment/results/scaling-results.json)) built
lineages of 25 to 1,600 revisions in fresh stores, once with every removal
unresolved (drops accumulate) and once with every removal resolved, and
timed the last checkpoint, a carry for each fixture receiver, and status
(median of five runs on an M2 Pro, Python 3.14, SQLite 3.53). Times are
milliseconds.

| Revisions | Checkpoint | Carry, large receiver | Status | Unaccounted drops | Large carry: drops included / omitted |
|---:|---:|---:|---:|---:|---:|
| 25 | 2.1 | 2.5 | 0.7 | 22 | 22 / 0 |
| 100 | 5.8 | 7.1 | 2.1 | 97 | 97 / 0 |
| 400 | 18.1 | 24.8 | 9.1 | 397 | 397 / 0 |
| 1,600 | 68.1 | 88.5 | 36.7 | 1,597 | 903 / 694 |

Every call is linear in lineage length, about 40 to 50 microseconds per
revision, and drop count adds little (about 6 microseconds per drop).
Checkpoint and carry run a full-store verification first, which is 55 to 70
percent of those calls; the chain read is most of the rest. Status runs no
verification at all, which is why it costs about half a checkpoint, and it
returns the boundary block with no integrity check, unlike checkpoint. That
is acceptable for the slice. Five consequences are not, once the carry is
called at every session start on a long-lived lineage:

- **Stored carries make later verification superlinear.** Each carry persists
  a projection, and every later checkpoint or carry re-verifies all of them.
  At 1,600 revisions each stored large-receiver projection adds about 30 ms to
  every later verification, and a 3 KB projection's cost grows roughly
  quadratically with lineage length because [verify](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/verify.py#L471-L481)
  builds the ancestor prefix list per projection and tests membership and
  `startswith` against a growing tuple per section. After three stored
  carries the checkpoint cost 158 ms instead of 67 ms.
- **Artifact hashing is unscoped.** The verifier re-hashes every exported
  brief and reconstruction template in the store on every write, whatever
  lineage is named, so cost also grows with handoff history. The probe did
  not vary that axis.
- **Boundary responses are unbounded.** Checkpoint and status responses
  return the whole unaccounted list: 347 KB at 1,600 revisions with 1,597
  open drops, against about 1 KB when removals are resolved.
- **Omitted drops are still built and sized.** The large receiver's 10,000-word
  budget fills at about 900 drops; after that every further drop is computed
  and then omitted, so included content plateaus while time keeps growing.
- **The rendered omission ledger is outside the budget.** Each omitted drop
  is rendered as one line of the delivered carry, so the model-visible text
  keeps growing after the budget is full: roughly 28 KB of unbudgeted
  omission lines for the 694 omitted drops at 1,600 revisions. Recording the
  rendered size would only observe this; the delivered omission list needs a
  bound of its own.

None of these changes the conclusion for the fixture. They do mean that the
"keeps asking in every carry" rule needs a bound before a real lineage runs
for months, that the verifier's ancestor check should use a precomputed set,
and that the single four-revision fixture says nothing about how the
provenance defects above compound across many handoffs; a stale disposition
that is itself carried, dropped, and re-surfaced is untested.

## Verification on this checkout

| Check | Result |
|---|---|
| `python -m pytest` (macOS, Python 3.14) | 265 passed in 3.2 s |
| `python -m ruff check .` | clean |
| `python -m torc doctor --json` | `p0_ready`, implementation `p5_receiver_carry_implemented`, no missing paths |
| `python -m torc demo` then `verify` (fresh state dir) | demo compiles `p0-1` at 65 of 70 words; verify valid, no errors |
| GitHub CI at a056c61 | ubuntu, macOS, Windows on Python 3.11 and 3.13: lint, tests, CLI smoke, installed artifact smoke all green; host-identifier scan green |
| `git diff --check`, line endings | whitespace clean; new files are LF |
| Merge with PR #26 head c600c0bc | textually clean; semantic ADR 0004 collision as noted |

Unlike PR #26, this PR has no platform-dependent fixture hashing, so the
cross-platform gate holds on this checkout as well as in CI. One local note:
`python -m torc` needs `PYTHONPATH=src` or an install on this host because the
default `python3` belongs to another project's virtual environment; the tests
set the path themselves.

## Composition with PR #26

The two branches solve different halves of the same problem. P5 decides
what the receiver should get, from history and by descriptor. PR #26 decides
how to present it so the model-visible text is short and the provenance
stays with TORC. On the rendered carry, the material a capsule split could
move off-model is bounded above by the bookkeeping sections and identifiers,
about 40 percent of delivered bytes; the stored-record figure says nothing
about delivery. How much is actually saved has to be measured on rendered
input in a live run. The [PR #26 assessment](pr-26-continuity-and-batching-assessment.md)
names the composition: verified P5 projection, then task claims, then a
compact capsule, with the control envelope holding P5 source references,
omissions, budget evidence, and authority context.

Three cautions carry over. The capsule builder accepts caller-supplied,
already-fitted sections and does no selection; P5's selection must remain
the input, and because compacting cannot recover what P5 omitted for budget,
the sizing order must be defined. An actual successor must still receive
every required P5 continuity field; keeping missing material only in the
off-model envelope is insufficient. And a critic or native child that
receives a capsule derived from a session-start carry is an observer;
authority still moves only through accepted handoff.

## Lugos Orca principles for deployment

Active Lugos Orca is an **advisory loadout and seat planner**. Lugos Link
supplies host facts; Orca resolves a target and profile and returns
`autowork_handoff` advice that Autowork may narrow or reject. Autowork owns
the immutable assignment, route, sandbox, capabilities, and launch. The parent
Lugos gitlink reviewed here pins Orca at fbaacba6, whose policy permits
same-harness and same-model review seats and makes independent review
optional. See the pinned
[README](https://github.com/mdn87/lugos-orca/blob/fbaacba6ef306bfc4531ee478e52b6f40a336f79/README.md)
and [coordinator role](https://github.com/mdn87/lugos-orca/blob/fbaacba6ef306bfc4531ee478e52b6f40a336f79/docs/coordinator-role.md),
and TORC's own [integration boundaries](integration-boundaries.md). A P5 carry
is continuity material for whichever seat those components authorize; it
selects no route and grants nothing.

| Step | Owner and gate | Evidence to keep |
|---|---|---|
| 1. Fix history reading and sizing | TORC maintainers fix the seven before-merge defects, each with its reproduction as a test; cap the floor; reuse the priority sort; and decide the preservation policy, the baseline contract, the handoff delivery contract (what a successor receives and must reproduce), and what the budget unit is named. | Full suite on Windows and macOS; the new tests listed above; a recorded decision for each contract question. |
| 2. Reconcile with PR #26 | Renumber the capsule decision, record how a capsule is derived from a `p5-1` projection including sizing order and the required-field mapping, and add the contract test before either branch merges on top of the other. | One verified P5-projection-to-capsule example in the repository. |
| 3. Reconcile the LIR boundary | The parent repository's owner brings `docs/lir/boundaries.md` into line with the receiver-facing interface this PR defines, as ADR 0004 requires; or records the deferral and the gate that releases it. | The reconciled boundary text, or the recorded deferral. |
| 4. Expose the carry to one real receiver | Extend the lugos-mcp TORC adapter, which today only wraps `lineage explain`, with a `lineage carry` call described as authority-preserving but state-mutating (it registers a descriptor and stores a projection), or a separate preview operation that stores nothing. Precondition: descriptor registration has an ownership rule and an authorized target is bound to its expected descriptor content, so an observer can neither block a handoff by conflict nor pre-register a future target's id with its own sizing. The receiver is an observer; Autowork or the operator admits it. | The rendered carry, its projection id, the descriptor and projection writes, and `authority_transferred: false` in the adapter receipt. |
| 5. Run the deferred live comparison | Entry condition: operator approval, because P1b recorded that a retry is a new scope decision and the P5 spec says the comparison needs its own approval. Preregister a source-to-target transition on a real Lugos task with at least one real omission. Arms: the P5 carry, the P0 projection, a compiled prompt built from the head, and a compiled prompt given the same history with comparable preparation effort; native persistence or its preregistered unavailability. Freeze thresholds first. Retain provider usage so tokens and cost are measured, not estimated, and count the complete bundle each arm delivers, template included. | Required commitment and constraint retention, unresolved-work accuracy, whether the receiver acted on the carried drop, context delivered in provider tokens for the whole bundle, preparation and acceptance steps, operator corrections. |
| 6. Apply the evaluation plan and the kill criteria | Judge the result against every initial pass criterion in `docs/evaluation-plan.md` and every kill criterion in `docs/project-brief.md`, not retention alone. If the history-informed compiled prompt matches the carry's retention at lower cost, narrow P5 to the history reader and the asks. If the carry wins on retention at acceptable overhead and operator steps, adopt the bounded preservation policy, including the bound on the delivered omission summary, and plan enforcement; a live experiment is not provider integration. Decide fit in either case: compare the gate's rejections with plain requirement validation on the same transitions, and narrow fit to a requirements surface unless the gate earns its place. | The decision, recorded against the brief, before any provider integration. |

Native subagents and interactive children remain execution-layer facilities.
They can receive a session-start carry as observers under the harness and
project policy that admits them. A child becomes the authoritative bearer only
through TORC's accepted handoff or explicit branch. PR #25 gives such a child
better material to start from; it gives no component a new way to grant
authority.

## Review provenance

Version 2 was produced through the Lugos Roundtable session `pr25-v2-review`
(technique `dimensional-review`: reviewers `codex` and `claude`, synthesizer
`orchestrator`), with every reviewer move executed through Autowork and
relayed into the shared document by the orchestrator. The models were chosen
by what answered a live probe on this host on 2026-10-08, not by the names
in older route definitions. Gemini was excluded because its CLI
authentication check timed out; the Autowork campaign dispatcher was not
used because it pins executor versions older than the installed Codex 0.158.0
and Claude Code 2.1.270, and those safety manifests were left unchanged.

| Seat | Lane and model | Dimension | Outcome |
|---|---|---|---|
| codex | Autowork cross-review, run 20261008-060757, route codex-sol, model gpt-5.6-sol, effort high, adversarial | Claims versus code: every statement in version 1 checked against the captured PR sources and tests | 8 findings, all accepted: five into the findings table (net-delta change summary, store and verifier resolution gap, event-type guard, compiler-version gate, filesystem atomicity), one into the spec row (initial-bearer baseline), one as a correction to version 1's remedy (status is itself unbounded), one as process (evidence bundle). Three were reproduced. |
| codex | Autowork cross-review, run 20261008-060918, route codex-astra, model gpt-6-astra, effort high, adversarial | Measurement validity and argument, against the brief, P1b, the evaluation plan, the concept, ADR 0004, and the PR #26 assessment | 8 findings, all accepted: history-informed compiled-prompt baseline, full evaluation gates, receiver-labeled ratios and the withdrawn "unchanged cost" claim, separated accounting and sizing order for the capsule, bounded preservation policy instead of automatic promotion, carry is state-mutating, evidence bundle, corrected spec reading. Autowork's automatic guardrail marked these "rejected: vague_no_evidence" because the evidence field was a list; the orchestrator adjudicated them on content. |
| claude | Autowork cross-review, run 20261008-061413, route claude-opus, model opus (resolving to claude-opus-5), effort high, adversarial | Concept fit, rollout, and reasoning, against the PR sources, the brief, P1b, the integration boundaries, and ADR 0004 | 23 findings, all accepted: self-referential concept scoring, mixed-unit ratio, strawman baseline, state-mutating carry over MCP with the descriptor-conflict precondition, atomicity re-ranked to before merge with the filesystem correction, bounded preservation wording, uncapped floor, rendered-unit budget as a design change, restatement label tradeoff, record-controlled verifier strictness, unscoped artifact hashing and status without verification, rendered composition, kill-criteria walk, the branch-root correction, per-section fitting, the missing disposition probe, the spec's internal inconsistency, the LIR boundary step, the conditioned verdict, the unsorted optional tier, the bare `ValueError`, and four points of version 1 confirmed correct. |
| panel | Autowork fusion-ask: panel Codex gpt-6-sol (high), Claude fable, Claude opus; judge Claude sonnet | The "does it work better" verdict, six questions | Consensus on content correctness, cost, unproven downstream benefit, the history-tier ranking as a gap, "both" on unit fidelity, and the next experiment. Disagreement on the decisive measurement: gpt-6-sol the P1b tie, fable the small-receiver row, opus the unbounded growth terms. Opus alone raised the baseline-artifact critique on the panel. The judge named six blind spots: descriptor trust, compounding defects across handoffs, no concrete bound design, single-fixture generalization, the attention cost of the asks, and version compatibility of `p5-1` with history compiled under earlier logic. The one-shot command retains the judge's analysis, not the panelists' raw answers. |

A second session, `pr25-v2-refine` (technique `adversarial-refine`, attacker
`codex`, defender `claude`), attacked this version after synthesis; its
record is noted below the provenance table when it converged.

Reproduction scripts, raw results, the reviewers' finding ledgers, the judge's
analysis, the roundtable session documents, and version 1 of this document
are under `docs/evidence/pr-25-assessment/`.
<!-- LUGOS-SECTION:END -->

## REGION: codex
<!-- LUGOS-SECTION:BEGIN -->
[seq 1 | round 1 | phase attack] Attacker: codex. Autowork cross-review run 20261008-063145-cross-review, route codex-astra, model gpt-6-astra, effort high, adversarial, packet manifest 9ae16e02b402e3a9…, status succeeded, 6 findings against version 2 (attack round 1).

- **AR2-01 [high] risk** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:292) — The long-lineage correction misses an unbounded component of the model-visible carry itself: the rendered omission ledger.
  - Evidence: torc/src/torc/projections.py:340-348 creates an omitted-section entry for every drop that does not fit. torc/src/torc/operator.py:597-601 renders every such entry into the delivered carry. Consequently, a fixed receiver budget still permits arbitrarily large delivered input as omitted drops accumulate. The assessment at torc/docs/pr-25-receiver-fitted-carry-assessment.md:292 proposes bounding checkpoint/status responses and avoiding unnecessary drop construction, but does not explicitly bound this rendered ledger. Recording rendered size also only observes the overflow.
  - Suggested fix: Add the rendered omission ledger to the scaling finding and preservation contract. Keep detailed omissions available for audit, but deliver a bounded summary with counts and a retrieval reference. Test increasing numbers of omitted drops against a fixed receiver budget, asserting the chosen bound on delivered output, including its omission summary.
- **AR2-02 [medium] guardrail_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:291) — Referencing descriptors by ID does not prevent observer ID squatting; it can turn a detected conflict into reuse of the observer's descriptor.
  - Evidence: The descriptor-conflict remedy at torc/docs/pr-25-receiver-fitted-carry-assessment.md:291 is subsequently made a rollout precondition intended to prevent squatting. However, torc/src/torc/operator.py:270-283 permits a carry to register the supplied descriptor, and torc/src/torc/projections.py:246-247 retrieves that registered descriptor to determine sizing. Counterexample: an observer first registers the future target's ID with a different context limit or capabilities. A later plan that references only that ID has no independently supplied descriptor against which to detect the substitution. ID-based reuse solves accidental duplication, not registration ownership.
  - Suggested fix: Separate descriptor reuse from descriptor admission. Restrict observer carries to owner-registered descriptors, or introduce an explicit ownership/namespace rule for registration. Bind the authorized target to the expected descriptor content where necessary. Add a test in which an observer attempts to register a future target's ID with different content.
- **AR2-03 [medium] contract_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:286) — The proposed store correction validates shape before writing but postpones eligibility until verification, leaving a supported path to permanently append an invalid resolution.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:286 prescribes shape validation at the store boundary and eligibility replay during verification. Those are different checks: torc/src/torc/history.py:179-199 additionally rejects resolutions for items still present or never dropped. A well-shaped resolution for a nonexistent item would therefore still reach torc/src/torc/store.py:466 onward, where append_revision seals and inserts the revision and advances the head, lease, and activation. Later verification can detect the invalid record but cannot make the append satisfy the pre-write rejection promise in torc/docs/p5-receiver-carry.md:101-104.
  - Suggested fix: Require both shape and eligibility validation inside the store append transaction before inserting the revision. Retain verifier replay as an independent check. Add a direct-store test asserting that a well-shaped but ineligible resolution leaves revisions, head, lease, and activation unchanged.
- **AR2-04 [medium] correctness** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:282) — Letting current unaccounted state override a stale disposition is not a sufficient alternative to scoping dispositions to their removal.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:282 offers these as alternative corrections. Counterexample: the receiver's base contains X; another bearer completes X with a resolution, restores X, then genuinely rolls back to an older revision without X. torc/src/torc/history.py:125-146 still finds the old completed disposition, while unaccounted_drops at lines 52-58 exempts the rollback removal. There is no current unaccounted entry to override completed, so the shortcut still mislabels the latest removal. The removal-scoped alternative would address this.
  - Suggested fix: Remove the unaccounted-only override as a complete remedy, or explicitly supplement it with latest-removal tracking that handles rollback removals. Add resolve-restore-rollback alongside resolve-restore-drop, asserting rolled_back for the former.
- **AR2-05 [medium] correctness** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:114) — Restricting fit evaluation to the source and named target does not establish that the fit-scoring kill criterion is met by construction.
  - Evidence: The assessment makes this conclusion at torc/docs/pr-25-receiver-fitted-carry-assessment.md:114-116 and repeats it at line 240. But torc/src/torc/operator.py:338-347 still evaluates both candidates and rejects preparation when the selected candidate differs from the requested target. Fit therefore remains a veto that could prevent an unsuitable operator choice, or unnecessarily reject a suitable one; the captured evidence does not compare those outcomes. torc/docs/project-brief.md:71-75 conditions the criterion on what the experiment shows.
  - Suggested fix: Describe the demonstrated architectural narrowing: this path no longer searches for another target and instead gates the named choice. Mark comparative value as untested, or justify removing the gate as a product decision. Compare its rejection behavior with simpler explicit requirement validation before claiming that scoring cannot outperform routing.
- **AR2-06 [low] consistency** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:206) — Several passages incorrectly say the floor is not capped by the context limit or can exceed that limit.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:133 says the floor is not capped against the context limit; lines 206-210 repeat that framing, and line 239 says it can exceed the context it is fitted to. torc/src/torc/projections.py:68 explicitly computes min(context_limit, max(CARRY_FLOOR[unit], share)). The assessment's own finding at line 290 correctly acknowledges that cap. A 120-word context receiving a 120-word budget demonstrates excessive allocation, not a budget exceeding the declared context.
  - Suggested fix: Consistently state that the floor is capped by the full context limit but lacks a smaller fractional cap, so it can consume the entire declared context. Keep rendered-output overshoot as a separate issue involving different accounting. <<codex/>>
[seq 3 | round 2 | phase attack] Attacker: codex. Autowork cross-review run 20261008-063954-cross-review, route codex-astra, model gpt-6-astra, effort high, adversarial, packet manifest a8f9e4923ad4f532…, status succeeded, 2 findings against the round-1 rebuttal (attack round 2). The six round-1 corrections were checked and not re-raised.

- **R2-01 [high] lifecycle_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:294) — The reserved-event defect is under-ranked: it can persist an invalid canonical revision that blocks subsequent integrity-gated operations, not merely suppress a boundary ask.
  - Evidence: The assessment at line 294 acknowledges that a checkpoint labeled rollback_applied succeeds and subsequently fails verification for missing rollback context. operator.py:84-125 checks integrity before appending, accepts the unrestricted event_type, and returns success; store.py:466-533 persists the revision and advances the lineage, lease, and activation heads. verify.py:99-102 then subjects that historical revision to rollback validation. Subsequent checkpoints and carries repeat the integrity precheck (operator.py:84-125 and 257-292), so appending another revision cannot clear the failure. This contradicts the assessment's line 293 rationale that handoff preparation is the one defect leaving durable state. The strongest contrary interpretation is that the CLI whitelist contains exposure, but the assessment already makes direct-store resolution poisoning a before-merge issue at line 292; deferring this comparable Python-path poisoning is inconsistent.
  - Suggested fix: Promote the event-type guard to before merge and describe the persistent integrity failure. Require the checkpoint API to accept only checkpoint and self_model_revised. Add a regression asserting that a rejected reserved event changes no stored state, verification remains valid, and a subsequent ordinary checkpoint succeeds. Correct the claim that preparation atomicity is the sole durable-state defect.
- **R2-02 [medium] contract_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:244) — The assessment misses a handoff sizing bypass: the required reconstruction template includes complete optional head-state fields even when the fitted projection omits them.
  - Evidence: The assessment's acceptance row at line 244 discusses missing acknowledgment of historical drops but overlooks the delivery implications of requiring full head-state reconstruction. handoffs.py:15-25 makes settled_decisions and uncertainties default acceptance requirements, and handoffs.py:119-141 copies both complete lists into the reconstruction. operator.py:377-393 exports that complete template; operator.py:534-535 explicitly instructs the recipient to copy it and preserve required fields exactly. Meanwhile projections.py:359-393 fits those lists as optional content. A head with a very large settled-decisions list and small mandatory state can therefore produce a fitting projection that omits the list, while the supplied template still contains it in full. Bounding the omission ledger, as proposed at assessment line 298, does not bound this additional input. The strongest contrary reading is that the template is operator-only; the recipient-facing copying instruction makes that delivery assumption unresolved.
  - Suggested fix: Add a handoff delivery-contract finding and a regression using oversized optional head state. Specify and measure the complete bundle the successor receives, including the reconstruction template. A simple consistent policy is to require all acceptance-required content to fit and reject preparation otherwise; alternatively, explicitly align optional reconstruction checks with selected projection content while preserving mandatory continuity requirements. <<codex/>>
[seq 5 | round 3 | phase attack] Attacker: codex. Autowork cross-review run 20261008-064903-cross-review, route codex-astra, model gpt-6-astra, effort high, adversarial, packet manifest 429aaf1db9950fdd…, status succeeded, 2 findings against the round-2 rebuttal (attack round 3). The round-2 corrections were checked and not re-raised.

- **R3-1 [medium] guardrail_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:309) — The proposed operator-only event guard prevents the demonstrated checkpoint call, but leaves the same permanent lineage poisoning reachable through Store.append_revision.
  - Evidence: The assessment's reserved-event remedy restricts checkpoint_operator_lineage only. Captured torc/src/torc/store.py:466-531 accepts event_type unchanged, seals and inserts the revision, and advances the lineage, lease, and activation. Calling this method with event_type='rollback_applied' produces a revision without rollback_context; torc/src/torc/verify.py:99-102 routes that revision to rollback verification. The assessment itself establishes the resulting permanent integrity failure at torc/docs/pr-25-receiver-fitted-carry-assessment.md:309. Its adjacent resolution finding at line 307 explicitly requires store-level enforcement for every caller. The strongest contrary interpretation is that Store is an intentionally trusted primitive, but that boundary is inconsistent with the resolution remedy.
  - Suggested fix: Enforce the ordinary checkpoint event vocabulary in Store.append_revision as well, preserving dedicated workflows for reserved events. Add a direct-store reserved-event regression asserting no records or heads advance, verification remains valid, and a later ordinary checkpoint succeeds. Alternatively, explicitly justify a consistent internal-only trust boundary instead of claiming validation for every caller.
- **R3-2 [low] consistency** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:136) — Replacing the sole-defect claim with an unqualified count of two remains inconsistent with the document's own findings.
  - Evidence: At torc/docs/pr-25-receiver-fitted-carry-assessment.md:136-139, the brief says two findings can leave durable state behind through supported paths. The atomicity row at line 308 likewise says 'one of the two defects'. However, line 307 describes a persisted malformed resolution that breaks every later history read, line 308 describes persisted partial preparation, and line 309 describes persisted reserved-event poisoning. These are three separately listed findings with durable consequences. Counting only the two operator-workflow paths is a credible interpretation, but the current wording does not state that restriction.
  - Suggested fix: Either count all three durable-state findings or explicitly qualify both occurrences as two operator-workflow defects, with the direct-store resolution defect separately acknowledged. <<codex/>>
[seq 7 | round 4 | phase attack] no new weakness <<codex/>>
<!-- LUGOS-SECTION:END -->

## REGION: claude
<!-- LUGOS-SECTION:BEGIN -->
[seq 2 | round 1 | phase defend] Defender: claude (Claude Fable 5.1, this session). All six attack findings accepted and applied to the artifact: AR2-01 the rendered omission ledger is now a fifth long-lineage consequence with a bounded omission-summary correction and a test; AR2-02 the descriptor precondition is restated as registration ownership plus binding the authorized target to its expected descriptor content, since id reuse alone lets an observer pre-register a target's id with its own sizing; AR2-03 the resolution correction now requires shape and eligibility inside the store append transaction, with verifier replay as an independent check; AR2-04 the unaccounted-override shortcut is withdrawn as a complete remedy and the resolve-restore-rollback case is added to the tests; AR2-05 the fit kill criterion is restated as narrowed to a gate on the named target with untested comparative value, in the brief, the commitments table, the kill-criteria walk, and rollout step 6; AR2-06 every passage now says the floor is capped only by the whole context limit and can consume all of it, never exceed it. <<claude/>>
[seq 4 | round 2 | phase defend] Defender: claude (Claude Fable 5.1, this session). Both round-2 findings reproduced and accepted. R2-01: the reserved-event finding is promoted to before merge; the reproduction now shows that after a rollback_applied-labeled checkpoint through the Python API every later checkpoint and carry is refused with IntegrityError, so the claim that handoff preparation was the only durable-state defect is withdrawn and the brief now counts seven before-merge findings. R2-02: a new finding records that acceptance requires settled_decisions and uncertainties in full, the template delivers them in full, and the brief tells the recipient to copy the template, whatever the fitted projection omitted (60 settled decisions, 120-word carry_limit: projection omits the remainder, template carries all 60); the commitments table, the live-comparison step, and the tests-to-add list are updated accordingly. Reproduction script and output added to the evidence bundle as round2_findings.py. <<claude/>>
[seq 6 | round 3 | phase defend] Defender: claude (Claude Fable 5.1, this session). Both round-3 findings accepted and applied. R3-1: the reserved-event correction now enforces the ordinary checkpoint vocabulary in Store.append_revision itself, with a direct-store regression, matching the store-level rule the resolution correction already demands. R3-2: the brief and the atomicity row now count three durable-state defects (store-appended resolution, partial handoff preparation, reserved-event poisoning) and say which two are reachable from operator workflows. This rebuttal reaches the session's sequence cap; a follow-on session pr25-v2-refine-b runs one convergence check. <<claude/>>
<!-- LUGOS-SECTION:END -->
