<!-- LUGOS-ROUNDTABLE v1 -->
## CONTROL
technique: dimensional-review
seq: 3
round: 2
turn: 
phase: synthesis
status: converged
max_seq: 30
max_rounds: 2
clean_attacks: 0
converge_k: 2
lease_until: 
participants: codex:reviewer:<<codex/>>, claude:reviewer:<<claude/>>, orchestrator:synthesizer:<<orchestrator/>>
submitted_round: 
topic: PR #25 assessment v2: Codex and Claude review the v1 assessment (torc/docs/pr-25-receiver-fitted-carry-assessment.md) along separate dimensions; the orchestrator synthesizes v2
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
  of them, fit scoring against explicit routing, is now met by construction
  in the only non-synthetic path.
- Six findings are now before-merge: the three provenance defects, the net-
  delta change summary, resolution validation at the store and verifier, and
  the non-atomic handoff preparation, which is the one defect that leaves
  durable state behind and whose correction must cover the filesystem.
- New findings: the Python checkpoint API accepts a `rollback_applied` label
  that exempts removals; the sizing floor can hand a small receiver its whole
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
- The replay, sweep, mutation, scaling, and reproduction scripts, their raw
  outputs, the reviewers' finding ledgers, and the panel's judged analysis
  are committed under `docs/evidence/pr-25-assessment/`.

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
that fit scoring cannot outperform explicit routing, is now met by
construction: in the only non-synthetic path, fit can confirm the operator's
named target and nothing else.

As submitted, the carry is more explicit than a plain summary about what it
omits and why, and it is contradictory about dispositions under specific
succession patterns. After the before-merge fixes it would also be more
correct. Six findings are before merge; they are local and have reproduction
scripts, and none touches canonical history, leases, or authority. The
review campaign also showed that the measurements most likely to decide the
overhead criterion are contested: the P1b tie, the small receiver's budget
row, and the unbounded growth terms on long lineages each had a panelist's
vote. This version leads with the facts that threaten the hypothesis rather
than with the fixture table.

## Significant improvements

| Area | What changed | Why it matters |
|---|---|---|
| Receiver-derived sizing | [receiver_budget](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/projections.py#L48-L73) uses the descriptor's `carry_limit`, otherwise 5 percent of the context limit with a floor; an operator cap can only lower it. | The receiver, not the operator's plan, decides how much it can take, and the derivation is recorded in the carry's `receiver-fit` section. The descriptor is self-reported and unverified, and the floor is not capped against the context limit (finding below). |
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
- **Floor against context.** The 200-word floor is not capped by the context
  limit: a receiver declaring a 300-word context gets a 200-word carry budget
  (67 percent of its context) and one declaring 120 words gets all 120, and
  the suite asserts both as correct. For the smallest receivers the sizing
  rule is the opposite of fitted.
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
| Compile a projection within a target budget; context sizing is a deterministic approximation (brief) | Budget from the descriptor, item-level fitting, one capability rule, omissions with reasons. | The unit counts content rather than delivery; the 5 percent share and the floors are unmeasured constants; the floor can exceed the context it is fitted to; the required tier is TORC's metadata while the history tier is optional; the descriptor is self-reported. |
| Fit scoring must outperform explicit routing or be narrowed (brief, kill criterion) | The operator handoff now confirms the named target instead of ranking every registered descriptor; selection survives only in the demo and experiment lanes. | Met by construction in the non-synthetic path. Narrow fit to the requirements-expression surface that the integration boundaries already describe ("Routing and fit are different"), and let Autowork and Orca route. |
| Validate target reconstruction before authority transfer (brief, ADR 0003) | Handoff and recovery preparation compile with `p5-1`; the brief carries the drops; the verifier checks ancestor references. | [Acceptance](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/handoffs.py#L119-L141) compares head-state fields only, so a successor is accepted without acknowledging the unaccounted drops. Consistent with "asks never block"; the spec should say so, or add an optional continuity requirement. The verifier's ancestor check is about hash-chain validity, not disposition correctness. |
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
its pair. (3) Fit scoring cannot outperform explicit routing: met by
construction after this PR, as above. (4) Projection and handoff overhead
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
| **Before merge** | [changes_since_substrate](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L125-L146) collects every resolution since the receiver's base revision and reuses it for a later removal of the same item. Reproduced: an item completed, restored, then dropped again without a resolution appears in the carry as `completed` in `changes-since-receiver` and as `unaccounted-open_work-3` at the same time. | Scope a disposition to the removal it accounts for, or let the current unaccounted state override the disposition. Add the resolve-restore-drop sequence to `tests/test_carry.py`, plus a plain unresolved removal asserted as `unaccounted` and a genuine `rollback_applied` removal asserted as `rolled_back`, since the fix edits exactly the expression those labels come from. |
| **Before merge** | [changes_since_substrate](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L114-L121) treats the `handoff_accepted` revision as work authored by the returning substrate. Reproduced: a successor completes an item with a resolution, hands the lineage back, and the returning bearer's carry has no `changes-since-receiver` section, although the same carry taken one step earlier reported two revisions of change. | Skip `handoff_accepted` revisions when finding the receiver's last authored revision, as `self_model_provenance` already does, and resolve the baseline contract (below) in the same change. |
| **Before merge** | [self_model_provenance](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L86-L90) assigns authorship by content change only. Reproduced: a successor that confirms the inherited self-model verbatim with a `self_model_revised` checkpoint stays at `restatement_due: true`; only a textual change clears it. | Treat a `self_model_revised` event as a restatement, keeping the `handoff_accepted` exclusion. This trades a content-derived signal for a self-declared label, so pair it with event-type validation and record `authored_by` (from content) and `last_restated_by` (from the event) separately, so a verbatim confirmation is visible as a confirmation. |
| **Before merge** (Codex gpt-5.6-sol) | The spec says `changes-since-receiver` "lists what was added, removed, and resolved" since the receiver last authored a revision. [The implementation](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L131-L148) is a net set difference between that base and the head. Reproduced: an item the successor added and then completed with a resolution before the original bearer returned is absent from `added`, `removed`, and the dispositions; the section reports only `self_model_changed`. | Either fold the revisions after the base and report additions, removal epochs, and resolutions as events, or redefine the section as a net delta in the spec and stop claiming it reports everything resolved. Add add-then-resolve and already-absent-then-resolve tests. |
| **Before merge** (Codex gpt-5.6-sol) | Resolution legality is enforced only on the operator checkpoint path. [append_revision](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/store.py#L466) stores any `resolutions` list, and `verify_store` never checks resolution shape or eligibility. Reproduced: a correctly sealed revision appended through the store with a fabricated `completed` resolution passes verification and silences the real drop; a malformed entry is stored and makes every later history read raise `KeyError`. | Validate resolution shape at the store boundary and replay eligibility during verification; a malformed record must be a verification error, not a crash in the carry. Add forged-resolution tests for a nonexistent item, a wrong section, and a malformed entry. |
| **Before merge** (independent review; Codex gpt-5.6-sol and Claude opus on the filesystem) | The spec says a carry that cannot fit stores nothing, and the carry honors that in one transaction. [prepare_operator_handoff](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L330-L358) does not: when the receiver-derived budget cannot hold the required tier, the registered target descriptor and the fit decision remain stored. The two handoff artifacts are written with exclusive-create before their metadata rows, so a database transaction alone cannot make preparation atomic, a retry fails on the existing file, and `artifact_metadata`'s own `with store.connection:` would commit an enclosing transaction early. This is the one defect that leaves durable state behind on a reachable path, which is why it moved up from version 1. | Render first, write both artifacts to temporary paths, do the database work in one immediate transaction with `prepare_handoff` and `artifact_metadata` joining it, finalize the files at the commit boundary, and clean up on every failure. Add an injected second-export failure test. |
| **Before the Python API is a consumer surface** (Codex gpt-5.6-sol; Claude opus) | The CLI restricts `--event-type` to `checkpoint` and `self_model_revised`, but [checkpoint_operator_lineage](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L84-L121) accepts any string, and `unaccounted_drops` exempts every removal made by a revision labeled `rollback_applied`. Reproduced: a plain checkpoint with that label removed an item without an ask; verification flags the missing rollback context only afterwards. | Validate `event_type` against the vocabulary in the operator API and route rollback, branch, and handoff events through their own workflows. Add a test that a reserved event type leaves the head unchanged. |
| **Before small receivers are real** | The required tier is TORC's metadata; the history tier is optional and ranks below it in code order. Measured: budgets of 55 to 68 words carry bookkeeping plus goals and uncertainties and omit both drops; 84 is the first budget that carries both. The spec's packing order permits this, so the gap is in the choice of required tier, not in the fitting loop. | Decide a bounded preservation policy rather than promoting the history tier to required outright, because the required tier is all-or-nothing and the scaling probe already has 1,597 drops against a 903-drop budget: which drops are mandatory, what happens on overflow, and the minimum supported budget, tested on a lineage whose history exceeds the receiver budget. |
| **Before small receivers are real** (Claude opus) | [receiver_budget](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/projections.py#L48-L73) takes the larger of the 5 percent share and the floor, capped only by the context limit itself, and the suite asserts a 300-word context gets 200 and a 120-word context gets 120. | Cap the floor as a fraction of the context limit, or require small descriptors to declare `carry_limit`. Record the rendered size in `receiver-fit` as evidence; treat a rendered-unit budget as its own design slice. |
| **Before exposing the carry to observers** (Claude opus) | A session-start carry registers the receiver's descriptor, and `_register_substrate_once` raises on a later plan that names the same `substrate_id` with different content. The candidate restriction removed the fit veto; a carry exposed over lugos-mcp would make this the reachable way for an admitted observer to block a handoff. The conflict surfaces as a bare `ValueError` rather than a TORC error, so the structured CLI error contract is not established for it. | Let a plan reference a registered descriptor by id, or require byte-identical descriptors and say so; raise `InvalidInputError`; make this a precondition of rollout step 4, not a documentation note. |
| **Before session-start carries run on long lineages** | Every carry stores a projection that every later checkpoint and carry re-verifies with a per-projection ancestor prefix walk, and both the checkpoint response and `lineage status` return every open drop. Measured below: superlinear verification after a few stored carries, and 347 KB responses at 1,600 revisions. The verifier also hashes every exported artifact file in the store regardless of the lineage argument, so write-path cost grows with handoff history independently of lineage length; that axis was not measured. | Precompute the ancestor set once per verification and scope artifact hashing. Bound the drop list in both responses with a total count, and add a separate paginated drop query with cursor and limit; routing the remainder through the same unpaginated status call, as version 1 proposed, keeps the problem. Stop building drops that cannot fit. |
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
malformed resolution, a reserved event type on the operator API, and a
transient add-then-resolve while the receiver is away.

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
is acceptable for the slice. Four consequences are not, once the carry is
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
| 1. Fix history reading and sizing | TORC maintainers fix the six before-merge defects, each with its reproduction as a test; validate event types on the operator API; cap the floor; reuse the priority sort; and decide the preservation policy, the baseline contract, and what the budget unit is named. | Full suite on Windows and macOS; the new tests listed above; a recorded decision for each contract question. |
| 2. Reconcile with PR #26 | Renumber the capsule decision, record how a capsule is derived from a `p5-1` projection including sizing order and the required-field mapping, and add the contract test before either branch merges on top of the other. | One verified P5-projection-to-capsule example in the repository. |
| 3. Reconcile the LIR boundary | The parent repository's owner brings `docs/lir/boundaries.md` into line with the receiver-facing interface this PR defines, as ADR 0004 requires; or records the deferral and the gate that releases it. | The reconciled boundary text, or the recorded deferral. |
| 4. Expose the carry to one real receiver | Extend the lugos-mcp TORC adapter, which today only wraps `lineage explain`, with a `lineage carry` call described as authority-preserving but state-mutating (it registers a descriptor and stores a projection), or a separate preview operation that stores nothing. Precondition: plans reference descriptors by id, so an observer cannot squat a substrate id. The receiver is an observer; Autowork or the operator admits it. | The rendered carry, its projection id, the descriptor and projection writes, and `authority_transferred: false` in the adapter receipt. |
| 5. Run the deferred live comparison | Entry condition: operator approval, because P1b recorded that a retry is a new scope decision and the P5 spec says the comparison needs its own approval. Preregister a source-to-target transition on a real Lugos task with at least one real omission. Arms: the P5 carry, the P0 projection, a compiled prompt built from the head, and a compiled prompt given the same history with comparable preparation effort; native persistence or its preregistered unavailability. Freeze thresholds first. Retain provider usage so tokens and cost are measured, not estimated. | Required commitment and constraint retention, unresolved-work accuracy, whether the receiver acted on the carried drop, context delivered in provider tokens, preparation and acceptance steps, operator corrections. |
| 6. Apply the evaluation plan and the kill criteria | Judge the result against every initial pass criterion in `docs/evaluation-plan.md` and every kill criterion in `docs/project-brief.md`, not retention alone. If the history-informed compiled prompt matches the carry's retention at lower cost, narrow P5 to the history reader and the asks. If the carry wins on retention at acceptable overhead and operator steps, adopt the bounded preservation policy and plan enforcement; a live experiment is not provider integration. Narrow fit to a requirements surface in either case. | The decision, recorded against the brief, before any provider integration. |

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
[seq 1 | round 1 | phase review] Reviewer: codex (two Autowork cross-review runs, adversarial mode, effort high, deadline 1800 s; both completed in under 4 minutes).

## Dimension: claims versus code
Provenance: run 20261008-060757-cross-review, route codex-sol, model gpt-5.6-sol, effort high, packet manifest fcb13fc4302d6041…, status succeeded, 8 findings.

- **CR-001 [high] correctness** (torc/src/torc/history.py:114-146) — The assessment and P5 spec describe `changes-since-receiver` as listing what was added, removed, and resolved while the receiver was away.
  - Evidence: The implementation selects one base revision and the head, then computes only their net set difference. A transient item that is added and later completed before the receiver returns is absent from both states, so `added`, `removed`, and `self_model_changed` are empty and the function returns `None`. Likewise, a resolution made after the base for an item already absent at the base is never reported. This contradicts the event-oriented wording in `torc/docs/p5-receiver-carry.md:64-68` and is not covered by `torc/tests/test_carry.py:300-365`, whose item exists at the base and remains absent at the head.
  - Suggested fix: Either fold revisions after the base and report additions, removal epochs, and resolutions as events, or explicitly redefine the section as a net head-versus-base delta and stop claiming that it reports everything resolved since the receiver left. Add add-then-resolve and already-absent-then-resolve tests.
- **CR-002 [high] guardrail_gap** (torc/src/torc/operator.py:55-91) — Checkpointing safely records ordinary checkpoints or explicit self-model restatements, while rollback accounting is reserved for the rollback workflow.
  - Evidence: `checkpoint_operator_lineage` accepts an unrestricted `event_type` string and commits it through `Store.append_revision`. `unaccounted_drops` treats any revision labeled `rollback_applied` as accounting for every removal solely from that label (`torc/src/torc/history.py:41-55`). A caller can therefore submit a normal checkpoint as `rollback_applied`, silently remove tracked work, receive an empty boundary, and only have the missing rollback context detected by a later verification (`torc/src/torc/verify.py:51-68`). The invalid revision has already been committed by then.
  - Suggested fix: Restrict the checkpoint API to its permitted event types, such as `checkpoint` and `self_model_revised`, and require rollback, branch, and handoff events to use their dedicated workflows with context validation before writing. Add a regression test proving a reserved event type leaves the head unchanged.
- **CR-003 [high] contract_gap** (torc/src/torc/verify.py:32-75) — The assessment presents resolutions as validated provenance and reports tamper and misattribution verification as passing.
  - Evidence: Resolution legality is enforced only by the operator checkpoint path. `Store.append_revision` accepts a `resolutions` list without calling either resolution validator (`torc/src/torc/store.py:466-518`), while `verify_store` checks revision hashes, parent links, rollback context, and branch context but never validates resolution shape or whether a resolution names a real removal. A directly appended, correctly sealed revision can therefore contain a fabricated resolution that `unaccounted_drops` trusts and that verification accepts. A malformed resolution can instead make history reading fail at `item["section"]` or `item["item"]`.
  - Suggested fix: Validate resolution shape and removal eligibility at the revision-writing boundary, and replay the same semantic checks during verification. Add valid-hash forged-resolution tests for a nonexistent item, a wrong section, and a malformed entry.
- **CR-004 [medium] spec_mismatch** (torc/src/torc/verify.py:471-481) — The spec and assessment state that the ancestor-reference exception applies to compiler `p5-1`, while `p0-1` remains strict.
  - Evidence: The verifier actually enables ancestor references for every compiler version whose string starts with `p5-`. Thus an unknown or forged `p5-experimental` or `p5-invalid` projection receives the same relaxed provenance rule. The captured test only forges a reference to another lineage and does not exercise compiler-version authorization (`torc/tests/test_carry.py:407-443`).
  - Suggested fix: Gate the exception on the exact supported compiler version, or on an explicit registry of versions and their reference policy. Add tests for an unknown `p5-*` version as well as the already-proposed descendant and `p0-1` ancestor cases.
- **CR-005 [medium] lifecycle_gap** (torc/src/torc/operator.py:304-405) — The assessment's smallest correction for non-atomic handoff preparation is to place registration, fit, compilation, activation, preparation, and artifact metadata in one immediate transaction.
  - Evidence: A handoff also writes two filesystem artifacts sequentially. `_export_text_artifact` creates each file with `open("x")` before inserting its metadata (`torc/src/torc/operator.py:735-758`). A database rollback cannot remove those files. Failure after the first export can leave an orphaned brief or metadata/file mismatch, and a retry can fail because the path already exists. Merely joining `artifact_metadata` to the SQL transaction therefore does not make preparation atomic.
  - Suggested fix: Include filesystem failure handling in the correction: render first, write both artifacts to temporary paths, perform database work in one transaction, finalize the files only at a defined commit boundary, and clean up staged or finalized files on every failure. Add an injected second-export or metadata-failure test.
- **CR-006 [medium] consistency** (torc/src/torc/history.py:107-121) — `changes-since-receiver` is absent only when the receiver has never borne the lineage or nothing changed since it last bore/authored it.
  - Evidence: The code recognizes bearing only through revisions whose actor has that substrate ID. A created lineage's root revision is operator-authored with a null substrate (`torc/src/torc/store.py:415-438`), even though `create_operator_lineage` immediately gives the supplied substrate the activation and lease (`torc/src/torc/operator.py:31-54`). If that initial bearer hands off before checkpointing, a later carry for it finds no base and reports no changes. The assessment notes this under “behavior that follows the spec,” but it conflicts with the spec's “never borne” condition and is not merely a consumer caveat.
  - Suggested fix: Define the baseline from authority/activation history rather than revision authorship, using the revision at which the receiver first or last acquired authority. Alternatively, change the contract consistently to “last authored a non-bookkeeping revision” and explicitly document that an initial bearer without a checkpoint receives no change summary.
- **CR-007 [medium] scope_management** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:6-16) — The assessment reports exact PR metadata, CI results, replay measurements, mutation outcomes, performance measurements, merge behavior, schema changes, fixture behavior, and behavior in uncaptured modules as verified facts.
  - Evidence: The packet contains only eight files. It does not contain the git diff or commit metadata, CI logs, schemas, fixture files, replay script or outputs, mutation harness/results, benchmark data, `handoffs.py`, `fit.py`, CLI implementation, ADRs, PR #26, or the referenced parent-repository documents. The assessment expressly says its replay script and outputs are in a session scratchpad rather than the repository (`torc/docs/pr-25-receiver-fitted-carry-assessment.md:76-79`). The captured sources can support some static conclusions but cannot substantiate the reported executions or exact measured numbers.
  - Suggested fix: Attach the replay program and raw output, benchmark and mutation artifacts, relevant schemas/fixtures and omitted modules, a captured diff/manifest, and CI evidence; otherwise label these statements as externally reported and exclude them from conclusions claimed to be reproducible from the packet.
- **CR-008 [low] correctness** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:150-154) — The proposed remedy for unbounded boundary responses is to return a count and newest few drops, with the remainder available through status.
  - Evidence: `lineage status` is itself one of the unbounded response paths: `operator_lineage_status` directly embeds `_boundary`, which returns the complete `unaccounted_drops` list (`torc/src/torc/operator.py:202-230` and `torc/src/torc/history.py:149-163`). Leaving the remainder available through the same unpaginated status call preserves the reported 347 KB response problem rather than fixing it.
  - Suggested fix: Specify a separate paginated history/drop query or add explicit cursor and limit semantics to status. Keep ordinary checkpoint and status summaries bounded and include total count plus continuation information.

## Dimension: measurement validity and argument
Provenance: run 20261008-060918-cross-review, route codex-astra, model gpt-6-astra, effort high, packet manifest 69219a998285f357…, status succeeded, 8 findings.

- **F1 [high] contract_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:315) — The proposed live comparison does not explicitly include the simpler alternative used by its own kill decision: a compiled prompt supplied with history.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:73-98 compares transports built from the same head and explains that only P5 sees the ancestor containing the dropped items. This establishes the benefit of access to history, but does not isolate receiver fitting or TORC's additional machinery. torc/docs/pr-25-receiver-fitted-carry-assessment.md:315 names P5, P0, and a compiled prompt; line 316 then proposes deciding whether a compiled prompt plus history matches P5. Equal access to history is not specified for that comparison. torc/docs/project-brief.md:73 explicitly names a compiled prompt plus existing Lugos records as the simpler alternative. torc/docs/evaluation-plan.md:15 includes relevant files in Baseline A, and lines 17-24 require native persistence or a preregistered explanation of its unavailability.
  - Suggested fix: Specify a history-informed compiled-prompt baseline with equivalent source information and comparable preparation effort. Include native persistence or preregister its unavailability. Keep the current head-only replay as a mechanism demonstration. The split verdict correctly withholds a receiver-performance claim; retain that limitation until this stronger comparison runs.
- **F2 [high] guardrail_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:316) — The rollout substitutes retention at acceptable overhead for the full existing advancement criteria.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:315-316 records retention, acted-on drops, tokens, and corrections, then proposes promotion and enforcement planning if retention wins at acceptable overhead. torc/docs/evaluation-plan.md:59-72 additionally requires zero required-commitment and hard-constraint loss, complete transfer provenance, exclusive authority, equal or better task quality, measurable reduction in irrelevant context or corrections, acceptable operator steps, and frozen thresholds. torc/docs/project-brief.md:71-77 also requires considering an existing runtime, routing value, and duplicated facilities. The assessment's final decision rule does not account for these alternatives.
  - Suggested fix: Make step 5 explicitly subject to all applicable evaluation gates and kill criteria, with thresholds frozen before runs. Define operational burden to include preparation, acceptance, and operator steps. Distinguish an external live experiment from production provider integration. A retention improvement alone must not authorize advancement.
- **F3 [medium] correctness** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:120) — The arithmetic supports bounded size comparisons, but the assessment overextends them into a conclusion that P5 leaves carrying cost unchanged.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:81-86 supports 116/67 = 1.73 for the large receiver, 99/67 = 1.48 for the small receiver, and 184/60 = 3.07 for the large rendered carry against the reported prompt word count. The small rendered ratio is 174/60 = 2.90. torc/docs/pr-25-receiver-fitted-carry-assessment.md:120-125 compares the rendered 3.1 ratio with P1b's 3.26 and concludes that P5 changes what is carried, not what carrying costs. torc/docs/p1b-results.md:14-24 reports the 3.26 word and 4.31 byte ratios on a different, ceiling-saturated synthetic fixture and records a small, mixed inherited/new-label difference. Thus 'tying every continuity measure' is also too absolute. torc/docs/decisions/0004-torc-is-always-in-charge.md:33 states that the fixed-packet P1b tie counts neither for nor against the shaped-carry decision.
  - Suggested fix: Label the 73 percent and 3.1 figures as large-receiver results, retain the valid P1b arithmetic, and describe the cross-fixture similarity as descriptive only. Replace the unchanged-cost conclusion with the supported finding that this replay delivers additional recovered information with substantial additional text. Preserve the conclusion that net benefit remains unmeasured.
- **F4 [medium] contract_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:280) — The capsule composition argument conflates stored-record overhead with removable delivered context and omits the sibling assessment's explicit successor-preservation condition.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:111-119 mixes rendered word counts, an unverified provider-token estimate, and the stored record's 31 percent section-content share. torc/docs/pr-25-receiver-fitted-carry-assessment.md:280-287 uses the complementary 69 percent stored-record share and TORC's three model-facing sections to motivate moving material off-model. Stored bytes do not establish how much delivered context can be removed. torc/docs/p5-receiver-carry.md:54 classifies purpose, receiver-fit, and self-model-provenance as required sections. torc/docs/pr-26-continuity-and-batching-assessment.md:78-85 expressly requires an actual successor to receive every required P5 continuity field and says that keeping missing material only in the off-model envelope is insufficient.
  - Suggested fix: Separate stored-record, rendered-delivery, and measured provider-token accounting. Treat the approximately 20-token identifier estimate as unverified. Restate the successor-preservation condition and define the required-field mapping in the composition test. Also specify whether sizing happens before or after capsule rendering: compacting an already-fitted projection cannot recover drops that P5 already omitted.
- **F5 [medium] risk** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:316) — Automatically promoting history to required after a retention win can make carries impossible on bounded receivers.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:102-110 reports that required metadata consumes space before dropped items; this is a valid challenge to the chosen required tier. torc/docs/p5-receiver-carry.md:45-56 deliberately makes required-section overflow fatal and gives history higher priority than optional head state. Smaller optional sections fitting after a history item fails is therefore consistent with the documented packing policy. torc/docs/pr-25-receiver-fitted-carry-assessment.md:228 reports 1,597 drops with only 903 fitting the large receiver, while line 316 proposes promoting the history tier to required without a bound.
  - Suggested fix: Distinguish required-tier policy from optional packing order. Replace automatic promotion with a measured, bounded preservation policy that defines mandatory drops, overflow behavior, and minimum supported budgets. Test a lineage whose required history exceeds the receiver budget before making history mandatory.
- **F6 [medium] consistency** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:314) — The proposed adapter call is described as read-only even though the assessment establishes that it persists state.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:314 requests a read-only lineage carry call. torc/docs/pr-25-receiver-fitted-carry-assessment.md:67 says that carry registers the descriptor and stores a projection; lines 237-244 explain the cumulative verification cost of those stored projections. torc/docs/p5-receiver-carry.md:26-30 and 139-140 likewise specify immutable projection storage and receiver registration. Receiving no authority does not make these writes read-only.
  - Suggested fix: Describe the existing call as authority-preserving but state-mutating, and expose its persistence semantics in the adapter contract. If a genuinely read-only interface is needed, define a separate preview operation. Include projection and descriptor writes in its focused verification.
- **F7 [medium] missing_test** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:78) — The new quantitative evidence is insufficiently preserved to reproduce the assessment's measurement-dependent recommendations.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:78-79 explicitly places the replay script and outputs in a session scratchpad outside the repository. torc/docs/pr-25-receiver-fitted-carry-assessment.md:102-125 depends on exact budget thresholds, rendering counts, and record-size decomposition. torc/docs/pr-25-receiver-fitted-carry-assessment.md:190-206 reports 24 mutations without captured mutation definitions, and lines 217-250 report synthetic scaling results without a captured generator or raw samples.
  - Suggested fix: Preserve a compact reproducibility bundle: replay and synthetic-lineage generators, input identities, per-budget included and omitted sections, exact counting methods, mutation definitions and outcomes, and timing samples. Until then, identify these as reported local observations rather than independently reproducible packet evidence.
- **F8 [low] spec_mismatch** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:172) — The assessment attributes a 'last bore the lineage' baseline to the P5 specification, which actually specifies the last authored revision.
  - Evidence: torc/docs/pr-25-receiver-fitted-carry-assessment.md:172-174 says the implementation keys on authored revisions while the spec says 'last bore the lineage'. torc/docs/p5-receiver-carry.md:68-70 explicitly defines changes since the receiving substrate last authored a revision. It separately says the section is absent when the receiver has never borne the lineage.
  - Suggested fix: Correct the quotation. Present the never-checkpointed bearer case as a possible gap in the chosen authored-revision semantics, rather than an established implementation/spec mismatch. If bearing intervals should define the baseline, propose that as an explicit contract change with a focused test. <<codex/>>
<!-- LUGOS-SECTION:END -->

## REGION: claude
<!-- LUGOS-SECTION:BEGIN -->
[seq 2 | round 1 | phase review] Reviewer: claude (one Autowork cross-review run, adversarial mode, effort high, deadline 1800 s; completed in about 10 minutes).

## Dimension: concept fit, rollout, and reasoning
Provenance: run 20261008-061413-cross-review, route claude-opus, model opus (resolves to claude-opus-5 on this host), effort high, packet manifest b0fe661eb6a28a4f…, status succeeded, 23 findings.

- **CR-001 [high] consistency** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:112) — The entire 'Fit with TORC's concept' judgment is argued from two documents the PR under review itself introduces, and one of them is not in the packet, so the concept-fit column is self-referential and unverifiable. The assessment never states this.
  - Evidence: The assessment lists the PR's own contents as including '... a four-revision fixture, the concept record, ADR 0004, and the P5 specification.' It then scores the PR against those same artifacts: 'The [original concept](concepts/0001-torc-original-concept.md) centers on a continuously revised self ... ADR 0004 assigns that carry to TORC', and the table's last row is headed 'TORC is always in charge (ADR 0004)'. `torc/docs/concepts/0001-torc-original-concept.md` is absent from the captured manifest (11 files, none of them the concept record), so the 'Concept requirement' column cannot be checked against packet evidence at all. Captured `torc/docs/decisions/0004-torc-is-always-in-charge.md:2-3` is dated 2026-09-20 with Status Accepted, which the assessment neither reconciles with nor distinguishes from 'the PR adds ADR 0004'.
  - Suggested fix: In v2, state explicitly which of ADR 0004 and the concept record pre-existed master and which land with the PR. Score the PR only against artifacts the PR does not author (project-brief.md, integration-boundaries.md, p1b-results.md); for PR-authored standards, assess them as proposals (is this the right ruling?) in a separate section rather than as a conformance test.
- **CR-002 [high] correctness** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:106) — The headline overhead figure ('about three times', '3.1 times') is a mixed-unit ratio: it divides the carry's rendered Markdown word count by the compiled prompt's compiler-estimated word count. The two like-for-like comparisons available in the assessment's own table give 1.9x and 4.3x, which materially changes how the overhead kill criterion reads.
  - Evidence: The replay table reports, for the compiled-prompt shape, 'Budget units used: 60 words' and 'What the receiver reads: 580 bytes' - no rendered word count. For the large receiver it reports '116 of 10,000 words' used and '184 words, 2,519 bytes' read. The assessment then asserts 'about three times the compiled-prompt shape once rendered' and 'The rendered P5 carry is 3.1 times the compiled-prompt shape from the same head' (184/60). Like-for-like: estimated units 116/60 = 1.9x; rendered bytes 2,519/580 = 4.3x. The same section criticises exactly this error elsewhere - 'the unit should at least measure what is delivered' - and the P1b corroboration is also cross-fixture and cross-unit: `torc/docs/p1b-results.md` records 3.26x on estimated words and 4.31x on UTF-8 bytes for the `p1a-review-001` fixture, not for `p5-dropped-work`.
  - Suggested fix: Report one ratio per unit, computed the same way on both sides: estimated-units vs estimated-units, rendered-words vs rendered-words (requires capturing the compiled prompt's rendered word count), and bytes vs bytes. Drop the P1b numeric comparison or label it explicitly as a different fixture and a different unit, consistent with p1b-results.md and ADR 0004's 'The P1b tie compared two fixed packets, so it counts neither for nor against this decision.'
- **CR-003 [high] scope_management** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:96) — The replay tests a strawman baseline. The captured kill criterion names 'a compiled prompt plus existing Lugos records'; the replay compares only head-sourced transports, so the proven contribution is the history reader, not the receiver-fitted carry - and the history reader is the cheap, separable half while receiver-fitting carries the cost.
  - Evidence: `torc/docs/project-brief.md` kill criteria: 'A compiled prompt plus existing Lugos records preserves the same required continuity with less operational burden.' The assessment's comparison set is 'the P0 compiler was run at the same budgets, and the P1 compiled-prompt shape (`experiment_lanes.materialize_compiled_prompt`) was built the way the P1 source capture builds it' - both from 'the same head'. It then over-generalises: 'No format change could recover the two items, because neither the P0 projection nor a compiled prompt ever sees the revision that held them' - true only of head-sourced formats. The assessment concedes the point only in rollout step 5 ('If the compiled prompt plus history matches the carry's retention at lower cost, narrow P5 to the history reader and the asks'), while 'Assessment in brief' and 'Significant improvements' credit the carry.
  - Suggested fix: Restate the verdict in v2 as: the history reader (`torc/src/torc/history.py` `unaccounted_drops`/`revision_chain`) is the demonstrated contribution; receiver-derived sizing and item-level shaping are unvalidated and are where the overhead sits. Add a third replay arm - a compiled prompt built from the chain rather than the head - so the measured baseline is the one the kill criterion names.
- **CR-004 [high] risk** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:336) — Rollout step 3 proposes exposing `lineage carry` over lugos-mcp as a 'read-only' call. The carry is not read-only: it writes two tables and permanently claims a `substrate_id`. Exposing it over MCP promotes the assessment's own 'Low' descriptor-conflict finding into a reachable path for an admitted observer to block future handoffs.
  - Evidence: Step 3: 'Extend the lugos-mcp TORC adapter, which today only wraps `lineage explain`, with a read-only `lineage carry` call.' `torc/src/torc/operator.py` `carry_operator_lineage` does `with store.transaction(immediate=True): ... _register_substrate_once(store, substrate); projection = compile_receiver_projection(...)` - two writes. The assessment itself says so twice: 'A session-start carry registers the receiver's descriptor. A later handoff plan that names the same `substrate_id` with different content fails with a descriptor conflict' and 'a carry writes only the projection and substrate tables'. The conflict is raised by `_register_substrate_once`: 'if canonical_json(existing) != canonical_json(substrate): raise ValueError(f"substrate already exists with different content...")', and `prepare_operator_handoff` calls `_register_substrate_once(store, target_substrate)` before anything else, so a squatted id fails the plan.
  - Suggested fix: Either drop 'read-only' and state the two writes, the substrate-id claim, and who authorizes them (per `torc/docs/integration-boundaries.md`: 'Expose a thin TORC surface after the local contract stabilizes'), or raise the descriptor-conflict finding out of 'Low' and make 'let the plan reference a registered descriptor by id' a precondition of step 3 rather than a documentation note.
- **CR-005 [high] scope_management** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:148) — Priority inversion: three defects that only corrupt an advisory, non-canonical artifact nobody consumes yet are 'Before merge', while the one defect that leaves durable orphan state is demoted. The proposed single-transaction fix for that defect is also incomplete - it cannot cover the filesystem writes in the same function.
  - Evidence: The assessment rates the three history defects 'Before merge' (Codex rated them P2) while itself arguing they are inert: 'no consumer parses the new `boundary` block (nothing breaks) and nothing consumes the carry yet', and 'The asks do not block'. The atomicity defect is filed lower, under 'Before relying on the sizing guarantee': 'when the receiver-derived budget cannot hold the required tier, the registered target descriptor and the fit decision remain stored.' Confirmed in `torc/src/torc/operator.py` `prepare_operator_handoff`, which runs `_register_substrate_once`, then `evaluate_fit`, then `compile_receiver_projection` (which raises `ProjectionBudgetError`) with no surrounding `store.transaction`. The proposed fix - 'Wrap register, fit, compile, activation, and prepare in one immediate transaction' - cannot cover `_export_text_artifact`, which writes to disk with `path.open("x", ...)` before calling `artifact_metadata`; a rolled-back transaction would leave orphan files that make the retry fail on the exclusive-create, and `verify_store` would then report `artifact_missing`/`artifact_hash_mismatch` for rows that did commit.
  - Suggested fix: Re-rank: make the atomicity gap a merge gate alongside (or ahead of) the three provenance defects, since it is the only one that leaves state behind. Extend the correction to the filesystem: write artifacts to a temp name and link/rename after commit, or move `_export_text_artifact` entirely after the transaction and make `artifact_metadata` idempotent. State that `artifact_metadata`'s `with store.connection:` would commit the outer transaction if nested.
- **CR-006 [high] consistency** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:344) — Rollout step 5's recommendation - 'promote the history tier to required' - would make carries uncompilable on exactly the lineages the assessment's own scaling probe measured, because required sections must all fit or compilation fails. The findings table's hedge ('up to a documented cap') is silently dropped in the rollout.
  - Evidence: Step 5: 'If the carry wins on retention at acceptable overhead, promote the history tier to required and plan enforcement.' `torc/src/torc/projections.py` `compile_receiver_projection`: 'used = sum(item["estimated_units"] for item in included); if used > budget["limit"]: raise ProjectionBudgetError(...)' - the required tier is all-or-nothing, confirmed by `torc/tests/test_carry.py` `test_required_continuity_must_fit_the_receiver` (carry_limit 20 raises, 'stored == 0'). The assessment's own cost table records '1,600 revisions | 1,597 unaccounted drops | 903 / 694' included/omitted at a 10,000-word budget - so as a required tier that carry could not compile at all. The findings table does hedge ('make them required up to a documented cap') but step 5 does not.
  - Suggested fix: Restate step 5 as 'promote unaccounted drops to required up to a documented cap, with the remainder reported as a count plus a status pointer' and tie it to the bounding work already identified in the long-lineage finding. Keep one wording across the findings table and the rollout.
- **CR-007 [high] correctness** (torc/src/torc/projections.py:68) — The 'Shaped and sized for optimized fit' row misses a reachable degenerate case that directly refutes the row: the carry floor can consume up to 100 percent of a receiver's declared context limit, and the test suite asserts that as correct behaviour. The assessment only says the floors are 'policy constants without measurement'.
  - Evidence: `receiver_budget`: 'share = context_limit * CARRY_SHARE_PERCENT // 100; limit, source = min(context_limit, max(CARRY_FLOOR[unit], share)), "descriptor_share"' with `CARRY_FLOOR = {"words": 200, "characters": 1200}` (projections.py:33). `torc/tests/test_carry.py` `test_receiver_budget_comes_from_the_descriptor_and_a_cap_only_lowers_it` asserts `receiver_budget({"context_budget": {"limit": 300}})["limit"] == 200` (67 percent of the receiver's whole context) and `{"limit": 120}` -> `120` (100 percent). `torc/docs/p5-receiver-carry.md` describes this as '5 percent of `context_budget.limit`, with a floor of 200 words or 1,200 characters and never more than the limit itself' - so the spec permits it and the assessment's 'Remaining work' cell does not flag it.
  - Suggested fix: Add to the 'Shaped and sized for optimized fit' row and to the history-tier finding: the floor must be capped as a fraction of the context limit (e.g. min(floor, share_ceiling)) or the descriptor must be required to declare `carry_limit` below some threshold; note that a receiver with a 120-word context is currently told the whole context is carry budget, which is the opposite of fitted sizing.
- **CR-008 [medium] correctness** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:155) — The 'smallest correction' for the budget unit - 'count rendered units rather than content units' - is not small. The renderer lives in the module that imports the compiler, and rendering would have to run inside the per-item fitting loop.
  - Evidence: The finding's correction reads: '... and count rendered units rather than content units so the budget means what the receiver reads.' The renderer is `render_carry`/`_projection_lines` in `torc/src/torc/operator.py`, which imports the compiler ('from .projections import compile_receiver_projection, receiver_budget'), so `projections.py` cannot call the renderer without a cycle. Sizing is also used inside the item-level fit loop in `compile_receiver_projection`: 'for item in content: candidate = kept + [item]; if used + estimate_units(candidate, unit) > budget["limit"]: break' - a rendered unit would require rendering a growing candidate per item. `estimate_words` is additionally shared with the frozen P0 compiler, which `projections.py:3-4` says 'must not change'.
  - Suggested fix: Either reclassify this as a design change with its own slice (extract a pure renderer below both modules, or record a separate `rendered_units` measurement alongside the budget without making it the budget), or narrow the correction to 'record rendered size in `receiver-fit` as evidence' and keep the budget unit as the documented deterministic approximation that `torc/docs/project-brief.md` already accepts.
- **CR-009 [medium] guardrail_gap** (torc/src/torc/history.py:86) — The 'smallest correction' for the self-model authorship defect converts a content-derived signal into an unvalidated self-asserted label: any bearer could then clear `restatement_due` with a byte-identical no-op checkpoint, because `event_type` is passed through with no vocabulary check in the captured path.
  - Evidence: The finding's correction: 'Treat a `self_model_revised` event as authorship regardless of content, keeping the `handoff_accepted` exclusion.' Current code (history.py:86-90) keys on content: 'elif current["event_type"] != "handoff_accepted" and (current["canonical_state"]["self_model"] != previous["canonical_state"]["self_model"]): author = current'. `torc/src/torc/operator.py` `checkpoint_operator_lineage` takes 'event_type: str = "checkpoint"' and passes it straight to `store.append_revision(..., event_type=event_type, ...)` with no membership check; `validate_canonical_state` validates state fields only. `torc/tests/test_carry.py` supplies `event_type="self_model_revised"` from the caller. ADR 0004 assigns TORC the duty to 'ask for the revision, attribute it, and record it' - attribution by self-declared label is weaker than attribution by content.
  - Suggested fix: Keep the fix but pair it with a guardrail the assessment does not currently require: validate `event_type` against the vocabulary, and either require a non-empty `self_model` restatement payload distinct from the acceptance-copied role, or record both facts separately (`authored_by` from content, `last_restated_by` from the event) so a verbatim confirmation is visible as a confirmation rather than indistinguishable from authorship. Note the tradeoff in the findings table instead of presenting the change as cost-free.
- **CR-010 [medium] security** (torc/src/torc/verify.py:471) — The assessment frames the relaxed ancestor rule purely as a missing test. The stronger point is that the verifier selects its strictness from a field inside the record it is verifying, so any projection self-labelled `p5-` inherits the latitude - a new class of permitted reference chosen by the artifact, not by the verifier.
  - Evidence: verify.py: 'source_prefixes = [f"{projection[\'source_revision_id\']}:"]; if str(projection["compiler_version"]).startswith("p5-"): # A receiver-fitted projection may cite the source revision's ancestors ...'. The assessment's treatment is confined to coverage: 'Ancestor allowance in `verify` applied to `p0-1` projections too | No forged `p0-1` projection with an ancestor reference' and '`verify` accepts any revision of the lineage as a `p5-1` source | ... the ancestor restriction itself is unverified.' Its 'Verification' improvement row says only 'accepts a `p5-1` source reference to an ancestor of the source revision; `p0-1` keeps the strict rule'. The prefix test is also a wildcard over future compiler names ('p5-'), not an exact `p5-1` match, and `torc/tests/test_carry.py` `test_verify_detects_a_tampered_or_misattributed_carry` forges only a cross-lineage reference, so the in-lineage ancestor restriction is unexercised.
  - Suggested fix: State in v2 that the ancestor allowance is keyed on a record-controlled field and that the gate should be an exact `p5-1` match (or an out-of-band policy table) rather than `startswith("p5-")`; add the two forged-projection tests the assessment already lists, plus one with `compiler_version` set to a fabricated `p5-9` value.
- **CR-011 [medium] risk** (torc/src/torc/verify.py:38) — The cost model is incomplete in a way the lineage-length-only probe could not see: `verify_store` hashes every artifact file in the state directory regardless of the `lineage_id` argument, on every checkpoint, carry, handoff and rollback. The assessment's 'each call' generalisation is also wrong for `status`, which runs no verification at all.
  - Evidence: verify.py `verify_store`: 'artifact_query = "SELECT * FROM artifacts ORDER BY artifact_id"' with no lineage filter, then 'actual = hashlib.sha256(path.read_bytes()).hexdigest()' per row, and 'artifacts_checked': 'SELECT COUNT(*) FROM artifacts'. Every write path calls it via `_require_integrity` in `torc/src/torc/operator.py` ('verification = verify_store(store, lineage_id)'), and `prepare_operator_handoff` adds two artifact files per handoff via `_export_text_artifact`. The assessment's analysis attributes cost only to lineage length and stored projections: 'Every call is linear in lineage length, about 40 to 50 microseconds per revision' and 'The full-store verification that every checkpoint and carry runs first is 55 to 70 percent of each call'. But `operator_lineage_status` does not call `_require_integrity` at all - it goes straight to `lineage` / `head` / `_boundary` - which is consistent with the probe's Status column being roughly half the Checkpoint column (36.7 vs 68.1 ms at 1,600 revisions) and means the proposed mitigation ('the verifier's ancestor check should use a precomputed set') does nothing for status.
  - Suggested fix: Add an artifact-count axis to the scaling probe and a second consequence: artifact verification is unscoped and re-hashes every exported brief and reconstruction template on every write, so cost grows with handoff history independently of lineage length. Correct 'every call'/'each call' to name which entry points verify; note separately that `operator_lineage_status` returns a `boundary` block with no integrity check, unlike checkpoint.
- **CR-012 [medium] correctness** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:300) — The '69 percent metadata' figure that motivates the PR #26 composition measures the stored projection record, but the renderer delivers only section ids and content, so most of that 69 percent is never model-visible and cannot be saved by moving it off the model-visible side.
  - Evidence: The assessment: 'Measured here, 69 percent of a stored P5 carry record is metadata and identifiers rather than section content ... That is precisely what the capsule and control envelope split would move off-model', derived from 'The stored projection record is 4.3 KB, of which section content is 1.3 KB (31 percent)'. `torc/src/torc/operator.py` `_projection_lines` emits only '### {section["section_id"]}' plus 'json.dumps(section["content"], ...)' for included sections and '- `{section["section_id"]}`: {section["reason"]}' for omitted ones - never `source_ref`, `required`, `priority`, `estimated_units`, or the sealed `integrity` block. The same section's replay table already gives the model-visible size directly (2,519 bytes rendered), which is the figure the argument needs.
  - Suggested fix: Recompute the composition against the rendered carry, not the stored record: how many of the 2,519 rendered bytes and 184 rendered words are TORC's three bookkeeping sections plus the revision/activation identifiers that do appear inside section content (`unaccounted-*` last_seen/dropped_at ids, `self-model-provenance`'s three ids, `session-purpose`'s activation id). Keep the 4.3 KB / 31 percent figure only as a storage observation, labelled as such.
- **CR-013 [medium] scope_management** (torc/docs/project-brief.md:54) — The split verdict applies only one of five captured kill criteria. In particular, the candidate restriction the assessment praises arguably satisfies the fit-scoring kill criterion by construction, and the assessment files that as a table cell rather than a verdict item.
  - Evidence: `torc/docs/project-brief.md` lists five kill-or-narrow criteria, including 'Fit scoring cannot outperform explicit operator or Autowork routing decisions' and 'An existing agent runtime already supplies canonical lineage, exclusive authority, target-fit projection, acceptance-gated succession, and provenance with an acceptable adapter surface.' The assessment's verdict addresses one: 'The kill criterion on overhead against measured benefit stays open', and step 5 tests only retention-versus-cost. Meanwhile its own table says 'Fit is a confirmation, not a selection' and the improvement row says `prepare_operator_handoff` 'evaluates fit for the source and the operator-named target only' - confirmed by `torc/src/torc/operator.py`: 'candidate_ids={authority["substrate_id"], target_substrate["substrate_id"]}' followed by 'if fit["selected_substrate_id"] != requested_target: raise HandoffError(...)'. `torc/docs/p5-receiver-carry.md` confirms real selection now survives only in synthetic lanes ('the demo and experiment lanes still evaluate every registered substrate'), and `torc/docs/integration-boundaries.md` says 'The first TORC fit evaluator uses synthetic candidates only.'
  - Suggested fix: In v2, walk all five kill criteria explicitly. State the finding that follows from the captured code: in the only non-synthetic path, fit can no longer outperform an operator routing decision because it can only confirm one, which meets the fit-scoring narrow criterion and argues for narrowing fit to a requirements-expression surface (as `integration-boundaries.md` 'Routing and fit are different' already describes) rather than keeping a scorer.
- **CR-014 [medium] correctness** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:178) — The independent-review bullet about branch roots is internally contradictory against the captured code: a branch root's actor substrate is the source substrate, not the operator, and an operator-authored self-model is precisely the case `restatement_due` exempts. As written, the stated cause cannot produce the stated effect.
  - Evidence: The bullet: 'A branch root is attributed to the source activation's substrate, so a child lineage's first bearer is asked to restate an operator-authored self-model.' `torc/src/torc/history.py` `restatement_due`: 'An operator-authored self-model is the operator's definition and is not due' / 'return author is not None and author != bearer_substrate_id' - a null-substrate author is never due. `torc/src/torc/verify.py` `_verify_branch_revision` requires the branch root's actor to be the source activation with a matching substrate ('_activation_matches_at(source_activation, origin["source_lineage_id"], actor["substrate_id"], created_at) ... or actor["activation_id"] != origin["source_activation_id"]' -> 'branch_source_activation_mismatch'), so the author substrate is a real source substrate. The genuinely operator-authored case is the `lineage_created` root, which the mutation table describes separately: 'the mutant makes a freshly created lineage ask its own bearer to restate.'
  - Suggested fix: Rewrite the bullet as: a branch root is attributed to the source activation's substrate, so the child's first bearer is asked to restate a self-model authored by the parent's substrate - which is intended; and note separately that for `lineage_created` roots the author substrate is null and no ask is raised. Keep the two cases distinct, since they have opposite behaviour and the surviving mutation only covers the null case.
- **CR-015 [medium] consistency** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:151) — 'The history tier ... is fitted whole or not at all' contradicts the assessment's own budget sweep and the captured code. Each drop section is whole-or-nothing; the tier is not. The mis-statement weakens the finding it supports.
  - Evidence: The finding row: 'The history tier is optional, ranks below `receiver-fit` and `self-model-provenance`, and is fitted whole or not at all.' The same assessment measures the opposite: 'budgets of 55 to 68 ... omit both drops with reason `budget`; 69 to 83 carry one drop; 84 is the first budget that carries both.' `torc/src/torc/projections.py` fits each drop independently: 'for index, drop in sorted(enumerate(drops, start=1), ...): ... if not fit_whole(_fitted_section(section_id, source_ref, False, 90, drop, unit)): omit(section_id, source_ref, "budget")'. Whole-or-nothing applies per drop section and to `changes-since-receiver` (a dict, so it gets no `.remainder` item-level treatment, unlike the optional list sections).
  - Suggested fix: Restate as: each `unaccounted-*` section and `changes-since-receiver` are fitted whole or omitted; the tier itself degrades drop by drop, newest first. Note the asymmetry worth fixing - optional list sections get a `.remainder` record but `changes-since-receiver` silently disappears whole - and that 'ranks below' describes code ordering, not the `priority` field.
- **CR-016 [medium] missing_test** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:232) — One of the seven surviving mutations has no entry in the assessment's 'tests to add' list - and it is exactly the branch the top before-merge fix would change, so that fix would land unverified.
  - Evidence: Surviving mutation 3: '`changes-since-receiver` labels an unresolved removal `rolled_back` instead of `unaccounted` | The only assertion on removals covers a `completed` item.' The remediation list names five probes - 'a rollback across a foreign self-model edit, an operator-authored lineage, two drops at different revisions under a tight budget, one `characters` carry, and two forged projections' - mapping to mutations 1, 2, 4, 5, 6 and 7, with nothing for mutation 3. The fix for the first before-merge finding ('let the current unaccounted state override the disposition') changes precisely that expression in `torc/src/torc/history.py:143-145`: 'disposition = dispositions.get(key, "unaccounted" if key in unaccounted else "rolled_back")'. The only captured assertion on `removed` is `torc/tests/test_carry.py` `test_carry_reports_what_changed_while_the_receiver_was_away`: 'removed == {"open_work": [{"item": "Write the export round-trip test", "disposition": "completed"}]}'.
  - Suggested fix: Add a sixth probe to the list: a plain unresolved removal asserted as `disposition: unaccounted` in `changes-since-receiver`, plus one genuine `rollback_applied` removal asserted as `rolled_back`. Make both part of step 1's deliverable so the resolve-restore-drop fix is covered on the branch it edits.
- **CR-017 [medium] docs_gap** (torc/docs/p5-receiver-carry.md:70) — The assessment classifies the never-checkpointed bearer as behaviour that 'follows the spec' and misquotes the spec to do so. The captured spec is internally inconsistent on this point, and the inconsistency is missing from the 'Spec and docs' row it belongs in.
  - Evidence: The independent-review bullet: 'A substrate that bore the lineage from creation but never checkpointed gets no `changes-since-receiver`; the code keys on authored revisions, the spec says "last bore the lineage".' The captured spec says neither thing cleanly: '`changes-since-receiver` lists what was added, removed, and resolved since the receiving substrate last authored a revision. It is absent when the receiver has never borne the lineage or nothing has changed since.' So the definition keys on authoring while the absence clause keys on bearing, and the bore-but-never-authored receiver falls under neither. The code keys on authoring: `torc/src/torc/history.py:114-121` selects 'max((position for position, revision in enumerate(chain) if revision["actor"]["substrate_id"] == substrate_id), default=None)'. The 'Spec and docs' finding row lists three items to state and not this one.
  - Suggested fix: Move this from 'behaviour that follows the spec' to the 'Spec and docs' row as a fourth item: the absence clause must say 'has never authored a revision in this lineage', or the implementation must fall back to the receiver's earliest borne revision. Resolve it together with the `handoff_accepted` fix, since both change which revision becomes the diff base.
- **CR-018 [medium] lifecycle_gap** (torc/docs/decisions/0004-torc-is-always-in-charge.md:28) — ADR 0004's own stated follow-up has now been triggered by this PR, the assessment identifies it as remaining work, and then no rollout step owns it - while a different parent-repository change (the lugos-mcp adapter) does get a step.
  - Evidence: ADR 0004 Consequences: 'The LIR boundary documents in the parent repository describe the older split. They need to be brought into line once TORC's receiver-facing interface is defined.' Its Context records the cause: 'the LIR design in the parent repository took the agent-facing resumption view for itself ... Two components then produced what a receiving agent reads, with no rule for which one governs.' The assessment confirms the trigger has fired and the docs still conflict: 'The parent repository's [LIR boundary](../../docs/lir/boundaries.md) still describes the older split in which LIR renders the agent-facing resumption view.' The five rollout steps cover history fixes, PR #26 reconciliation, the lugos-mcp adapter, the live comparison, and the kill criteria - none covers the LIR boundary reconciliation, even though step 3 is itself a consumer-side change.
  - Suggested fix: Add a rollout step (or fold into step 3) that reconciles the parent LIR boundary document with the now-defined receiver-facing interface, owned by whoever owns the parent repo, with the reconciled boundary text as the retained evidence. If deferral is deliberate because `torc/docs/p5-receiver-carry.md` scopes out 'parent-repository change', say so and name the gate that releases it.
- **CR-019 [medium] consistency** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:30) — The 'more correct' half of the split verdict is stated unconditionally, while the assessment's own before-merge findings show the pre-fix carry asserts self-contradictory dispositions - in that respect less trustworthy than a plain summary, not more.
  - Evidence: 'Assessment in brief': 'The carry is more correct and more explicit about what it omits, and it is more expensive to read.' The first before-merge finding: 'an item completed, restored, then dropped again without a resolution appears in the carry as `completed` in `changes-since-receiver` and as `unaccounted-open_work-3` at the same time'. Reproduced in `torc/src/torc/history.py:125-145`, where `dispositions` is built flat over 'for revision in chain[index + 1 :] for item in revision.get("resolutions") or []' and `dispositions.get(key, ...)` takes precedence over the `unaccounted` membership test. The second finding removes `changes-since-receiver` entirely for a returning bearer, and the third leaves `restatement_due: true` after a genuine restatement.
  - Suggested fix: Condition the verdict: 'after step 1, more correct; as submitted, more explicit about omissions but contradictory about their dispositions.' Carry the same conditioning into the 'Passed with a snapshot for provenance' row, whose claim that the verifier 'checks ancestor references' is about hash-chain validity, not disposition correctness.
- **CR-020 [low] contract_gap** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:130) — Two load-bearing claims cite files absent from the packet, including the one that drives a 'spec should say' recommendation, so they cannot be checked against captured evidence.
  - Evidence: 'Passed with a snapshot for provenance' remaining work rests on `src/torc/handoffs.py#L119-L141`: 'Acceptance still compares head-state fields only, so a successor is accepted without acknowledging the unaccounted drops ... the spec should say that history sections are advisory at acceptance too, or add an optional continuity requirement for them.' `handoffs.py` is not among the 11 captured files, and `operator.py` only calls through to it ('from .handoffs import expected_reconstruction, prepare_handoff, resolve_handoff'). Likewise the Resolutions row cites `src/torc/store.py#L466` for 'writes it only when non-empty' - `store.py` is not captured, though that specific claim is independently supported by `torc/tests/test_carry.py` `test_revision_without_resolutions_keeps_its_recorded_shape` ('assert "resolutions" not in plain').
  - Suggested fix: For v2, either include the acceptance-path code in the evidence set or mark the acceptance claim as unverified-here and cite the test that would establish it. Prefer claims a reader can check from the same artifact set, as the Resolutions row's test-backed claim already does.
- **CR-021 [low] maintainability** (torc/src/torc/projections.py:356) — The P5 compiler's optional-tier order is governed by literal list order, not by the `priority` field that the spec publishes as the rule - unlike the P0 compiler, which sorts. The assessment's 'ranks below' language implies priority-driven shaping that the code does not implement.
  - Evidence: `compile_projection` (P0) sorts: 'for section_id, source_ref, priority, content in sorted(optional_specs, key=lambda item: (-item[2], item[0]))'. `compile_receiver_projection` (P5) does not: 'for section_id, source_ref, priority, content in optional_specs:' - correctness depends on the literal list happening to be ordered 80, 70, 60, 50, 40, 30. `torc/docs/p5-receiver-carry.md` presents the tier table ('`goals` 80, `settled-decisions` 70, `uncertainties` 60, `methods` 50, `artifact-refs` 40, `memory-refs` 30') as the governing order, and the assessment's history-tier finding reasons in those terms ('ranks below `receiver-fit` and `self-model-provenance`').
  - Suggested fix: Note in v2 that the recorded `priority` is descriptive metadata in the P5 path, not the sort key, so a reorder of `optional_specs` silently changes what a tight receiver gets. Smallest correction: reuse the P0 sort in `compile_receiver_projection`, and add one assertion that shaping is invariant to the literal list order.
- **CR-022 [low] consistency** (torc/src/torc/operator.py:1) — The independent review's blanket 'CLI errors are structured' is not supported for the descriptor-conflict path it reports in the same assessment: that path raises a bare `ValueError`, unlike the module's other validation failures.
  - Evidence: `_register_substrate_once` raises 'ValueError(f"substrate already exists with different content: {substrate_id}")', and `load_json_object` raises 'ValueError(f"expected a JSON object: {path}")', while every other validation failure in the module raises `InvalidInputError` or `HandoffError`. The independent review asserts 'CLI errors are structured and create no state directory', and the captured test only exercises the structured cases: `torc/tests/test_carry.py` asserts 'json.loads(output)["error"] == "InvalidInputError"' for a bad resolutions file and a zero budget cap. The descriptor-conflict path - the assessment's own 'Low' finding - is never exercised through the CLI, and `cli.py` is not in the packet.
  - Suggested fix: Narrow the claim to the paths actually probed, and add to the Low finding that the conflict surfaces as a bare `ValueError` rather than a TORC error, so the structured-output contract may not hold for it. A one-line change to raise `InvalidInputError` would settle it.
- **CR-023 [nit] consistency** (torc/docs/pr-25-receiver-fitted-carry-assessment.md:40) — Contested points where the assessment is right against the captured evidence and should be preserved verbatim in v2: the three before-merge reproductions, the single-transaction carry claim, the unit-fidelity criticism, and the step 4 preregistration requirements.
  - Evidence: (1) All three history defects reproduce in captured code: `history.py:125-129` builds `dispositions` flat across 'chain[index + 1 :]' and `:143-145` lets it override `unaccounted`; `:114-121` selects the max position by 'revision["actor"]["substrate_id"] == substrate_id' with no `handoff_accepted` exclusion, so the acceptance revision becomes the base and `:122` 'if index is None or index == len(chain) - 1: return None' suppresses the section; `:86-90` gates authorship on a self_model content difference. (2) The carry's atomicity claim holds: `operator.py` `carry_operator_lineage` wraps register + compile in 'with store.transaction(immediate=True)', and `torc/tests/test_carry.py` `test_required_continuity_must_fit_the_receiver` ('stored == 0', 'registered == ["p5-implementer"]') and `test_carry_changes_no_canonical_or_authority_record` ('before == after' over revisions, lineages, activations, leases, authority_transitions) back it. (3) Unit fidelity is right: 'estimate_words' uses 'r"\b[\w\'-]+\b"' over canonical JSON, and because the character class includes the hyphen, a `revision-<hex>` identifier counts as a single word. (4) Step 4's requirements match `torc/docs/p1b-results.md`: 'a new preregistered series with a real Lugos subsystem transition, more discriminating continuity demands, and retained latency/token evidence.'
  - Suggested fix: Keep these four as-is. Add the one gate p1b-results.md attaches and the assessment's step 4 omits: that retry 'would be a new scope decision, not a continuation of this series', which `torc/docs/p5-receiver-carry.md` echoes as 'needs its own approval' - so step 4 should name the operator approval as its entry condition. <<claude/>>
<!-- LUGOS-SECTION:END -->

## REGION: orchestrator
<!-- LUGOS-SECTION:BEGIN -->
[seq 3 | round 2 | phase synthesis] Synthesis by the orchestrator (Claude Fable 5.1, this session). Adjudication: all 8 codex-sol findings accepted (3 reproduced by script: net-delta change summary, fabricated/malformed resolution passes verify, rollback_applied label on the Python API); all 8 codex-astra findings accepted on content although Autowork's guardrail auto-rejected them for a list-typed evidence field; all 23 claude-opus findings accepted, including the re-ranking of handoff-prepare atomicity to before-merge, the mixed-unit ratio correction, the strawman-baseline restatement of the verdict, the uncapped sizing floor, and the kill-criteria walk; the fusion panel's consensus and disagreements are recorded in the artifact's provenance table. Version 1 preserved in the evidence bundle. The artifact is version 2 of torc/docs/pr-25-receiver-fitted-carry-assessment.md. <<orchestrator/>>
<!-- LUGOS-SECTION:END -->
