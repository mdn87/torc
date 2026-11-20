# Claude continuation accounting

Autowork records each worker and checker start, including starts that end before
Claude returns a final result. TORC reads the exported counters and independent
candidate scores. The study uses eight tasks with two repetitions per arm.

## Development checks

`development.py` has two fixed practice assignments. The first asks for a short
answer. The second asks the worker to read and edit one text file. Each uses the
Autowork measured-continuation profile and the local subscription executor. The
worker and checker share 600 seconds and have at most one start each.

Run the script with Python 3.11 or newer and the qualified Lugos checkout's
`autowork/src` on `PYTHONPATH`. The checkout must pass Autowork's local-node
attestation. Supply an output root and either `single` or `multi`. The default
checks placement, the installed CLI's options, and subscription authentication.
The separate `--admit` flag consumes a development assignment. Use the study's
designated directory for each admission. The script refuses to replace a case.
The development allowance is two assignments across the entire study.

## Read an assignment ledger

Use the execution owner's CLI with the assignment's usage directory and
completion checkpoint. It verifies the saved event chain and writes JSON.

```text
python -m autowork.campaign.claude_stream_usage attempt-001.claude-usage --completion attempt-001.completion.json
```

Each start has a role, prompt and trial binding, first-request input, duration,
request IDs and models, raw usage categories, terminal model totals, retry
evidence when emitted, and the SHA-256 of the underlying records. A missing
terminal or unmatched counter leaves the total unknown. The observed request
counts remain available.

## Analyze a frozen comparison

The offline entry point takes the frozen schedule, the published scorer
preparation receipt, a results index, and the schedule's previously recorded
canonical JSON digest.

```text
python -m torc.claude_continuation_evidence schedule.json preparation.json results.json --schedule-sha256 DIGEST
```

Use contract `torc.claude_continuation_analysis.v1`. The schedule records its
`order_seed` and 32 trials, each with a unique `trial_id`, frozen `case`,
`prompt_sha256`, `arm` (compiled or torc), `repetition` (1 or 2), and
`position` (1 or 2 within that pair). The order reverses for repetition two.
Each trial ID becomes the owner's correlation ID.

Freeze the client version, launch SHA-256, main model, permitted auxiliary
models, and cache sharing scope in the schedule's `policy`. Its `prices` record
contains a date, documented source and model-specific rates in USD per million
tokens. Each tier specifies an inclusive input threshold (`through`, null for
the final tier), fresh input, 5-minute and 1-hour writes, reads, and output.
The allowed service tier, speed and geography specify which rates apply.
Missing TTL attribution or an unknown price setting leaves the corresponding
estimate unresolved. The CLI dollar estimate has its own field. [Anthropic
pricing](https://platform.claude.com/docs/en/about-claude/pricing)

The results index contains `schedule_sha256` and a list of `trials`. Each trial
can reference a `usage` export and a separate `score` file by relative path
and SHA-256 of the exact bytes. Bind the score to the trial ID, candidate
SHA-256, and frozen native oracle SHA-256. The scorer supplies
`verified_success` and `critical_failures`. A missing trial or score stays in
the denominator. Subjective reviewer answers have their own review store.

The report lists all eight reductions, counted input and cache categories,
paired first-request differences, per-start elapsed times, estimated costs
and acceptance. The cohort median and two-sided sign test require complete
usage for every task and a positive compiled-prompt denominator. Only a
qualified model, complete scores, no critical failures, no loss of passes on
any task, significant direction, and at least 20% median savings can support
considering a larger study.
