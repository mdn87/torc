# Measure whether TORC reduces continuation usage

Status: reviewed and authorized for staged execution on 2026-10-21. The operator
subsequently required collecting eight real tasks across at least three
repositories before proceeding. The fixture gate remains unmet; no comparison
is admitted. See [execution goals and collection results](2026-10-21-efficiency-execution.md).
Review assignments are separate from experiment admissions and do not reuse
the completed cohort's allowance. Retain the existing $2 spending ceiling.

## What we already know

The [completed diagnostic](../../experiments/session-continuation-001/diagnostic-results.md)
contains real CLI-reported token measurements. Saying there is no token-usage
evidence is inaccurate. The unresolved question is whether TORC reduces usage
while preserving task success across representative continuations.

On the one workload where both portable arms passed, TORC reported 834,771 input
tokens versus 578,622 for the plain compiled handoff: **44.27% more**. Output
tokens were 15.23% higher. This describes that pair, not a population effect.
The prepared capsule prompts were also larger in bytes on both workloads:
4,240 versus 3,999 and 4,226 versus 3,893. Bytes are not provider tokens.

The completed experiment compared two representations of operator-authored notes.
It does not establish that TORC avoids replaying a naturally accumulated long
history. Measure a concrete mechanism: smaller useful context at resumption,
followed by less additional context processing without lost requirements.

## Use Claude Code through the existing execution owner

Claude Code 2.1.296 is installed locally. The installed Autowork controller
already has a Claude executor and command builder. The prior cohort used the
already-qualified Codex lane; that was an implementation choice, not a TORC
restriction. Keep execution in Autowork and reporting in TORC.

The current `autowork/campaign/claude_route_execution.py` command uses
`--output-format json` and `--no-session-persistence`. Its
`parse_claude_result` returns only the result string. `executor_adapter.py`
retains redacted stdout, which can contain final accounting, but that is not a
validated per-request ledger.
Capturing and exporting accounting is **new Autowork implementation work**;
it must land and pass qualification before a Claude comparison counts.

The owner must retain structured assistant events and the terminal result,
including usage, `modelUsage`, and `total_cost_usd`, with raw evidence references.
Use a qualified stream capture mode; changing the command alone is insufficient.
Deduplicate repeated message IDs, reconcile request records against terminal
totals, and retain error/partial captures. Estimated dollars are not invoices.
Disable nested model delegation for this pilot; if later enabled, qualify
whole-tree accounting before using it, since top-level usage excludes children.
[CLI contract](https://code.claude.com/docs/en/headless),
[accounting contract](https://code.claude.com/docs/en/agent-sdk/cost-tracking).

Both arms start fresh processes. The control is an ordinary **compiled prompt**
from the interruption record; the treatment is a TORC projection from that same
record. This lane does not support the old `native_warm` resumed-session arm.
There is no inherited session baseline to subtract in this design.

An experimental assignment is one owned process tree, not necessarily one CLI
start. The qualified Claude write lane uses `completion_worker.py` and
`completion_check.py` to run a worker, a model checker, and potentially further
workers. Its current wrapper retains the last worker output and limited checker
evidence, not usage for every call. Capture must therefore occur inside the
completion loop, before an earlier call's output is overwritten.

For this pilot, pin `max_continuations=0` and `max_model_calls=2`: at most one
worker CLI start and one checker CLI start per assignment, under the same shared
600-second deadline. Keep checker policy identical between arms. Include both
calls in strategy usage, since the checker receives the arm's envelope. A checker
request to continue becomes a retained incomplete outcome; no replacement call.
The checker verdict is not the independent task acceptance score. Nested agent
tools are already absent from this route; qualification must keep that invariant.

First compare both strategies on the same Claude model/version, effort, tools,
authentication mode and environment. Do not compare a Claude treatment against
a Codex control and attribute the difference to TORC. Refresh only Claude-specific
execution/capture controls; reuse still-valid independent scorer evidence.

Actual billed-dollar measurement needs a separately implemented and qualified
Autowork API-auth route. The current executor accepts subscription/flat-rate
routes, strips competing API credentials and checks subscription authentication;
changing an environment variable does not enable a paid cohort. That later owner
work must define its cost class, credential injection and auth preflight before
reconciling an isolated experiment workspace/key/time window with Console or the
[Usage and Cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api).
Use billing buckets at their real granularity; do not invent per-trial charges
from a shared bucket. Confirm suitable administrative reporting credentials and
scope without exposing credentials before promising reconciliation. A normal
inference key or subscription login does not establish Usage and Cost API access.
Subscription measurements can answer reported usage without billing access.

## Execution stages and deliverables

| Stage | Work | Concrete completion condition |
|---|---|---|
| 1. Inventory fixtures and access | Before test repairs or scratch setup, inspect retained real interruptions with zero model calls. List candidate task IDs, repository/commit, interruption checkpoint and history references, access, acceptance criteria, and prior development exposure. Check billing-report access only if billing is proposed. | Eight eligible held-out tasks across at least three repositories are evidenced, or the exact shortfall is recorded. Old diagnostic tasks are excluded. A changed sample/design is stated before proceeding; unavailable fixtures are not silently synthesized. |
| 2. Repair setup and prepare context | After fixture feasibility, test required behavior rather than incidental error wording, contain scratch files, equalize dependencies, and validate hidden scoring with good/broken candidates. Develop projection changes only on development fixtures; preserve requirements, holds and provenance. Retain exact prompt bytes/hashes without adding a tokenizer. | Frozen scoring accepts good and rejects broken candidates. Equal source access and deterministic preparation are documented. First-request token measurement waits for stage 3; no claim that prompt bytes equal tokens. |
| 3. Implement and qualify accounting and analysis | Autowork owns stream capture, normalized counters and error evidence; TORC consumes its records under a new analysis-contract version. Add owner tests for cache categories, duplicated IDs, missing terminal events, unsuccessful attempts and termination; add TORC tests for the endpoint, repetition pooling and missingness rules below. Reserve at most two live checks: a fresh single-step and a fresh multi-step call, not native resume. | Landed owner capture and versioned consumer/analyzer changes produce a reproducible ledger. Complete first-request and whole-invocation totals reconcile on development checks, with zero unexplained token discrepancy. Confirm tool adequacy for fixtures; scoring stays independently owned. No comparison is admitted before this gate. |
| 4. Freeze and run a paired benchmark | Freeze the eligible manifest, model/version, tool profile, projections, scoring, endpoint and order schedule. Run eight tasks, two fresh-process arms and two repetitions per task/arm. Randomize each task's first arm using a recorded seed; reverse it for repetition two. | 32 planned comparison invocations, every outcome retained, no outcome-dependent replacement. Retain timestamps and cache categories per call. Report preparation costs separately and include strategy-specific model work in its total. |
| 5. Decide from results | Compare task-level paired usage, acceptance and elapsed time. Publish savings, no detectable improvement, or a regression, with the actual numbers and uncertainty. | A decision about this measured deployment setting; a larger confirmation study only if the result merits it. |

Stage 1 must apply the installed write-lane constraints when selecting fixtures:
Windows execution, Opus/high, literal allowlisted edit files, and a child limited
to Read/Glob/Grep/Edit/Write without shell commands. Record the resolved model
identity, not just the moving `opus` alias. Tasks requiring child-run commands are
ineligible unless the execution owner separately expands and qualifies the lane.
Record the subscription config/auth mode as part of the matched environment,
without copying credentials. Read-only review qualification does not establish
write-lane experimental readiness.

Stage 2 must validate scorer custody for Windows-produced candidates: requalify
the scorer on that host, or qualify transfer with candidate hashes and provenance
to the existing isolated scorer. Prior host evidence alone is insufficient.

Stage 3 owner deliverables include the stream command/preflight contract
(`stream-json` plus required verbosity), terminal/error parsing, and a Claude
`AttemptLedger` entry for every worker/checker CLI start, including killed calls.
Test incremental capture before process termination, preservation of numeric
usage through redaction, and completion-loop aggregation. Do not replace the
current JSON parser with a flag change or count only the last worker.

Stage 1 is a feasibility gate, not a claim that the fixture inventory is already
complete. New history-generation calls must be separately counted;
do not fabricate natural histories or hide preparation expense. The two old
tasks are development fixtures, not held-out effectiveness evidence.

Preparation for this pilot is deterministic: compile both prompts from the same
frozen interruption record, without a preparation model call. Record human
preparation time and shared source acquisition separately. Any later proposal
using model-based preparation must enumerate those calls in a revised allowance
and charge their input to the corresponding strategy before admission.

## Endpoint and decision rule

Primary endpoint: total reported input tokens processed over the entire bounded
continuation strategy across all reported models, paired by task. For each unique
Claude request:

```text
input_total = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
```

These fields are disjoint. Sum each unique request once; do not add terminal
totals again. Preserve categories, model identities and raw provider names. Codex counters require
their own provider mapping: never apply the Claude formula to a provider whose
input counter already includes cache reads.
[Anthropic usage definitions](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#tracking-cache-performance).

Qualify the terminal `modelUsage` mapping against the request ledger. Report
main-loop input separately from whole-invocation input. If auxiliary requests
appear only in terminal aggregates, retain that aggregate coverage explicitly:
use qualified whole-invocation totals once, not the aggregate plus its constituent
messages. Do not invent request-level attribution. An unexplained discrepancy
or incomplete model/category coverage makes the total incomplete. Retain emitted
retry/API-error evidence; hidden provider work remains outside reported coverage.

Verify the main-loop model on every observed request and retain all terminal
model keys. Freeze any expected auxiliary-model policy at qualification. Any
unexpected main-model fallback or auxiliary model is a protocol deviation: keep
the outcome and measured usage, bar the intended-model headline, and report it
separately without replacing the run.

Measure first-request input using the same three-field sum on the first unique
assistant request. It includes system/tool context as well as the handoff; it
does not isolate handoff tokens. Input plus cache creation alone undercounts a
warm first request. Freeze settings, tool/MCP configuration, instruction/memory
loading and environment metadata. Report the paired first-request difference,
attributing it solely to handoff text only if all other delivered context matches.
Retain exact handoff bytes/hashes separately. Add no tokenizer
dependency or standalone token-count API call.

Secondary endpoint: estimated input cost = fresh input times its unit price +
cache writes times their TTL-specific unit prices + cache reads times their unit
price. Also report output cost and estimated total strategy cost. Pin a dated
price table per model, including any request-size tiers and applicable surcharges;
do not hardcode a universal 0.1 cache-read multiplier. If the
write TTL breakdown is unavailable, mark that estimate unresolved rather than
guessing. `total_cost_usd` is a separate CLI estimate to reconcile, not billing.
A paid cohort can additionally report reconciled strategy-level API spend.

Fresh processes do not imply cold caches. Use the three-field primary endpoint
so reclassifying identical input from writes to reads cannot reduce it. Retain
the randomized/counterbalanced schedule and show categories, estimated cost and
elapsed time by order and repetition. Record known TTL and sharing scope; never
claim cold cache from process isolation alone. The API currently isolates caches
by workspace (some other deployments by organization); subscription scope must
be verified or labeled unknown. This pilot measures ordinary shared-cache
operation, not a cold-cache cost effect. Any later cold-cache cohort needs a
verified TTL/isolation protocol, including intervening refreshes.
[Cache sharing and TTL](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#cache-storage-and-sharing).

For each task, sum the two repetitions per arm, including failures, then compute
`1 - sum(TORC) / sum(baseline)`. Report all eight task reductions and their median.
A nonpositive baseline makes the relative endpoint undefined. Use an exact
two-sided sign test against zero improvement at alpha 0.05, removing exact ties
from its binomial denominator and reporting them. At eight non-tied tasks, all
eight must agree for significance. Report min/max as the descriptive range,
without calling it a conventional 95% confidence interval.

Missing terminal coverage or a timeout leaves observed request sums as lower
bounds, never zeros or complete totals. Retain all scheduled tasks in the report.
Any incomplete task prevents the cohort median, cohort sign-test decision
and headline efficiency conclusion; publish complete-pair diagnostics explicitly
labeled as such and the unresolved-task count. A partial TORC total already
exceeding a complete control can show a directional regression, but does not
restore a complete cohort. No outcome-dependent exclusions or replacements.

The existing `continuation_trials.py` v0 contract and `continuation_analysis.py`
use `uncached_processed_token_proxy`, repetition zero and a non-inferiority gate.
They cannot analyze this follow-on unchanged. Stage 3 must add a separately
versioned contract using `total_context_tokens`, Claude non-overlap evidence,
both repetitions and these decision rules. Preserve the frozen old protocol,
manifests and results; this is a new study, not a reinterpretation of that cohort.

The existing 20% improvement target remains a useful candidate target for this
new reported-usage endpoint. Report acceptance out of 16 runs per arm and by task,
plus usage stratified by paired pass/fail outcomes. Require at least the same
total passes, no task with fewer TORC passes than control, and no critical
authority failures before considering a broader confirmation run. A cheap early
failure is not an efficiency success. Advancing requires the median target and
the stated sign-test criterion as well as complete accounting and these quality
gates; it authorizes considering confirmation, not an adoption claim.
If neither arm produces a verified completion, report a failed feasibility pilot,
not a positive efficiency conclusion.
Eight tasks cannot establish the original five-percentage-point non-inferiority
claim. Two repetitions do not create sixteen independent tasks. The pilot has
power only for strongly consistent effects. Choose a
larger confirmation sample from measured variability and a
declared precision/power requirement before making that stronger claim.

Corrected proposed allowance: 32 comparison assignments (8 tasks x 2 arms x 2
repetitions), at most 64 CLI starts including their checkers, plus two qualification
assignments with at most four CLI starts: **34 assignments / 68 CLI starts maximum**.
Each assignment shares a 600-second deadline across its process tree; no owner
retries, continuation starts or outcome-dependent replacements. Each CLI start
can issue multiple provider requests; retain those separately in the usage ledger.
The earlier "32 comparison calls plus two checks" wording understated the owner
loop. Staged execution of this corrected allowance was subsequently authorized;
the fixture and qualification gates still control admission. It does not reset
either old allowance. Model-based preparation
would require a newly enumerated allowance, as above.
Prefer subscription execution; if billing evidence is needed, first check that
the chosen bounded batch can fit within $2, otherwise present its actual budget
requirement before incurring it. CLI estimated-budget controls complement the
owner's limits; they do not certify the final invoice amount.

Future summaries should lead with what was measured: for example, "TORC used X%
less reported input at Y/Z acceptance on this cohort." State the missing billing
or generalization evidence specifically, rather than substituting a blanket
"no evidence" statement for the measured result.
