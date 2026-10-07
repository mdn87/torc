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
