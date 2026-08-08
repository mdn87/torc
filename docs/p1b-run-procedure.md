# P1b Comparative Run Procedure

Status: frozen procedure; P1a gate passed; execution ready but not started

## Comparison decision

P1b is narrowed to two lanes for the named Codex-to-Claude Code pair:
compiled-prompt (A) and TORC (C). Native persistence (B) remains a recorded
unavailable disposition and is not included in comparative scoring. A future
same-harness persistence study requires a new manifest and is not part of this
procedure.

## Frozen inputs

- Manifest contract: version 1.
- Fixture: `p1a-review-001`, using the hashes pinned in
  `examples/experiment-manifest.example.json`.
- Source harness: Codex.
- Target harness: Claude Code.
- Scorer: `p1a-1`.
- Normalization: `unicode-casefold-1`.
- Measures: exactly those registered by the P1a schemas and scorer.
- Target workspace: `task.json`, the selected continuity payload, and its
  visible-workspace manifest only.

Harness versions, model settings, effort, tool policy, and assignment text are
recorded before the first run and remain fixed for the series. A change creates
a new series; it cannot be mixed into this one.

## Run sequence

Run five paired blocks, using fresh run identifiers and fresh target
activations:

1. A then C
2. C then A
3. A then C
4. C then A
5. A then C

For every run, execute prepare, source, target, score, and verify as separate
operator-invoked stages. Do not edit an artifact between stages. Record all
operator interventions. A failed attempt may be retried only as a new attempt
against the identical payload; a payload or controlled-setting change requires
a new run identifier.

## Inclusion and stop rules

A run enters the paired comparison only when it has an accepted disposition,
a valid artifact manifest, a clean best-effort credential scan, and no manual
edit between payload freeze and scoring. Preserve and report failed, rejected,
unavailable, and contaminated runs; never relabel or silently replace them.

Stop the series if:

- oracle isolation cannot be evidenced;
- any controlled setting differs between a pair;
- verification or provenance fails;
- the scorer or fixture changes;
- a credential-like artifact is reported; or
- an operator intervention changes the target-visible continuity.

Correct an apparatus defect before restarting the entire five-pair series under
a new series identifier.

## Reporting

Report each run and paired differences for all registered measures. Report
medians and ranges by lane; do not claim statistical significance from five
pairs. Include failures and operator interventions in the same report. P1b may
support a bounded comparative conclusion, but it does not authorize P2.
