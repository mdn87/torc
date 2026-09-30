# Series 002 calibration report

Status: calibration passed; no comparative claim authorized

All four fresh GPT-6 Sol targets reconstructed the complete inherited state,
made the correct `block` decision, supplied recoverable provenance, and
introduced no forbidden contradiction.

| Mechanism | Effort | Continuity recall | Blocking areas | Decision |
|---|---:|---:|---:|---|
| compiled handoff | low | 1.000 | 6/7 | block |
| TORC projection | low | 1.000 | 6/7 | block |
| compiled handoff | xhigh | 1.000 | 6/7 | block |
| TORC projection | xhigh | 1.000 | 7/7 | block |

The three 6/7 runs omitted `audit-retention`. The TORC `xhigh` run connected
the candidate's destructive rollback proposal to the seven-year retention
commitment and included that seventh blocking area.

This one observation is not evidence that TORC is better. It may be sampling
variation, ordering, or a format interaction. The corrected TORC payload also
used 1.216 times the canonical JSON bytes of the corrected compiled handoff.

The fixture passes calibration because the low-effort condition is useful but
not ceiling-saturated. A confirmatory series should now use at least six
independent fixtures, balanced assignment paraphrases, randomized lane order,
and repeat runs. It must fix scorer version 1's inherited-label denominator
before freezing the next manifest.

The initial series-001 outputs remain preserved but are excluded because of a
prompt-rendering defect documented in `runs/series-001/disposition.json`.
