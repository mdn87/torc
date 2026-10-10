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
| Compact claim-link confirmation, four calls | 52/52 statuses correct; 28/28 findings linked | 42.1% below summed direct median | 19.6% below summed direct median |
| New-fixture claim-link capability, one call | 12/12 statuses correct; 5/5 findings linked | 14,618 absolute; no matched direct control | 19.3 seconds; no matched direct control |
| New-fixture matched controls, both orders | 24/24 batch statuses correct; 10/10 findings linked | 47.2% below summed direct in both orders | 9.3%-33.5% below summed direct |
| New-fixture replication, four total batches | 48/48 statuses correct; both orders repeated | 47.2% below summed direct median | 7.8% below summed direct median |

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

1. The candidate identifier, in the requested candidate order.
2. A `claim_links` entry for every reviewable claim in the capsule.
3. An empty finding-ID list for `met`, or same-claim finding IDs for `unmet`.
4. A normal critique whose findings contain concrete evidence and the same
   stable claim identifiers. Evidence is attached to findings, not to met claims.

Every `unmet` assessment must reference at least one finding that cites that
same claim. A `met` assessment cannot reference a finding. Open-work questions
remain visible in the capsule but are not misrepresented as candidate
predicates.

Every finding must also be linked back from every claim it names.
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

## Confirmed operating bound

The four-call `AB, BA, BA, AB` confirmation preserved all 52 expected claim
statuses, linked all 28 findings, and passed every frozen input and completion
threshold. Median provider input fell 42.1% and median completion time fell
19.6% against matched summed-direct controls. Candidate position did not change
quality. The recommendation is therefore batch size two for independent,
read-only critiques with one model, effort, policy boundary, and compact
claim-link contract.

This is a narrow operating bound from two synthetic fixtures, not evidence that
larger batches, dependent tasks, mutable work, or other providers behave the
same way. The older lexical scorer remains descriptive because it mislabeled
two structurally valid critiques.

## Reference adapter policy

`critic_batch_adapter.py` implements the decision boundary without moving
provider execution into TORC. Batching requires explicit opt-in, exactly two
jobs, a named evaluated model/provider/effort/output-contract bound, read-only
tool-free work, no dependencies, and equal policy and data boundaries. It
hash-binds ordered payloads and claim identities, fails the whole response on
coverage or attribution drift, retains only aggregate usage, and records that
lineage authority did not change.

This module is a reference for the Lugos execution owner. It is not registered
as a TORC provider adapter and cannot route or execute a model call.

The local consumer and provenance gate is complete. It adds pinned approval
checks, model-free request/response binding, full failed-attempt retention, and
an ordinary TORC evidence checkpoint under the same lease. See
`critic-batch-integration-proposal.md` and
`critic-batch-consumer-smoke-009-results.json`.

## Next evidence gates

1. Implement batch size two at the execution-adapter boundary for independent,
   read-only critiques under the same model, effort, policy, and output contract.
   Treat input reduction as the primary benefit and latency as secondary.
2. Add a new frozen evaluation before changing batch size, model, effort,
   provider, policy boundary, or task dependency assumptions.
3. When Claude organization policy permits inference, run the same structured
   contract as a separate provider series. Compare quality and latency, but do
   not combine tokenizer totals.
4. Add batching only at an execution-adapter boundary. Keep TORC core
   provider-neutral and retain batch-level usage rather than inventing
   per-candidate token totals.
5. Re-run the frozen structured gates for every new model, provider, effort, or
   fixture family before expanding its operating bound.

Stop pursuing batching if structured coverage repeatedly misses explicit
claims, median input saving falls below 25%, or attribution cannot fail closed.

## Usage-efficient execution

The ChatGPT Plus rate-limit snapshot covers the coordinating Codex session as
well as experiment workers. In this run, the meter rose from 51% to 63% after
the last worker call while the apparatus and documentation were being built.
Long setup work can therefore consume the room reserved for a live cell.

Freeze, test, and commit apparatus in one session, then execute the live cell
early in a fresh post-reset session. The compact
`critic-claim-matrix-capability-001-next.json` checkpoint contained the exact
hashes, commands, guard, and dispositions needed to resume without reconstructing
the full conversation. The runner rechecked every control independently, and
the deferred call ran at 0% five-hour usage without consuming a reset credit.

## Reproduce the confirmation audit

The audit makes no model call. It revalidates all four frozen runs and compares
their aggregate with the matched separate-call controls:

```text
python experiments/cross-agent-collaboration-001/critic_claim_link_confirmation_audit.py --pretty
```
