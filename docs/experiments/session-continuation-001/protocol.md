# Session continuation 001 — preregistration skeleton

Status: **not ready for model trials**. This file establishes the accounting
and comparison contract for the first implementation. It does not authorize a
provider run or claim measured token savings. Complete and hash-pin the trial
manifest before observing any model results. A completed manifest, not this
skeleton, is the preregistration.

The [offline comparison apparatus](comparison-preparation.md) now pins draft
inputs and analyzes supplied all-trial evidence. Its synthetic
[replay report](comparison-report.json) does not complete this preregistration
or authorize a live run.

## Questions and frozen rules

Experiment A compares native warm/cold continuation, a deterministic compiled
prompt with equivalent history access, and TORC's verified capsule. Every arm
gets the same recovery assistance, permitted evidence, tools and intervention
rules. Arm-specific context bindings necessarily differ.

Experiment B holds one context strategy fixed and ablates the reconciliation
report. Both arms retain the same sandbox and execution restrictions. Use only
disposable local scenarios; no actual sends, deploys or external mutations.

Mechanical fixtures validate capture/report behavior only. Realistic tasks
have no exact-payload schedule, occurrence protocol, or answer-checking tool
gate. A scorer blinded to the arm evaluates artifacts, tests and constraints.
No adapter provides exactly-once retry, effect quiescence or liveness.

The expected local lane is subscription-metered Claude Code, but the actual
lane, model and telemetry contract must be recorded before trials. API cost
is unavailable on a subscription-only lane. Do not translate rate limits into
dollars. Use the separately named uncached-processed token proxy only after
the lane's counter semantics are verified:

```text
proxy = input_tokens + cache_write_input_tokens + output_tokens
```

Report `cached_input_tokens` alongside it. Cache reads are omitted from this
proxy, not free or unprocessed. Any missing summand produces a missing result.
For incompatible or unknown semantics, the proxy is unavailable. Report total
context processed only when input/cache-read/cache-write non-overlap is proven.
Use `torc.experiment_usage.normalize_usage` and retain raw source counters.

The API lane, if selected with actual billing evidence, uses whole-task API
cost. Pin prices, date, model and cache terms. The candidate meaningful savings
threshold is **20% median reduction** in the eligible cold-resume stratum
against the strongest safe baseline. This is a decision threshold, not an
observed result.

The candidate verified-success non-inferiority margin is **5 absolute
percentage points**. Before trials, freeze the margin with the sample count
and confidence procedure. Passing requires the prespecified lower confidence
bound for TORC minus baseline success to exceed `-0.05`, not merely a favorable
point estimate. An underpowered pilot remains inconclusive. Critical authority
violations, duplicate non-idempotent actions and false verified completion
have a zero observed-failure adoption gate.

## Whole-task and all-attempt accounting

Each workload/arm record retains every attempted start and every model request
through independently verified completion or declared failure. Charge failed
reconstruction, retries, retrieval, reconciliation, root/subagent work, synthesis,
model-authored notes and fallback to the originating strategy. A fallback pays
for both paths. Keep deterministic local CPU time and human inspection time
as separate measurements; do not invent token costs for them.

Request IDs and exporter semantics must distinguish incremental counters from
cumulative updates. Deduplicate observations of a request; never add a final
cumulative total to its component deltas. Do not treat absent counters as zero.
Keep the raw evidence reference and normalization version for every aggregate.

Only an arm-independent setup failure before delivery of arm-specific context
and before an arm-specific model request can be excluded from the endpoint.
Every exclusion is listed with its reason. Failures after delivery stay in the
arm's failure table and cost accounting. Missing usage stays missing; freeze a
maximum missingness and sensitivity rule before trials. Do not calculate a
headline savings result from whichever successful subset happens to have usage.

## Values that must be filled and pinned before trials

| Field | Required value |
|---|---|
| Execution lane | Provider, model/version, effort, harness/adapter version, billing mode, resource authorization and cap |
| Usage semantics | Exporter version, primary counter definitions, incremental/cumulative treatment, source documentation or validation evidence |
| Workloads | Exact artifacts and hashes, source, counts in each warm/cold/interrupted stratum |
| Repetitions | Paired repetition count, seeds, arm-order permutations, stopping rule |
| Context | Compiler version, capsule budgets, common instructions, history and retrieval access |
| Assistance | Exact report bytes, tool surface, operator decision rules, visible feedback |
| Scoring | Hidden tests, rubric, blinded scorer procedure and critical-failure definitions |
| Inference | Final non-inferiority margin, sample-size rationale, confidence method, multiplicity treatment |
| Cost | Primary endpoint, candidate threshold disposition, API price evidence if applicable, whole-task boundaries |
| Missing data | Maximum missingness, sensitivity analysis and setup-exclusion procedure |
| Analysis | Script version/hash, output schema, raw evidence retention and analysis freeze date |

No field in this table may be resolved after inspecting comparative outcomes.
Changes produce a new protocol version and separately reported cohort.

## Required result columns

Record workload, stratum, arm, repetition, attempt IDs, completion/failure,
verified task score, violated constraints, false verification, duplicate effects,
unsafe proposals, operator interventions, elapsed time, request count, raw and
normalized counters, token proxy or reason unavailable, cached inputs, actual
API cost or reason unavailable, fallback cost, missingness and exclusion reason.
Rendered prompt bytes/words are diagnostic columns, never provider token totals.

Report negative trials, outliers and uncertainty intervals. Separate mechanical
tests from realistic tasks, warm from cold, and ordinary outcomes from operator
overrides. Experiment A alone supports capsule claims; B supports reporting
claims. Adoption needs realistic evidence meeting both savings and quality
criteria. A negative or inconclusive result is acceptable.
