# Cross-agent collaboration experiment 001

Status: smoke apparatus implemented; no live runs completed

Scope envelope: `scope-envelope.json`

## Question

Can TORC improve completed work by carrying governed continuity between Codex
and Claude while keeping context, elapsed time, and operator effort below a
duplicated two-agent workflow?

This experiment evaluates workflows, not a universal ranking of model brands.
The useful decision is which substrate fits a task phase and whether a foreign
critic adds enough value to justify its cost.

## Ownership boundary

The experiment runner or the Lugos orchestrator launches each harness. TORC
records fit evidence, compiles the handoff capsule, checks reconstruction, and
governs lineage authority. TORC does not become the provider router or worker
orchestrator.

The single-worker launcher therefore lives in this experiment directory, not
in the `torc` package. It requires an explicit `--execute` switch before it can
make a model call.

## Candidate workflows

1. Codex completes the task alone.
2. Claude completes the task alone.
3. Codex implements, Claude critiques, and the same Codex thread revises.
4. Claude implements, Codex critiques, and the same Claude session revises.

The primary and reviser use the same frozen high-capability settings. The
foreign critic begins at low effort. A later series may vary critic effort only
after the workflow comparison identifies a useful cross-agent effect.

## Continuity paths

- A same-provider resume or compacted context remains provider-native.
- A cross-provider review receives a TORC claim capsule containing the task,
  responsibility, active claims, and short claim identifiers.
- Full source references, authority state, hashes, and acceptance evidence stay
  in TORC's control envelope and do not consume target context.
- The critic cites claim identifiers. TORC resolves those identifiers to
  canonical sources and rejects unknown or stale identifiers.

Native opaque compaction is a separate same-provider baseline. It cannot be
used as the portable Codex-to-Claude representation.

## Calibration fixtures

Use four repository-backed tasks with deterministic acceptance evidence:

1. A bug fix whose obvious solution violates a hidden regression test.
2. A refactor constrained by an architectural decision and a superseded path.
3. A security or release review containing one subtle blocking interaction.
4. A design decision with competing options, explicit constraints, and a
   required implementation plan.

Each task is hash-pinned and staged in an isolated Git workspace. Agent-visible
inputs exclude hidden tests, scoring rules, other agents' output, and the
fixture oracle.

## Measures

- visible and hidden test results;
- required-constraint and commitment compliance;
- valid claim citations and unsupported-claim count;
- defects introduced, unresolved findings, and unauthorized changes;
- input, cached-input, cache-write, reasoning-output, and output tokens;
- time to first output, completion time, and subprocess startup time;
- operator corrections and failed attempts; and
- final diff size and deterministic artifact verification.

Model judgment may explain qualitative differences, but it cannot override
tests, policy violations, invalid provenance, or authority checks.

## Staged run plan

1. **Apparatus smoke:** two fixtures and all four workflows. Preserve failures;
   make no comparative claim.
2. **Calibration:** four fixtures and all four workflows, one pass each. Use the
   result only to select useful workflows and remove ceiling-saturated tasks.
3. **Handoff comparison:** rerun useful cross-agent workflows with compiled and
   claim-capsule handoffs in matched, randomized order.
4. **Confirmation:** at least six independent fixtures and two repeats for the
   surviving workflow pair, split across usage windows if needed.

Stop before confirmation if the foreign critic does not improve deterministic
task quality, or if the same improvement is available from the primary agent's
native review at lower cost.

## Runtime controls

- Claude uses `-p`, structured streaming output, an explicit model and effort,
  a bounded process timeout, restricted tools, and an isolated workspace.
- Codex uses non-interactive structured output or the app-server protocol with
  equivalent model, effort, sandbox, and workspace controls.
- Internal subagent spawning is disabled for the first comparison so the unit
  under test is the explicit Codex/Claude workflow.
- Live runs record usage before synthesis. A root-agent summary is not part of
  the scored target output.

## Implemented smoke apparatus

- `fixture_control.py` verifies the hash-pinned fixture and oracle trees,
  stages only agent-visible files into a new Git repository, and scores visible
  and hidden tests separately.
- `worker_runner.py` builds fresh-session Codex and Claude Code commands,
  verifies the installed harness version, records raw JSONL, normalizes supplied
  token counters, and measures startup, first-output, and completion time.
- `fixtures/bug-hidden-regression` starts with both visible and hidden failures.
- `fixtures/refactor-superseded-path` passes its visible behavior tests while a
  hidden structural test catches the superseded production path.

Verify the fixtures without making a model call:

```text
python experiments/cross-agent-collaboration-001/fixture_control.py verify
```

Running `worker_runner.py` without `--execute` prints the resolved command,
prompt hash, and installed harness version without starting an agent. An actual
run additionally requires an output directory outside the worker workspace and
the exact version returned by the dry plan through
`--expected-harness-version`.

`workflow_runner.py` plans or executes one fixture/workflow pair at a time. A
solo workflow makes one model call. A cross-agent workflow makes three calls:
the primary implementation, a low-effort foreign critique, and a same-session
primary revision. The committed manifest contains a balanced smoke order, but
the runner never starts the whole matrix implicitly.

```text
python experiments/cross-agent-collaboration-001/workflow_runner.py \
  --fixture bug-hidden-regression --workflow codex-claude
```

Token counters remain separated by phase and provider. Because Codex and Claude
use different tokenizers and cache-accounting rules, the apparatus does not
manufacture a cross-provider total.

The first attempted Codex smoke was retained but excluded: its noninteractive
approval policy blocked every shell command, and built-in app resources
contaminated context usage. `runs/smoke-001/01-bug-codex-solo/disposition.json`
records the failure and corrective action.
