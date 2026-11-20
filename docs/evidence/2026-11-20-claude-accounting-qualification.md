# Claude usage accounting passed both development checks

Autowork captured all four CLI starts and all six reported provider requests.
TORC independently recomputed the first worker request and the combined worker
and checker totals. The observed requests and Claude's terminal counters agreed
in every input and output category. The eight-task comparison can now be
scheduled. It has zero admissions. [Machine-readable results](2026-11-20-claude-accounting-qualification.json)

| Development assignment | Worker requests | Checker requests | First worker input | All worker input | Checker input | Combined input | Output |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Return “violet square” | 1 | 1 | 6,715 | 6,715 | 4,165 | 10,880 | 67 |
| Read the label and change blue to violet | 3 | 1 | 6,732 | 20,670 | 4,273 | 24,943 | 417 |

The first worker returned the requested words and left the practice file intact.
The second worker changed the file to `violet square`. Autowork's checker accepted
each answer, and the development driver independently inspected the answer or
file. Both were fresh Windows assignments with a shared 600-second deadline
per assignment, zero continuations and zero replacements. Each task used the
local subscription route through the inventoried controller.

## Measurement settings

Claude Code 2.1.325 resolved the Opus/high route to `claude-opus-5-5` on every
request. Both terminal model lists contained only that model. Freeze this
client build, the recorded launch digest, and an empty list of auxiliary models
for this measured lane. The elapsed times from the first worker reservation to
the checker exit were 8.15 seconds and 13.35 seconds. Cache sharing scope is
unknown. Both runs reported cache reads and one-hour writes. [Owner implementation](https://github.com/mdn87/lugos/pull/747)

The input endpoint sums fresh input, cache creation and cache reads. The price
calculation used the reported global, standard settings and write lifetime.
The two estimated totals were $0.0536072 and $0.0506352, agreeing with Claude's
CLI estimates to rounding. Both assignments used the subscription. The study
has made zero paid API calls and retains its $2 paid ceiling. [Dated rates](../../experiments/claude-accounting-qualification/prices-2026-11-20.json)

## Reproduce the check

The saved development directory contains each assignment's owner reservation,
chained accounting events, completion checkpoint and exported usage. To replay
the arithmetic, pass that directory and the dated rate file to the offline
checker. The JSON result includes the hashes of both exact owner exports,
per-request counters and terminal totals. [Offline checker](../../experiments/claude-accounting-qualification/check_results.py)

```text
python experiments/claude-accounting-qualification/check_results.py <saved-development-directory> experiments/claude-accounting-qualification/prices-2026-11-20.json
```

The TORC analyzer pools both repetitions of each arm and keeps unsuccessful or
incomplete trials in the report. Any unresolved task suppresses the cohort
median and sign test. The next stage must freeze the order and measured settings
before the first benchmark admission. Human review and independent automated
correctness retain their own artifacts. [Analyzer and development driver](https://github.com/mdn87/torc/pull/40)
