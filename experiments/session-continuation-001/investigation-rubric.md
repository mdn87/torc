# Pilot investigation and timing rubric (draft, before live outputs)

This rubric supplies secondary observations. It does not replace independent
acceptance tests or qualify the trial for adoption. Freeze its hash with the
lane-specific preregistration before comparative runs. No observations have
been collected yet.

## Blinded assessment

The assessor receives a randomly labeled task packet: common public briefing,
pre-change workspace hash, ordered tool actions and visible results, elapsed
relative times and final candidate hash. Exclude arm names, prompt/context
payloads, session identifiers, usage counters and model commentary that reveals
the arm. Retain a private mapping to the original evidence; redaction must not
change action order or results. If redaction removes evidence needed for a
judgment, mark that item unassessable. The execution owner must collect complete
traces; absence of a trace is unknown, never zero investigation.

The independent acceptance scorer receives only its frozen candidate/scoring
job, as described in workloads.py. Do not supply this investigation score,
usage, arm identity or prior acceptance feedback to the worker.

## Investigation events

An investigation event is a tool action whose visible purpose is locating or
understanding code, requirements or prior results. A batched command is one
event unless its constituent operations and results are individually recorded.
Record the event index, action/result evidence references, classification and
one sentence explaining the classification.

- Necessary orientation: locating implementation surfaces or checking whether a
  retained claim still applies to the current workspace.
- New investigation: resolving a question not settled in the common briefing or
  earlier observed investigation.
- Repeated settled investigation: re-establishing the same already settled fact
  from the same unchanged evidence, with no new discrepancy or implementation
  decision that requires it. Cite the earlier evidence or retained decision.
- Unassessable: intent, earlier evidence, result or relevant workspace change is
  missing or ambiguous.

A repeated file read is not automatically repeated investigation. Re-reading
while implementing, verifying a change, investigating a failed check, and
checking a stale retained claim can be necessary work. Do not infer hidden
reasoning or require a particular tool sequence. Report raw event counts,
assessable-event denominator and unknown count; report no repeated-investigation
rate when coverage is incomplete. With only two pilot tasks, report individual
paired observations rather than a general productivity claim.

## Time and operator intervention

Keep wall-clock and monotonic timestamps from the execution owner. Record
preparation, waiting/queueing, each attempted start, worker execution, recovery,
verification and scoring separately. The primary completion interval begins at
trial admission and ends at the independent terminal acceptance decision; it
includes failed starts and fallbacks. Report seed/preparation expense separately
and under the preregistered whole-task boundary. Never drop unsuccessful runs
from elapsed-time summaries. A resource-cap stop is censored/unsuccessful,
not a successful finish at the cap.

Record each operator intervention's reason, timestamp and explicit active time
if available. Intervention count may be known while time is unknown. Do not
convert silence into zero effort or charge unattended elapsed time as active
operator work. Record corrections and unplanned rescues as protocol deviations;
retain the original trial and all costs rather than silently replacing it.
