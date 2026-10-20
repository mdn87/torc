# Session-handoff final decisions — October 19, 2026

October 20 continuation: the next bounded step is
[offline comparison preparation](2026-10-20-continuation-trial-preparation.md).
It adds pinned Experiment A pilot drafts and all-trial analysis, while leaving
live admission with the existing execution owner. Draft manifests and synthetic
confidence arithmetic cannot establish savings, quality or rollout eligibility.
The [apparatus contract](../experiments/session-continuation-001/comparison-preparation.md)
records the fixed missingness, pairing and uncertainty rules. Experiment B,
live-lane qualification and API billing remain subsequent work.

Scope: final disposition of rounds 3 and 4 against TORC `255acea`, followed by
the bounded first implementation. The operator's current instruction authorizes
implementation after the decision; the pasted review-only prompt describes the
reviewer role, not a prohibition on the root implementing the chosen slice.

| Round 3 or 4 addition | Decision | Reason |
|---|---|---|
| Quiescence distinct from transcript coverage | reduce | Keep the distinction as an explicit unknown; transcript completion cannot establish settled effects. |
| Process-group termination and wait-for-every-member rule | cut | The collector does not own process lifecycle and grants no absence-based retry. |
| Fake sink with atomic effect/terminal receipt semantics | cut | A transactional sink would test a new execution protocol rather than context efficiency. |
| Invocation ledger before dispatch | cut | No tool dispatch or automatic recovery remains in the slice. |
| Never grant live `retry_safe` | keep | Extend the restriction to all adapter reports, including synthetic fixtures. |
| Exception status with occurrence scope and incarnation expiry | reduce | Record operator overrides as experimental interventions without changing evidence or installing a capability-release mechanism. |
| Separate payload fingerprint from logical occurrence | keep | Exact payload equality does not identify intent, repeated work or permission. |
| Predeclared occurrence/payload schedule | cut | It introduces execution ownership and an answer key unrelated to realistic context evaluation. |
| Typed mutating fixture tool schemas | cut | The retained schema is for observations; there are no mutating fixture tools to authorize. |
| Alias/default rejection before dispatch | reduce | Document exact-byte fingerprint limits; no semantic-equivalence or alias-based retry claim is made. |
| Occurrence-keyed replay guard | cut | A report describes evidence and cannot enforce one-use execution. |
| Execution journal: eligible, claimed, dispatched, resolved | cut | This is the transaction machinery that violates the intended ownership boundary. |
| Exclusive retry claims and simultaneous-claim handling | cut | No retry permission exists to allocate or consume. |
| Dispatch markers and resolution records | cut | No new execution lifecycle is retained. |
| Second-crash re-entry by attempt ID | reduce | Missing outcome evidence remains uncertain after any number of interruptions. |
| Supersedes chain plus locked latest pointer | cut | Explicit immutable artifact references suffice; no durable freshness pointer or claim state is needed. |
| Replay protection carried across handoff | cut | Existing TORC handoff governs authority, not tool-effect replay. |
| P3 read-only reconstruction under separate assignment | keep | Existing assignment and lineage authorities remain independent and are reused unchanged. |
| Acceptance-specific R0→R1 rebind protocol | reduce | Acceptance makes old bindings stale; collect fresh observations and preserve the old report without transporting permissions. |
| Per-mutating-call head check and checkpoint rebind | cut | The adapter has no mutating-tool surface; ordinary TORC authority checks remain with their existing owners. |
| Per-tool file/delete pre/post crash recovery | reduce | Current bytes cannot establish historical execution or non-execution; ambiguous effects stay held. |
| Committed/rejected/missing sink receipt release branches | cut | No receipt or absence predicate automatically releases a retry. |
| Whole claim publication via hard link | cut | Claims are removed; immutable data publication may independently use the same OS primitive without retirement or permission semantics. |
| Unparseable claim identity recovery | cut | There are no claim files or synthesized attempt IDs. Malformed observation/artifact handling remains. |
| Predecessor eligibility, terminal applied/skipped states | cut | No occurrence schedule or scheduler remains. |
| Nonterminal no-effect and operator-only skip | cut | Both depend on an execution state machine removed from scope. |
| Out-of-order and simultaneous adjacent execution gates | cut | Replace protocol gates with ordinary parser/report tests, not a different ordering protocol. |
| Tier 1 answer-key warning | keep | Scripted fixtures demonstrate mechanisms only and cannot establish realistic task quality or savings. |
| Tier 2 realistic disposable coding tasks | reduce | Retain realistic tasks and blinded scoring without an alternate occurrence-allocation protocol. |
| Minted new occurrences and intended-repeat override | cut | The collector does not authorize new logical work or try to infer model intent. |
| Freeze model-visible information and refusal feedback | reduce | Freeze all context, tool feedback and assistance; there is no schedule oracle or retry refusal channel. |
| Proposal-error and intended-repeat measurements | reduce | Score unsafe proposals, actual repeats, failures and human interventions without occurrence machinery. |
| Realistic-only adoption and pilot gate | keep | Mechanical demonstrations cannot justify default coding-workflow use. |
| Expanded retry/kill-point fixture battery | reduce | Keep capture and publication interruption tests plus counterexamples; remove gates requiring the discarded coordinator. |

**Round 5, finding 1 — Tier 2 A→B→A attribution.** Required by the accepted
threat model: v4 could infer `no_effect` from final bytes even after an effect
had been overwritten. The final plan removes pre/post-based historical
classification and automatic retry. The retained report cannot infer that a
write never happened from current bytes. Overlap recovery is outside scope;
its uncertainty remains visible and acceptable because nothing executes from
the report.

**Round 5, finding 2 — stale resolver deletes a newer claim; pre-intent crash.**
The finding is valid against the discarded journal. Claims, retirement,
allocation and resolver re-entry are cut, so there is no path for stale evidence
to delete a new retry permission. Content-addressed artifact publication never
recycles its destination or authorizes execution. Missing intent/outcome evidence
does not generate invented pre-state or release a retry.

**Round 5, finding 3 — delayed ingress after apparent quiescence.** Required
by the accepted threat model: accepted-request receipts do not fence requests
still in transit. The plan cuts the sink quiescence predicate and makes absent
effect evidence insufficient for retry. Live ingress fencing is out of scope,
not solved. Leaving it open is acceptable for a read-only report with no safe-to-
resume or exactly-once guarantee; it would not be acceptable for a future retry
executor.

Citation checks and corrections:

- `src/torc/experiment_runs.py::write_canonical_artifact` uses a shared
  per-target temporary and `os.replace`; it does not serialize writers, enforce
  immutability, or fsync the parent directory. The new publisher leaves it
  unchanged and reuses only canonical serialization.
- `_unchanged` is in `tests/test_p5_capsule_adapter.py`, and checks both the
  SQLite dump and every state-directory file. The new tests reuse it.
- `canonical_json` in `src/torc/canonical.py` supplies deterministic JSON
  formatting, not path or operation semantic equivalence.
- `src/torc/p5_capsules.py::{derive,verify}` establishes faithful rendering and
  expected-hash binding, not freshness, effect completion or tool permission.
- `docs/p3-recovery.md` explicitly excludes restoration of process, tool and
  workspace state; acceptance appends a new `handoff_accepted` revision.
- The Commands paragraph in `docs/p5-receiver-carry.md` still says `p5-1` at
  the baseline. `src/torc/operator.py` uses `compile_receiver_projection`, whose
  current version in `src/torc/projections.py` is `p5-2`. The plan cites the
  implementation for new projections and retains support for stored `p5-1`.
- The 2.9–3.1 comparison in
  `docs/pr-25-receiver-fitted-carry-assessment.md` is delivered words on one
  fixture, not provider tokens or whole-task savings. Its baseline lacks equal
  history access.
- Mutable `master` links and unverified external-hook behavior were removed as
  support for implementation guarantees. No line-range claims are necessary.

The exact requested Autowork command completed as run
`20261020-030514-cross-review` with reviewer `codex-astra`. Its response states
that it reviewed only the captured authoring prompt, not the referenced plans,
repository citations or first-PR scope. Its zero findings therefore provide no
substantive sign-off for this implementation. The root checked the inputs and
made the decisions above; no further review round is scheduled.
