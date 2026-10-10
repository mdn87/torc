# Critic batch adapter contract

This reference policy turns the confirmed batching result into an opt-in
execution-layer contract. It does not call a provider, select a route, grant
tools, or change TORC authority.

`critic_batch_adapter.py` accepts two immutable critic job descriptors and an
immutable operating bound earned by a named evaluation. It batches only when
both jobs are independent, read-only, tool-free, share provider, model, effort,
policy boundary, data boundary, and output contract, and match that approved
operating bound. Every other case produces a direct-execution decision with
explicit reason codes.

An eligible decision binds ordered candidate IDs, payload hashes, claim IDs,
and execution controls into a deterministic batch ID. The adapter validates
payload hashes before constructing the envelope. On return it requires exact
candidate order, complete claim coverage, same-claim finding links, and no
unlinked findings. Any mismatch rejects the entire response.

Usage remains one aggregate provider record. The adapter refuses invented
per-candidate token allocations. Its receipt is derived evidence and explicitly
records that no lineage authority changed.

The owning Lugos execution adapter may serialize the envelope for its provider
and persist the receipt. TORC core should only supply or reference the claim
capsules and record resulting artifact hashes where an authorized workflow
needs provenance.

The evidence-replay tests feed both recorded Series 008 batch orders through
this contract. They recover all expected claim statuses, retain the provider's
14,618-token aggregate record, and confirm that the derived receipt changes no
authority.

Envelope construction and response validation recompute the decision from its
retained operating bound and supplied jobs. Changing payload hashes, claims,
controls, or order therefore invalidates the decision. A finding must be linked
from every claim it names, so partial attribution cannot mark a named claim met.
Aggregate usage rejects boolean counters and non-string keys.
Job descriptors enforce immutable tuple IDs and valid scalar types. Malformed
nested JSON values fail with an adapter error. An approval may contain only
nonblocking findings; a changes-requested verdict must contain a finding.

The next consumer step is specified in
[the integration proposal](critic-batch-integration-proposal.md). Its local
model-free transport smoke and authorized TORC evidence checkpoint are now
implemented in `critic_batch_consumer_smoke.py` and `critic_batch_provenance.py`.
They preserve the full response and aggregate receipt, label replay usage,
reject incomplete claim sets before dispatch, and retain the same lease.
