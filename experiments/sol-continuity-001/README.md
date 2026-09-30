# Sol continuity experiment 001

Status: series 001 excluded; corrected series 002 calibration complete;
confirmatory series pending

This experiment is separate from TORC P1a/P1b. It asks whether a TORC
projection improves continuity or reduces prompt sensitivity when a fresh
GPT-6 Sol activation succeeds an implementation activation.

The existing P1 results and fixtures are not inputs to this series.

## Questions

1. Does a TORC projection outperform a carefully compiled handoff when the
   target is GPT-6 Sol at the same reasoning effort?
2. Does any difference become larger at `low` effort than at `xhigh` effort?
3. Is either mechanism more robust to semantically equivalent assignment
   wording?
4. What context, latency, and usage overhead accompanies any quality change?

Authority, tamper detection, rejection, and lease exclusivity remain separate
system-invariant tests. They are not folded into the model-quality score.

## Calibration design

The source state is frozen rather than generated anew for every lane. This
keeps the continuity mechanism as the intentional difference.

The corrected calibration has four fresh, isolated target activations:

| Run | Mechanism | Target effort | Assignment |
|---|---|---|---|
| `cal-v1-compiled-low` | compiled handoff | low | v1 |
| `cal-v1-torc-low` | TORC projection | low | v1 |
| `cal-v1-compiled-xhigh` | compiled handoff | xhigh | v1 |
| `cal-v1-torc-xhigh` | TORC projection | xhigh | v1 |

Each target receives only:

- one lane payload;
- `fixture/candidate-release.json`;
- the selected assignment wrapper; and
- `schemas/target-output.schema.json`.

The target must not receive `fixture/oracle.json`, the other lane payload,
another target's output, or this README. Target outputs are scored
deterministically before any root-agent synthesis.

Series 001 exposed a citation-rendering defect and is preserved but excluded.
Series 002 corrected that defect before its live runs. Its results and bounded
interpretation are in `runs/series-002/results.json` and
`runs/series-002/report.md`.

Post-calibration apparatus work is versioned separately from those frozen
series. `score_v2.py` corrects inherited/new classification without changing
the Series 002 score record. The production package now also contains a claim
capsule compiler that keeps full provenance in a control envelope and gives the
target short claim handles. On this fixture, its model-visible canonical JSON
is 2,243 bytes, compared with 2,930 for the corrected compiled handoff and
3,563 for the original TORC projection. These byte counts are design evidence,
not token or quality results.

Calibration is successful when the task is neither ceiling-saturated nor
floor-saturated. As a working rule, at least one low-effort run must score
below 1.0 on continuity or review coverage, while at least one run must score
at or above 0.75 on both. This rule may select a fixture for a later frozen
confirmatory series; it may not turn calibration results into a comparative
claim.

## Confirmatory design after calibration

Use at least six independent fixtures with the same semantic structure. Cross
mechanism (`compiled`, `torc`), effort (`low`, `xhigh`), and assignment wrapper
(`v1`, `v2`) in matched blocks. Each mechanism receives each wrapper equally
often. Randomize lane order within a block and preserve every failed or
malformed attempt.

If usage permits, repeat every cell once. Report paired differences and
bootstrap confidence intervals; do not claim significance from the four-run
calibration.

A native-compaction arm is intentionally deferred until the harness can force
and evidence `/compact` at the same checkpoint without exposing the oracle.
It must be added as a new preregistered series, not silently approximated with
a summary.

## Measures

- exact recall and precision for settled decisions, commitments, constraints,
  and unresolved work;
- identity, responsibility, handoff-reason, and source-revision accuracy;
- inherited/new labeling accuracy;
- provenance recoverability;
- contradiction count;
- blocking-review-area recall and precision;
- correct release decision;
- payload and output bytes and estimated words;
- duration and available usage evidence.

## Stop rules

- Stop a run if its model, effort, assignment, payload, or fixture hash differs
  from the manifest.
- Treat oracle exposure or reading outside the target-visible inputs as
  contamination.
- Never replace a failed run; append a new attempt against identical inputs.
- Do not tune the fixture after viewing calibration results and then report the
  tuned runs as part of the same series.

## Local scoring

After placing target JSON in `runs/<run-id>/target-output.json`, run:

```text
python experiments/sol-continuity-001/score.py --run-dir experiments/sol-continuity-001/runs/<run-id>
```

The scorer writes nothing. Its JSON output can be captured as the immutable
score artifact once the target output has been frozen.
