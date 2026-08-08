# P1b Comparative Run Procedure

Status: controls frozen for series `p1b-codex-claude-001`; execution not started

Pre-series control evidence: `docs/p1b-control-preflight.md`

## Comparison decision

P1b is narrowed to two lanes for the named Codex-to-Claude Code pair:
compiled-prompt (A) and TORC (C). Native persistence (B) remains a recorded
unavailable disposition and is not included in comparative scoring. A future
same-harness persistence study requires a new manifest and is not part of this
procedure.

## Frozen inputs

- Manifest contract: version 1.
- Series manifest: `examples/p1b-experiment-manifest.json`.
- Series identifier: `p1b-codex-claude-001`.
- Fixture: `p1a-review-001`, using the hashes pinned in
  `examples/p1b-experiment-manifest.json`.
- Source harness: `codex-cli 0.147.0`.
- Source model controls: `gpt-5.6-sol`, reasoning effort `high`, service tier
  `fast`.
- Target harness: `2.1.226 (Claude Code)`.
- Target model controls: `claude-opus-4-7`, effort `high`.
- Scorer: `p1a-1`.
- Normalization: `unicode-casefold-1`.
- Measures: exactly those registered by the P1a schemas and scorer.
- Target workspace: `task.json`, the selected continuity payload, and its
  visible-workspace manifest only.
- Tool policy: Codex source has read-only access to its visible workspace and
  generated-command network denial; Claude target has only `Read`, a strict
  empty MCP configuration, no session persistence, and fail-closed sandboxing.
- Assignment text: the exact source assignment and target assignment template
  embedded in the series manifest.

The adapters fail closed on a harness-version mismatch and pass the frozen
model, effort, and service-tier values explicitly. Public harness evidence
records the effective controls and assignment hash. A change creates a new
series; it cannot be mixed into this one.

## Run sequence

Run five paired blocks, using fresh run identifiers and fresh target
activations:

1. A then C
2. C then A
3. A then C
4. C then A
5. A then C

Use these unique run identifiers in that order:

1. `p1b-codex-claude-001-pair-01-a`, then
   `p1b-codex-claude-001-pair-01-c`
2. `p1b-codex-claude-001-pair-02-c`, then
   `p1b-codex-claude-001-pair-02-a`
3. `p1b-codex-claude-001-pair-03-a`, then
   `p1b-codex-claude-001-pair-03-c`
4. `p1b-codex-claude-001-pair-04-c`, then
   `p1b-codex-claude-001-pair-04-a`
5. `p1b-codex-claude-001-pair-05-a`, then
   `p1b-codex-claude-001-pair-05-c`

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

## Operator command pattern

For each preregistered run identifier, create a fresh directory outside the
repository and invoke the six stages separately. Substitute `compiled-prompt`
and suffix `a`, or `torc` and suffix `c`, as registered above.

```powershell
$runId = "p1b-codex-claude-001-pair-01-a"
$runDir = Join-Path $env:TEMP $runId
python -m torc experiment prepare --manifest examples/p1b-experiment-manifest.json --lane compiled-prompt --run-id $runId --run-dir $runDir --json
python -m torc experiment source --run-dir $runDir --adapter codex --json
python -m torc experiment target --run-dir $runDir --adapter claude-code --json
python -m torc experiment score --run-dir $runDir --json
python -m torc experiment inspect --run-dir $runDir --json
python -m torc experiment verify --run-dir $runDir --json
```

## Reporting

Report each run and paired differences for all registered measures. Report
medians and ranges by lane; do not claim statistical significance from five
pairs. Include failures and operator interventions in the same report. P1b may
support a bounded comparative conclusion, but it does not authorize P2.
