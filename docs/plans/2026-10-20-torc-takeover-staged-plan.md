# TORC takeover and staged execution plan

This session on 4070pc owns coordination of the remaining session-continuation
readiness work. The immediate deliverable is a verified apparatus and a concrete
launch proposal. Comparative model runs require their own authorization. TORC
owns the experiment consumers, scoring records, observations and preregistration;
Autowork owns worker admission, execution, isolation and provider evidence.
`lugos-host` is an execution host, not a replacement owner of these components.

## Recovered state

- TORC's latest work is `26950f65b57a42a7e32681d430146a96f03d54ac`, seven
  commits ahead of GitHub `master` at `255acea`. It is preserved on
  [wip/torc-readiness-takeover](https://github.com/mdn87/torc/tree/wip/torc-readiness-takeover).
  These commits remain unmerged pending inherited-change verification. The local
  inspection worktree is `.torc/takeover-source`, branch `plan/torc-takeover`.
- The untracked applemac draft was copied to the ignored takeover evidence
  directory without changing its original. It is historical input, not a new
  authority source. The accepted October 19 decisions supersede its broader
  recovery proposals.
- Autowork PRs 584–588 are landed. The
  [live qualification report](https://github.com/mdn87/lugos/blob/673d1e5bc0077347eb932f62b1277cc30aa36dec/autowork/docs/native-live-qualification.md)
  establishes six successful mechanical canaries on the pinned macOS subscription
  lane. The archive SHA-256 is
  `f0ba4d8ea36f3e63336c90ec833053f81508b56248f194b71024f1dcbb88031a`;
  local verification matched all 467 manifest entries across 468 ZIP members.
- The single qualification allowance remains on applemac: **9 total, 6 used,
  3 remaining, none pending in the retained report**, 600 seconds per worker,
  no paid fallback. Do not copy or reset this allowance. Planning dispatches
  requested for this takeover are separate development work, not experiment data.
- Native fork/resume counters include inherited thread usage. Seven distinct
  successful response records reconcile with six worker outcomes. The evidence
  does not establish coverage of hidden provider retries or failed requests.
  Existing usage ledgers remain unqualified. A fresh native session reported
  cached input, so fresh session state does not establish a cold provider cache.
- TORC's committed readiness report predates these results. Its zero-live-call,
  ephemeral-only and final-attempt-only diagnoses need a new reconciliation
  record, while the original reports and failed attempts remain intact.

The takeover notification is agent-mail message 688. Before overlapping writes
or live qualification work, record the old session stopping or independently
verify that no conflicting writer/admission remains. Planning and isolated
evidence inspection can proceed.
This coordination change does not transfer any canonical TORC lineage lease.

## Decisions that need Matt

No answer is needed to finish the offline work below. Prepare the exact evidence
and proposed limits first, then ask only for decisions that affect execution.

| Decision | Recommendation to prepare | What waits |
|---|---|---|
| Authorize comparative runs with a separate total invocation/time budget | Start with a diagnostic Experiment A pilot on the existing subscription lane: two historical tasks, four arms, one repetition. That is eight arm runs **plus explicitly enumerated seed/setup calls**. Retain the 600-second worker ceiling, no paid fallback and no automatic retries. Present the exact total after arm preparation. | Live seeds, comparative workers and any new model-based scorer. The three spare qualification slots do not authorize this pilot. |
| Accept a narrower measurement claim if complete request coverage cannot be established | Prepare reported-response usage diagnostics, with unknown provider-internal cost explicit and whole-task savings unavailable. Do not silently change the existing full-coverage endpoint. If Matt wants this narrower pilot, record the changed claim before launch. | Promoting reported usage into the pilot's primary endpoint or making a weaker effectiveness/cost claim than the accepted protocol permits. Offline import and descriptive reports do not wait. |
| Change the four-arm design if an operational cold baseline proves infeasible | First distinguish native state from provider cache and investigate using existing evidence. Keep the intended arms and leave unsupported cache claims unknown. Present a concrete amendment only if the intended comparison cannot be realized. | Dropping an arm or substituting a materially different baseline. Routine versioned naming and evidence definitions are root decisions. |

No repeat approval is needed for the settled qualification cap, subscription
choice, source recovery, routine implementation choices, bounded offline tests,
or use of inventoried hosts within existing authority. Deployment changes,
credential rotation, schema changes and other separately gated operations are
not part of this plan.

## Autonomous work inventory

Paths below refer to the recovered TORC revision. New filenames are proposed
assignment boundaries; the root freezes their record interfaces before dispatch.

| Item | Owner | Completion evidence |
|---|---|---|
| A0. Preserve source, draft, owner evidence and exact qualification balance | Root | Source commit and archive hashes, old-session acknowledgment or direct ownership checks, no competing writer or pending admission; no native-state or credential copying. |
| A1. Verify and land the inherited seven commits | Root | Review the complete inherited diff once; run repository checks and deterministic experiment replays; compare platform failures with the untouched baseline. Preserve history through a normal PR. Keep the parent Lugos pointer unchanged. |
| A2. Reconcile current readiness with PRs 584–588 | Root | New dated report maps each old gate to current evidence or remaining work. Qualification success stays separate from comparison readiness and effectiveness. |
| A3. Import owner evidence into whole-task accounting | Worker A | Unique response IDs, source baselines, all owned attempts and missing fields survive import; inherited usage is counted once; incomplete coverage cannot produce an eligible savings endpoint. |
| A4. Establish counter/cache definitions | Worker A evidence; root decision | Establish input/cache overlap semantics independently of cumulative-counter arithmetic; preserve raw counters. Record native-state condition and observed provider-cache condition separately. Unknown cache state is never relabeled cold. |
| A5. Admit frozen candidates to an isolated scorer | Worker B | Terminal worker receipt and capture/tree-absence evidence bind the exact candidate and blinded scoring packet; absent, stale or conflicting evidence rejects before execution. Hidden tests run only through the qualified execution owner. |
| A6. Collect blinded investigation, timing and intervention observations | Worker C | Ordered traces and private provenance mapping, no arm/context/usage leakage; missing evidence remains unassessable; operator active time is not inferred from elapsed time. |
| A7. Finish equal-access four-arm workload preparation | Root after A3–A6 | Same historical task/workspace/history/tool access across arms; capsule verified by its existing owner; native seed/fork/resume bindings specified without fabricating state. Exact seed and setup call counts included in the launch proposal. |
| A8. Freeze preregistration and owner launch procedure | Root | Hash-pinned contexts, workloads, scoring, versions, schedule, resource limits, stopping rules, missingness and analysis. An explicit Autowork admission bridge consumes this evidence; a TORC manifest never grants execution authority. |
| A9. Verify end-to-end readiness | Root | Offline replay plus refusal tests, current host-specific execution/scorer evidence, complete check inventory and a launch checklist whose unresolved gates are explicit. |
| A10. Execute and report a bounded pilot | Root/Autowork after Matt's run decision | Every admission, failure, intervention and result retained; no outcome-dependent replacements; blinded scoring and conservative analysis. Two historical tasks cannot establish broad adoption or population-level non-inferiority. |

Experiment B (reconciliation-assistance ablation), API billing, general adoption,
new capture providers and cross-harness continuation are subsequent work. They
are not hidden requirements for completing this Experiment A readiness plan.

## Stages and dependency gates

### Stage 0: Establish the working baseline

Complete A0–A2, retaining original reports and failures. Source and archive
preservation are already done; inherited implementation verification and current
readiness reconciliation are not. Root owns remote inspection and landing.
An offline development lane is sufficient here; no experiment invocation is needed.

Before dispatch, root freezes the minimum shared evidence record: trial/attempt
identity, immutable candidate and packet hashes, owner terminal receipt reference,
capture status, response identity/source baseline and coverage status. Reuse
existing owner records rather than introducing another authority state machine.

### Stage 1: Three bounded packages in parallel

Every child gets one isolated worktree, an immutable Autowork assignment,
explicit allowed paths and targeted tests. Autowork selects its qualified route;
host and model identity are not chosen by the child. Children do not recurse,
operate remotely, handle credentials, land commits or sign off. The root performs
host-specific probes and final verification. No package consumes experiment calls.

| Package | Write scope | Inputs and acceptance checks |
|---|---|---|
| **A: Accounting and measurement evidence** | `src/torc/continuation_usage.py`; proposed `src/torc/continuation_evidence.py`; their dedicated tests and sanitized fixtures | Retained owner records and qualification report. Test duplicate/conflicting response IDs, inherited seed counted once, resume/fork overlap, missing failed-request usage, counter regression/epoch changes and input/cache overlap. Existing raw ledgers remain unchanged. Do not set `proxy_compatible` from names or arithmetic alone. |
| **B: Scorer admission** | Proposed `experiments/session-continuation-001/scoring_admission.py`; dedicated scorer-admission tests | Reuse `workloads.py::prepare_score`, `continuation_trials.scoring_packet` and the existing narrow scorer qualification. Bind terminal worker, candidate, trial and frozen packet; reject nonterminal/stale/mismatched/tampered inputs and protected-path changes. Parent performs the actual sandbox controls. Do not use the general root-read verifier for untrusted candidates. |
| **C: Blinded observation collector** | Proposed `src/torc/continuation_observations.py`; its tests; `experiments/session-continuation-001/investigation-rubric.md` | Retained/synthetic ordered traces and rubric. Test redaction of arm/session/context/usage, private-map binding, incomplete traces, clock boundaries, intervention count with unknown active time and necessary re-reading versus repeated investigation. No new provider capture surface or model assessor. |

Common stop conditions: an input contract conflicts with the frozen interface;
the assignment needs a write outside its scope, a new dependency/authority owner,
remote effects, a credential, or a live model probe. Return the evidence and
smallest required change to the root. A failed test within scope is work to fix,
not a reason to ask Matt. Retain partial work under the same assignment owner.

**Early end-to-end proof:** import the preserved fork-recall case, reconstruct
`19,569 = 9,240 + 10,329`, retain its source/attempt identities, and produce a
descriptive report while full-coverage savings remains unavailable. Then attach
a trusted fixture candidate, a bound terminal receipt and a blinded observation
packet. A missing receipt must refuse scoring; missing usage must prevent the
headline endpoint. This uses real retained telemetry and trusted fixture code,
without a new model call or root execution of an untrusted candidate.
Extend the proof to one workload across all four draft arms, using explicitly
synthetic terminal/score fixtures. This checks schedule and missingness behavior,
not native-context equivalence or comparative performance.

### Stage 2: Integrate the experiment

Root integrates A–C once, resolves interface mismatches and completes A7–A8.
Root owns `continuation_trials.py`, `continuation_analysis.py`, workload/context
assembly and the shared readiness/preregistration documents, avoiding concurrent
writers in these files. Preserve draft-only manifest semantics; implement any
launch bridge in the existing execution owner's boundary rather than changing
`launch_authorized` to true inside the offline preparer.

Freeze the existing 20% savings target, five-point quality margin, workload as
the independent unit, failure/missingness retention and no outcome-dependent
replacement. The two historical workloads are a diagnostic pilot, not a powered
adoption study. Repetitions do not create additional independent workloads.

### Stage 3: Verify and present the launch decision

Run targeted checks after the parallel batch, then the full TORC suite, Ruff,
doctor, and demo/verify using one disposable state directory. Replay contexts,
accounting and comparison preparation; include baseline/reference/mutant scoring
controls and refusals for drift, absent terminal evidence and absent authority.
Inspect the complete integration diff once. Reuse still-valid evidence unless
changed source/runtime/policy or a failure requires a fresh check.

Publish the exact remaining evidence gaps, eight-arm-run schedule, additional
seed/setup count, total time ceiling and requested claim boundary. Ask Matt for
the live-run decision only once this packet is concrete. Apparatus completion
does not mean live admission, measured savings or adoption approval.

### Stage 4: Run only the separately authorized cohort

Autowork admits workers against the frozen packet and a separate comparative
allowance. Stop on the preregistered failure/ambiguity conditions; do not spend
spare qualification slots as automatic replacements. Root reconciles all attempts,
scores and observations and reports inconclusive/negative outcomes honestly.

## Platform plan

| Platform | Current role | Additional evidence needed |
|---|---|---|
| 4070pc, Windows/Python 3.14 | Coordination, source custody, portable code and offline tests | Windows path/serialization checks. A planning worker's sandbox does not qualify a comparative worker or blinded scorer. |
| applemac, macOS/Python 3.14 | Custodian of the original qualification root and native state; existing qualified reference lane | Refresh only evidence invalidated by the selected runtime/policy/host changes; verify exclusive ownership before new writes/calls. |
| lugos-host, Linux | Optional Autowork worker/scorer host | Inventoried identity and exact source, execution and scorer isolation, native behavior and telemetry qualification on Linux. Mac receipts do not transfer. No reason to migrate native state merely to transfer coordination. |

## Planning evidence and completion status

Local source/evidence preparation used no qualification or comparative calls.
Autowork run `20261021-015432-2f10b73bd282` completed with one read-only
`codex:terra-medium` worker, no remote or paid route. Its result and the root's
disposition are recorded in the
[planning evidence](2026-10-20-torc-takeover-planning-evidence.json). The first
attempt failed before worker launch because a Windows multiprocessing helper could not reload a standard-input script; the
second uses a saved, guarded entrypoint. Both attempt records are retained.
Orca advice was rejected by the runtime and is not claimed as applied.

The root adopted Autowork's evidence corrections, operator gates, draft-only
admission boundary, four-arm proof and platform limits. Its suggested packages
overlapped in experiment/test paths, so this plan assigns three disjoint write
areas and reserves shared integration files for the root. Offline admission
bridge development can proceed before a live budget decision; issuing a live
admission cannot. The six model-worker outcomes affirm tree absence, while the
60 capability subprocess records do not carry that field.

This plan completes the takeover planning deliverable. A1–A10 remain execution
work; the repository is not yet ready for live comparisons. Preserve the source
worktree until the inherited history is validated and landed, then remove it as
routine reversible cleanup. Do not merge unverified inherited work just to make
the takeover branch disappear.
