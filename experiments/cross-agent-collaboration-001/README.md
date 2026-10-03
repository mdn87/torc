# Cross-agent collaboration experiment 001

Status: artifact smoke active; three Codex solo cells and two review controls valid

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
3. Codex implements and a fresh low-effort Codex critic reviews the TORC capsule.
   The same primary thread revises only after `changes_requested`. This is the
   native-review control.
4. Codex implements and Claude critiques; the same Codex thread revises only
   after `changes_requested`.
5. Claude implements and Codex critiques; the same Claude session revises only
   after `changes_requested`.

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

## Worker interface

The smoke series uses `patch-artifact-v1`. The runner serializes only the
agent-visible fixture files, their hashes, and a frozen editable-path allowlist.
Workers receive that bundle in their prompt with local tools disabled and return
complete UTF-8 replacements in a small JSON contract. The runner validates path,
shape, uniqueness, and size before applying replacements and running tests.

This interface keeps file authority and test execution outside both providers,
avoids host-specific nested tool routing, and makes the portable context bytes
directly measurable. It is an experiment transport, not a TORC provider router.

The first two live Codex artifact cells passed all visible and hidden tests.
The bug fixture finished in 11.7 seconds with 13,013 input tokens; the refactor
fixture finished in 8.1 seconds with 13,303. These are valid smoke evidence,
not yet a cross-provider comparative result.

Generate a machine-readable evidence summary with:

```text
python experiments/cross-agent-collaboration-001/experiment_report.py
```

The report keeps usage grouped by provider and interface and emits matched
solo-versus-review comparisons when both use the same fixture, provider, and
artifact interface. In the current smoke ledger, eight excluded direct-tool
Codex phases report 851,208 input tokens, while eight valid artifact phases
report 121,014. That large interface gap is diagnostic evidence from failed
harness attempts, not a controlled quality comparison.

The first native-review control (`14-bug-codex-artifact-review`) also passed,
but its primary had already passed before a zero-finding approval. The forced
no-op revision raised reported input from 13,013 to 54,396 tokens and summed
worker time from 11.7 to 27.4 seconds on the matched bug fixture. This single
smoke result motivates skipping revision after an approval; it is not a general
quality or latency estimate.

The conditional control (`15-refactor-codex-artifact-review-conditional`)
stopped after approval and passed all tests with 27,024 reported input tokens
and 12.0 seconds of summed worker time. The matched solo used 13,303 tokens and
8.1 seconds, so review cost about 2.0x input and 1.5x time without improving this
ceiling-saturated fixture. Harder calibration fixtures are required to measure
whether review earns that overhead.

The release-policy solo baseline (`16-release-policy-codex-artifact-solo`)
passed all 17 visible and hidden checks with 13,278 input tokens. Its 81.2-second
worker time and 2,896 reasoning tokens show that the compact prompt size stayed
stable while the harder task moved cost into reasoning and output.

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
- `fixtures/release-policy-interaction` passes visible behavior tests while
  hidden security checks cover path normalization, segment boundaries, rename
  sources, constant-time digest comparison, and fail-closed malformed inputs.
- `fixtures/design-cutover-plan` passes visible schema checks while hidden
  acceptance checks require the only feasible strategy, a safe dependency
  order, atomic cutover evidence, and authority-preserving recovery behavior.

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
solo workflow makes one model call. A reviewed workflow makes two calls when
the critic approves and three when it requests changes: primary implementation,
low-effort critique, and only then a same-session primary revision. The
committed manifest contains a balanced smoke order, but the runner never starts
the whole matrix implicitly.

```text
python experiments/cross-agent-collaboration-001/workflow_runner.py \
  --fixture bug-hidden-regression --workflow codex-claude
```

Token counters remain separated by phase and provider. Because Codex and Claude
use different tokenizers and cache-accounting rules, the apparatus does not
manufacture a cross-provider total.

The first two attempted Codex smokes were retained but excluded. The first used
an unsuitable noninteractive approval policy and inherited built-in app
resources. The second fixed those controls but still mixed the legacy sandbox
setting with the host's permission-profile system, so shell reads remained
blocked. Each run has a `disposition.json`. The current launcher clears
parent-session controls, disables daemon reuse, selects an explicit
`workspace-write` or `read-only` sandbox, and performs a model-free access
preflight before spending usage. Native Windows runs also freeze the
`unelevated` sandbox backend so ignoring unrelated user configuration does not
erase the platform implementation.

Later Codex retries proved that the nested host still rejects every direct
worker command even when the standalone stable CLI reports a writable managed
profile and every filesystem preflight passes. Those immutable attempts remain
excluded. Further smoke cells use the tool-free artifact interface instead of
spending usage on the same host-specific failure.

The first Claude smoke also stopped before inference and is excluded. WSL
resolved `claude` to a Windows-mounted npm shim, so no Linux sandbox was
available; the provider recorded zero tokens. The launcher now rejects mounted
Windows shims during planning. Claude cells require a native Linux Claude Code
installation and its WSL sandbox dependencies (`bubblewrap` and `socat`).
