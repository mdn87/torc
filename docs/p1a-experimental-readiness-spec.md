# P1a Experimental Readiness Specification

Status: accepted for implementation planning

Scope envelope: `docs/p1a-scope-envelope.json`

## Decision

Split the former P1 milestone into:

- **P1a, experimental readiness**: build the smallest repeatable apparatus that
  can run equivalent source-to-target transitions through compiled-prompt,
  native-persistence, and TORC lanes.
- **P1b, comparative experiment**: use the frozen P1a apparatus to measure
  continuity, task quality, context, correction, provenance, and overhead.

P0 established internal correctness for a synthetic handoff. It did not
establish external validity with real agents. P1a closes that testability gap;
it does not claim TORC is better than either baseline.

## Outcome

P1a is complete when an operator can select one versioned fixture and produce
three structurally comparable run directories with:

- a frozen source state and fixture hash;
- a lane-specific continuity payload;
- source and target harness evidence;
- a structured target reconstruction;
- deterministic scoring inputs and output;
- timing, context-size, and operator-step measurements;
- an immutable artifact manifest; and
- a clear accepted, rejected, unavailable, or failed disposition.

At least one real Codex-to-Claude Code smoke transition must complete through
the compiled-prompt and TORC lanes. Native persistence is run only when an
existing harness supplies an equivalent continuation path. If it does not,
P1a records `unavailable` with evidence instead of inventing a substitute.

## Platform matrix

| Component | Windows windows-primary and windows-secondary | macOS macos-primary and macos-secondary |
|---|---|---|
| TORC experiment library and CLI | Required | Required |
| Lane C TORC state and artifact hashing | Required | Required |
| Deterministic replay adapters | Required | Required |
| Codex source adapter | Authoritative P1a smoke on windows-primary | Contract verification where installed |
| Claude Code target adapter | Authoritative P1a smoke on windows-primary | Contract verification where installed |
| P1a automated test suite | Authoritative on windows-primary | Separate verification required before P1b |

Repository-relative paths are authoritative. Windows commands use PowerShell
and `.venv\Scripts\python`; macOS commands use a POSIX shell and
`.venv/bin/python`. The artifact layout, JSON bytes, hashes, and score output
must be identical across platforms for the deterministic replay fixture.

## Scope

P1a includes:

1. One versioned, redistributable experiment fixture stored in this repository.
2. One adapter-neutral experiment manifest and artifact layout.
3. A Codex source adapter and a Claude Code target adapter that use existing,
   operator-authorized harness entrypoints.
4. Deterministic replay adapters for contract and failure testing without live
   model calls.
5. Lane materializers for compiled prompt, native persistence when available,
   and TORC.
6. Structured reconstruction capture and deterministic scoring.
7. Idempotent resume after interruption at defined stage boundaries.
8. Inspect and verify commands for experiment runs.

The production-parity vertical slice is due before two elapsed implementation
hours: one replay fixture must complete prepare, source capture, payload freeze,
target reconstruction, deterministic scoring, and artifact verification for
the compiled-prompt and TORC lanes without a live harness.

P1a does not include:

- comparative performance conclusions;
- provider SDK or direct provider API calls;
- model selection, routing, or credential custody;
- an always-on process, daemon, watcher, queue, or network service;
- cross-host authority or synchronization;
- Autowork, Sulis, Bran, Omniroute, agent-mail, HUD, or parent Lugos changes;
- production permissions, sandboxing, or tool grants;
- rollback, branching, lineage merging, or P2 contract integration;
- a generic plugin system or support for more than the two named live adapters.

## Experiment fixture

P1a owns one controlled fixture under `examples/p1a-fixture/`. It represents a
bounded implementation-to-independent-review transition and must contain:

- settled decisions;
- active commitments;
- hard constraints and prohibitions;
- unresolved work;
- uncertainties;
- evidence references;
- one plausible but explicitly superseded direction; and
- an oracle describing required continuity without prescribing review findings.

The fixture is derived from TORC-owned material so it can be committed without
copying private transcripts or third-party content. The manifest pins every
fixture file by relative path and SHA-256. P1b may select a real Lugos task only
after the P1a gate passes; that selection receives its own frozen manifest.

## Three experiment lanes

All lanes receive the same fixture bytes, source assignment, target assignment,
harness versions, model settings, effort, tool policy, and scoring oracle. The
continuity mechanism is the only intentional difference.

### Lane A: compiled prompt

The source adapter emits one structured prompt using the same required
continuity field names as the oracle. The prompt and referenced fixture files
are the complete continuity input to a fresh target activation. No TORC
authority state is presented to the target.

### Lane B: native persistence

The runner invokes the closest unmodified resume, checkpoint, or continuation
feature supplied by the selected harness. P1a records the harness feature,
session relationship, and any automatically restored context. It adds no TORC
projection or compiled handoff prompt.

If no equivalent source-to-target continuation exists, the lane disposition is
`unavailable`. An unavailable lane is not scored and cannot be silently
replaced by a different mechanism.

### Lane C: TORC

The source adapter appends a checkpoint, TORC compiles a target projection and
freezes a handoff snapshot, and the target adapter returns a structured
reconstruction. TORC evaluates continuity requirements and transfers its local
lineage lease only after acceptance.

TORC authority remains lineage metadata. The target harness still requires a
separately authorized assignment and tool policy.

## Artifact contracts

P1a adds version 1 JSON Schemas for:

- `experiment-manifest`: fixture, lanes, harness identities, assignments,
  controlled settings, oracle reference, and pre-registered measures;
- `experiment-run`: immutable stage receipts, timestamps, lane disposition,
  adapter evidence, operator interventions, and artifact references;
- `continuity-payload`: the exact lane-specific material delivered to the
  target, with byte and word counts;
- `score-report`: field-level results, contradictions, provenance, context,
  timing, operator steps, and scorer version; and
- `artifact-manifest`: relative paths, media types, byte sizes, and SHA-256
  values for the immutable run evidence.

These are local file and library contracts, not a transport protocol. JSON that
contributes to a hash uses TORC canonical serialization. Raw credentials,
environment dumps, authentication tokens, and unrestricted transcripts are
forbidden artifacts.

## Adapter boundary

Adapters translate between a named harness and the experiment contracts. They
do not select a model, grant permissions, broaden an assignment, decide
acceptance, score results, or mutate canonical history directly.

The narrow adapter operations are:

1. `probe`: report harness version and whether the required source, target, or
   native-persistence capability is available.
2. `capture_source`: run or replay the frozen source assignment and return the
   allowlisted source checkpoint fields.
3. `start_target`: start a separately authorized fresh target activation with
   the lane payload.
4. `collect_target`: return the target reconstruction, task output references,
   usage evidence when supplied by the harness, and exit disposition.

Live adapters may invoke existing local harness CLIs. TORC itself performs no
provider request and stores no harness credential. Tests use replay adapters;
the automated suite must not require network access.

## Run evidence and idempotency

One run directory contains immutable artifacts and stage receipts. Lane C may
contain a normal P0 TORC state directory; the experiment runner adds no second
database or mutable workflow store. Completion is derived from verified stage
receipts:

```text
created -> source_captured -> payload_frozen -> target_completed
        -> reconstruction_recorded -> scored -> verified
```

A stage command writes its output and receipt atomically, and the receipt
references its input artifact hashes. Re-running a completed stage with
identical inputs returns the existing output. Different inputs require a new
run identifier. A failed or interrupted target does not transfer TORC
authority and may be retried only as a new target attempt linked to the
original frozen payload.

P1a does not add a durable workflow state machine or background process. Stages
advance only through an operator-invoked CLI command.

## CLI surface

The planned stable surface is:

```text
torc experiment prepare --manifest <path> --lane <compiled-prompt|native-persistence|torc> --run-dir <path> --json
torc experiment source --run-dir <path> --adapter <codex|replay> --json
torc experiment target --run-dir <path> --adapter <claude-code|replay> --json
torc experiment score --run-dir <path> --json
torc experiment inspect --run-dir <path> --json
torc experiment verify --run-dir <path> --json
```

The live `source` and `target` commands require explicit operator invocation.
They must print the harness command plan and artifact destinations before the
harness is started. P1a does not add a command that automatically runs all live
lanes.

## Scoring

The scorer consumes only frozen artifacts and the pre-registered oracle. It
does not call a model. P1a proves deterministic scoring; P1b interprets the
results.

Required measures are:

| Measure | P1a calculation |
|---|---|
| Required commitment retention | Exact normalized set recall |
| Hard-constraint retention | Exact normalized set recall |
| Settled-decision accuracy | Supported items divided by asserted items |
| Unresolved-work accuracy | Exact normalized set recall |
| Inherited versus new inference | Correctly labeled assertions divided by all assertions |
| Contradiction count | Oracle-declared contradiction rules |
| Provenance recoverability | Assertions with valid source references divided by assertions requiring provenance |
| Context delivered | UTF-8 bytes and deterministic word estimate |
| Preparation and acceptance overhead | Monotonic elapsed duration when available, plus stage timestamps |
| Operator correction count | Explicit interventions appended to the run record |
| Task output quality | Pre-registered fixture checks only; no model judge in P1a |

The scorer version and normalization rules are pinned in the manifest.
Thresholds for P1b must be frozen before its first live comparative run.

## Failure behavior

- Invalid fixture or manifest hashes stop before source capture.
- An unavailable adapter produces an evidence-bearing `unavailable` result.
- Source failure creates no continuity payload.
- Payload failure creates no target activation.
- Target failure or malformed reconstruction leaves TORC authority unchanged.
- Rejection records failed continuity fields and leaves source authority intact.
- Score or verify failure never changes the underlying handoff disposition.
- An artifact hash mismatch fails the run and identifies the smallest invalid
  file or link.

## Verification

The automated P1a suite must prove:

1. All new schema examples validate.
2. The same manifest and replay evidence produce byte-identical payloads,
   scores, and artifact hashes on repeated runs.
3. Each lane receives the same fixture hash and controlled settings.
4. Lane A contains no TORC authority artifact.
5. Lane B is either native and evidenced or explicitly unavailable.
6. Lane C cannot transfer authority before accepted reconstruction.
7. Retry with identical stage inputs is idempotent.
8. Retry with changed inputs requires a new run.
9. Interrupted or failed target attempts preserve source authority.
10. Artifact, payload, reconstruction, and score tampering is detected.
11. Credentials and unrestricted environment data are absent from artifacts.
12. The deterministic replay path passes on Windows and macOS.

The live readiness smoke must additionally prove:

1. Codex source capture completes under a bounded source assignment.
2. A fresh Claude Code target receives only the selected lane payload and
   fixture references.
3. Compiled-prompt and TORC lanes both produce parseable reconstruction and
   verified run artifacts.
4. Native persistence is either completed through an existing feature or
   recorded unavailable with the adapter probe.
5. No manual edit is needed between payload freeze and scoring.

## P1a gate

P1a passes only when:

- the full automated suite passes on Windows;
- deterministic replay verification separately passes on macOS;
- one real Codex-to-Claude Code smoke run completes for lanes A and C;
- every completed run verifies with no artifact or provenance error;
- interruption and idempotent resume evidence is captured;
- the operator performs no more than eight documented steps per live lane; and
- the fixture, adapters, schemas, scorer, and exact P1b run procedure are frozen.

Passing this gate authorizes P1b experiment execution, not P2 integration.

## Stop and scope-change conditions

Stop for operator approval if implementation requires:

- a daemon, watcher, queue, broker, server, or custom transport;
- direct provider API integration or credential handling;
- parent Lugos edits or a cross-host production dependency;
- more than the two named live adapters;
- model-based judging;
- changes to Autowork assignment authority or harness permissions;
- a durable experiment store beyond the existing Lane C TORC database;
- more than two design-review rounds; or
- observed scope at twice an estimate in `docs/p1a-scope-envelope.json`.

At 1.5 times an estimate, simplify the apparatus before adding capability.

## Spec self-review

- The user-visible outcome is one repeatable, inspectable experiment apparatus.
- P1a makes no comparative claim and cannot authorize P2.
- The three lanes differ only in continuity mechanism.
- Native persistence unavailability is explicit rather than papered over.
- Harness adapters translate; they do not route, authorize, score, or own state.
- Windows and macOS verification lanes are separately stated.
- Persistent and background runtime processes remain zero.
- Failure, retry, authority, credential, and artifact boundaries are explicit.
