# P1b Controlled Comparison Results

Status: series complete; roadmap P1b gate not passed

Date: 2026-08-08

## Conclusion

Series `p1b-codex-claude-001` completed all five preregistered pairs in order.
All ten runs were accepted and verified, with no credential-scan findings,
recorded in-run operator interventions, failed target attempts, integrity
errors, or control drift.

TORC matched the compiled-prompt baseline on required commitment retention,
constraint retention, settled-decision and unresolved-work accuracy,
provenance recoverability, contradiction count, and target task quality. It did
not show a material continuity improvement on this fixture. TORC delivered
3.26 times as many estimated words and 4.31 times as many UTF-8 bytes. Its
median inherited/new label accuracy was 0.006410 higher, but paired differences
were mixed and the procedure does not support a significance claim.

This series also reused the synthetic `p1a-review-001` readiness fixture. It
therefore does not satisfy the evaluation plan and roadmap requirement for a
real Lugos subsystem task-phase transition. The result does not authorize P2.

## Frozen controls

- Codex source: `codex-cli 0.147.0`, `gpt-5.6-sol`, effort `high`, tier `fast`.
- Claude target: `2.1.226 (Claude Code)`, `claude-opus-4-7`, effort `high`.
- Source assignment SHA-256:
  `e6adfb08fb048b6f790d85411d27bc44ae56e54cf94ef490a479d5ade0cc74b5`.
- Target assignment-template SHA-256:
  `70b8751e1dd200d9f9f2d33d0748f5e64d5e06a988755ea48a9419fd9ea0bb96`.
- Scorer `p1a-1`; normalization `unicode-casefold-1`.

Every source and target artifact recorded these controls. Run directories are
preserved under `%TEMP%/<run-id>` on the authoritative Windows host.

## Run outcomes

| Pair | Order | A score-core SHA-256 | C score-core SHA-256 | A label accuracy | C label accuracy |
|---|---|---|---|---:|---:|
| 1 | A, C | `97fdafeb0a2680f5930cd304627cdf8b1d61ec75109e075e878b8ceb79457154` | `17254a93dc321809b9fdbeee310fe2ac20039ea6f427339e9189fefa8dcb9449` | 1.000000 | 0.916667 |
| 2 | C, A | `7447802197cd85d3b4de49199e14869d7892f44d2cd34aa1712c4a6a8e1c0f4c` | `f64ab5ed29ee49dedb00a17cf849085f16ec79a8f19d5f04dff43a332360fd8a` | 0.888889 | 0.928571 |
| 3 | A, C | `20c1ec50eba8d2a0b6df5078b8fec9066f8586039c786e70e6ac7da8e6974850` | `96f476bce8c5b0d2da5ebd3e2f717a536eef15b4a7f502e4f3a9619f7662d040` | 0.875000 | 0.923077 |
| 4 | C, A | `af16ad13fbeee34f0b0a293c199e0a81b5a7d9b109ce66e0962ef9cb247d4a4a` | `96f476bce8c5b0d2da5ebd3e2f717a536eef15b4a7f502e4f3a9619f7662d040` | 0.916667 | 0.923077 |
| 5 | A, C | `97fdafeb0a2680f5930cd304627cdf8b1d61ec75109e075e878b8ceb79457154` | `96f476bce8c5b0d2da5ebd3e2f717a536eef15b4a7f502e4f3a9619f7662d040` | 1.000000 | 0.923077 |

## Registered measures

Values are lane median followed by `[minimum, maximum]`. Paired differences
are C minus A.

| Measure | Compiled prompt A | TORC C | Paired difference median [range] |
|---|---:|---:|---:|
| Required commitment recall | 1.000000 [1, 1] | 1.000000 [1, 1] | 0 [0, 0] |
| Hard-constraint recall | 1.000000 [1, 1] | 1.000000 [1, 1] | 0 [0, 0] |
| Settled-decision accuracy | 1.000000 [1, 1] | 1.000000 [1, 1] | 0 [0, 0] |
| Unresolved-work accuracy | 1.000000 [1, 1] | 1.000000 [1, 1] | 0 [0, 0] |
| Inherited/new label accuracy | 0.916667 [0.875000, 1.000000] | 0.923077 [0.916667, 0.928571] | 0.006410 [-0.083333, 0.048077] |
| Provenance recoverability | 1.000000 [1, 1] | 1.000000 [1, 1] | 0 [0, 0] |
| Contradictions | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] |
| Target task quality | 1.000000 [1, 1] | 1.000000 [1, 1] | 0 [0, 0] |
| Context delivered, estimated words | 102 [102, 102] | 333 [333, 333] | +231 [+231, +231] |
| Context delivered, UTF-8 bytes | 928 [928, 928] | 3,998 [3,998, 3,998] | +3,070 [+3,070, +3,070] |
| Operator steps | 6 [6, 6] | 6 [6, 6] | 0 [0, 0] |

The apparatus records duration as zero and does not retain provider usage in
the scored artifact, so the series supports no latency, token, or cost claim.
There were no operator corrections within a prepared run.

## Authority and integrity

Every TORC run passed all nine frozen handoff-acceptance requirements. Source
authority remained unchanged before acceptance, and each accepted result moved
authority to `p1a-target-attempt-0001` at `p1a-revision-0003`. Store and
artifact verification found no duplicate authoritative activation or provenance
error. The compiled-prompt lane carried provenance references but did not
perform an authority transition.

## Operator record

Before Pair 1 A was prepared, the initial PowerShell prepare command was split
after `--run-dir`. Later stages correctly failed because no run existed. The
correct prepare command then created the run. No payload, frozen control, run
artifact, or target attempt existed during the command-entry error, so it is
recorded here but is not an in-run intervention or contamination.

## Gate interpretation

The initial pass criteria for zero loss, complete accepted-transfer provenance,
single authority, and equal target quality passed. The required measurable
reduction in irrelevant context or operator correction did not: corrections
tied at zero and TORC context was larger. The simpler baseline therefore tied
all scored continuity and quality measures while using substantially less
context on this ceiling-saturated synthetic fixture.

The bounded conclusion is to stop before P2. A definitive roadmap P1b retry
would require a new preregistered series with a real Lugos subsystem transition,
more discriminating continuity demands, and retained latency/token evidence.
That would be a new scope decision, not a continuation of this series.
