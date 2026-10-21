# Offline comparison preparation and analysis

This batch continues `9d96039` with an offline Experiment A pilot preparer,
all-trial analyzer and deterministic replay. It does **not** complete the live
preregistration or launch models. There is no measurement of agent resumption,
repeated investigation, elapsed time or token savings yet. Experiment B remains
separate future work; this batch cannot support a reconciliation-assistance claim.

## Reproduce

From the repository root in the development environment:

```sh
comparison_root=$(mktemp -d)
PYTHONPATH=src python3 docs/experiments/session-continuation-001/comparison.py demo \
  --output-dir "$comparison_root" > "$comparison_root/summary.json"
diff -u docs/experiments/session-continuation-001/comparison-report.json \
  "$comparison_root/summary.json"
```

The [retained report](comparison-report.json) names the plan, externally pinned
manifest, synthetic input results and complete analyses. Publication uses
content-addressed, create-once artifacts; no mutable latest pointer is added.
The manifest pins preparation, analysis, accounting and normalization sources.
Each reference contains an asset-root-relative path and the exact byte hash.
The manifest ID hashes its canonical payload; artifact filenames hash their
serialized bytes including the publisher's newline. These are different hashes.

The replay reuses the previous [capsule integration replay](offline-milestone.md).
It derives and verifies an actual P5 capsule against disposable state without
changing authority or the capsule verifier. The capsule context file contains
the exact verified canonical bytes without an added newline. The comparison
prompt deterministically includes the full fixture history. Both have the same
history-access declaration and recovery report. These are mechanics inputs,
not qualified native contexts or realistic continuation tasks.

Two workload IDs deliberately duplicate that one fixture. The independent
sampling assumption does **not** hold for this demonstration. Scores, candidate
hashes and counters are synthetic; no independent scorer or worker ran. The
numbers below exercise the formulas and cannot estimate population performance.

| Replay case | Observed attempts | Headline savings arithmetic | Result |
|---|---:|---|---|
| Complete synthetic inputs | 24, including 8 fallbacks | 0%, equal fixture usage | No quality or adoption pass |
| Missing scheduled trial | 21 known; total unknown | unavailable | Missing row retained |
| Missing usage in a repeated run | 24 | unavailable | Complete primary pairs cannot hide the gap |
| False completion claim | 24 | 0%, equal fixture usage | One critical failure retained |

Elapsed time, investigation count and operator time stay null in the replay.
The full analysis retains attempts, raw observations, normalized counters,
cached inputs, setup exclusions, costs and their unavailable reasons from the
existing accounting owner. Cumulative snapshots and their duplicates are not
summed again by the analyzer. Accounting evidence stays attached even when
independent scoring contradicts a completion claim.

## Preparation contract

`torc.continuation_trials.prepare_manifest(plan, asset_root)` generates a
deterministic schedule from the cohort, integer seed, workload and repetition.
Each workload/repetition is a block; hash ordering permutes blocks and arms
before results exist. Every arm has the common instructions, execution contract,
history/workspace references and assistance report; context bytes differ by arm.
Pin compiler versions, budgets, tool restrictions, history access and observed
cache-state rules in those referenced contracts. A declared stratum alone does
not prove a provider's cache state.

The plan must have unique workload IDs, all scheduled contexts, finite resource
limits and enough arm-run budget for the complete schedule. Hidden scoring
assets cannot share paths or hashes with any worker-visible asset, even under
another workload. Paths cannot escape the asset root. Verification requires the
caller-held manifest ID and rejects changed files, sources, contract or schedule.
The hashes detect substitution; they do not authenticate evidence owners.

`scoring_packet` emits only the opaque trial ID, candidate hash and scoring
references. Keep the manifest, arm identity, context and usage logs away from
the scorer. A receipt must bind the candidate hash and trial ID, identify an
independent blinded scorer, and supply a score and evidence reference. The
analyzer checks that binding and shape, not whether the producer was actually
independent. Operational isolation and executable hidden scoring still need
qualification before a live cohort.

This version supports **subscription proxy pilot drafts only**. It always emits
`state: draft`, `launch_authorized: false`; `require_ready=True` rejects even if
all reference fields are supplied. A capsule receipt file does not replace
the existing verifier, and a resource-authorization reference does not admit
work. Live admission belongs to the existing execution owner. No provider
client, API cost adapter, hook, retry coordinator or service was added.

The public offline command paths are:

```sh
PYTHONPATH=src python3 docs/experiments/session-continuation-001/comparison.py prepare \
  --plan <plan.json> --asset-root <asset-root> --output-dir <derived-output>
PYTHONPATH=src python3 docs/experiments/session-continuation-001/comparison.py analyze \
  --manifest <manifest.json> --expected-manifest-id <externally-retained-id> \
  --results <results.json> --asset-root <asset-root> --output-dir <derived-output>
```

The demo's generated `trial-plan` and `trial-results` files are complete format
examples. Results files contain a `results` list. Each row binds `manifest_id`,
`trial_id`, `candidate_sha256`, the existing `accounting_input`, optional `score`,
and optional `metrics`. A failed run without a candidate can use null and a
failure score; verified success requires a candidate hash. Absent accounting,
scores and metrics remain absent. Duplicate/unknown trials, mismatched arm/task
identities, invalid scores and nonfinite or negative metrics reject.

## Frozen analysis rules

The primary unit is a workload, using repetition zero as fixed before outcomes.
Other repetitions remain in raw output and completeness/critical-failure gates;
they do not inflate independent sample size. Every declared baseline gets its
own comparison within each stratum. A later operator cannot select the easiest
baseline or omit unsuccessful trials. Full adoption would additionally need
the strongest fair native baseline and representative realistic workloads.

The subscription endpoint remains `input + cache_write + output`, with cached
input reported separately. Every attempted start and fallback belongs to its
originating arm. Unverified semantics or missing counters propagate from
`account_task`. Any missing scheduled trial, missing proxy or whole-trial setup
exclusion in a comparison makes its headline savings unavailable, including
gaps in nonprimary repetitions. A zero baseline proxy also prevents a ratio.
Complete-pair medians remain explicitly diagnostic. Missing costs have no
finite worst-case bound without an externally justified cost ceiling; none is
invented. Attempt totals are unknown when an entire row or its accounting is
missing; known attempt counts are reported separately.

Only accounting-approved setup exclusions are accepted. An excluded setup
followed by execution retains the whole executed trial. A completely excluded
trial is listed and prevents a complete primary endpoint; this version never
automatically replaces it. All independently scored failures remain in cost
arithmetic. Missing scores prevent quality inference and get worst/best paired
point sensitivity assignments, not fabricated successes or failures.

For success, define a gain as TORC passing while baseline fails, and a loss as
the reverse. The bound is `lower(P(gain)) - upper(P(loss))`, using exact
one-sided Clopper–Pearson bounds with half the comparison error allowance per
tail. A union bound makes this conservative without assuming gains and losses
are independent. Divide the familywise 0.05 allowance across every declared
baseline/stratum comparison. The individual exact-binomial method follows
[NIST's exact binomial confidence bounds](https://itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm);
the paired gain/loss combination is the explicit method chosen here.

Non-inferiority passes only if the lower bound exceeds `-0.05`. With two
hypothetically independent all-tied pairs, this arithmetic gives approximately
`-0.842`, hence no pass. The replay's duplicated fixtures do not even warrant
that population interpretation. Savings uncertainty uses an exact binomial
order-statistic median interval; too few pairs produce unbounded/null ends,
never a zero-width interval manufactured from repeated executions. Both kinds
of interval assume independent representative workload sampling. The 20%
median savings threshold remains a decision target, not an observed gain.

`criteria_met` and `adoption_authorized` are always false in this draft-only
version. Scoring, counter semantics and metric collection are assertions by
their evidence owners; the offline analyzer cannot attest them or establish
that all actual requests were exported.

## Remaining live work and scope disposition

Select an explicit lane/resource ceiling, then qualify its existing harness,
native-state behavior, isolation and whole-task telemetry. Construct realistic
continuation workloads, equal-access baseline inputs and executable hidden
scoring with a defined repeated-investigation rubric. Freeze lane versions,
sample-size rationale, stopping limits and the complete protocol before any
comparative outputs. Only then may the authorized execution owner admit a
bounded pilot. A small pilot can validate collection but is likely inconclusive
on the five-point quality margin. Experiment B and API billing remain separate.

The lead implemented and verified this batch. The previously unqualified
Autowork dispatch surface was not retried or repaired, and no alternate child
was launched. This avoids treating a generic child session as a qualified
worker. Parent files, canonical authority, capsule-verifier semantics and the
unrelated untracked planning draft were preserved.

Validation is recorded after fresh checks in the
[milestone envelope](../../plans/continuation-trial-preparation-scope.json).
The replay test runs twice in independent output directories, compares exact
retained report bytes, verifies artifact hashes and exercises both public CLI
paths. Focused tests cover missing primary/repeated trials, missing scores and
usage, exclusions, false completion, source/asset substitution, scoring leakage,
duplicate rows, metrics, paired bounds and baseline multiplicity.

Recorded on macOS/Python 3.14: **847 tests passed**, Ruff passed, doctor found
no missing paths, and demo/verify validated seven artifacts without errors.
The Lugos quick audit passed all three checks. Other operating systems and
live execution lanes were not qualified by this batch.
