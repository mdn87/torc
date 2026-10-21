# Review of the continuation efficiency plan

The [revised plan](2026-10-21-measured-efficiency-plan.md) incorporates the
operator-supplied review and two completed, read-only Autowork reviews. This
records a plan review, not experiment readiness or a new measurement result.

## Review provenance

| Dimension | Autowork run | Status | Selected route / model |
|---|---|---|---|
| Measurement validity | `20261021-061342-e16a92c62933` | `completed` | `claude:deep-review` / `opus` |
| Execution feasibility | `20261021-061710-cedec71c5c9f` | `completed` | `claude:deep-review` / `opus` |

Both assignments used the subscription review lane, retained no worktree and
changed no repository files. The root verified the material code findings and
integrated the corrections. No benchmark, accounting qualification, paid API
trial or additional reviewer assignment ran for this review.

The dimensional roundtable is `torc-efficiency-20261021-v2`. The root relayed
each answer verbatim with Autowork provenance and supplied the synthesis. The
original `torc-efficiency-20261021` halted when its one-round cap encountered
the synthesis phase. That record remains intact; v2 reuses the same answers
under a two-phase allowance, without new reviewer calls. Full local records are
under `.torc/takeover-evidence/.roundtable/sessions/`, with request snapshots and
normalized review results beside that directory.

## Findings and disposition

| Finding | Disposition in the revised plan |
|---|---|
| Claude input/cache semantics differ from Codex | Primary input sums Claude's three disjoint fields; keep provider-specific mappings and separate price-weighted estimates. The old measured result remains unchanged. The proposed Codex uncached subtraction is not promoted to verified evidence while its retained overlap semantics remain unverified. |
| Cache warming biases uncached-only comparisons | Use total processed input, randomized first order and reversed second order; publish category/order effects. Shared-cache behavior is accepted. API workspace isolation does not prove subscription cache scope. |
| Turn-one usage was described too strongly | Include cache reads and describe the whole first request. A paired difference isolates the handoff only with evidence that all other delivered context matches. No tokenizer dependency. |
| Fixture feasibility came too late | Inventory eight held-out interruptions across three repositories first, applying the actual write-lane constraints. No fixture availability is claimed by this review. |
| Existing analyzer implements the old protocol | Add a new versioned TORC analysis contract for total context, pooled repetitions and the declared missingness/statistical rules. Preserve old manifests and analysis. |
| Final Claude output is not whole-strategy accounting | Capture every worker and checker call inside Autowork's completion loop before outputs are overwritten. Retained redacted stdout is useful raw evidence, not a normalized ledger. |
| Extra models, incomplete captures and early failure can distort results | Qualify model/category coverage, retain lower bounds, block cohort conclusions when accounting is incomplete, declare model deviations and report paired acceptance. Checker work counts in strategy usage; its verdict is not the independent score. |
| The proposed call allowance omitted completion checks | Pin zero continuations and two CLI starts per assignment. The corrected proposal is 34 assignments / at most 68 CLI starts including qualification, with a shared 600-second deadline per assignment. It is not a new admission. |
| Existing route cannot use API billing credentials | A paid cohort requires a new, qualified Autowork API-auth route plus suitable billing-report access. The current subscription lane strips competing API credentials. The $2 ceiling remains unchanged. |
| Scorer and fixture environment may differ from prior evidence | Inventory against Windows, Opus/high, literal file scopes and no child shell. Qualify independent scoring or candidate transfer for that environment. |

The source checks covered TORC's `continuation_trials.py`,
`continuation_analysis.py` and `continuation_usage.py`, and the installed
Autowork controller's Claude route, executor adapter, completion loop, completion
worker and authentication code. Official usage references are linked in the plan.
Claims about auxiliary model behavior require qualification evidence; the review
does not establish which auxiliary requests this CLI version emits.

## Remaining execution work

1. **TORC, no model calls:** inventory fixtures, their prior exposure and permitted
   source access against the actual execution constraints; record any shortfall.
2. **TORC:** freeze deterministic prompt preparation and independent scoring;
   qualify candidate custody across the chosen execution/scoring environments.
3. **Autowork:** implement and test per-call stream accounting, completion-loop
   capture, normalized ledger export and bounded termination.
4. **TORC:** implement the separately versioned consumer and analyzer; test cache
   semantics, both repetitions, deviations and incomplete coverage.
5. **Execution owner:** qualify the combined path on development tasks, then
   freeze the cohort and obtain admission for its explicitly counted allowance.
6. **Only if actual billed dollars are needed:** qualify an API-auth route and
   confirm administrative billing-report access and a batch fitting the $2 cap.

Fixture discovery, setup, code changes and offline tests can proceed through
bounded autonomous assignments. A fixture shortfall may require another declared
design; unavailable billing access or a higher paid budget requires operator
input only if that optional billed cohort is pursued. This review does not claim
those prerequisites have been completed.
