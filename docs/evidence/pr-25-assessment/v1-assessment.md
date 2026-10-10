# PR #25 assessment: receiver-fitted carry

Status: local architectural, code, and measured assessment, 2026-10-08. This is
a review record, not an acceptance decision or a change to TORC runtime policy.

Reviewed [PR #25](https://github.com/mdn87/torc/pull/25) at commit
a056c61be4dddce8a71fd9cb31f585b70a3b510d, based on
bad615ca6303e88edae2e483b74d544657b8cb9e, which is still the head of master.
The PR is the local checkout, branch agent/p5-receiver-shaped-carry. It
contains two commits and changes 26 files (+1,953 / -60): one new module,
734 production lines by its scope envelope, 615 test lines, a four-revision
fixture, the concept record, ADR 0004, and the P5 specification. GitHub CI
passed on all six OS and Python combinations plus the host-identifier scan.
The Codex reviewer left three P2 comments on the history module; all three
reproduce on this checkout and are itemized below. The companion
[PR #26 assessment](pr-26-continuity-and-batching-assessment.md) covers the
other open branch.

## Assessment in brief

The PR builds the part of TORC that every phase after P0 skipped: the carry
itself. Compiler `p5-1` derives the budget from the receiving substrate's
descriptor, fits optional state item by item, applies one capability rule, and
reads the lineage history behind the head, so work that a bearer dropped from
its summary still reaches the next bearer together with the revision that last
held it and the revision that dropped it. Revisions gain an optional,
hash-stable `resolutions` list. Checkpoint and status responses gain a
non-blocking `boundary` block that asks about unaccounted drops and about
restating a self-model that another substrate wrote. `torc lineage carry`
compiles the carry at session start without creating an activation or
touching a lease.

Replayed here, the mechanism does what the PR says (figures in the next
section). It carries the two dropped items that the P0 compiler and a
compiled-prompt shape built from the same head both lose, and canonical
history stays byte-identical. Two things it does not do. It does not show
that a receiving agent performs better, which the PR states plainly. And it
does not reduce the context cost that decided P1b against TORC: for the same
head, the P5 carry is 73 percent larger than the P0 projection by the
compiler's own unit, and about three times the compiled-prompt shape once
rendered, close to the 3.26 ratio P1b recorded. So "does it work better"
splits. The carry is more correct and more explicit about what it omits, and
it is more expensive to read. The kill criterion on overhead against measured
benefit stays open; the PR makes it testable on a fixture that finally
contains a real omission.

Three defects in history reading, the Codex findings, make the new provenance
contradictory or stale under specific succession patterns. They are local,
have failing-test-sized reproductions, and should be fixed before any consumer
relies on the carry's history sections. None of them touches canonical
history, leases, or authority. An independent review, a 24-mutation coverage
pass, and a scaling probe add a non-atomic handoff preparation, seven
behaviors the suite does not check, and an unbounded ask list on long
lineages; none of those is a merge gate for a local slice, and all are
itemized below.

## Significant improvements

| Area | What changed | Why it matters |
|---|---|---|
| Receiver-derived sizing | [receiver_budget](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/projections.py#L48-L73) uses the descriptor's `carry_limit`, otherwise 5 percent of the context limit with a floor; an operator cap can only lower it. | The receiver, not the operator's plan, decides how much it can take, and the derivation is recorded in the carry's `receiver-fit` section. |
| Shaping by item and capability | [compile_receiver_projection](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/projections.py#L226-L396) fits optional lists item by item, records a `.remainder` omission, and omits `artifact-refs` for a receiver without `repository_read`. | Partial sections survive instead of disappearing whole. Every omission has a reason the operator can read. |
| History reading | [history.py](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py) follows parent links to the lineage root and reports tracked items removed without a resolution, a rollback, or a later restoration. | A head revision is one bearer's summary. Reading the chain is what makes "an omission is not permanent" true, and it is where the fixture evidence comes from. |
| Resolutions | The revision schema adds an optional `resolutions` list; [append_revision](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/store.py#L466) writes it only when non-empty; [validate_resolutions](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L179-L199) rejects a name that is not a real removal before any write. | Existing records keep their hashes. A bearer has a recorded way to say completed, superseded, or withdrawn. |
| Boundary asks | Checkpoint and status responses add a [boundary](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L755-L758) block. The asks never block. | The protocol now asks for the self-model revision that ADR 0004 describes and keeps asking, without turning TORC into an enforcement gate before use provides evidence. |
| Session-start carry | [carry_operator_lineage](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L257-L292) registers the receiver's descriptor and stores one projection in a single transaction. | Observers and returning bearers can be shaped for without a handoff. Verified here: the revision, lineage, activation, lease, and authority-transition tables are identical before and after a carry. |
| Handoff fit scope | [prepare_operator_handoff](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L336-L341) evaluates fit for the source and the operator-named target only. | An observer that only asked for a carry can no longer out-rank the named target and block a handoff. The PR reproduced that failure before fixing it. |
| Verification | [verify](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/verify.py#L471-L481) accepts a `p5-1` source reference to an ancestor of the source revision; `p0-1` keeps the strict rule. Tamper and misattribution tests pass. | History sections can cite the revision that held an item while the hash chain still checks them. |

## What the replay measures

The fixture in `examples/p5-dropped-work` was replayed on macOS with Python
3.14 through the operator API. From the same head revision, the P0 compiler
was run at the same budgets, and the P1 compiled-prompt shape
(`experiment_lanes.materialize_compiled_prompt`) was built the way the P1
source capture builds it. Figures are the compiler's own word estimate unless
stated. The replay script and outputs are in this session's scratchpad, not
in the repository.

| Transport from the same head | Budget units used | What the receiver reads | Dropped work item | Dropped constraint |
|---|---:|---:|---|---|
| P0 projection, budget 100 or 10,000 | 67 words | not rendered | lost | lost |
| P1 compiled-prompt shape | 60 words | 580 bytes | lost | lost |
| P5 carry, small receiver (`carry_limit` 100) | 99 of 100 words | 174 words, 2,435 bytes | carried | carried |
| P5 carry, large receiver (5 percent of 200,000) | 116 of 10,000 words | 184 words, 2,519 bytes | carried | carried |

The small receiver's carry matches the PR text: both drops ahead of optional
state, one settled decision kept with the remainder recorded, uncertainties
and methods omitted for budget, artifact-refs omitted as capability-irrelevant.
The last checkpoint was accepted and asked about both drops; status repeats
the ask; a later checkpoint that restores the constraint and withdraws the
work item clears it.

Why it works better: the compiler reads the chain instead of the head, and
the head is whatever the last bearer chose to keep. No format change could
recover the two items, because neither the P0 projection nor a compiled
prompt ever sees the revision that held them.

Three further measurements qualify the sizing claim:

- **Required floor.** The smallest `carry_limit` that compiles is 55 words,
  and 27 of those are TORC's own sections (`session-purpose` 9,
  `receiver-fit` 8, `self-model-provenance` 10). The history tier has priority
  90 but is not required and is fitted whole or not at all. Swept from 55 to
  100 words: budgets of 55 to 68 carry TORC's bookkeeping plus `goals` and
  `uncertainties` and omit both drops with reason `budget`; 69 to 83 carry one
  drop; 84 is the first budget that carries both. On a tight receiver the
  compiler protects its own metadata, and then smaller head-state sections,
  before the material P5 exists to carry.
- **Unit fidelity.** The budget counts regex words over the canonical JSON of
  each section's content. The receiver reads rendered Markdown with headers
  and pretty-printed JSON: 174 words for a 100-word budget. Identifiers count
  as one word each, and each unaccounted section carries two 32-hex revision
  identifiers that a provider tokenizer would charge at roughly 20 tokens
  apiece. The stored projection record is 4.3 KB, of which section content is
  1.3 KB (31 percent); 25 revision and activation identifiers account for
  about 1 KB. The brief accepts a deterministic approximation, but the unit
  should at least measure what is delivered.
- **Overhead relative to P1b.** [P1b](p1b-results.md) recorded TORC at 3.26
  times the compiled prompt's estimated words while tying every continuity
  measure. The rendered P5 carry is 3.1 times the compiled-prompt shape from
  the same head. P5 changes what is carried, not what carrying costs. The
  cost lives in provenance identifiers and bookkeeping sections, which is the
  exact material PR #26's capsule split moves off the model-visible side.

## Fit with TORC's concept

The [original concept](concepts/0001-torc-original-concept.md) centers on a
continuously revised self carried in a shape and size fitted to the receiving
agent, with a snapshot at each passing for provenance. ADR 0004 assigns that
carry to TORC. ADR 0001 keeps inference and execution outside it.

| Concept requirement | PR contribution | Remaining work |
|---|---|---|
| Continuously self-redefining | A restatement ask whenever the self-model's author differs from the bearer's substrate; a `self_model_revised` checkpoint by the new bearer clears it. | An unchanged restatement is not honored (finding below). Nothing yet revises the self-model; the asks are advisory, as the scope envelope says, and blocking enforcement waits for evidence from use. |
| Shaped and sized for optimized fit | Budget from the descriptor, item-level fitting, one capability rule, omissions with reasons. | The unit counts section content rather than what the receiver reads; the 5 percent share and the floors are policy constants without measurement; the history tier ranks below TORC's own sections. |
| Best available frontier agent | Unchanged by design. The operator handoff now confirms the named target instead of ranking every registered descriptor. | Fit is a confirmation, not a selection. Orca advises the seat; the operator or Autowork authorizes the route. |
| Passed with a snapshot for provenance | Handoff and recovery preparation compile with `p5-1`; the brief carries the drops; the verifier checks ancestor references. | [Acceptance](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/handoffs.py#L119-L141) still compares head-state fields only, so a successor is accepted without acknowledging the unaccounted drops. That is consistent with "asks never block", but the spec should say that history sections are advisory at acceptance too, or add an optional continuity requirement for them. |
| TORC is always in charge (ADR 0004) | A session-start carry owned by TORC; the P0 compiler, demo, and frozen experiment lanes are untouched. | The parent repository's [LIR boundary](../../docs/lir/boundaries.md) still describes the older split in which LIR renders the agent-facing resumption view. The lugos-mcp TORC adapter only exposes `lineage explain`, so no consumer parses the new `boundary` block (nothing breaks) and nothing consumes the carry yet. |

## Findings and disposition

| Priority | Finding and evidence | Smallest correction |
|---|---|---|
| **Before merge** | [changes_since_substrate](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L125-L146) collects every resolution since the receiver's base revision and reuses it for a later removal of the same item. Reproduced: an item completed, restored, then dropped again without a resolution appears in the carry as `completed` in `changes-since-receiver` and as `unaccounted-open_work-3` at the same time. | Scope a disposition to the removal it accounts for, or let the current unaccounted state override the disposition. Add the resolve-restore-drop sequence to `tests/test_carry.py`. |
| **Before merge** | [changes_since_substrate](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L114-L121) treats the `handoff_accepted` revision as work authored by the returning substrate. Reproduced: a successor completes an item with a resolution, hands the lineage back, and the returning bearer's carry has no `changes-since-receiver` section, although the same carry taken one step earlier reported two revisions of change. | Skip `handoff_accepted` revisions when finding the receiver's last authored revision, as `self_model_provenance` already does. |
| **Before merge** | [self_model_provenance](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/history.py#L86-L90) assigns authorship by content change only. Reproduced: a successor that confirms the inherited self-model verbatim with a `self_model_revised` checkpoint stays at `restatement_due: true`; only a textual change clears it. | Treat a `self_model_revised` event as authorship regardless of content, keeping the `handoff_accepted` exclusion. |
| **Before small receivers are real** | The history tier is optional, ranks below `receiver-fit` and `self-model-provenance`, and is fitted whole or not at all. Measured: budgets of 55 to 68 words carry TORC's bookkeeping plus goals and uncertainties and omit both drops; 84 is the first budget that carries both. | Rank unaccounted drops above TORC's own sections, or make them required up to a documented cap, and count rendered units rather than content units so the budget means what the receiver reads. |
| **Before integrating with PR #26** | Both open branches add a different decision numbered 0004. Git merges the two filenames cleanly (checked with merge-tree against c600c0bc), so the conflict is semantic only. | Give the capsule decision a distinct number, state how it implements the receiver-facing P5 decision, and add a P5-projection-to-capsule contract test. |
| **Before relying on the sizing guarantee** | The spec says a carry that cannot fit stores nothing, and [carry_operator_lineage](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L270-L283) honors that in one transaction. [prepare_operator_handoff](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/operator.py#L330-L358) does not: when the receiver-derived budget cannot hold the required tier, the registered target descriptor and the fit decision remain stored. Pre-existing shape, but P5 now derives the budget from the descriptor, so the failure is reachable from a plan that used to succeed. | Wrap register, fit, compile, activation, and prepare in one immediate transaction; `prepare_handoff` and `artifact_metadata` must then join it rather than commit on the connection. |
| **Before session-start carries run on long lineages** | Every carry stores a projection that every later checkpoint and carry re-verifies with a per-projection ancestor prefix walk, and the boundary block returns every open drop. Measured below: superlinear verification after a few stored carries, and 347 KB responses at 1,600 revisions. | Precompute the ancestor set once per verification, bound the reported drops (count plus the newest few, with the rest available through status), and stop building drops that cannot fit. |
| **Low** | A session-start carry registers the receiver's descriptor. A later handoff plan that names the same `substrate_id` with different content fails with a descriptor conflict. The candidate restriction removed the fit veto; this is the residual way an observer carry can block a handoff. | Document that a descriptor is identified by `substrate_id` and must be byte-identical across carry and plan, or let the plan reference a registered descriptor by id. |
| **Spec and docs** | The P5 spec says the asks persist "in every carry"; the carry omits them under budget pressure (above). The spec does not say that acceptance ignores history sections. `unaccounted-*` section ids are stable across budgets, as the code comments say, but shift when an older drop is resolved, so a consumer must key on section and item, not on the id. | State all three in `docs/p5-receiver-carry.md`. |

### Independent review

A second review of the diff, run without sight of the Codex comments or the
findings above, reached the same two top defects (stale disposition in
`changes-since-receiver`, authorship keyed on content rather than on the
`self_model_revised` event) and added the handoff-prepare atomicity gap and the
descriptor-conflict path. It also recorded behavior that follows the spec but
that a consumer should know:

- A rollback to a revision that itself silently dropped an item yields the
  same head state as the drop but an empty `boundary.unaccounted`. The ask is
  path-dependent, because a `rollback_applied` revision accounts for every
  removal it makes.
- A branch root is attributed to the source activation's substrate, so a
  child lineage's first bearer is asked to restate an operator-authored
  self-model.
- A substrate that bore the lineage from creation but never checkpointed gets
  no `changes-since-receiver`; the code keys on authored revisions, the spec
  says "last bore the lineage".
- An observer carry computes `restatement_due` relative to the receiver, not
  the current bearer. That is the intended reading for an observer, and the
  `session-purpose` section says whether the receiver holds authority.

Everything else probed was found correct: the ancestor allowance rejects a
later revision, a branch parent's revision, and a `p0-1` ancestor reference;
resolution cycles, wrong-section and partly invalid resolution lists, and
wrong-activation checkpoints leave the head and the connection untouched;
partial fits in both units keep `estimated_used` equal to the sum of included
sections; CLI errors are structured and create no state directory; the
`boundary` field is not embedded in any closed view schema; and a carry writes
only the projection and substrate tables.

### Test coverage under mutation

The PR reports that four deliberate mutations of the history logic were each
caught. A broader pass on a scratch copy of this checkout applied 24 single
edits across `history.py`, `projections.py`, `verify.py`, `operator.py`, and
`store.py` and ran the full suite after each (two full runs, identical
verdicts). Seventeen were caught, every one by `tests/test_carry.py`. Seven
survived; each was probed and changes observable behavior, so none is an
equivalent mutant.

| Surviving mutation | What the suite does not check |
|---|---|
| Rollback no longer restores the rolled-back revision's self-model authorship | No test rolls back across a self-model edit by a different substrate. |
| `restatement_due` no longer treats an operator-authored (null substrate) self-model as not due | No test asserts the operator-authored case; the mutant makes a freshly created lineage ask its own bearer to restate. |
| `changes-since-receiver` labels an unresolved removal `rolled_back` instead of `unaccounted` | The only assertion on removals covers a `completed` item. |
| History tier fitted oldest drop first instead of newest first | The fixture drops both items at one revision, so order is never exercised. With drops at different revisions and a 70-word budget, the mutant keeps the older drop. |
| `characters` budgets counted as words | No carry is compiled for a `characters` receiver; only `receiver_budget` is tested for that unit. The mutant counts 116 where 1,464 is correct. |
| Ancestor allowance in `verify` applied to `p0-1` projections too | No forged `p0-1` projection with an ancestor reference. |
| `verify` accepts any revision of the lineage as a `p5-1` source | The only forgery cites another lineage; a later revision of the same lineage is never forged, so the ancestor restriction itself is unverified. |

The three before-merge defects above sit exactly in the under-tested region
(`changes_since_substrate` dispositions and `self_model_provenance`
authorship). The tests to add are the probes: a rollback across a foreign
self-model edit, an operator-authored lineage, two drops at different
revisions under a tight budget, one `characters` carry, and two forged
projections (a `p0-1` ancestor reference and a `p5-1` descendant reference).

### Cost against lineage length

A synthetic probe built lineages of 25 to 1,600 revisions in fresh stores,
once with every removal unresolved (drops accumulate) and once with every
removal resolved, and timed the last checkpoint, a carry for each fixture
receiver, and status (median of five runs on an M2 Pro, Python 3.14, SQLite
3.53). Times are milliseconds.

| Revisions | Checkpoint | Carry, large receiver | Status | Unaccounted drops | Large carry: drops included / omitted |
|---:|---:|---:|---:|---:|---:|
| 25 | 2.1 | 2.5 | 0.7 | 22 | 22 / 0 |
| 100 | 5.8 | 7.1 | 2.1 | 97 | 97 / 0 |
| 400 | 18.1 | 24.8 | 9.1 | 397 | 397 / 0 |
| 1,600 | 68.1 | 88.5 | 36.7 | 1,597 | 903 / 694 |

Every call is linear in lineage length, about 40 to 50 microseconds per
revision, and drop count adds little (about 6 microseconds per drop). The
full-store verification that every checkpoint and carry runs first is 55 to
70 percent of each call, and the chain read is most of the rest. That is
acceptable for the slice. Three consequences are not, once the carry is
called at every session start on a long-lived lineage:

- **Stored carries make later verification superlinear.** Each carry persists
  a projection, and every later checkpoint or carry re-verifies all of them.
  At 1,600 revisions each stored large-receiver projection adds about 30 ms to
  every later verification, and a 3 KB projection's cost grows roughly
  quadratically with lineage length because [verify](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/src/torc/verify.py#L471-L481)
  builds the ancestor prefix list per projection and tests membership and
  `startswith` against a growing tuple per section. After three stored
  carries the checkpoint cost 158 ms instead of 67 ms.
- **Boundary responses are unbounded.** The checkpoint and status responses
  return the whole unaccounted list: 347 KB at 1,600 revisions with 1,597
  open drops, against about 1 KB when removals are resolved.
- **Omitted drops are still built and sized.** The large receiver's 10,000-word
  budget fills at about 900 drops; after that every further drop is computed
  and then omitted, so included content plateaus while time keeps growing.

None of these changes the conclusion for the fixture. They do mean that the
"keeps asking in every carry" rule needs a bound before a real lineage runs
for months, and that the verifier's ancestor check should use a precomputed
set rather than a per-projection prefix walk.

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
how to present it so the model-visible text is short and the provenance stays
with TORC. Measured here, 69 percent of a stored P5 carry record is metadata
and identifiers rather than section content, and TORC's own three sections
are a third of the model-facing content. That is precisely what the capsule
and control envelope split would move off-model, and the [PR #26
assessment](pr-26-continuity-and-batching-assessment.md) already names the
composition: verified P5 projection, then task claims, then a compact capsule,
with the control envelope holding P5 source references, omissions, budget
evidence, and authority context.

Two cautions carry over. The capsule builder accepts caller-supplied sections
and does no selection; P5's selection must remain the input, so the capsule
cannot become an independently authored replacement for TORC's carry. And a
critic or native child that receives a capsule derived from a session-start
carry is an observer; authority still moves only through accepted handoff.

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
| 1. Fix history reading | TORC maintainers fix the three succession defects, each with the reproduction as a test, and decide the history-tier rank and the budget unit. | Full suite on Windows and macOS; the three new tests; a recorded decision for rank and unit. |
| 2. Reconcile with PR #26 | Renumber the capsule decision, record how a capsule is derived from a `p5-1` projection, and add the contract test before either branch merges on top of the other. | One verified P5-projection-to-capsule example in the repository. |
| 3. Expose the carry to one real receiver | Extend the lugos-mcp TORC adapter, which today only wraps `lineage explain`, with a read-only `lineage carry` call. The receiver is an observer; Autowork or the operator admits it. | The rendered carry, its projection id, and `authority_transferred: false` in the adapter receipt. |
| 4. Run the deferred live comparison | Preregister, as P1b did, a source-to-target transition on a real Lugos task with at least one real omission. Compare the P5 carry, the P0 projection, and a compiled prompt. Retain provider usage so tokens and cost are measured, not estimated. | Required commitment and constraint retention, unresolved-work accuracy, whether the receiver acted on the carried drop, context delivered in provider tokens, operator corrections. |
| 5. Apply the kill criteria | If the compiled prompt plus history matches the carry's retention at lower cost, narrow P5 to the history reader and the asks. If the carry wins on retention at acceptable overhead, promote the history tier to required and plan enforcement. | The decision, recorded against `docs/project-brief.md`, before any provider integration. |

Native subagents and interactive children remain execution-layer facilities.
They can receive a session-start carry as observers under the harness and
project policy that admits them. A child becomes the authoritative bearer only
through TORC's accepted handoff or explicit branch. PR #25 gives such a child
better material to start from; it gives no component a new way to grant
authority.
