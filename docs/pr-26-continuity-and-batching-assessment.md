# PR #26 assessment: portable continuity and bounded critic batching

Status: local architectural and code assessment, 2026-10-08. This is a review
record, not an acceptance decision or a change to TORC runtime policy.

Reviewed [PR #26](https://github.com/mdn87/torc/pull/26) at commit
c600c0bc08430487ed5129041a9699383e32eeb0, based on
bad615ca6303e88edae2e483b74d544657b8cb9e. The local TORC checkout used
for this document is branch agent/p5-receiver-shaped-carry at a056c61. These
are separate branches. The PR contains 133 commits and changes 812 files,
mostly experiment plans, fixtures, run evidence, and tests; only two new
files are under src/torc.

## Assessment in brief

The PR substantially improves the discipline around portable continuity and
independent review. It separates compact text shown to a receiving agent from
the source references and capsule hash held in its control record. It also
turns exploratory critic trials into a bounded, replayable two-job policy
with explicit controls, structural claim coverage, failed-attempt retention,
and aggregate usage accounting.

The guarded worker sessions are experiment apparatus. The PR does not deploy
production subagents, add a TORC provider runtime, or connect batching to
Autowork dispatch. Its measured recommendation is specifically to batch
**two independent, read-only, tool-free critiques** at an execution-owner
boundary. A native Codex subagent probe had correct review quality but failed
its provenance gate and used about 4.05 times the direct critic's total input
when root and child were counted together; the PR preserves that negative
result. See the
[experiment account](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/README.md)
and [batching decision](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic-batching-design.md).

## Significant improvements

| Area | What changed | Why it matters |
|---|---|---|
| Continuity representation | A compact execution capsule carries deterministic claim handles; an off-model control envelope retains source references and a capsule hash. The [decision](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/docs/decisions/0004-separate-control-and-execution-capsules.md) treats provider-native compaction as opaque adapter evidence. | A receiver can consume selected claims without spending context on repeated provenance and authority metadata. TORC can still resolve citations. |
| Usage records | The [normalizer](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/src/torc/experiment_usage.py) preserves provider counters and distinguishes missing values from reported zeroes without inventing cross-provider totals. | Cost comparisons have an auditable basis and do not imply precision that the provider did not report. |
| Experiment design | Hash-pinned visible fixtures, separate hidden oracles, isolated workers, frozen plans, matched direct controls, usage records, and explicit exclusion and stop decisions. The [runner](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/worker_runner.py) applies tool and sandbox controls for experiment calls. | Review quality, cost, and failures can be rechecked against recorded inputs. Failed or ineligible trials remain visible. |
| Review contract | Every reviewable claim receives a structured assessment; findings must link to the same claim. Missing, reordered, or misattributed output rejects the whole batch. | This replaces wording-sensitive lexical gates. The stopped free-text result was retained, then the contract was improved before rerunning. |
| Bounded batching policy | An opt-in [reference adapter](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic_batch_adapter.py) permits exactly two independent jobs only under matching provider, model, effort, policy and data boundaries, tool posture, and output contract. It binds ordered payload hashes and claim IDs to a batch ID. | The optimization has a narrow eligibility rule. Ineligible work uses the direct path; malformed results cannot publish one half of the pair. |
| Evidence and authority | A model-free [consumer smoke](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic_batch_consumer_smoke.py) retains request, response, receipt, disposition, and aggregate usage. The [provenance helper](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic_batch_provenance.py) appends evidence under the existing TORC lease. | A critic result can be recorded without confusing review with succession or granting a child lineage authority. |

The new-fixture replication reports 48 of 48 correct claim statuses across
four batches, all findings linked, and 47.2% lower median provider input
than matched separate calls. Median completion improvement was 7.8% and
varied by run. These are synthetic fixtures under one recorded model, effort,
and harness configuration. They do not establish the same bound for another
provider, larger batch, mutable task, or current route availability. Claude
organization policy also prevented the planned cross-provider comparison. See the
[recorded analysis](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic-claim-link-replication-008-analysis.json)
and [integration proposal](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic-batch-integration-proposal.md).

## Fit with TORC's concept

The [original concept](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/docs/concepts/0001-torc-original-concept.md) centers on a
continuously revised self carried forward in a shape and size fitted to the
receiving agent. Snapshot provenance makes that carry trustworthy.
[ADR 0001](decisions/0001-torc-is-a-control-plane.md) keeps inference and
execution outside TORC; [ADR 0002](decisions/0002-canonical-lineage-and-projection-are-separate.md)
keeps canonical evidence separate from derived projections; and
[the local ADR 0004](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/docs/decisions/0004-torc-is-always-in-charge.md) assigns the
receiver-facing carry to TORC.

| Concept requirement | PR contribution | Remaining work |
|---|---|---|
| Durable lineage with provenance | Claim handles resolve through a separate control map; review evidence can be attached to a checkpoint without moving the lease. | Outside an in-memory experiment, verify the capsule and control map against a sealed projection and canonical sources. The current helper's control record is narrower than the PR decision's described omissions and authority context. |
| Receiver-shaped carry | A smaller, portable model-facing format is available. | The [capsule builder](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/src/torc/execution_capsules.py) accepts caller-supplied sections. It does not select from history, derive the receiver budget, or compile a P5 projection. |
| Continuously revised self-model | The experiment makes claims and critic evidence more inspectable. | It does not revise the self-model or prove that a recipient performs better because of the carry. The live comparison against a compiled prompt remains due under the [project brief](project-brief.md). |
| Best available frontier agent | The experiment records one provider/model/effort bound and compares review transports. | It does not select the best bearer. TORC evaluates lineage fit; Orca advises loadout; the operator or Autowork authorizes the actual route and permissions. |
| Controlled authority | Batch receipts leave authority unchanged and use the existing checkpoint path. | A native child receiving context is an observer unless a separate accepted TORC handoff or branch establishes its lineage role. Autowork authorizes policy-bound dispatched work; native interactive children follow harness and applicable user/project admission. |

The local [P5 receiver-fitted carry](https://github.com/mdn87/torc/blob/a056c61be4dddce8a71fd9cb31f585b70a3b510d/docs/p5-receiver-carry.md) already reads
canonical revision history, derives the budget from the receiver descriptor,
surfaces unaccounted drops, and asks for self-model restatement. PR #26 was
branched before P5 and does not call that compiler. The coherent composition
is **verified P5 projection → task claims → compact capsule**, while the
control envelope retains P5 source references, omissions, compiler/budget
evidence, and authority context. A read-only critic may receive a narrower,
task-scoped derivative that grants no lineage authority. An actual successor
must receive every required P5 continuity field and pass the normal handoff
acceptance gate; storing missing material only in the off-model envelope is
insufficient. The capsule must not become an independently authored
replacement for TORC's carry.

Both branches introduce a different decision numbered 0004. Before integrating
them, give the capsule decision a distinct number, state how it implements
the receiver-facing P5 decision, and add a focused P5-to-capsule contract
test. This is a semantic documentation conflict even if Git merges the
different filenames cleanly.

## Findings and disposition

The earlier quick review grouped several issues as possible merge blockers.
The evidence supports a narrower disposition:

| Priority | Finding and evidence | Smallest correction |
|---|---|---|
| **Merge gate** | [Fixture hashing](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/fixture_control.py#L31-L58) sorts native paths. Windows and macOS order mixed-case names differently; all four pinned visible-fixture hashes fail on this clean macOS checkout. Sorting relative POSIX paths by case-folded name reproduces every pin. | Sort on a platform-independent relative path key, using the original path as a tie-breaker; run the fixture audit on Windows and macOS. |
| **Merge gate** | [Consumer approval](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic_batch_consumer_smoke.py#L41-L50) pins two recorded JSON files by CRLF byte hashes, while the committed blobs and checkout are LF. All 25 consumer smoke tests fail before dispatch. | Repin those inputs to committed LF bytes, refresh dependent approval/results hashes, and replay both smoke orders on both systems. |
| **Before reusable capsule integration** | [Claim generation](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/src/torc/execution_capsules.py#L49-L87) accepts prefixes such as c and c1; their generated c11 handles collide, replacing one source mapping. Existing fixed fixture prefixes do not exercise this case. | Reject duplicate generated claim IDs and test overlapping prefixes. |
| **Before live batch integration** | [Usage validation](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic_batch_adapter.py#L240-L252) rejects names containing candidate or beginning per_, but accepts job_1_tokens as an aggregate field despite the aggregate-only contract. | Allow only named aggregate provider counters, or explicitly separate and reject per-job attribution. |
| **Before trusted live accounting** | A changed usage file plus a recomputed receipt can still produce a valid lineage checkpoint. The [integration proposal](https://github.com/mdn87/torc/blob/c600c0bc08430487ed5129041a9699383e32eeb0/experiments/cross-agent-collaboration-001/critic-batch-integration-proposal.md#L100-L119) explicitly says counter validation does not authenticate its source. | Bind captured usage or its digest to immutable attempt evidence before TORC records it. Treat this as an integration gate, rather than claiming the structural validator authenticates counters. |
| **Experiment polish** | The batch probe and series reserve an attempt directory before loading provider settings; a settings error can strand an attempt without a disposition and block retry. | Preflight before reservation or record a failed disposition for every reserved attempt. |

On this macOS checkout with Python 3.14, the PR's full test suite recorded
423 passed and 124 failed; the failures traced to the two portability issues.
Ruff, TORC doctor, deterministic demo, and store verification passed. Focused
capsule and adapter tests passed. The PR had no GitHub checks at the reviewed
head. These results do not overturn the author's reported Windows Python 3.13
result; they show that the same commit does not yet pass the project's
cross-platform gate.

## Lugos Orca principles for deployment

Active Lugos Orca is an **advisory loadout and seat planner**. Lugos Link
supplies host facts; Orca resolves a target/profile and returns advisory
autowork_handoff data. In the policy-bound dispatch lane, Autowork owns the
immutable assignment, route, capabilities, sandbox, tool permissions, and
launch. Orca's Codex start
hooks provide scope advice but are fail-open, not an admission or containment
gate. Current Orca policy permits same-harness and same-model review seats
and does not require independent review for every task. The parent Lugos
gitlink reviewed here pins Orca at fbaacba6. Its separate behavior-policy
companion is also read-only advice, resolved after Autowork selects and
observes an occupant; it is not launch authority. See the pinned
[README](https://github.com/mdn87/lugos-orca/blob/fbaacba6ef306bfc4531ee478e52b6f40a336f79/README.md),
[coordinator role](https://github.com/mdn87/lugos-orca/blob/fbaacba6ef306bfc4531ee478e52b6f40a336f79/docs/coordinator-role.md), and
[TORC integration boundaries](integration-boundaries.md).

| Step | Owner and gate | Evidence to keep |
|---|---|---|
| 1. Reconcile and repair | TORC maintainers resolve the two cross-platform merge gates, claim-ID collision, duplicate ADR numbering, and P5-to-capsule contract. | Clean Windows and macOS fixture audit, full tests, both model-free consumer orders, and one verified P5-to-capsule example. |
| 2. Add a model-free consumer | Autowork's execution owner admits two separate, already authorized read-only/tool-free critic assignments. Orca supplies seat/loadout advice only. The owner checks effective controls and applies the reference batch policy, with direct fallback before dispatch. | Assignment IDs, exact capsule/claim hashes, effective route and sandbox, one batch decision, rejected attempts, and aggregate usage. TORC receives evidence references under the current activation and lease. |
| 3. Run one live synthetic canary | Preregister provider/model/effort/harness, two independent jobs, token/time ceiling, stop rules, and a direct control. If current controls differ from the recorded bound, earn a new bound first. | Full root-plus-worker cost, prompt/output/usage digests, complete claim links, assignment revalidation, and no automatic retry after a failed batch. |
| 4. Pilot real read-only review | After the canary passes, enable a small opt-in review lane and compare quality, cost, and latency with direct calls. Keep mutable or dependent work on its existing path. | Per-attempt disposition and quality and operational-overhead review. |
| 5. Test the central continuity claim separately | Compare a P5-shaped carry with a carefully compiled prompt on real dropped-work or receiver-change tasks. | Receiver reconstruction quality, retained commitments, omissions, overhead, and whether P5 earns its added machinery. |

Native subagents remain useful for bounded independent interactive work when
the user or project policy admits them. They can receive a task-scoped TORC
projection as **observers** without inheriting a lineage lease. A child
becomes the authoritative bearer only through TORC's normal accepted handoff
or explicit branch protocol. Orca may advise the seat; it does not launch
the child or grant authority. PR #26 gives no basis to deploy native
subagents as a general token-saving substitute for the measured two-job
execution-adapter batch.
