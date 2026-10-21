# Continue whole-task usage accounting

Implement `src/torc/continuation_usage.py` with `account_task(task: dict) -> dict`.
The function consumes offline evidence. It must retain every attempted start,
failed reconstruction and fallback through completion or declared failure.
There are no provider calls, discovered request inventories or inferred costs.

## Retained investigation and decisions

`torc.experiment_usage.normalize_usage` is the existing counter owner. Reuse it
and its five `TOKEN_FIELDS`: input, cached input, cache-write input, reasoning
output and output. Missing counters stay null. Reasoning output must not be
added to output a second time. Canonical JSON/hash helpers already exist.

Exporter observations may be cumulative snapshots or deltas. Summing a final
session total with its request components was rejected: choose one disjoint
coverage basis. Counter resets need distinct epochs/groups; do not guess one.
A group may cover requests from several attempts. Such a group can support the
whole-task total while leaving per-attempt allocation unknown.

The subscription proxy is `input + cache_write + output`. It requires explicit
compatible semantics evidence. Cached input remains separate. Total context
is `input + cached + cache_write` only when non-overlap is explicitly established.
Actual API cost is unavailable in this task. Known subtotals are diagnostics,
never replacements for missing whole-task usage or evidence of savings.

## Input contract

A task has nonempty `task_id` and `arm`, `outcome` equal to
`verified_completion` or `declared_failure`, a nonempty
`completion_evidence_ref` for verified completion, and lists `attempts` and
`usage_groups`. Do not mutate it.

Every attempt has a unique `attempt_id`, terminal `status` (`failed` or
`completed`), boolean `context_delivered`, `arm_independent_setup_failure` and
`requests_complete`, a `fallback_from` ID or null, and a `requests` list.
A fallback refers to a preceding failed attempt. Requests have a task-unique
`request_id` and nonempty `role` and `phase`; phases are provenance, not an enum.
An empty but explicitly complete inventory represents zero requests, not zero
attempts. At least one attempt is required.

An optional nonempty `exclusion_reason` is valid only for a failed,
arm-independent setup before context delivery, with complete empty request
inventory and no fallback parent. List exclusions without erasing the attempt.
Failures after delivery are never setup exclusions.

Each usage group has unique `group_id`, nonempty unique inventoried
`request_ids`, `mode` (`cumulative` or `deltas`), boolean `complete`, nonempty
`source`, `exporter_version`, `semantics`, and an `observations` list.
Group request sets must not overlap. `semantics` has boolean `proxy_compatible`
and `input_cache_nonoverlap`, backed by nonempty `evidence_ref` when true.

Each observation has a nonempty `observation_id`, nonnegative integer
`sequence`, nonempty `evidence_ref`, and raw `usage` object or null accepted by
the existing normalizer. Its optional `mode` must agree with the group.
Retain all raw observations. Count exact duplicate observation IDs once;
reject conflicting reuse or distinct IDs sharing a sequence.

Cumulative mode uses the final sequence's counters, without backfilling fields
missing from that final observation. Reject a decrease in any observed field
across the sequence. Delta mode sums unique sequences, propagating absent
fields. Empty observations are unknown usage. Incomplete groups, uncovered
requests or incomplete inventories prevent full totals.

## Output contract

Return the original input under `input` plus `input_sha256`, task identity,
outcome and completion evidence. Use `schema_version:
torc.continuation_usage.v0` and `normalization_version:
torc.experiment_usage.normalize_usage.v1`. Retain enriched `groups`, including
raw observations with `normalized` values, `counters`, duplicate observation
counts and normalization provenance.

Include `attempt_count`, `failed_attempt_count`, `fallback_attempt_count`,
`excluded_attempt_count`, `request_count`, and enriched `attempts`. At both
task and attempt levels, include:

- `totals` and `known_subtotals`, each keyed by all five token fields;
- `missing_group_ids_by_field`, `uncovered_request_ids`,
  `unallocated_group_ids`, and `request_inventory_complete`;
- `uncached_processed_token_proxy` and `proxy_unavailable_reason`;
- `total_context_tokens` and `context_unavailable_reason`;
- null `api_cost` and `api_cost_unavailable_reason: no_actual_billing_evidence`.

A cross-attempt group appears in each affected attempt's unallocated list and
makes that attempt's full counters unknown. Its whole-task counters still count
once. Missing required summands produce null metrics. Use reason
`counter_semantics_unverified` for unqualified semantics and
`missing_or_unallocated_usage` for incomplete evidence; available metrics have
null reasons. Reject invalid inventory, counter ambiguity and exclusions with
`ValueError` or the existing normalizer's validation error. Do not silently fix
evidence or assume that an absent exporter field means zero.

Only this new module may remain changed. Preserve the existing normalizer,
authority, capsule code and dependency set. Hidden acceptance exercises failed
starts/fallbacks, omissions, duplicates, overlapping groups, session allocation,
counter resets, malformed counters and setup exclusions.
