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

## Current lane evidence

Installed versions observed on this host are Claude Code `2.1.296` and Codex
`0.163.0`. The current Autowork checkout is
`27006c5a2ee60693796a0a3177e9dbbd15c981fc`. Its provider-safety registry does not
accept that Codex version. The [retained qualification attempt](qualification-report.json)
failed with `ProviderSafetyError: unsupported Codex version '0.163.0'` before
the sandbox effect checks, with zero model calls. This does not establish a Mac
runtime fault, remote host/service fault, or a passed workspace isolation check.

Reproduce the bounded qualification attempt on this macOS host:

```sh
python3 experiments/session-continuation-001/qualification.py > qualification-report.json
```

Exit 1 and a failed JSON report are expected with the current provider policy.
The script pins the inspected Autowork capability-source hash, refuses other
platforms, and adds a refusal for model execution. It uses the existing owner's
deterministic macOS sandbox route, including its strict-config negative control;
it does not replace provider policy or credential isolation. Source changes
require inspecting that route again before updating the pin. No provider-policy
file, credential, parent repository file, host service or hook was changed.

The older October 18 read-only attestation is historical evidence, not a current
workspace-write or resume qualification. The cross-agent experiment's existing
launcher also needs a new qualified integration for this task: it inherits
environment state, selects one usage snapshot and can reject session identity
before saving raw output. Its frozen implementation has not been modified here.

## Readiness still required

| Requirement | Current evidence |
|---|---|
| Real repository tasks and hidden acceptance | Implemented; baseline/reference/defect controls pass |
| Exact worker/scorer input separation | Implemented in staging; runtime read isolation unqualified |
| Task-specific equal-access compiled and verified capsule contexts | Common task/history inputs prepared; context compilation remains |
| Qualified execution and scoring sandbox | Blocked at current Codex provider-version admission |
| Actual native session creation/resume and cache-state evidence | Not run; requires authorized lane and resource cap |
| Complete usage across attempts, timeouts, failures and fallbacks | Accounting exists; live exporter/capture qualification remains |
| Repeated-investigation and operator-effort observations | Rubric and collection integration remain |
| Explicit operator lane/resource ceiling | Awaiting selection; no default permission inferred |
| Frozen live preregistration and verified launch procedure | Incomplete pending the above |

The live-readiness goal remains active. The next independent work is to compile
task-specific contexts and finish capture/scoring integration contracts. A
qualified execution-owner route and explicit resource choice are still needed
before any seed, canary or comparative model call. No credential repair, paid
fallback or alternate provider is silently authorized by these artifacts.

Repository verification on macOS/Python 3.14: **851 tests passed**, including
the retained reference-report comparison; Ruff and local documentation links
passed; doctor found no missing paths; demo/verify checked seven artifacts
without errors. These checks do not change the failed lane qualification.
