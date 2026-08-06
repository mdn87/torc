# P1a Experimental Readiness Implementation Plan

Status: ready for implementation

Specification: `docs/p1a-experimental-readiness-spec.md`

Scope envelope: `docs/p1a-scope-envelope.json`

## Objective

Implement the smallest cross-platform apparatus that can prepare, execute,
score, inspect, and verify equivalent compiled-prompt, native-persistence when
available, and TORC continuity runs.

P1a proves experimental readiness. It does not compare lane performance,
authorize P2, or claim TORC is better than a baseline.

## Fixed constraints

- Python 3.11+ and the standard library at runtime.
- No provider SDK, direct provider API, daemon, server, watcher, queue, or
  background process.
- No second experiment database. Lane C may use the existing P0 TORC store.
- No parent Lugos edits or integration work.
- No model-based scoring.
- Only Codex source, Claude Code target, and deterministic replay adapters.
- Live agents receive staged, role-allowlisted workspaces without oracle or
  scoring material.
- Live harness commands require explicit operator invocation.
- Repository-relative paths and canonical UTF-8 JSON are authoritative.

## Planned file set

The implementation is expected to touch 23 files. This refines the original
20-file estimate before implementation and remains below the 1.5-times warning.

### Contracts and examples

1. `schemas/experiment-manifest.schema.json`
2. `schemas/experiment-run.schema.json`
3. `schemas/continuity-payload.schema.json`
4. `schemas/score-report.schema.json`
5. `schemas/artifact-manifest.schema.json`
6. `examples/experiment-manifest.example.json`
7. `examples/experiment-run.example.json`
8. `examples/continuity-payload.example.json`
9. `examples/score-report.example.json`
10. `examples/artifact-manifest.example.json`

### Controlled fixture

11. `examples/p1a-fixture/agent-visible/task.json`
12. `examples/p1a-fixture/oracle/continuity-oracle.json`
13. `examples/p1a-fixture/scoring/structural-rules.json`

### Runtime

14. `src/torc/experiment_runs.py`
15. `src/torc/experiment_lanes.py`
16. `src/torc/experiment_scoring.py`
17. `src/torc/experiment_adapters.py`
18. `src/torc/cli.py`

### Tests and evidence

19. `tests/test_schemas.py`
20. `tests/test_experiments.py`
21. `docs/p1a-scope-envelope.json`
22. `docs/p1a-results.md`
23. `docs/p1b-run-procedure.md`

Do not add a package dependency, generic adapter registry, separate database,
or additional live adapter to make implementation more convenient.

## Run directory contract

Every run directory uses this layout:

```text
<run-dir>/
  manifest.json
  fixture-manifest.json
  artifacts/
    source-capture.json
    continuity-payload.json
    reconstruction.json        # reference to the final selected attempt
    score-report.json
    artifact-manifest.json
  receipts/
    created.json
    source-captured.json
    payload-frozen.json
    target-completed.json
    reconstruction-recorded.json
    scored.json
    verified.json
  attempts/
    <attempt-id>/
      attempt.json
      target-output.json
      reconstruction.json
  workspaces/
    source/
      visible-workspace-manifest.json
      ...
    target/
      visible-workspace-manifest.json
      ...
  torc-state/                 # Lane C only; normal P0 state directory
```

Files are written to a sibling temporary path, flushed, and moved into place
with `os.replace`. A receipt is written only after its referenced artifact is
durable. Receipts are immutable: an existing receipt with matching input hashes
is returned; mismatched inputs raise a domain error and require a new run.

The artifact manifest uses relative POSIX-style paths even on Windows. It never
contains an absolute host path.

The `experiment prepare` command writes `receipts/created.json`; `prepare` is
the CLI action and `created` is the stage name from the accepted spec.
`receipts/target-completed.json` identifies the final completed attempt.
`artifacts/reconstruction.json` is an immutable reference containing that
attempt identifier, the attempt-local reconstruction path, and its SHA-256; it
does not overwrite or duplicate earlier attempt reconstructions.

The completed-target receipt graph uses all seven spec stages. An unavailable
Lane B terminates through `created -> source-captured -> payload-frozen ->
verified`: its source receipt contains probe evidence, its payload is an
unavailable descriptor, and it has no target-completed, reconstruction, or
scored receipt.

`artifact-manifest.json` covers every immutable run artifact and receipt that
exists before verification. `verified.json` is excluded from that manifest to
avoid a circular hash; it seals the artifact-manifest hash and verification
result.

## Runtime boundaries

### `experiment_runs.py`

Owns local artifact mechanics, not TORC lineage behavior.

Planned public functions:

```python
prepare_run(manifest_path, lane, run_dir, *, clock) -> dict
write_canonical_artifact(path, payload) -> ArtifactRef
write_stage_receipt(run_dir, stage, inputs, outputs, *, clock) -> dict
load_run(run_dir) -> dict
append_target_attempt(run_dir, attempt, *, clock) -> dict
build_visible_workspace(run_dir, role, allowlist) -> dict
build_artifact_manifest(run_dir, *, clock) -> dict
verify_experiment_run(run_dir) -> dict
scan_artifacts_for_credentials(run_dir) -> list[dict]
assert_manifest_adapter(manifest, stage, adapter_name) -> None
```

Rules:

- Reject absolute paths, `..`, symlink escapes, duplicate normalized paths, and
  case-colliding paths before staging.
- Copy only manifest-allowlisted files into source or target workspaces.
- Never copy `oracle/`, `scoring/`, repository planning documents, environment
  dumps, or unrestricted transcripts into a live workspace.
- Record visible-workspace paths, sizes, and SHA-256 values.
- Treat failed isolation evidence as `contaminated`, not as a warning.
- Credential scanning is best-effort. It reports findings; it does not claim
  proof that arbitrary text is secret-free.

### `experiment_adapters.py`

Owns translation to existing harnesses. It does not route, authorize, score, or
mutate TORC history.

Planned types and operations:

```python
class ExperimentAdapter(Protocol):
    def probe(self, manifest, stage) -> dict: ...
    def capture_source(self, context) -> dict: ...
    def start_target(self, context) -> dict: ...
    def collect_target(self, context) -> dict: ...

class ReplayAdapter: ...
class CodexSourceAdapter: ...
class ClaudeCodeTargetAdapter: ...
```

Implementation rules:

- Build subprocess arguments as lists and do not invoke through a shell.
- Set the subprocess working directory to the staged role workspace.
- Pass only an allowlisted environment; never serialize the environment.
- Capture only structured, allowlisted output fields and explicit artifact
  references.
- Record harness name, version, redacted argument plan, working-directory
  identity, allowed paths, exit status, and supplied usage evidence.
- Probe actual installed CLI help/version output before fixing any live command
  syntax. If the installed harness cannot enforce and evidence the workspace
  boundary, return `contaminated` and do not score the run.
- For Codex-to-Claude Code native persistence, return an evidence-bearing
  `unavailable` result unless an existing equivalent continuation is found.

### `experiment_lanes.py`

Owns only the difference in continuity mechanism.

Planned functions:

```python
materialize_compiled_prompt(run_context, source_capture) -> dict
materialize_native_persistence(run_context, probe_evidence) -> dict
materialize_torc_projection(run_context, source_capture) -> dict
record_torc_reconstruction(run_context, attempt, reconstruction) -> dict
```

Lane rules:

- Lane A produces a structured continuity prompt and fixture references. It
  contains no TORC authority or snapshot record.
- Lane B records the unmodified native continuation feature and restored
  context evidence, or `unavailable`. It cannot substitute another mechanism.
- Lane C creates a P0 lineage and authoritative source activation under
  `torc-state/`, appends the source checkpoint, compiles a projection, and
  prepares a handoff. It calls the existing `resolve_handoff` only after a
  parseable target reconstruction is recorded.
- A failed, interrupted, malformed, or contaminated target attempt cannot
  transfer the Lane C lease.

### `experiment_scoring.py`

Owns deterministic P1a scoring from frozen artifacts.

Planned functions:

```python
normalize_string(value) -> str
normalize_string_set(values) -> tuple[str, ...]
score_reconstruction(oracle, reconstruction, rules) -> dict
build_score_core(field_scores, structural_checks) -> dict
score_run(run_dir) -> dict
```

Scoring rules:

- Exact normalized-set recall for commitments, constraints, and open work.
- Supported/asserted ratios for settled decisions.
- Explicit inherited-versus-new-inference labeling.
- Oracle-declared contradiction rules only.
- Provenance references must resolve to agent-visible fixture or lane artifacts.
- Context uses UTF-8 bytes and the existing deterministic word estimator.
- Task-quality checks are structural: required review areas, completion fields,
  and output shape. They cannot encode expected defects or conclusions.
- `score-report.json` contains a deterministic `score_core` plus separate
  `operational_measurements` for timing and operator steps.
- `score_core_sha256` hashes only canonical `score_core`; wall-clock timestamps,
  durations, and operator steps are excluded from that parity hash.
- The same fixed clock, fixture, replay evidence, and scorer version must
  produce byte-identical full score reports in automated replay tests.
- Windows/macOS CLI parity compares continuity-payload bytes and canonical
  `score_core` bytes plus `score_core_sha256`, not the full timing-bearing score
  report.

## Implementation sequence

### Batch 1: production-parity replay slice

Target: complete before two elapsed implementation hours.

#### Task 1.1: Freeze the contracts and controlled fixture

Files:

- Add all five schema and example pairs.
- Add the three fixture files.
- Extend `tests/test_schemas.py`.

Contract requirements:

- IDs and relative paths follow existing P0 patterns.
- `experiment-run` includes immutable `target_attempts`.
- Dispositions include `accepted`, `rejected`, `unavailable`,
  `contaminated`, and `failed`.
- Manifest separates runner-only oracle/scoring paths from role-visible paths.
- `experiment-run` includes `operator_interventions` from its first example;
  absence of intervention is represented by an empty array.
- `score-report` separates deterministic `score_core` from operational timing
  and operator-step measurements and records `score_core_sha256`.
- Artifact entries include media type, byte size, and SHA-256.
- Examples validate against Draft 2020-12.

Verification:

```text
python -m pytest tests/test_schemas.py
python -m ruff check tests/test_schemas.py
```

#### Task 1.2: Implement the smallest end-to-end replay path

Files:

- Add `experiment_runs.py`, `experiment_lanes.py`,
  `experiment_scoring.py`, and `experiment_adapters.py`.
- Add the first tests in `tests/test_experiments.py`.

Implement only enough to:

1. Load and hash the fixture.
2. Prepare Lane A, Lane B, and Lane C run directories.
3. Capture a fixed replay source checkpoint.
4. Freeze each lane payload, including an unavailable descriptor for Lane B.
5. Stage an oracle-free replay target workspace.
6. Record a fixed replay target reconstruction.
7. Score deterministically.
8. Build and verify the artifact manifest.
9. Confirm Lane C transfers authority only after accepted reconstruction.
10. Confirm Lane B reaches a verified `unavailable` disposition without a
    target attempt or score.

Inject a fixed clock and fixed replay evidence in tests. Production code uses a
real UTC clock by default.

Required vertical-slice tests:

```text
test_replay_compiled_prompt_run_completes_and_verifies
test_replay_native_persistence_unavailable_run_completes_and_verifies
test_replay_torc_run_transfers_only_after_reconstruction
test_fixed_clock_replay_produces_identical_payload_and_score_report_bytes
test_score_core_excludes_operational_measurements
test_target_workspace_excludes_oracle_and_scoring_material
```

Verification:

```text
python -m pytest tests/test_experiments.py -k "replay or workspace"
python -m ruff check src/torc/experiment_*.py tests/test_experiments.py
```

Checkpoint:

- Record elapsed time, production LOC, test LOC, and changed files.
- If the replay slice is not working by two hours, stop broad implementation
  and apply this pre-decided simplification order without weakening the gate:
  1. Keep all five version 1 schemas but limit them to spec-required fields and
     the smallest valid examples.
  2. Keep one compact JSON object in each of the three fixture files; defer
     narrative enrichment.
  3. Implement only the fixed replay adapter and happy-path Lane A/B/C
     materializers; defer stricter path checks and tamper cases to Batch 2.
  4. Do not defer oracle separation, acceptance-gated Lane C authority,
     deterministic `score_core`, or verified Lane B unavailability.
- Do not start live adapter work before this slice passes.

### Batch 2: receipts, attempts, isolation, and tamper verification

#### Task 2.1: Complete idempotent stage receipts

Implement and test:

- Atomic artifact-before-receipt ordering.
- Existing matching receipt returns the stored result.
- Mismatched receipt inputs require a new run identifier.
- A changed payload cannot be attached as another attempt to the same run.
- Multiple failed attempts remain append-only.
- The final completed attempt is referenced without rewriting failed attempts.
- Every attempt stores its own reconstruction; the top-level reconstruction
  artifact references only the final attempt selected for scoring.

Required tests:

```text
test_identical_stage_retry_is_idempotent
test_changed_stage_input_requires_new_run
test_failed_target_attempt_is_preserved
test_changed_payload_cannot_reuse_run
```

#### Task 2.2: Enforce workspace and artifact isolation

Implement and test:

- Path traversal, symlink escape, case collision, and duplicate-path rejection.
- Source and target role allowlists.
- Oracle, scoring, and planning-document denial.
- Visible-workspace manifest creation.
- `contaminated` disposition when isolation cannot be evidenced.
- Allowlisted artifact shapes and best-effort credential-pattern scan.

Required tests:

```text
test_target_workspace_manifest_contains_only_allowlisted_files
test_oracle_exposure_marks_run_contaminated
test_path_escape_and_case_collision_are_rejected
test_environment_dump_is_rejected
test_credential_scan_reports_fixture_finding_without_exposing_value
test_completed_replay_artifacts_pass_credential_scan
```

#### Task 2.3: Complete experiment verification

`verify_experiment_run` must check:

- Manifest and fixture hashes.
- Receipt input/output links.
- Stage order derived from receipts.
- Presence and linkage of the `target-completed` receipt for completed targets.
- Target-attempt payload hashes and dispositions.
- Final-attempt reference.
- Lane-specific artifact exclusions.
- Lane C snapshot, result, lease, and authority integrity through existing P0
  verification.
- Artifact manifest completeness and file hashes.
- Score inputs and scorer version.

Tamper tests cover manifest, payload, attempt, reconstruction, score, receipt,
workspace manifest, and artifact manifest.

Verification:

```text
python -m pytest tests/test_experiments.py -k "idempotent or attempt or isolation or tamper"
python -m pytest
python -m ruff check .
```

Budget checkpoint:

- Compare observed scope to `docs/p1a-scope-envelope.json`.
- At 1.5 times any estimate, simplify before adding live capability.
- At twice an estimate or on a new architecture trigger, stop for operator
  approval.

### Batch 3: CLI and deterministic cross-platform replay

#### Task 3.1: Add the experiment CLI

Modify `src/torc/cli.py` to add the six accepted subcommands without moving
domain logic into the parser.

CLI requirements:

- JSON output is deterministic apart from documented operational timestamps.
- Domain failures return nonzero with structured `error` and `detail`.
- `--adapter` must match the frozen manifest before work begins.
- `inspect` and `verify` do not mutate a completed run.
- Live `source` and `target` print the redacted command plan and artifact
  destinations before harness invocation.

CLI tests call `main([...])` directly and cover successful replay plus adapter
mismatch, tamper, and a full Lane B prepare, probe, unavailable-disposition,
and verify path.

#### Task 3.2: Run the Windows replay lane

PowerShell commands:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m torc experiment prepare --manifest examples/experiment-manifest.example.json --lane compiled-prompt --run-dir .torc/p1a/replay-a --json
.\.venv\Scripts\python -m torc experiment source --run-dir .torc/p1a/replay-a --adapter replay --json
.\.venv\Scripts\python -m torc experiment target --run-dir .torc/p1a/replay-a --adapter replay --json
.\.venv\Scripts\python -m torc experiment score --run-dir .torc/p1a/replay-a --json
.\.venv\Scripts\python -m torc experiment verify --run-dir .torc/p1a/replay-a --json
```

Repeat for `--lane torc` under `.torc/p1a/replay-c`. Record payload and score
hashes for the macOS comparison.

Run Lane B through its complete unavailable path:

```powershell
.\.venv\Scripts\python -m torc experiment prepare --manifest examples/experiment-manifest.example.json --lane native-persistence --run-dir .torc/p1a/replay-b --json
.\.venv\Scripts\python -m torc experiment source --run-dir .torc/p1a/replay-b --adapter replay --json
.\.venv\Scripts\python -m torc experiment verify --run-dir .torc/p1a/replay-b --json
```

The verified Lane B directory contains the frozen fixture and settings,
unavailable continuity-payload descriptor, probe evidence, terminal
disposition, receipts reached before unavailability, and artifact manifest. It
contains no target attempt, reconstruction, or score.

The schema example is also the runnable replay manifest. It references the
three fixture files by relative path and pinned SHA-256.

#### Task 3.3: Run the macOS replay lane

This is a separate verification lane after the Windows replay artifacts are
frozen. It does not authorize SSH automation.

POSIX commands:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m torc experiment prepare --manifest examples/experiment-manifest.example.json --lane compiled-prompt --run-dir .torc/p1a/replay-a --json
.venv/bin/python -m torc experiment source --run-dir .torc/p1a/replay-a --adapter replay --json
.venv/bin/python -m torc experiment target --run-dir .torc/p1a/replay-a --adapter replay --json
.venv/bin/python -m torc experiment score --run-dir .torc/p1a/replay-a --json
.venv/bin/python -m torc experiment verify --run-dir .torc/p1a/replay-a --json
```

Repeat for Lane C. Compare deterministic payload and score-core bytes plus
their SHA-256 values with the Windows evidence. Specifically, compare the full
continuity-payload bytes and the canonical `score_core` bytes plus
`score_core_sha256`. Full `score-report.json` bytes, receipt timestamps,
durations, and operator-step measurements may differ. Fixed-clock automated
replay tests still compare the complete score report byte-for-byte.

Also run the Lane B unavailable sequence and verify its disposition and
artifact manifest on macOS.

Do not begin the live smoke until all three replay lanes pass or the macOS
blocker is recorded for operator disposition.

### Batch 4: bounded live adapters and readiness smoke

#### Task 4.1: Probe installed harness capabilities

Before writing live command builders:

1. Record Codex CLI version and relevant help output.
2. Record Claude Code version and relevant help output.
3. Identify the supported non-interactive invocation and filesystem boundary
   mechanisms.
4. Confirm that neither adapter needs a provider SDK or credential capture.
5. Confirm the operator-authorized assignment can restrict the live activation
   to the staged workspace.

If either harness cannot enforce and evidence oracle isolation, preserve replay
support, return `contaminated` for the live path, and stop the live gate rather
than weakening it.

#### Task 4.2: Implement Codex source adapter

The adapter:

- Probes version and source capability.
- Uses only the staged source workspace.
- Captures the allowlisted checkpoint fields required by all lanes.
- Records a redacted argument plan and assignment boundary evidence.
- Does not read the oracle or scoring files.

Tests mock `subprocess.run`; automated tests never invoke a live harness.

#### Task 4.3: Implement Claude Code target adapter

The adapter:

- Probes version and target capability.
- Uses a fresh activation and only the staged target workspace.
- Receives the selected lane payload and visible fixture references.
- Returns a structured reconstruction and task-output reference.
- Records workspace-boundary evidence and refuses scoring when contaminated.

Tests mock `subprocess.run` and assert list-form arguments, sanitized
environment, staged `cwd`, and output allowlisting.

#### Task 4.4: Record native-persistence availability

Probe the Codex-to-Claude Code pair. Expected result is `unavailable`.

Evidence must state:

- which existing continuation features were inspected;
- why none supplies equivalent cross-harness continuation, if unavailable; and
- that no alternative mechanism was substituted.

Do not add a third live adapter or same-harness pair during P1a. That decision
belongs in the frozen P1b procedure and its own scope.

#### Task 4.5: Execute the live readiness smoke

The operator explicitly invokes, in order, for Lane A and Lane C:

1. `experiment prepare`
2. `experiment source --adapter codex`
3. `experiment target --adapter claude-code`
4. `experiment score`
5. `experiment verify`

Each lane must remain within eight documented operator steps. No manual file
edit is permitted between payload freeze and scoring.

Required evidence:

- Harness versions and redacted command plans.
- Source and target visible-workspace manifests.
- Oracle/scoring exclusion evidence.
- Parseable reconstruction.
- Lane C lease holder before preparation, after preparation, and after result.
- Verified artifact manifest and score report.
- Native-persistence probe disposition.

Any contaminated, malformed, interrupted, or rejected run remains valid
failure evidence but does not pass the live readiness gate.

### Batch 5: freeze P1a evidence and the P1b procedure

#### Task 5.1: Complete documentation and scope accounting

Create `docs/p1a-results.md` with:

- exact replay and live commands;
- fixture and manifest hashes;
- platform evidence;
- adapter probe results;
- operator-step counts;
- lease holder before and after;
- artifact paths and verification result;
- interruption and idempotent-resume commands, attempt identifiers, receipt
  hashes, and verification evidence;
- the completed replay artifact credential scan with zero findings;
- accepted threats and operational risks;
- observed elapsed hours, production LOC, test LOC, changed files, persistent
  runtime processes, and operator steps; and
- any divergence from this plan or the accepted spec.

Update `docs/p1a-scope-envelope.json`:

- observed budgets;
- vertical-slice status and evidence;
- review-round count;
- architecture triggers, if any; and
- final P1a gate disposition.

#### Task 5.2: Freeze `docs/p1b-run-procedure.md`

Before the first P1b live run, record:

- selected real task and immutable manifest;
- source and target harness identities, versions, model settings, effort, and
  tool policy;
- whether a same-harness pair exercises native persistence or Baseline B is
  pre-registered unavailable;
- trial count and run order;
- scorer and normalization versions;
- pass/fail thresholds;
- contamination and exclusion rules;
- allowed operator interventions; and
- exact commands and artifact destinations.

This document freezes procedure only. Do not execute or interpret P1b in the
P1a implementation task.

## Acceptance-to-test traceability

| Spec requirement | Primary evidence |
|---|---|
| Schema examples validate | `tests/test_schemas.py` |
| Replay outputs are deterministic | fixed-clock full-report tests and cross-platform payload/score-core hashes |
| Lanes share fixture and settings | manifest and fixture-hash assertions |
| Lane A contains no TORC authority | Lane A artifact exclusion test |
| Lane B is native or unavailable | end-to-end verified unavailable run directory |
| Lane C transfer is acceptance-gated | P0 authority assertions in experiment tests |
| Identical retry is idempotent | receipt replay test |
| Changed input requires new run | receipt mismatch test |
| Failed target preserves authority | failed-attempt Lane C test |
| Tampering is detected | parameterized artifact/receipt tamper tests |
| Artifact capture is allowlisted | schema and forbidden-field tests |
| Credential scan is best-effort | planted-finding test plus clean completed-run scan |
| Oracle is isolated | role-workspace manifest tests and live boundary evidence |
| Attempts are append-only | multiple-attempt and final-reference tests |
| Adapter flag matches manifest | CLI mismatch test |
| Task-quality checks are structural | scorer rule tests |
| Windows/macOS replay parity | recorded canonical JSON and SHA-256 comparison |
| Live Codex-to-Claude smoke | Lane A and C run artifacts |

## Completion verification

Run on the authoritative Windows host:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m torc doctor --json
.\.venv\Scripts\python -m torc experiment inspect --run-dir .torc/p1a/replay-a --json
.\.venv\Scripts\python -m torc experiment verify --run-dir .torc/p1a/replay-a --json
.\.venv\Scripts\python -m torc experiment inspect --run-dir .torc/p1a/replay-b --json
.\.venv\Scripts\python -m torc experiment verify --run-dir .torc/p1a/replay-b --json
.\.venv\Scripts\python -m torc experiment inspect --run-dir .torc/p1a/replay-c --json
.\.venv\Scripts\python -m torc experiment verify --run-dir .torc/p1a/replay-c --json
```

Run the equivalent deterministic replay verification on macOS with
`.venv/bin/python`.

Inspect the complete diff and confirm:

- no runtime dependency was added;
- no file outside TORC changed;
- no provider, daemon, server, watcher, or background process was added;
- no oracle or scoring file appears in an agent-visible workspace fixture;
- no absolute host path or credential appears in committed artifacts;
- the P0 demo and verification still pass; and
- observed scope remains below stop thresholds.

Commit coherent batches, push the implementation branch, open a reviewable PR,
and land only after the full gate is satisfied. Preserve failed or contaminated
run evidence outside version control under `.torc/`.
