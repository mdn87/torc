# Continuation diagnostic readiness

This record supersedes the remaining-gates assessment at recovered commit
`26950f65`. The original reports remain historical evidence. Matt resolved the
run, measurement and cold-baseline decisions in the
[execution amendment](2026-10-21-continuation-execution-amendment.md).

## Work completed before comparative admission

The seven inherited commits are preserved in the integration history. Windows
verification found and corrected newline-dependent replay output, newline
translation in a historical mutant, and an inapplicable POSIX mode assertion.
An editable TORC installation contaminated a negative control by supplying an
absent historical module; verification now uses a dependency-only environment.
CI fetches the historical Git objects required by the task controls. Its Python
3.11 import-boundary test allows the standard library's path-serialization
`urllib.parse` dependency while continuing to reject network/provider imports.

Three disjoint Autowork development jobs produced the accounting importer,
scorer admission and observation collector. Their original outcomes remain
`held_verification_failed`: the scorer job encountered Windows temporary-path
permissions; the other two passed their requested tests but did not pass the
assignment-review stage. These are not reported as successful child signoffs.
The root reviewed and integrated the returned source, adding regression fixes
for overlapping cumulative baselines, wrong hidden-test content despite valid
packet pins, leaking owner/clock labels, and overlapping elapsed intervals.

| Package | Retained Autowork run | Final validation owner |
|---|---|---|
| Reported accounting | `20261021-042559-f82d4f2f2c2e` | Root |
| Frozen scorer admission | `20261021-042610-afde4eb4fbba` | Root |
| Blinded observations | `20261021-042620-144a4d0cf6cb` | Root |

The final local suite passed **915 tests**. Ruff, doctor, demo/verify and the focused
Python 3.11 import check passed. The Mac scorer was requalified against the
inspected native-continuation owner at
`ffda6e1cf6810605f24cf96a638d82bcc00fdae1`; its archive preserves all **74** old
and new model-free process attempts. Positive, negative, protected-runtime,
private-read and network controls passed. Original failed controls remain in
the archive. No qualification invocation was consumed by these scorer checks.

## Evidence that remains limited

`retained_evidence.py` verifies the original qualification archive and all 467
member hashes. It imports six owner completion-counter observations and
reproduces the fork relation **19,569 = 9,240 + 10,329**. Those six completions
are not relabeled as the seven individual successful provider responses
described by the qualification report. Hidden failed requests and retries
remain unknown; input and cache counters are not assumed disjoint. No eligible
whole-task savings endpoint or actual API charge is manufactured.

The observation collector emits ordered action kinds, result statuses and
timing, while retaining raw content and provenance privately. Since that
redaction removes evidence needed to assess investigation, its investigation
classifications and rates remain unassessable. Repeated reads do not become
repeated investigation. Operator active time requires explicit observations.

## Execution ownership

`diagnostic.py` freezes six paired comparisons and two seed intents, with nine
total admissions at most and a zero-paid-API configuration under Matt's $2
ceiling. The intended cache-cold arm is removed. Native warmth describes owned
session state only. The draft manifest continues to grant no launch authority.

A private, hash-pinned operator adapter composes Autowork's existing dispatcher,
native executor, budget, session custody and owned-process APIs. It supplies a
dedicated bounded assignment profile and the qualified narrow scorer callback.
It does not alter the configured controller, provider policy, TORC authority,
or capsule verifier. The profile schema has a minimum model-call ceiling of
eight; the adapter's stricter one-invocation guard rejects additional workers,
reviews and fallbacks before release, and the cohort owner enforces nine total
admissions. No general root-read verifier executes a candidate.

The independent scorer receives an opaque trial identifier, a frozen candidate
and its tests. Terminal worker capture and process-tree absence must be proven
before freezing. Candidate, scoring-packet and hidden-test hashes must agree.
The executed cohort is reported separately in the
[diagnostic results](../../experiments/session-continuation-001/diagnostic-results.md).
Neither apparatus tests nor this small, amended diagnostic establish measured
savings or adoption readiness.

## Staged-plan reconciliation

| Original item | Disposition and evidence |
|---|---|
| A0: Preserve source and owner evidence | Original archive and qualification balance preserved; seven inherited commits retained. |
| A1: Verify and land inherited work | Integration PR preserves history; 915 local tests and platform CI verify the combined source. |
| A2: Reconcile readiness | This dated record replaces the outstanding-gates assessment without deleting historical reports. |
| A3–A4: Accounting and semantics | Pure importer plus retained fork proof; reported counters remain separate from unknown complete provider usage and cache semantics. |
| A5: Frozen scorer admission | Terminal receipts and external pins checked; current isolated controls passed; actual trial candidates scored only through that owner boundary. |
| A6: Observations | Conservative packets retain action order and unknown times; raw provenance stays private. Investigation rate and active operator time remain unavailable. |
| A7–A8: Contexts and launch | Three approved arms, two seeds, frozen inputs/source/policy/runtime/schedule; existing Autowork ownership retained. |
| A9: End-to-end verification | Retained real counter import, refusal tests, historical controls and actual admitted scoring exercise the integration. |
| A10: Bounded execution | Results retain every scheduled disposition, procedure correction and scope failure; no outcome-dependent replacement. |

All three operator decisions in the original plan were answered by the October 21
instruction. No additional user decision is needed to finish this diagnostic.
Experiment B, a larger effectiveness study, complete provider accounting and
adoption remain outside this task. The next study would need its own design and
resource authorization; this result does not silently authorize one.
