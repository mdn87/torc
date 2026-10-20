# Live continuation comparison readiness

Status: **not ready to launch**. This apparatus advances the
[active readiness plan](../../docs/plans/2026-10-20-live-comparison-readiness.md).
The earlier [offline analyzer](../../docs/experiments/session-continuation-001/comparison-preparation.md)
remains a draft-only consumer of supplied evidence. No model trial has run.

## Repository-task workloads

The two workloads replay actual TORC engineering changes, using the complete
repository tree at `a798bbc4c45527952510a5f3d239f49c5b67a2de`:

| Workload | Requested implementation | Hidden acceptance |
|---|---|---|
| `capsule-context` | Read-only bindings around existing P5 capsules and recovery reports | Exact bytes and pins, preserved holds, unchanged store, real P3 staleness |
| `whole-task-usage` | Complete attempt/request accounting | Failures and fallbacks, missing usage, cumulative/delta semantics, exclusions and allocation |

These are historical repository tasks, not tiny mechanical scoring exercises.
They are still only pilot workloads: two related changes in one repository do
not establish representative workload sampling or general effectiveness. Public
briefings are operator-authored retained decisions, not exported model history.
The native seed/session has not been created. Future cohorts must record these
limitations and must not label the histories as naturally observed interruptions.

The historical implementation and hidden tests come from
`9d96039a0e1fefecfc75948fc31464dc6706fee9`. Staging uses Git objects, not the
current worktree, so later fixes and unrelated local changes cannot leak into a
worker's snapshot. It exports no `.git` directory, later implementation, or hidden
test. All strategies receive identical task/rules files and the same snapshot.
Only the declared module is editable in the final candidate. There is no
required patch text, exact tool sequence or answer-checking tool gate.

From the repository root:

```sh
workload_root=$(mktemp -d)
python3 experiments/session-continuation-001/workloads.py stage capsule-context \
  --destination "$workload_root/candidate"
python3 experiments/session-continuation-001/workloads.py prepare-score capsule-context \
  --candidate "$workload_root/candidate" --destination "$workload_root/scoring"
```

`prepare-score` checks the entire protected tree and rejects symlinks before
copying anything. It freezes the candidate hash and a separate scoring copy,
then adds hidden tests only to that copy. The returned job contains no arm or
context identity. The worker workspace stays unchanged. The execution owner
must first establish that the worker has stopped; a snapshot hash is not proof
of process termination. Scores must be bound to the returned candidate hash.

**Preparing a scoring job does not execute it or qualify isolation.** Do not run
untrusted candidate code with the root session's privileges. The isolated scorer
must be separately qualified, keep the arm/context/usage records unavailable,
and execute the pinned test command without hidden feedback to workers. The
helper's `verify-references` command executes only trusted pinned historical
implementations and deliberately defective controls, never a supplied candidate.

## Reproduce acceptance validation

```sh
reference_root=$(mktemp -d)
python3 experiments/session-continuation-001/workloads.py verify-references \
  --destination "$reference_root/full" > "$reference_root/full-report.json"
python3 experiments/session-continuation-001/workloads.py verify-references --summary \
  --destination "$reference_root/summary" > "$reference_root/summary.json"
diff -u experiments/session-continuation-001/reference-report.json \
  "$reference_root/summary.json"
```

The [retained summary](reference-report.json) pins source and candidate hashes.
The full receipt retains raw pytest output; its temporary paths and timings are
intentionally excluded from the deterministic summary. Both baselines fail;
both historical implementations pass. A stale-head mutation in the capsule
task and cumulative-counter summation in the accounting task both fail.
Protected-source changes reject before scoring. This proves useful acceptance
discrimination, not live worker performance or independent scorer isolation.

## Task-specific context preparation

`contexts.py` builds both deterministic context arms from each public task brief
and its retained investigation. It uses the existing capsule derivation and
verifier, checks exact delivered bytes and actual lineage head, and records the
same recovery-report hash for both arms. The private operator-authored lineage
is preparation state, not a fabricated native session. Its held recovery report
has unknown quiescence and grants no retry or receiving authority.

```sh
context_root=$(mktemp -d)
python3 experiments/session-continuation-001/contexts.py replay \
  --destination "$context_root/prepared" > "$context_root/report.json"
diff -u experiments/session-continuation-001/contexts-report.json "$context_root/report.json"
```

The [retained context report](contexts-report.json) is deterministic and pins
source code, workspace and arm assets. To verify a prepared task, run
`contexts.py verify --root <prepared-task> --expected-manifest-id <external-pin>`.
The complete manifests and private preparation state remain under the chosen
output directory. They must not be exposed wholesale to a worker.

These are byte counts, **not measured token savings**:

| Task | Compiled context / prompt bytes | Capsule context / prompt bytes |
|---|---:|---:|
| Capsule context integration | 2728 / 3999 | 2969 / 4240 |
| Whole-task accounting | 2620 / 3893 | 2953 / 4226 |

The capsule is larger than the plain compiled baseline here. The capsule budget
omits the uncertainty section on the first task; all arms retain access to the
same complete public brief. Native arms, task success, elapsed time, repeated
investigation and whole-task usage have not been measured.

## Current lane evidence

The initial [qualification attempt](qualification-report.json) inspected the
adjacent development checkout at `27006c5`, which rejected Codex 0.163.0.
That was not the operator-configured controller. The configured controller at
`7699b3c` already carries an untracked macOS 0.163.0 policy from October 18.
The qualifier now requires an explicit `--autowork-source` path.

Two fresh failures from the configured controller are retained:

- [Project virtualenv interpreter](configured-qualification-report.json): the
  sandbox could not execute the home-directory Python. Candidate access failed;
  apparent negative effects were not independent evidence because the commands
  never started.
- [System interpreter](system-python-qualification-report.json): candidate read
  and write worked, but writing outside the candidate succeeded. This was a real
  workspace isolation failure, not a remote service diagnosis.

The operator explicitly expanded scope to the two Autowork fixes. Autowork's
workspace-write projection inherited `:workspace`, retaining shared temporary
write access. Starting from `:read-only` with the existing explicit candidate
write grant blocks the same outside sentinel and allows candidate writes.
The [fixed qualification](fixed-qualification-report.json) passes the existing
model-free macOS effect checks and retains source hashes, executable identity,
policy hash and usage missingness. Its attestation is short-lived evidence of
that run, not a reusable grant. No credential protections were relaxed.

Reproduce on macOS with a system interpreter readable under the policy:

```sh
python3 experiments/session-continuation-001/qualification.py \
  --autowork-source <explicit-controller-checkout>/autowork > qualification.json
```

The qualifier pins the inspected capability-source versions and refuses model
execution. The Autowork change also adds format-only Codex 0.163.0 raw counters,
including cache writes in new immutable record versions. Ambiguous completions
and missing fields remain unknown. Derived totals remain null for 0.163.0 until
counter semantics are independently established. Neither a parser unit test nor
a model-free sandbox probe qualifies live whole-task telemetry or native resume.

## Readiness still required

| Requirement | Current evidence |
|---|---|
| Real repository tasks and hidden acceptance | Baseline/reference/defect controls pass |
| Exact worker/scorer input separation | Staging implemented; scorer runtime still unqualified |
| Equal-access compiled and verified capsule contexts | Implemented with reproducible exact-byte verification |
| Execution sandbox | Fixed model-free macOS workspace-write effects pass |
| Native session creation/resume and cache-state evidence | Not run; needs authorized lane and cap |
| Every attempt, timeout, failure and fallback captured | Offline accounting exists; live capture/coverage qualification remains |
| Counter semantics | 0.163.0 format retained; totals and cross-request semantics unqualified |
| Repeated-investigation and operator-effort observations | [Draft blinded rubric](investigation-rubric.md); collection integration remains |
| Operator lane/resource ceiling | Pending; no live authority inferred |
| Frozen live preregistration and launch procedure | Incomplete pending these gates |

## Verified repository state

[Readiness report](readiness-report.json): still not ready for live comparisons.
Autowork fix `79e701c1e5c1fc2b44029a3b4be99c17b0693344` is applied to the
configured controller, preserving its local provider policy. A fresh controller
qualification passes; existing MCP processes were not restarted. No model calls,
credential changes, hooks, retry coordinator or parent submodule-pointer update
were performed.

TORC: 857 tests pass, Ruff passes, doctor has no missing paths, and demo/verify
checks seven artifacts without errors. Context replay matches the retained
report. Autowork: 767 focused tests pass with three opt-in skips; the standalone
sandbox regression also passes. Its broader suite remains non-green: 65 failures
against 136 in the untouched baseline, with no introduced failed test IDs.
Both repositories have valid quick audit receipts. The Autowork commit retains
the detailed test inventories in `autowork/docs/torc-readiness-verification.json`.
No general effectiveness or token-saving conclusion is warranted.
