# Cross-agent collaboration experiment 001

Status: artifact smoke active; three Codex solo cells and three review controls valid

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
   full-bundle native-review control.
4. Codex implements and a fresh low-effort Codex critic receives only the TORC
   claim capsule and editable candidate files. This is the compact-handoff
   control.
5. Codex implements and Claude critiques; the same Codex thread revises only
   after `changes_requested`.
6. Claude implements and Codex critiques; the same Claude session revises only
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

Reviewed workflows also freeze a critic-context mode. The full control receives
the entire visible fixture plus the claim capsule. The compact mode receives
only the claim capsule and hash-labeled editable candidate files; tests, task
prose, harness instructions, and the duplicate diff stay outside target context.
On the frozen design candidate this reduces critic prompt bytes from 15,849 to
4,801 (69.7%) before inference. That is transport-size evidence, not yet a token
or quality result.

The first two live Codex artifact cells passed all visible and hidden tests.
The bug fixture finished in 11.7 seconds with 13,013 input tokens; the refactor
fixture finished in 8.1 seconds with 13,303. These are valid smoke evidence,
not yet a cross-provider comparative result.

Generate a machine-readable evidence summary with:

```text
python experiments/cross-agent-collaboration-001/experiment_report.py
```

The report keeps usage grouped by provider, interface, and attempt validity; it
also emits matched solo-versus-review comparisons when both use the same
fixture, provider, and artifact interface. In the current smoke ledger, eight
excluded direct-tool Codex phases report 851,208 input tokens, while twenty-one
valid artifact phases report 333,315. That large interface gap is diagnostic
evidence from failed harness attempts, not a controlled quality comparison.

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

The matched conditional review (`17-release-policy-codex-artifact-review-conditional`)
also passed after a zero-finding approval and skipped revision. It used 27,779
input tokens and 92.4 seconds of summed worker time: 2.09x the solo input and
1.14x the solo time, with no quality change. Two conditional controls now show
the same pattern: native review roughly doubles input after a correct primary,
but has not yet improved deterministic acceptance.

The first valid design baseline (`20-design-cutover-codex-artifact-solo`) passed
all visible and hidden checks with 14,405 input tokens and 54.6 seconds of worker
time. Runs 18 and 19 remain excluded calibration evidence and their 28,808 input
tokens are reported separately from valid artifact usage.

The matched design review (`21-design-cutover-codex-artifact-review-conditional`)
also passed after a zero-finding approval and skipped revision. It used 30,934
input tokens and 56.8 seconds of summed worker time: 2.15x the solo input and
1.04x the solo time, with no quality change. Across the three current-policy
approval controls, median review overhead is 2.09x input and 1.14x worker time;
none changed deterministic acceptance. The report emits this approval-only
aggregate separately from the earlier forced-revision control.

Six fresh low-effort critics then reviewed the exact same accepted design
candidate. The three compact critics all requested changes and produced six
findings; the three full-bundle critics all approved with no findings. The
compact critics repeatedly identified an unbounded write-pause path and also
raised watermark binding, failed-CAS recovery, and in-flight-write fencing.
Compact median context was 5,036 prompt bytes and 13,371 input tokens versus
16,319 bytes and 16,585 tokens for full context (69.1% and 19.4% lower). Compact
median critic time was 11.6 seconds versus 5.7 seconds (2.02x higher) because it
performed more reasoning and emitted findings. `critic-transport-analysis.json`
records the qualitative adjudication and limitations. This is a strong
feasibility signal on one candidate, not a general causal quality claim.

`critic-transport-series-002-plan.json` preregistered a confirmation on two
independent, hash-pinned flawed baselines. The completed 12-call series produced
the correct changes-requested verdict in every run. Compact and full transports
both had 1.0 median deterministic defect recall on both candidates; compact had
full recall in 6/6 runs and full context in 5/6. A post-hoc audit found that the
single mechanical miss still described the required defect but used synonyms
outside the frozen lexical scorer.

Compact transport cut total explicit prompt bytes by 56.1% but provider-reported
input by only 7.0%, showing that fixed CLI/model context dominates the serialized
payload savings. Compact median completion was 8.0% to 14.2% slower by candidate.
`critic-transport-series-002-analysis.json` preserves the exact aggregate,
scorer caveat, usage checkpoints, and limits on interpretation.

`critic-batch-capability-001` then tested the practical consequence of that
fixed overhead: amortize it across two independent compact critiques. The one
batch call preserved full deterministic recall for both candidates with zero
unsupported findings. It used 14,387 input tokens versus 25,107 across the
matched separate-call medians, a 42.7% reduction, and completed in 15.0 seconds
versus a 23.4-second summed median, a 35.8% reduction. The explicit batch prompt
was larger than the two payloads alone, so the saving came from sharing the
harness context, not more aggressive TORC compression. This is a strong
one-call capability result. `critic-batch-confirmation-004-plan.json` freezes
the next gate as four fresh batches in `AB, BA, BA, AB` order. The exploratory
call is excluded from its estimates, every candidate-position result must have
full recall and zero unsupported findings, and median input must remain at
least 30% below the matched separate-call baseline.

That confirmation stopped after its third call under the frozen quality rule.
All six critiques requested changes, five had full deterministic recall, and
none had an unsupported finding. The sixth cited `x5` and described the right
malformed-input and unknown-action behaviors, but split them across findings
and used `failing closed` rather than one exact lexical scorer term. The strict
failure remains unchanged. Descriptively, the three-call median still reduced
input by 42.8% and completion time by 36.1%. The next gate is a structured
per-claim assessment contract, not another free-text batch repeat.

`critic-batching-design.md` turns those results into the current design:
provider-neutral capsules, two independent reviews per call, honest batch-level
usage accounting, and a claim-assessment matrix before a batch can pass. The
one-call `critic-claim-matrix-capability-001` probe ran after the usage reset.
It correctly assessed all 13 claims, retained full legacy defect recall, linked
all six findings, and cut input by 40.6%. Its 26.1-second completion was 11.6%
above the frozen summed-direct threshold, so the overall capability was
rejected without retry. The exact output expansion points to a smaller claim
link map as a new contract, not a post-hoc relaxation of this result.

`critic-claim-link-capability-002` tested that new contract. All 13 claim
statuses were correct, both candidates retained full defect recall, and every
finding was structurally linked. Compared with separate compact calls, input
fell 42.0% and completion time fell 28.3%. Compared with the verbose matrix,
output fell 41.2% and completion time fell 35.7%. The compact link map passed
all frozen gates; a fresh four-call counterbalanced confirmation is next.

The preregistered native-context follow-up is documented in
`native-context-follow-up.md` and `native-context-series-003-plan.json`. It is
budget-gated because Responses API charges are separate from a ChatGPT
subscription. The first authorized step is a three-call pilot, not the full
series. `native_context_request.py` reconstructs and hashes any of those three
request arms without a network call. `native_context_response.py` validates a
supplied response, checks agent topology and aggregate usage, and scores the
critic result while retaining only hashes of encrypted provider artifacts.
`native_context_pilot_report.py` combines one validated result per arm and
applies the preregistered stop or continue rules.

The cheaper prerequisite is `codex-native-capability-001-plan.json`. It asks
whether the local Codex app-server can expose one child's topology and usage
under the existing Plus allowance. `codex_native_capability.py` builds its
ephemeral, read-only, collaboration-only request without starting Codex.
`codex_native_probe_runner.py` is guarded by the committed plan status, exact
version and content hashes, a clean apparatus, and a fresh usage check; failed
capability evidence is preserved without an automatic retry.
The model-free `--preflight` mode exercises the exact app-server launch,
initialization, and ephemeral thread creation, but deliberately sends no
`turn/start` request.

The one allowed live probe is complete and excluded. It produced the correct
two-finding critique with full deterministic recall, exposed one child's
activity and separate token usage, and returned the child's answer unchanged.
However, the app-server emitted no completed `spawnAgent` item, child settings,
or child prompt. That fails the frozen provenance requirement, so the local
Plus-backed series is not authorized and the call will not be retried.

The cost signal also runs against native delegation as a token-saving strategy.
The child used 11,955 input tokens versus the matched direct compact median of
12,587, but the root used another 38,970 across spawn, wait, and return rounds.
Combined native input was 50,925 tokens (4.05x direct) and completion time was
3.46x the direct median. Recompute the complete audit without a model call:

```text
python experiments/cross-agent-collaboration-001/codex_native_probe_audit.py
```

`codex-native-capability-001-analysis.json` contains the deterministic result.
The separately billed Responses API pilot remains available only if measuring
the hosted opaque transport is worth its own budget; the local result is not a
reason to expect lower end-to-end usage.

The separate `claude-critic-capability-001` check also completed without model
inference. Claude Code 2.1.285 reported an active Pro login, initialized the
tool-free WSL harness, and then returned
`oauth_not_allowed_for_organization`. Provider usage and cost were both zero.
This confirms that `claude -p` is a viable TORC adapter shape, but the current
organization policy still blocks the cross-provider quality experiment. No
retry is allowed until that external policy changes or an API budget is
explicitly authorized.

## Implemented smoke apparatus

- `fixture_control.py` verifies the hash-pinned fixture and oracle trees,
  stages only agent-visible files into a new Git repository, and scores visible
  and hidden tests separately.
- `worker_runner.py` builds fresh-session Codex and Claude Code commands,
  verifies the installed harness version, records raw JSONL, normalizes supplied
  token counters, and measures startup, first-output, and completion time.
- `critic_replay.py` reconstructs a committed primary artifact, refuses a
  workspace-hash mismatch, and sends that exact candidate through one selected
  critic transport with a single model call. It can also reconstruct a
  hash-pinned fixture baseline without a primary model call.
- `critic_probe_score.py` fails closed on candidate or worker-control drift and
  scores critic verdict, preregistered defect-area recall, unsupported findings,
  usage, and timing without model judgment.
- `critic_transport_report.py` deterministically rescores the frozen confirmation
  series, enforces its counterbalanced order, and summarizes progress and costs.
- `codex_usage_snapshot.py` reads a sanitized, read-only local Codex usage
  snapshot and returns exit status 3 when the configured stop threshold is met.
- `codex_native_probe_audit.py` proves the preserved native capability outcome
  and compares its quality, usage, and timing with the matched direct compact
  baseline without making a model call.
- `critic_batch_probe.py` reconstructs two hash-pinned compact capsules, runs
  one guarded tool-free critic batch, and scores each nested critique against
  its own frozen defect oracle.
- `critic_batch_series.py` enforces the four-run counterbalanced confirmation,
  stops on the first quality or execution failure, and produces its aggregate
  report without another model call.
- `critic_batch_confirmation_audit.py` reproduces the stopped confirmation's
  strict outcome, descriptive cost, and lexical-scorer sensitivity without
  changing the preregistered score.
- `critic_claim_matrix_probe.py` requires every reviewable capsule claim to be
  explicitly assessed and linked to same-claim findings in one guarded batch.
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

Plan a one-call critic replay without creating a run directory:

```text
python experiments/cross-agent-collaboration-001/critic_replay.py \
  --fixture design-cutover-plan \
  --source-run experiments/cross-agent-collaboration-001/runs/smoke-001/22-design-cutover-codex-artifact-review-compact \
  --critic-provider codex \
  --critic-context full-visible-bundle-v1
```

For the planned confirmation series, replace `--source-run ...` with
`--source-baseline`. After a baseline replay is complete, score it with:

```text
python experiments/cross-agent-collaboration-001/critic_probe_score.py \
  --run-dir <immutable-run-directory> \
  --candidate refactor-baseline-v1

python experiments/cross-agent-collaboration-001/critic_transport_report.py

python experiments/cross-agent-collaboration-001/codex_usage_snapshot.py \
  --stop-threshold 75
```

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

The first design-fixture solo (`18-design-cutover-codex-artifact-solo`) is also
excluded. It exposed an underspecified representation check: the hidden oracle
required `compare_and_swap` while the visible task accepted a descriptive mode,
and the worker returned the equivalent `compare-and-swap`. The task now freezes
the exact enum before any comparative design-fixture run. The next calibration
(`19-design-cutover-codex-artifact-solo`) is excluded because the oracle required
extra constraint labels on specific steps even though the candidate attached
them to the actual controlling operations. Those reference-answer annotations
were relaxed before the next run; the safety ordering and coverage checks remain.

The first Claude smoke also stopped before inference and is excluded. WSL
resolved `claude` to a Windows-mounted npm shim, so no Linux sandbox was
available; the provider recorded zero tokens. The launcher now rejects mounted
Windows shims during planning. Claude cells require a native Linux Claude Code
installation and its WSL sandbox dependencies (`bubblewrap` and `socat`).
