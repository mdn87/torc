# The 32-assignment run order is frozen

The comparison's run order and measured settings are fixed before the first
admission. Benchmark admissions remain zero, and the study has made no paid
calls. [Frozen schedule](2026-11-21-continuation-schedule.json)

Record this digest independently. The analyzer refuses results whose schedule
hashes to anything else.

```text
schedule_sha256 e02a67e8d80e859d630b7941ee9fbd951cc9de34fd5fa875b52ace2bb3830977
order_seed      1fec266c10f5f7e6bd7aeac7936519ec
```

## What is fixed

- **Tasks and prompts.** The eight cases and both prompt digests per case come
  from the published scorer preparation (`9e919604…`).
- **Measured settings.** The policy is the qualified accounting result: Claude
  Code 2.1.325, its recorded launch digest, `claude-opus-5-5` as the only main
  model, no auxiliary models, unknown cache sharing scope and the dated
  2026-11-20 rates.
- **Execution limits.** Each assignment uses the Autowork measured-continuation
  profile on the subscription, with one worker and one checker start sharing
  600 seconds. There are no continuations or replacements, and the $2 paid
  ceiling stands.
- **Order.** The seed picks each task's first arm in repetition 1. Repetition 2
  reverses it, so each arm leads eight of the sixteen pairs. The seed also
  draws a separate task order for each repetition. All sixteen repetition-1
  assignments run before repetition 2. Each trial ID is the Autowork
  correlation ID for that assignment.

| Run | Repetition 1 task | First arm | Run | Repetition 2 task | First arm |
| ---: | --- | --- | ---: | --- | --- |
| 1–2 | tableforge-settlement-renderer | compiled | 17–18 | tableforge-coordinator | compiled |
| 3–4 | tuan-incremental-validation | torc | 19–20 | wow-context-channel | compiled |
| 5–6 | autowork-agy-completion | torc | 21–22 | tableforge-settlement-renderer | torc |
| 7–8 | tuan-workflow-forecast | torc | 23–24 | autowork-agy-completion | compiled |
| 9–10 | cormac-powershell-quotes | compiled | 25–26 | cormac-powershell-quotes | torc |
| 11–12 | tableforge-persistence | torc | 27–28 | tableforge-persistence | compiled |
| 13–14 | tableforge-coordinator | torc | 29–30 | tuan-workflow-forecast | compiled |
| 15–16 | wow-context-channel | torc | 31–32 | tuan-incremental-validation | compiled |

## Reproduce the schedule

Pass the recorded seed to rebuild the file byte for byte. Omitting the seed
draws a new one and starts a different schedule.

```text
python -m torc.claude_continuation_schedule docs/evidence/2026-11-20-continuation-scorer-preparation.json docs/evidence/2026-11-20-claude-accounting-qualification.json rebuilt.json --order-seed 1fec266c10f5f7e6bd7aeac7936519ec
```

The tests rebuild the committed file, check its digest, and run the analyzer
on it with no results. It reports all eight tasks as unresolved and all
thirty-two assignments as unscored.

## Next

Run the 32 assignments in sequence on the qualified Windows lane, retaining
every outcome. A failed or timed-out assignment stays in the record and is
not replaced.
