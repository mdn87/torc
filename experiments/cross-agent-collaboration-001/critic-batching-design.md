# Critic batching design

## Decision

Use provider-neutral TORC claim capsules and batch only independent, bounded,
tool-free review tasks at the execution-adapter boundary. Do not use native
subagent delegation as a token-saving mechanism. Require a structured
assessment for every reviewable claim before treating batching as quality-safe.

This is an experiment design, not a new TORC runtime responsibility. Provider
calls, routing, retries, and usage accounting remain in the harness adapter.

## Evidence behind the decision

| Trial | Quality result | Provider input | Completion time |
|---|---|---:|---:|
| Compact capsule versus full visible bundle | Same median deterministic recall | 7.0% lower | 8.0–14.2% slower by candidate |
| Local native Codex subagent | Full recall, but incomplete transport observability | Child 5.0% below direct; root plus child 304.6% above direct | 246.0% above direct |
| Two-candidate batch capability | Both candidates full recall | 42.7% below summed direct medians | 35.8% below summed direct medians |
| Free-text batch confirmation, three completed calls | Strictly stopped at 5/6 full-recall critiques | Descriptive median 42.8% below direct | Descriptive median 36.1% below direct |

The batching saving is consistent with amortizing roughly one large fixed
Codex harness context. Shrinking the explicit capsule alone cannot remove that
fixed cost. Adding another native root makes it worse.

The stopped confirmation also exposed a protocol problem. Its failed critique
cited the correct `x5` claim and described malformed-input and unknown-action
failures, but split the evidence across findings and used `failing closed`
rather than an exact lexical term. The frozen result remains a failure. The
production-shaped fix is structured coverage, not a post-hoc score override.

## Structured result contract

For each candidate, the batch result contains:

1. The candidate identifier.
2. One ordered assessment for every reviewable claim in the capsule.
3. `met` or `unmet`, concrete evidence, and finding references for each claim.
4. A normal critique whose findings use the same stable claim identifiers.

Every `unmet` assessment must reference at least one finding that cites that
same claim. A `met` assessment cannot reference a finding. Open-work questions
remain visible in the capsule but are not misrepresented as candidate
predicates.

Every finding must also be linked back from at least one `unmet` assessment.
That structural linkage replaces lexical unsupported-finding matching as the
quality gate. The older lexical score remains in the evidence only for
comparison; wording variants cannot decide the structured result.

The expected statuses remain in the scorer and are not sent to the critic. The
critic sees only the claim text, candidate source, and output contract.

## Provenance and accounting

An adapter should retain:

- capsule, candidate, prompt, and output hashes;
- ordered candidate membership and one batch identifier;
- exact model, effort, tool, session, and harness controls;
- each claim assessment and its finding links;
- total provider-reported batch usage and timing;
- validation, exclusion, and retry disposition.

Do not manufacture per-candidate token totals from one provider call. Store the
batch total and compare it with a matched sum of separate-call controls. A
candidate projection and assessment remain derived artifacts, never canonical
lineage truth or an authority transfer.

## Safe batching boundary

Batch only work that is:

- read-only and tool-free;
- independent across candidates;
- governed by the same model, effort, data boundary, and output contract;
- small enough for explicit candidate delimiters and exact attribution;
- safe to fail as a complete batch when schema or identity validation fails.

Do not batch authority changes, mutable implementations, dependent workflow
steps, mixed policy domains, secrets with different access boundaries, or work
whose result depends on ordering. Keep the tested batch size at two until a
broader fixture set earns a larger bound.

## Next evidence gates

1. Run the frozen one-call `critic-claim-matrix-capability-001` only after the
   five-hour usage window falls below 60%; do not consume a reset credit.
2. On success, freeze four fresh structured batches in `AB, BA, BA, AB` order.
   Exclude all capability and free-text calls from that estimate.
3. Add at least two new fixtures with different claim shapes before making a
   general quality claim or testing a batch size above two.
4. When Claude organization policy permits inference, run the same structured
   contract as a separate provider series. Compare quality and latency, but do
   not combine tokenizer totals.
5. Add an execution-adapter integration only after the structured confirmation
   passes. Keep TORC core provider-neutral.

Stop pursuing batching if structured coverage repeatedly misses explicit
claims, median input saving falls below 25%, or attribution cannot fail closed.

## Pending capability command

First recheck usage:

```text
python experiments/cross-agent-collaboration-001/codex_usage_snapshot.py --stop-threshold 60
```

Then inspect the model-free request. The live runner independently verifies the
plan, prompt, apparatus hashes, exact run directory, and usage gate:

```text
python experiments/cross-agent-collaboration-001/critic_claim_matrix_probe.py
```

The frozen plan hash is
`245da3f6520bf31ce5fd60692081dc95914b09934ae80e70418bffc2df760931` and
the prompt hash is
`f5f867a4eb3b7bbfe7671fad3314a618295125c5db954472ecd761668be8065f`.
