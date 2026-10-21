# Measure whether TORC reduces continuation usage

Status: proposed follow-on experiment. This plan does not launch workers or
reuse the completed cohort's allowance. Matt accepts adding billing evidence
if needed; retain the existing $2 spending ceiling until explicitly changed.

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

The current experiment compares two representations of operator-authored notes.
It does not establish that TORC avoids replaying a naturally accumulated long
history. Measure a concrete mechanism: smaller useful context at resumption,
followed by less additional context processing without lost requirements.

## Use Claude Code through the existing execution owner

Claude Code 2.1.296 is installed locally. The installed Autowork controller
already has a Claude executor and command builder. The prior cohort used the
already-qualified Codex lane; that was an implementation choice, not a TORC
restriction. Keep execution in Autowork and reporting in TORC.

Use `claude -p` with structured output. Retain the event stream and terminal
result, including usage, `modelUsage`, and `total_cost_usd`. The latter is an
estimate, not an invoice. Resumed totals include earlier spend; deduplicate
message IDs and subtract explicit baselines. If delegation is enabled, use
the documented whole-tree fields rather than top-level `usage` alone.
[CLI contract](https://code.claude.com/docs/en/headless),
[accounting contract](https://code.claude.com/docs/en/agent-sdk/cost-tracking).

First compare both strategies on the same Claude model/version, effort, tools,
authentication mode and environment. Do not compare a Claude treatment against
a Codex control and attribute the difference to TORC. Refresh only Claude-specific
execution/capture controls; reuse still-valid independent scorer evidence.

For actual dollar savings, run that same CLI with API-backed authentication and
reconcile an isolated experiment workspace/key/time window with Console or the
[Usage and Cost API](https://platform.claude.com/docs/en/manage-claude/usage-cost-api).
Use billing buckets at their real granularity; do not invent per-trial charges
from a shared bucket. Administrative reporting access may be needed. Subscription
measurements can answer the reported-usage question without this access.

## Execution stages and deliverables

| Stage | Work | Concrete completion condition |
|---|---|---|
| 1. Repair the measurement setup | For new workloads, test required behavior rather than incidental exception wording. Declare a contained scratch directory and provide identical dependencies. Validate the frozen hidden-test command and terminal capture. Preserve the old cohort unchanged. | Known-good candidates pass; deliberately broken candidates fail; scratch files do not masquerade as source violations. |
| 2. Measure and improve the context mechanism | Count the exact delivered context with a pinned tokenizer, labeling estimates as estimates. Separate useful task text from serialized metadata and repeated instructions. Test a smaller receiver projection while preserving constraints, holds and provenance. | Report before/after context size and omissions; demonstrate a real context reduction or explicitly test reduced subsequent investigation instead. No success inferred from short prompts alone. |
| 3. Validate Claude accounting | Reuse existing owner tests and retained Claude evidence. If live checks are needed, reserve two small calls covering a fresh call and continuation. Match per-message records to terminal totals; retain partial/error evidence and owner termination. | A reproducible usage ledger with stated coverage, no inherited double-counting, and separate estimated versus billed dollars. |
| 4. Freeze and run a paired benchmark | Select eight distinct held-out continuation tasks across at least three repositories from retained real interruption artifacts. Use a credible ordinary handoff and TORC, both with equal source/history access. Two repetitions per task and arm; alternate/randomize order. | 32 planned comparison invocations, every outcome retained, no outcome-dependent replacement. Report preparation costs separately and include strategy-specific model work in its total. |
| 5. Decide from results | Compare task-level paired usage, acceptance and elapsed time. Publish savings, no detectable improvement, or a regression, with the actual numbers and uncertainty. | A decision about this measured deployment setting; a larger confirmation study only if the result merits it. |

If eight suitable retained interruptions do not exist, identify the missing
fixtures before launch. New history-generation calls must be separately counted;
do not fabricate natural histories or hide preparation expense. The two old
tasks are development fixtures, not held-out effectiveness evidence.

## Endpoint and decision rule

Primary subscription endpoint: reduction in CLI-reported input consumption over
the entire bounded continuation strategy, paired by task. Report output, cache
reads/writes, preparation and failure counts alongside it. Do not combine cache
fields with input until their non-overlap is established. A paid cohort can use
reconciled strategy-level API spend as its dollar endpoint.

For each task, aggregate the same number of repetitions per arm, including
failures. Report `1 - TORC / baseline`, then the median paired reduction and
uncertainty with tasks as the independent units. Do not select only successful
or fully observed cheap runs. Missing terminal usage stays missing, and prevents
a complete-cost statement; available measurements remain publishable with their
coverage and paired outcomes.

The existing 20% improvement target remains a useful candidate target for this
new reported-usage endpoint. Require no observed reduction in acceptance and
no critical authority failures before considering a broader confirmation run.
Eight tasks cannot establish the original five-percentage-point non-inferiority
claim. Choose a larger confirmation sample from measured variability and a
declared precision/power requirement before making that stronger claim.

Proposed new allowance: 32 comparison calls plus at most two accounting checks,
600 seconds each, no automatic retries. Any model-based preparation is additional
and must be enumerated before launch. This is not a reset of either old allowance.
Prefer subscription execution; if billing evidence is needed, first check that
the chosen bounded batch can fit within $2, otherwise present its actual budget
requirement before incurring it. CLI estimated-budget controls complement the
owner's limits; they do not certify the final invoice amount.

Future summaries should lead with what was measured: for example, "TORC used X%
less reported input at Y/Z acceptance on this cohort." State the missing billing
or generalization evidence specifically, rather than substituting a blanket
"no evidence" statement for the measured result.
