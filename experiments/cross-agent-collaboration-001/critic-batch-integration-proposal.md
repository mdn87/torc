# Critic batch integration proposal

Status: the local model-free consumer and TORC provenance gate are implemented
and tested. The owning Lugos checkout is unavailable here; its concrete module
and assignment mapping remain a separate consumer integration.

## Result to deliver

Add an opt-in path for two already authorized, independent, read-only,
tool-free critic jobs. The execution owner prepares their capsules, applies
the reference policy, makes one provider call when eligible, and stores a
validated aggregate receipt. Ineligible work follows its existing direct path.

The [reference contract](critic-batch-adapter-contract.md) supplies the local
policy. [Integration boundaries](../../docs/integration-boundaries.md) keep
assignments, provider routing, execution, retries, and usage in Lugos; TORC
retains capsule provenance and references to resulting evidence.

## Evidence and initial bound

The [Series 008 audit](critic-claim-link-replication-008-analysis.json) reproduced
four batches across both candidate orders: 48 correct claim decisions, no
unlinked findings, 47.2% median input reduction, and 7.8% median completion
reduction against matched direct controls. These are synthetic fixture results.

Start with the evaluated combination only:

| Control | Initial value or requirement |
|---|---|
| Evaluation | `critic-claim-link-replication-008` |
| Provider / model / effort | `codex` / `gpt-6-sol` / `low` |
| Output contract | `compact-claim-link-v1` |
| Batch size | Exactly two |
| Access / tools | `read_only` / `none` |
| Dependencies | None for either job |
| Policy and data boundaries | Equal; independently approved by the execution owner |
| Harness and session | Match the frozen evaluation: `codex-cli 0.159.3`, fresh ephemeral |

These identifiers describe recorded evidence, not current route availability.
The execution owner must resolve its authorized route and compare the effective
controls before dispatch. A changed model, effort, harness, provider, contract,
policy boundary, or fixture family needs a new frozen evaluation before the
operating bound expands. Input reduction is the primary benefit; latency is
secondary.

`BatchOperatingBound` binds evaluation ID, provider, model, effort, contract,
and size. It does not authenticate an evaluation or validate harness versions,
session controls, policy approval, payload budgets, or assignment permissions.
The consumer must enforce those checks from its trusted configuration and
existing assignment machinery. A worker response cannot choose its own bound.
Pin the evaluation artifacts and approved configuration by hash; equal boundary
labels alone do not establish that a policy or data domain was evaluated.

The implemented compact response has ordered `critiques`, each containing
`candidate_id`, `claim_links`, and `result`. Every reviewable claim appears in
`claim_links`: an empty finding list yields `met`, and a nonempty list yields
`unmet`. Findings carry their claim IDs and concrete evidence. There is no
separate ordered assessment array or evidence field for a `met` claim. The
reference validator rejects blocking findings under `approve` and requires a
finding under `changes_requested`. Nonblocking findings may accompany approval.
`validated` still confirms structure and attribution rather than finding truth.

## Consumer flow

1. Validate both existing assignments and their effective execution controls.
   Freeze each exact capsule and candidate payload as UTF-8, its SHA-256, and
   its complete reviewable claim IDs. Keep open-work questions separate from
   reviewable predicates. Record assignment and canonical source references
   outside the model-visible payload.
2. Construct two `CriticJob` records with tuple claim and dependency IDs. Load
   the approved `BatchOperatingBound` from execution-owner configuration.
   Pass an explicit operator or assignment opt-in to `decide_batch`.
   The reference descriptors enforce tuple and string types, rejecting mutable
   ID lists before a decision can be constructed.
3. On `direct`, retain the reason codes and use the existing direct execution
   path, subject to the original assignments. On `batch`, use
   `build_envelope` to verify exact payload bytes against the decision.
4. Serialize and hash one bounded prompt through the existing tool-free
   transport. Preserve candidate delimiters and order. Include the batch ID
   and require the exact response envelope. Check context and output limits
   before dispatch; exceeding them uses the direct path before spending usage.
5. Immediately before the call, revalidate the assignments and effective
   controls. Use the existing harness, timeout, route, and usage capture. A
   logical batch ID identifies inputs; each provider attempt also needs its
   own execution-owner attempt ID.
6. Decode the response and invoke `validate_response` with those same jobs,
   decision, and the provider's aggregate usage. Publish candidate results
   only after the entire batch validates. Validation confirms structural
   attribution, not the truth of the model's findings.
7. Persist prompt, output, receipt, and attempt disposition in the execution
   owner's artifact store. Return their references and hashes. An authorized
   TORC activation may append those references through existing evidence
   paths; a batch receipt does not accept a handoff or transfer a lease.

Recorded Series 008 outputs predate the batch-ID response envelope. Their
replay tests wrap existing critiques with a locally calculated ID. The
consumer smoke must exercise the actual serialized request and echoed ID;
replay alone cannot prove transport binding.

## Failure and accounting contract

An eligibility rejection happens before dispatch and can use the ordinary
direct path. A malformed, incomplete, reordered, or misattributed response
rejects both results after dispatch. Preserve its output and aggregate usage
as a failed attempt; never salvage one candidate or silently turn that failure
into two new calls. Retry requires the existing execution-owner policy and a
separate recorded attempt.

Store the full response alongside its receipt: candidate receipts summarize
statuses and finding counts but do not contain the complete finding evidence.
Retain the operating-bound configuration hash, ordered jobs, payload hashes,
canonical source and assignment references, effective controls, prompt and
output hashes, UTC attempt timestamps, elapsed time, disposition, and supplied
usage. Keep input and output counters at batch level. Optional provider
counters remain optional; missing counters are not zero and token counts are
not divided among candidates.
Capture usage from the existing provider transport, never from model-authored
response fields. Counter validation does not authenticate their source.

## Completed local implementation gate

`critic_batch_consumer_smoke.py` implements the model-free consumer using a local
recorded-response transport and fresh attempt directory. Its pinned smoke
configuration restricts exact candidate payloads and complete claim ID sets,
effective harness controls, policy and data boundaries, and prompt/output size.
The consumer tests prove:

- Opt-in disabled or unmatched effective controls use the direct path without
  making a batch call.
- An eligible pair produces one captured request with exact ordered payloads,
  a bound batch ID, and the full required response contract.
- Changed jobs or payload bytes fail before dispatch.
- Valid responses persist complete output and one aggregate receipt, with
  isolated claim results even when both candidates use the same claim IDs.
- Reordering, missing claims, cross-claim links, partially linked findings,
  and malformed responses publish no candidate result and preserve failure
  evidence and aggregate usage.
- Assignment revocation before dispatch prevents a call; a failed response
  does not trigger an implicit retry or direct rerun.
- The path creates no lineage authority change.

`critic_batch_provenance.py` revalidates the unmodified adapter receipt, preserves
the full response and replay context as sealed artifacts, and appends an ordinary
checkpoint under the current lease. It rejects unauthorized and stale-head
callers; verification detects tampered exports. No schema or core execution
surface was added.

Run the complete local consumer and provenance gate with fresh directories:

```text
python experiments/cross-agent-collaboration-001/critic_batch_consumer_smoke.py --output-dir <fresh-attempt-directory> --state-dir <fresh-state-directory>
```

The command makes zero live calls. Usage is copied from the pinned recorded
provider evidence and labeled as replay. A local stand-in echoes the batch ID;
this proves consumer binding and persistence, not live provider behavior.
See [the recorded results](critic-batch-consumer-smoke-009-results.json).

Keep this smoke in the experiment until an actual Lugos consumer is selected.
Port only the small policy and its tests into that consumer's existing
execution boundary; avoid a new provider framework or TORC CLI command.

After that model-free gate, preregister one live consumer smoke with frozen
inputs, controls, usage budget, and stop conditions. It exercises transport and
artifact persistence without expanding the measured operating bound. Parent
repository changes and live calls require separately expanded scope under
the current repository and experiment envelopes.
