# TORC: Session Handoff and Token-Efficient Continuation

**Status:** Final scope decision; the bounded first implementation is authorized. Later phases are an evaluation sequence, not deployment authority.
**Date:** October 16, 2026; final pass October 19, 2026.
**Baseline checked:** `255acea197bdaee74ed7ebbbe004584f6a950281`.
**Initial target:** local Python on macOS, using synthetic Claude-shaped transcripts. Live Claude Code capture is later work.
**Secondary targets:** Linux, Windows and Codex after their capture contracts are separately demonstrated.

## 1. Decision and objective

Build a small model-free evidence collector and a read-only reconciliation report. Then test whether TORC's existing verified capsule can reduce the tokens consumed by a whole resumed task while preserving independently verified task success. Token savings are a hypothesis to measure, not a property conferred by producing a short handoff.

Keep the useful corrections from rounds 1 and 2: exact byte boundaries, separate raw and redacted digests, session-scoped operation identities, coverage independent of visible operations, unchanged capsule semantics, comparable safety assistance, and all-attempt accounting. Remove the retry coordinator introduced in rounds 3 and 4. The harness reports uncertainty and holds; it does not provide exactly-once retry. The detailed disposition is in [the decision log](2026-10-19-session-handoff-decisions.md).

The first delivery proves that interrupted evidence can be represented honestly without changing canonical lineage. It does not prove token savings, live transcript completeness, safe automatic recovery, or better receiving-agent performance. Those are distinct claims requiring different evidence. An adapter that proves only its own parsing and persistence contract can still be useful, provided its reports say exactly that.

### Desired outcome

A receiving session should be able to establish the authorized task, accepted lineage base, retained constraints and commitments, unresolved work, relevant evidence, and uncertain operations. It should distinguish inherited claims from fresh observations and identify what needs inspection before further action. Eventually an operator should also see the measured tradeoff between native resume, a history-informed compiled prompt, and a verified TORC capsule.

Zero model calls during capture mean zero model tokens for capture itself. They say nothing about startup instructions, capsule reading, artifact retrieval, reconciliation, failed reconstruction, retries, or fallback. All those costs belong in the continuation measurement. A smaller prompt that causes more repeated investigation may increase total consumption; a larger carry might reduce total consumption if it preserves decisions that would otherwise be rediscovered.

### Three trust objects

Keep the model-visible continuation context, recovery evidence, and context binding separate. In the TORC arm the first object is the existing verified P5 capsule. Its guarantee is faithful rendering of a stored projection. It supplies neither freshness nor proof of tool effects. A compiled prompt or native session handle fills that role in other arms.

Recovery evidence is a derived, arm-independent report containing the capture digest, base bindings, coverage gaps, uncertain operations and independent evidence references. It is not canonical state. It must remain available outside the capsule's budget; a small receiver omitting `uncertainties` must not thereby erase the execution layer's knowledge of uncertainty.

A context binding, added only in the later bridge, identifies the specific context paired with that report. A digest can detect substitution; it cannot grant permission or prove readiness. None of these objects is an execution journal, one-use capability, or authority store. The first implementation produces only capture manifests and reconciliation reports.

## 2. Existing TORC baseline: reuse, do not duplicate

The following claims were checked in the pinned checkout. Paths in this section are repository citations; proposed files elsewhere are explicitly future implementation surfaces.

| Existing facility | Checked behavior and use |
|---|---|
| `docs/architecture.md`, `docs/domain-model.md` | Lineage history and acceptance records are immutable; authority belongs to the leased activation. Evidence collection cannot change those rules. |
| `docs/p3-recovery.md` | Operator-declared recovery prepares a replacement without transferring authority. Acceptance closes the old lease and appends `handoff_accepted`; it does not restore process, tool or workspace state. |
| `src/torc/projections.py`, `docs/p5-receiver-carry.md` | The current receiver compiler is `p5-2`; it reads lineage history and fits optional context to a receiver budget. Uncertainties and artifact references can be omitted. |
| `src/torc/p5_capsules.py`, `docs/p5-capsule-consumer.md` | `derive` and `verify` use the caller's projection ID and expected record hash, verify lineage integrity, and compare the full rendered objects. Extra claims, altered mappings and resealed substitutions are rejected. |
| `docs/thread-checkpoint-authority.md` | Checkpoint bodies remain with their owners; TORC controls acceptance and continuation-grant authority. A capture is not an accepted checkpoint. |
| `src/torc/experiment_usage.py` | `normalize_usage` preserves reported counters and missing values as `None`. It does not infer equivalent billing semantics across providers. |
| `docs/project-snapshot-artifacts.md` | Existing project snapshot evidence can supply bounded Git/workspace references. A second transcript or workspace mirror is unnecessary. |
| `src/torc/canonical.py` | `canonical_json` sorts keys and fixes serialization formatting. It does not identify semantically equivalent operations or normalize path aliases. |
| `src/torc/experiment_runs.py` | `write_canonical_artifact` writes canonical JSON through a shared per-target temporary, fsyncs the file and replaces the target. It provides neither writer serialization nor create-once immutability. |
| `tests/test_p5_capsule_adapter.py` | `_unchanged` compares SQLite `iterdump` and hashes of every state-directory file around read-only operations. Reuse this test pattern for the first slice. |

The P5 assessment in `docs/pr-25-receiver-fitted-carry-assessment.md` reports approximately 2.9–3.1 times the delivered words of a compiled-prompt comparator on its fixture. That comparator did not receive equivalent history access. The result establishes neither superior continuation quality nor a token-saving benefit. This experiment must give the compiled baseline access to the same history and evidence and count all consumed context.

There is a documentation inconsistency at the pinned baseline: the Commands paragraph in `docs/p5-receiver-carry.md` still names `p5-1` for preparation, while `src/torc/operator.py` calls `compile_receiver_projection` and `src/torc/projections.py` defines the current compiler as `p5-2`. Use the implementation and recorded projection version, not the stale paragraph, when describing a newly generated carry. Existing `p5-1` projections remain supported by the capsule consumer.

## 3. Ownership boundaries

| Responsibility | Owner and limit |
|---|---|
| Transcript lifecycle observations | Harness adapter; observations are untrusted evidence, never checkpoint authority. |
| Raw transcript and checkpoint bodies | Existing harness/evidence owner or OGMI; no canonical transcript mirror. |
| Workspace observations | Existing snapshot tooling or explicitly supplied fixtures; current bytes are observations, not a history of effects. |
| Canonical decisions, carry and acceptance | Existing TORC interfaces and invariants, unchanged. |
| Derived report and later context binding | Small read-only adapter; no tool dispatch or permission consumption. |
| Assignments, tool permissions, process control and routing | Existing execution systems and operator, as specified in `docs/integration-boundaries.md`. |
| Memory and transport | Existing Sulis and agent-continuity ownership; no replacement memory or synchronization service. |

Non-goals include a daemon, watcher, scheduler, new provider SDK, continuous summarizer, semantic intent detector, transaction coordinator, retry journal, occurrence allocator, tool gateway, cross-host production dependency, or new canonical schema. Do not change leases, acceptance, checkpoint semantics, grants, projection rendering, or the capsule verifier. Do not modify the parent repository.

There is no exactly-once, idempotency, or liveness guarantee for live Claude Code tools. This plan does not intercept arbitrary shell writes, fence remote ingress, recover child processes, or establish that absent receipts mean absent effects. It also makes no power-loss durability or hostile-filesystem-writer guarantee. A hold can remain unresolved indefinitely; that is an honest outcome, not a reason to add a release protocol.

The accepted environment is a trusted single operator working on local disposable fixtures. SHA-256 supplies integrity evidence, not access control or secrecy. The implementation is direct and bounded, with one consolidated self-review and relevant verification. The associated scope envelope records estimates and evidence; estimate variance is advisory and does not authorize expanding the outcome.

## 4. Proposed control flow

```text
owner-supplied exact transcript prefix and observation facts
    -> pure parser and conservative operation classification
    -> capture manifest with raw digest, coverage and bindings
    -> read-only reconciliation against independent fixture evidence
    -> held / stale / observations_complete report

later, separately:
accepted lineage -> existing P5 carry -> existing verified capsule
report + concrete continuation context -> derived context binding
operator/existing execution layer -> ordinary authority and tool decisions
```

A completed turn and an interrupted operation are different events. A clean stop can provide useful capture evidence; it cannot certify that every side effect is settled. A hard kill may produce no hook at all. The adapter must preserve the distinction between the last accepted canonical checkpoint and a newer candidate recovery observation.

Uncertainty reaches the receiver through a separate report. Do not splice a warning or extra claim into the verified capsule and reseal it: that violates the consumer's faithful-rendering contract. If the current lease holder chooses to make uncertainty canonical, it may use the existing authorized checkpoint path. The collector never performs that append. A later carry may include the resulting state subject to its existing selection rules.

For a true bearer change, the replacement reconstructs under a separately valid assignment and uses unchanged TORC recovery or handoff acceptance. Acceptance changes the head, so the old report becomes stale. Gather fresh observations and produce a new report against the current base; preserve the old one. Do not copy a retry permission or automatically carry dispositions across the transition. A report is evidence about one observation base, not a durable permission awaiting rebinding.

## 5. Evidence format and interruption semantics

### Capture manifest v0

The first schema is an adapter-owned derived record, not a TORC canonical schema. Its fields identify the synthetic adapter version, session reference and incarnation, UTC observation time, boundary, exact prefix, post-capture status, coverage, base bindings, sanitized operations, raw/redacted digests and diagnostics. Optional usage references remain opaque references; absent usage stays absent.

`capture_id` is SHA-256 of the canonical manifest body excluding `capture_id` itself. The raw digest hashes exactly the declared byte prefix. The redacted-view digest hashes the canonical metadata-only object containing `tool_operations` and `collector_errors`. Neither digest substitutes for the other. Published artifact filenames separately hash the serialized file bytes, including their final newline; document these boundaries so a verifier knows which bytes to reproduce.

An operation records a session-scoped ID, recognized kind, idempotency classification, typed target identity, exact-payload fingerprint, observation and optional independent evidence reference. The initial metadata-only policy hashes path identities and arguments rather than retaining path strings, command bodies, file contents, tool outputs or assistant prose. Trusted callers supply allowlisted bindings and opaque references; the adapter does not claim to redact arbitrary caller metadata automatically.

The synthetic input subset uses assistant messages containing `tool_use` blocks and user messages containing matching `tool_result` blocks. A synthetic `stop` event represents a fixture boundary. Text blocks are ignored as operation evidence. Unknown event types, unsupported content forms, malformed fields, orphan results and repeated IDs produce diagnostics and incomplete coverage. This is not a claim to parse every current Claude Code transcript variant.

### Read boundary and binding rules

The pure parser accepts bytes and an explicit prefix length. It never opens a live file. It parses only newline-terminated JSON objects within that prefix, rejecting duplicate object keys and malformed records. At the first malformed or unterminated record, the remaining prefix is quarantined and counted. Valid later records are not used to pretend a broken prefix is complete. Diagnostics contain reason codes, not potentially sensitive raw fragments.

The later file adapter will open the owner transcript, observe size and identity, read exactly that prefix once, collect permitted workspace evidence, then check size and identity again. Appending, truncation, rotation, a short read or unavailable observations produce explicit incomplete coverage. A prefix digest proves which bytes were read; it does not prove the whole session was captured or that a file was a consistent snapshot against arbitrary in-place writers.

Tool-use IDs are scoped to a session incarnation, not assumed globally unique. Rotation requires a new incarnation. The fingerprint identifies equal serialized payloads; it is not logical operation identity, semantic equality, or proof that a later identical call is a duplicate. Two intended writes can have identical payloads. Path aliases and omitted defaults can make equivalent effects hash differently. No hold is released or retry blocked solely through fingerprint equality.

Bindings carry lineage identity and revision, accepted checkpoint reference and hash when available, and workspace evidence identity. Unknown fields remain null or unavailable. Reconciliation copies these as `base_bindings`. Before relying on a report, compare them with current observations. Any difference makes it stale, including normal TORC acceptance. Equal supplied bindings prove consistency with those supplied facts only, not live freshness or settled external effects.

### Observations, coverage and holds

The parser/classifier emits `started_without_confirmed_result`, `reported_success`, `reported_failure`, or `not_observable`. It never emits `verified_effect`. The reconciler may use that state only for operation-specific independent fixture evidence with a nonempty reference bound to the same observation base. A result, final prose, present file bytes, or absence from an unrelated sink is insufficient on its own. Duplicate-ID ambiguity cannot be repaired by attaching one ambiguous evidence reference.

Hold every non-idempotent or unknown operation, and every operation with an unknown target, unless suitable independent evidence verifies its effect. Reported failure still holds because the effect may have preceded the error. A verified effect describes observed execution; it does not authorize repeating the operation. A known read can be treated as idempotent for this fixture classification, without claiming that all operations named Read in arbitrary tools share that property.

Coverage is independent of the operation list. An empty list may mean that a write occurred entirely beyond the captured prefix. Complete fixture coverage requires unchanged capture observations, no quarantined bytes or diagnostics, confirmed stopped writer, complete lifecycle observations, available workspace evidence and bindings, and an explicit synthetic operation-coverage attestation. Without that fixture attestation, operation coverage stays unknown even if the transcript is well formed and its writer exited.

The report statuses are `held`, `stale`, and `observations_complete`. The last means only that the supplied fixture's observations contain no reported gap or unresolved held operation. It deliberately does not say `clear` or `safe_to_resume`. Every report states `retry_authorized: false`; quiescence remains unknown. No implementation path emits `retry_safe`, infers historical `no_effect`, or enables mutation. A coverage hold is actionable advice to inspect or obtain evidence, not an installed live-tool interceptor.

### Process and external-effect limits

A stopped parent is not proof that its children exited. Even a stopped process group is not proof that a previously sent request cannot arrive later. A drained accepted-request queue says nothing about a request still in transport. Consequently, no process-group termination machinery, receipted sink protocol, or absence-based retry rule belongs in this slice. Static fixtures can represent delayed requests without implementing a transport.

Likewise, present file state A cannot prove that A→B→A never occurred. File equality is evidence of current state, not attribution of each historical write. A second crash can erase outcome observations. All such cases remain held unless independently established evidence resolves the observation; they never cause automatic retry. An operator who acts outside the report does so through existing authorization, and that intervention must be recorded as an override in any experiment.

### Persistence contract

Publish sanitized capture and report bodies under content-addressed names in a private ignored output directory outside the canonical state directory. Each writer creates a private temporary directory and complete file, flushes and fsyncs the file, then publishes it with create-once atomic hard-link semantics on the tested local filesystem. An existing identical file is reusable; different bytes at the expected digest path are an integrity error and remain untouched.

This publication rule is for immutable data, not for claims that are retired and reused. No publication path is recycled as retry permission. There is no `latest.json`, lock file, mutable pointer, supersession chain or journal. Callers retain the returned explicit artifact reference. Removing the optional pointer avoids adding concurrency behavior that the first demonstration does not need.

Leave `write_canonical_artifact` unchanged. Its shared temporary name and overwrite semantics are unsuitable for concurrent create-once publication. The small publisher may reuse canonical serialization, but should not import a store-dependent experiment subsystem merely to borrow a few write operations. On unsupported filesystems publication fails visibly; there is no silent overwrite fallback. Process interruption may leave private temporary debris but must not alter a previous published artifact or expose a partial new one.

### Focused fixture set

Test complete and interrupted messages, missing results, failure after a possible effect, malformed or truncated tails, append beyond prefix, rotation metadata, duplicate and cross-session IDs, unknown event shapes, stale bindings, and distinct raw/redacted hashes. Test an empty operation list with incomplete coverage. Supply independent evidence both correctly and against the wrong base. Test simultaneous identical publication, corrupt existing content, and process exit before publication.

Retain the round-5 scenarios as counterexamples to inference: A→B→A is not proof of non-execution; a reused claim cannot be safely released by an old resolver; and absence of accepted requests does not fence ingress. Since there is no claim or retry implementation, executable gates assert no retry authorization and unchanged data, not one effect after automatic recovery. A single developer can run every first-slice gate on macOS without a service or provider.

## 6. Continuation strategy: advisory, not autonomous routing

A later read-only adviser compares native warm resume, native cold resume and fresh context. Warm resume is a plausible winner where reported cache behavior supports it. A fresh capsule is a plausible winner when a large cold history can be replaced with sufficient verified context. Native continuation may also preserve opaque provider state that a portable capsule cannot reconstruct. These are hypotheses for specific lanes, not routing constants.

Use observed usage, rendered context, measured retrieval overhead and explicit pricing configuration where applicable. Do not assume a universal cache lifetime or convert a subscription limit into dollars. Missing cache counters mean unknown cache confidence. Do not recommend a strategy merely because missing measurements make its numeric total smaller. The adviser must show unavailable alternatives and the evidence behind its uncertainty.

The adviser makes no model request and changes no session, route, model, assignment or lease. Its implementation is outside the first batch. Raw usage references and the accounting protocol established now make later comparison possible without pretending that local JSON bytes are provider tokens. The operator retains native/manual fallback; every fallback consumes part of the originating strategy's measured budget.

## 7. Implementation phases and gates

### Phase 0: baseline, scope, reproducibility

Pin the baseline, record existing tests, check the reused interfaces and finalize this plan with the decision log. Create a protocol skeleton that names required measurements and forbids trials until lane-specific choices and fixtures are frozen. Record scope, accepted limits and estimates. Preserve the unrelated original planning document and frozen earlier experiment lanes.

Gate: the repository baseline is understood, every current-facility citation is checked, and no new component assumes ownership belonging to TORC's existing store or another Lugos component. This is a local inspection gate, not a further design-review cycle. The first production-shaped proof is an interrupted fixture flowing through capture, report and immutable publication while an existing store stays unchanged.

### Phase 1: model-free capture

First implement the pure parser, classifier, manifest builder and publisher against synthetic fixtures. All environmental facts are explicit inputs. Only after that delivery should a live adapter obtain those facts from a pinned supported transcript version. The live adapter must account for unsupported records and unavailable observations rather than quietly treating the synthetic fixture attestation as live completeness.

Gate: deterministic replay from a fixed prefix; correct raw digest and quarantine accounting; no raw arguments or outputs in the sanitized manifest; conservative failure classification; no model/network execution surface. Persistence gates require complete immutable publication and preservation of previous artifacts across process interruption and overlapping identical writers. Live hook installation remains outside the first PR.

### Phase 2: read-only reconciliation

Compare capture bindings with independent fixture evidence and current supplied bindings. Produce explicit holds, coverage gaps, stale status and inspection guidance. Keep verified effects separate from reported outcomes. Later workspace integration should consume bounded existing evidence references, including a clear unknown when ignored or non-Git state is outside observation scope.

Gate: neither failure-after-effect nor success-without-independent-evidence becomes verified completion; incomplete coverage cannot yield observations-complete; stale evidence cannot verify a new base; every report grants no retry. There are no release dispositions, retry gates, fixture tool executors or process supervisors. The phase can finish with unresolved operations, because safe reporting is the delivered behavior.

### Phase 3: existing capsule integration

Build the thin bridge only after the first slice is complete. Use the recorded carry ID and expected record hash with existing capsule `derive`/`verify`. Retain the report independently and bind it to the exact delivered context. TORC, compiled-prompt and native arms need their own context identities; they can still share byte-identical recovery evidence.

Gate: unchanged capsule contract tests; extra-claim rejection; a tight-budget capsule omitting uncertainties leaves the separate report intact; mismatched context identity rejects; stale bindings remain stale after actual P3 acceptance. Existing recovery tests prove authority transitions; this bridge must not turn those transitions into a new retry guarantee. Fresh report construction replaces the proposed rebind protocol.

### Phase 4: read-only cost adviser

Normalize recorded usage with the existing utility and retain raw counters. Distinguish API charges, subscription telemetry, the token proxy, rendered bytes and estimates. Identify request-level versus cumulative counters before aggregation; a final cumulative session total must not be added to each incremental update. Track the entire attempt chain through completion or declared failure.

Gate: synthetic accounting fixtures include a failed start followed by fallback, a missing counter, cache reads, and a repeated cumulative usage record. Totals neither omit failed attempts nor double-count updates. No fabricated cache hits, prices or missing-value zeroes are permitted. These tests validate arithmetic and provenance, not actual model savings.

### Phase 5: controlled comparison

Run the frozen Experiment A and B protocols. Mechanical fixtures first establish capture and report behavior. Realistic tasks then test useful continuity with blinded scoring in disposable workspaces and without a known-payload gate. Any live model run needs its execution-layer authorization and explicit resource budget; this implementation batch does not launch one.

Gate: a complete report of all attempts, failures, missing data, operator interventions, task quality and token usage. An inconclusive or negative result is a valid completion. Synthetic demonstrations alone cannot justify a claim of better coding outcomes or default adoption. No expansion into retry coordination is necessary to make the evaluation useful.

### Phase 6: opt-in pilot and disposition

Only realistic-task evidence meeting the frozen success and savings criteria can justify proposing an opt-in pilot. The operating guide must repeat that the adapter reports uncertainty and supplies neither exactly-once retry nor live liveness guarantees. Preserve immediate manual/native fallback and record why the operator used it. Evaluate maintenance, friction, storage and portability alongside tokens.

Gate: a documented adopt, narrow or stop decision with the limits visible. No production default, autonomous routing, live tool interception or broader rollout is authorized by passing an experiment. A useful negative result should end unnecessary implementation rather than produce another safety protocol to protect the original hypothesis.

## 8. Evaluation design

### Two questions, two designs

Experiment A measures context strategy. Compare native warm resume where available, native cold resume, a deterministic history-informed compiled prompt, and the verified TORC capsule. Match task, model/version/effort, tools, permissions, workspace, history access, retrieval access, operator rules and recovery assistance. The model-visible continuation context differs; its context binding necessarily differs too. Safety information must not be exclusive to the TORC arm.

Experiment B measures reconciliation assistance. Hold the context strategy fixed, declared before the first trial, and compare receiving the report with not receiving it. Use only disposable local scenarios without real sends, deploys or other external mutations. The independent observer still records outcomes in both arms. Any execution restriction needed to keep the trial bounded is identical in both arms; the ablation changes information, not authorization.

Claims about capsules come from A. Claims about recovery reporting come from B. The earlier comparison of plain prompt against TORC plus extra reconciliation cannot isolate either contribution. Equal information access means a baseline can retrieve the same history, not that it is forced to ingest every byte. Its generation and retrieval costs are counted just as TORC's are.

### Mechanical fixtures and realistic tasks

Keep the distinction between mechanical validation and realistic task evaluation; drop the two execution protocols. Mechanical fixtures have known inputs and outcomes because they test parsing and conservative reporting. They are not model-quality benchmarks. If a scripted reconstruction microbenchmark is ever reported, label it as such in every table and forbid real-workload adoption claims from it.

Realistic tasks have no exact-payload schedule or answer-checking tool gate. Models may propose different valid implementations. A blinded scorer evaluates tests, artifacts, constraints and task requirements without seeing arm labels. Use disposable local workspaces. Unknown interrupted effects may require an operator to inspect, abandon a run, or restart in a fresh fixture. Count the intervention, elapsed time and all prior tokens; do not claim the report restored uninterrupted autonomy.

### Frozen before the first trial

The protocol skeleton must become a complete versioned preregistration before any model output is inspected. Freeze:

- Lane, provider, model/version, effort, harness/adapter versions, billing mode and counter semantics.
- Workload count per stratum, exact workload/artifact hashes, task source and permitted evidence.
- Paired repetitions, random seeds, arm-order permutation schedule and stopping rule.
- The history-informed baseline compiler, receiver budgets, common instructions, tools, information shown to each model and operator intervention policy.
- Independent success rubric, hidden tests, blinded scoring procedure and critical failure definitions.
- Verified-success non-inferiority margin, confidence method, sample-size rationale and missing-data treatment.
- Whole-task start/end boundaries, request identities, incremental/cumulative counter policy, fallback accounting and exclusion rule.
- Primary endpoint, minimum meaningful savings, secondary metrics, cache strata and analysis code/version.

Any later protocol change creates a new version and separately reported cohort. Do not quietly retune a budget, baseline, missing-value treatment or stopping rule after seeing which arm wins. The committed skeleton alone is not a completed preregistration; it lists the concrete lane-specific values still needed before trials.

### Billing lane and primary endpoint

On an API-metered lane with usable billing data, the primary endpoint is whole-task measured API cost in the cold-resume stratum. Freeze the pricing source, model identity, date, cache pricing and any unmetered components. The candidate threshold is at least 20% median reduction against the strongest safe baseline, subject to verified-success non-inferiority and critical safety constraints.

For a subscription lane, API cost is unavailable unless separately measured; do not synthesize dollars from subscription rate limits. The primary endpoint is the separately named uncached-processed token proxy: `input_tokens + cache_write_input_tokens + output_tokens`. Report `cached_input_tokens` alongside every value. Cache reads are omitted from this proxy, not declared free or unprocessed. Missing any required summand makes the proxy missing, not zero.

The proxy's interpretation requires lane-specific counter semantics. Normalized names do not prove that counters are disjoint. Before using it, pin documentation or validated exporter behavior establishing what input and cache counters mean; otherwise report the proxy unavailable. Report total context processed only when non-overlap is established for input, cache-read and cache-write fields. Do not generalize one provider's accounting to another or add reasoning tokens twice when they are already included in output.

Both endpoints cover every request attributable to the chosen strategy: initial context preparation if model-authored, attempted starts, reconstruction, follow-on retrieval, root/subagent work, reconciliation, retries, synthesis, recovery and fallback. Continue through independently verified completion or declared failure. Report both task-level totals and their request/attempt components so cheaper failures cannot disappear inside an average of successful runs.

### Success, exclusions and missing data

Set an explicit absolute verified-success non-inferiority margin before trials. The protocol skeleton proposes five percentage points, to be frozen with a justified sample count before execution. Passing requires the prespecified confidence bound for TORC minus the strongest safe baseline to remain above minus that margin. A small pilot unable to exclude a larger regression is inconclusive, even if its point estimate looks favorable.

Critical authority violations, duplicate non-idempotent actions and falsely verified completion have a zero tolerance in the observed adoption gate. Zero observed incidents in a small sample is not a proof of general safety. Count actual effects and independent artifact results, not labels in the report. Report unsafe proposals, blocked progress and operator actions as well as final task success so the benefit is not hidden in human labor.

Exclude a trial from the endpoint only for an arm-independent setup failure occurring before delivery of any arm-specific context and before any arm-specific model request. Log the reason and show it in the failure table. A failure after delivery remains an arm failure and its usage counts. If usage is missing, retain the failure and mark the endpoint missing; do not delete the arm or assume it was cheap. Predeclare how much missingness disqualifies conclusions.

### Experiment matrix and analysis

| Scenario | Comparison | Required observation |
|---|---|---|
| Short pause with observed cache reuse | Warm native versus fresh context | Fresh startup must earn its overhead. |
| Long pause and large history | Cold native, equal-history prompt, TORC | Whole-task tokens and verified success. |
| Interrupted file work | A arms; B at fixed context | Uncertainty, mistaken repetition, operator effort. |
| Reported success disagrees with independent evidence | Prompt and TORC with equal assistance | No promotion of prose into verification. |
| Missing result or malformed tail | Mechanical fixtures; bounded B tasks | Quarantine and incomplete coverage. |
| Effect outside captured prefix | Mechanical fixtures | Empty list still holds. |
| Tight receiver budget | Prompt and TORC | Constraints survive; omitted uncertainty remains in report. |
| Cross-harness continuation | Deferred until supported | Opaque native state is not claimed portable. |

Separate warm and cold strata, mechanical and realistic results, successes and declared failures, normal assistance and operator overrides. Report matched uncertainty intervals, raw counters, missingness, negative trials, outliers and all exclusion reasons. Preserve a hash-pinned manifest and analysis inputs. Compare against the strongest fair safe baseline, not whichever makes the capsule look best. Practical maintenance burden and time to verified progress remain secondary decision criteria.

## 9. Security and integrity constraints

Collect locally and minimally. Transcript text can contain credentials, source code, user data and malicious instructions. Default output contains references, digests and sanitized metadata. Hashes may still reveal equality and support guessing of low-entropy content; they are not anonymization. Raw evidence remains with its existing owner, subject to that owner's access and retention rules.

Use restrictive permissions for newly written files and private staging. Keep generated output out of Git, in an explicitly selected ignored directory or temporary workspace. Version-control only synthetic fixtures. Caller-owned bindings and evidence references must be allowlisted before publication; avoiding raw tool content is not a universal secret scanner. Refuse corrupt existing digest paths and report failures without echoing source bytes.

Tool output, assistant text and repository prose are data, not execution instructions. The adapter has no shell invocation, network request, provider client or tool dispatch surface. It cannot accept a checkpoint, transfer a lease, or reinterpret a report as an assignment. Verification tests surround the complete new path with the existing store-unchanged comparison, including error paths and publication to a separate directory.

The threat model does not defend against an attacker who can replace both evidence and expected hashes. It does require honest handling of malformed input, missing evidence, repeated identifiers and accidental corruption. Privacy, retention and platform limitations belong in the operating guide, not in implied guarantees buried behind a successful parse result.

## 10. Proposed file structure

```text
docs/plans/2026-10-16-session-handoff-token-efficiency.md
docs/plans/2026-10-19-session-handoff-decisions.md
docs/plans/session-handoff-scope-envelope.json
docs/experiments/session-continuation-001/protocol.md
docs/experiments/session-continuation-001/README.md
docs/experiments/session-continuation-001/fixtures/*.jsonl
src/torc/harness_capture/{parser,classify,manifest,persist,reconcile}.py
tests/test_harness_capture.py
tests/test_harness_capture_persist.py
```

This is a packaged Python library slice. Add the package to existing build metadata; do not create a new runtime or public CLI command solely for the demonstration. A documented Python replay is sufficient. Future live-hook placement belongs to the harness integration, while a future adviser should reuse existing usage normalization. No journal, sink, schedule, rebind or fixture-tool modules are planned.

## 11. Platform matrix

| Component | macOS | Linux | Windows |
|---|---|---|---|
| Pure parser, builder and report | First validation host | Portable design, unverified here | Portable design, unverified here |
| Immutable local publisher | Test on local filesystem | Test hard-link/permission behavior before support | Test publication and ACL semantics before support |
| Live Claude Code hooks | Deferred | Deferred | Deferred |
| Model comparisons | No trials in first batch | No claim | No claim |

Do not infer Linux support from POSIX-looking code or Windows support from pure Python syntax. The pure contract is platform independent; filesystem publication and live event capture need host-specific evidence. The first gate is executable with local macOS Python, pytest and no background service. Existing TORC cross-platform promises remain unchanged.

## 12. Implementation order and first PR

The first PR remains narrowly demonstrable and does not touch the authority store. Its scope is the v4 Section 12 baseline reduced where discarded protocols had leaked into it. Finalize this plan and decision log, add the protocol skeleton and synthetic fixtures, implement the pure capture/classification/manifest functions, immutable publisher and pure reconciler, then document and run one end-to-end replay.

Do not add the cost adviser, live hooks, capture file watcher, model experiment runner, capsule bridge, recovery-record wrapper, context binding, fixture tools, sink, replay guard, execution journal or rebind step. Preserve raw usage reference slots and the measurement design; actual token arithmetic belongs to Phase 4. No savings claim is part of this first exit condition.

The replay must produce an exact prefix digest, a session-scoped uncertain operation and fingerprint, a coverage hold, and a read-only report with base bindings and useful next inspection guidance. A wholly unseen operation must still yield a coverage hold. Reported failure must not imply no effect. Independent verification must not erase unrelated coverage uncertainty or grant retry permission.

Test parser boundaries, ambiguous IDs, malformed records, redaction, stale evidence and no execution dependencies. Test publication interruption, simultaneous identical writers, and corruption refusal. Compare SQLite dump and every state-directory file before and after the full capture/report/publication sequence, using the existing `_unchanged` pattern. A helper name is not the evidence; inspect the actual before/after comparison.

Run focused tests, the full suite, lint, and the repository's doctor/demo/verify smoke sequence against a temporary state directory. Verify installed-package inclusion as packaging changes. Record actual results and remaining limits in the experiment README and scope envelope. Commit only this coherent task-owned batch, preserving unrelated user changes; pushing or changing repository settings is outside this instruction.

## 13. Go/no-go decision

Adopt only if realistic Experiment A shows a meaningful whole-task savings result on the declared endpoint, counting every attempt and fallback, while passing the frozen verified-success non-inferiority criterion and observed critical-failure gate. Prefer warm native resume wherever it wins. Mechanical fixtures, smaller JSON, or lower capsule word counts cannot satisfy adoption.

Narrow to evidence collection and reconciliation if Experiment B shows useful reporting but A shows no capsule benefit over a history-informed prompt with equal assistance. Narrow further if the report creates more operator burden than it removes. Stop if correctness, authority, privacy, uncertainty or maintenance costs outweigh the measured savings. Do not expand TORC merely to obtain a favorable token figure.

### Round 5 disposition

The A→B→A finding is valid against v4's current-file pre/post attribution. Remove that classifier and all automatic `no_effect` release. Present bytes never establish the absence of an earlier effect. The retained report holds the ambiguity; no target-ownership protocol is needed because it does not retry.

The claim-recycling race and pre-intent crash gap are valid against v4's retry journal. Cut claims, release, allocation and re-entry. Immutable artifact publication has no retirement or permission-spending role and cannot admit a second tool execution. No-intent evidence stays unknown rather than being manufactured.

The late-ingress finding is valid against v4's accepted-request quiescence predicate. Cut that predicate and the sink protocol. Neither process exit nor an empty accepted queue establishes no future effect. Live ingress fencing remains outside scope; this is acceptable because the adapter never grants a retry based on absence.

### Reference implementation caveats

The earlier plans used an external handoff script as motivation. This final plan makes no claim about its current hooks, security, portability or costs and relies on no external implementation guarantee. The local pinned TORC sources and explicit synthetic contracts define the first delivery. Verify any live harness documentation when implementing that later adapter rather than carrying forward an unpinned assumption.

### Revision log

- **2026-10-16, original:** proposed model-free capture, continuation advice, TORC integration and a cost comparison. It conflated handoff footprint with evidence needed for reliable recovery in several gates.
- **2026-10-19, round 1:** separated recovery evidence from the verified capsule, added exact prefix and binding rules, narrowed first-PR ownership, corrected platform claims and distinguished metered API cost from a subscription endpoint.
- **2026-10-19, round 2:** separated coverage from visible operations, held failures with possible effects, corrected artifact-writer and store-unchanged citations, split arm-independent evidence from arm-specific binding, and added all-attempt accounting and non-inferiority. These substantive corrections remain.
- **2026-10-19, round 3:** introduced quiescence, fixture intents, occurrence schedules, retry claims, journal state and P3 rebinding. This pass retains their counterexamples and evidence boundaries while removing their execution machinery.
- **2026-10-19, round 4:** added per-tool crash recovery, whole-claim publication, predecessor ordering and scripted/realistic tiers. This pass retains the warning about answer-key benchmarks and removes the protocols that still failed round 5.
- **2026-10-19, final pass:** made the scope decision and authorized the reduced first implementation. Replaced retry guarantees with explicit holds and limits, removed mutable publication pointers and rebind logic, retained measurable Experiment A/B and all-attempt endpoints, checked baseline citations, and disposed of all three round-5 findings above. The decision log records each round-3/4 addition. No further review loop is proposed.
