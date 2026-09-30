# Cross-agent collaboration experiment 001

Status: apparatus design; no live runs authorized

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

Each task is pinned to one commit and staged in isolated worktrees. Agent-visible
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
  bounded turns, restricted tools, and an isolated workspace.
- Codex uses non-interactive structured output or the app-server protocol with
  equivalent model, effort, sandbox, and workspace controls.
- Internal subagent spawning is disabled for the first comparison so the unit
  under test is the explicit Codex/Claude workflow.
- Live runs record usage before synthesis. A root-agent summary is not part of
  the scored target output.
