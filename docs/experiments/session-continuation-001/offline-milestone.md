# Existing-capsule integration and offline accounting

This milestone continues `a798bbc` with two library modules and a deterministic
synthetic replay. It implements the bounded Phase 3 bridge and Phase 4 token
arithmetic. It does not run the model comparisons, establish token savings,
install hooks, or execute retries. The [preregistration](protocol.md) remains
incomplete for live trials.

## Reproduce the report

From the repository root, using the development environment:

```sh
mkdir -p /tmp/torc-continuation-replay
PYTHONPATH=src python3 docs/experiments/session-continuation-001/replay.py \
  --output-dir /tmp/torc-continuation-replay \
  > /tmp/torc-continuation-replay/report.json
diff -u docs/experiments/session-continuation-001/offline-report.json \
  /tmp/torc-continuation-replay/report.json
```

The [retained report](offline-report.json) pins the replay, implementation and
fixture bytes. The replay creates its own temporary authoritative store with
fixed identifiers and timestamps. After fixture setup, the bridge runs against
a read-only store; its SQLite dump and every state file must remain unchanged.
Derived artifacts are published separately with the existing create-once
publisher. Identical replay output is reusable. The output directory contains
the full raw/normalized accounting evidence and separate capsule, capture,
report and binding artifacts referenced by the summary.

The synthetic result is:

| Case | Attempts / failed / fallback | Requests | Input / cached / cache write / output | Token proxy |
|---|---|---|---|---|
| Failed reconstruction, then fallback | 3 / 2 / 1 | 2 | 20 / 40 / 6 / 10 | 36 |
| Missing fallback output | 3 / 2 / 1 | 2 | 20 / 40 / 6 / unknown | unavailable |
| Session cumulative total spanning attempts | 3 / 2 / 1 | 2 | 20 / 40 / 6 / 10 | 36 |

The first failed start has an explicitly complete empty request inventory, so
it counts as an attempt with zero model requests. Failed reconstruction and
fallback both contribute usage. Duplicate cumulative observations do not add
usage. A session group spanning attempts has a known task total but unknown
attempt/fallback allocation; the full accounting artifact records that limit.
There are no actual API charges in these fixtures. CPU and human time remain
separate supplied measurements. These numbers are arithmetic fixtures, not
performance or savings results.

The small capsule omits uncertainties while the separate report retains its
uncertain operation and coverage hold. The bridge reports `held`, unknown
quiescence, and `retry_authorized: false`.

## Capsule and context contract

`torc.continuation_context.derive_capsule_context` takes a read-only `Store`,
the carry response's projection ID and expected record SHA-256, and the existing
reconciliation report. It calls the unchanged capsule `derive` and `verify`.
Its returned `capsule`, `control`, and `composition` remain the existing objects;
the new `binding` is separate. The report must name the projection's lineage
and source revision. A different base requires a fresh report and suitable
carry through the existing owners, not mutation of the old evidence.

`verify_capsule_context` requires that same expected projection pair, the
independently retained `expected_binding_id`, the separate report, exact
`delivered_context` bytes and current observations. It verifies the full
composition and reads the actual lineage head in the same SQLite snapshot.
Acceptance therefore makes an old pairing stale even when a caller mistakenly
supplies the old head. A valid historical capsule remains valid historical
rendering; the bridge adds no freshness claim to its verifier. Existing P3
acceptance/rejection, authority transfer and lease semantics are unchanged.

TORC context bytes are canonical JSON encoded as UTF-8 **without a newline**.
The binding hashes those exact bytes and canonical report JSON without a
newline. Its own ID hashes its canonical body without `binding_id`. Published
artifact filenames retain the existing convention: hash the full serialized
file including its newline. Pins must come from the owner, not from an
untrusted replacement object supplied alongside a replacement hash.

For `compiled_prompt`, `native_warm` and `native_cold`, use `bind_context` and
`verify_context` with an explicit context identity and exact delivered bytes.
The same report bytes can accompany all arms. A native context may be an opaque
owner-supplied versioned handle: its binding covers that handle, not undisclosed
provider state behind it. Generic binding alone never verifies a TORC capsule,
probes a workspace, confirms freshness, or grants authority. Reports already
marked stale remain stale even if bound again. Substitution rejects; ordinary
staleness is reported without changing retained evidence.

## Accounting input contract

`torc.continuation_usage.account_task` consumes one complete offline task record.
See [the executable fixture](fixtures/offline-usage.json). IDs are scoped by
the exporter before import. Every task has an originating `arm`, terminal
`outcome` and ordered `attempts`. Verified completion requires an independent
`completion_evidence_ref`; the accountant retains this assertion without
performing task scoring. Failed starts, reconstruction, retries, root/subagent
requests, retrieval, reconciliation, synthesis and fallback all belong in the
inventory through completion or declared failure. The module cannot discover
an omitted attempt or call.

Each attempt includes a unique ID, terminal status, `context_delivered`,
`arm_independent_setup_failure`, `requests_complete`, and a request list. Each
request has a task-unique `request_id`, `role` and `phase`. A `fallback_from`
names a preceding failed attempt. All attempts and their metadata are retained
under the task's original arm. An `exclusion_reason` is allowed only for an
arm-independent failed setup before context delivery, with an explicitly
complete empty request list and no fallback parent. Exclusions are listed and
counted; post-delivery failures cannot disappear.

`usage_groups` partitions the observed requests. A group identifies its covered
`request_ids`, source, exporter version, completeness, counter mode, semantics
evidence and observations. It may cover one request or an explicitly bounded
session containing several requests. No request can belong to two groups.
Choose a session total **or** its request/delta components. Overlap rejects;
the module does not guess which exporter is authoritative. A cumulative
session must start at zero for the listed requests, or the owner must supply
validated deltas excluding pre-task usage. An unbounded lifetime total is not
a task total. Reset epochs require separately scoped identities and disjoint
request groups; the accountant does not infer them from a counter decrease.

Each observation carries `observation_id`, integer `sequence`, raw `usage`
(object or null), and an `evidence_ref`. The existing `normalize_usage` supplies
normalized counters and retains raw fields. Exact repeats of an observation ID
deduplicate; conflicting repeats or ambiguous sequences reject. In cumulative
mode the highest sequence is used once, regardless of input order. Decreasing
reported counters reject, and absent final fields stay absent. In delta mode,
unique observations sum once; missing delta fields make that field's total
unknown. Modes cannot be mixed within a group. `complete` asserts that the
owner supplied the entire group's usage through its endpoint. Incomplete groups
and incomplete request inventories make full totals unavailable.

Aggregates retain the input hash, raw observations, evidence references,
exporter version, normalization version, request/attempt components, missing
fields and uncovered requests. Known subtotals are labeled diagnostics and
must not be used as whole-task savings endpoints. If a cumulative group spans
attempts, per-attempt totals remain unavailable instead of dividing the group
arbitrarily. This preserves an honest fallback cost limit.

The uncached-processed proxy is `input + cache_write + output`. Cached inputs
remain separate, and reasoning output is not added again. The proxy requires
an explicit `proxy_compatible` assertion backed by a semantics evidence
reference; total input context additionally requires
`input_cache_nonoverlap`. These flags describe independently validated exporter
semantics, not a property inferred from normalized names. Missing required
summands make the metric unavailable. API cost is always unavailable in this
slice because it has no actual billing evidence or pricing adapter. No dollar
value, cache hit or missing zero is fabricated.

## Dispatch and scope disposition

Autowork preflight did not pass. The registered `lugos.models` schema advertised
`allowed_paths` and `verification` as arrays of strings, while the repository's
dispatch skill requires structured path and argv objects. A read-only `help`
request did not return before the lead terminated the wait. No `delegate`
request was sent, no assignment/run ID was created by this work, and there was
no child writer to recover. Both workstreams were implemented by the lead;
the requested Autowork condition was not satisfied. No alternate child or
provider was launched. This is a tooling limitation, not an experiment result.

The consolidated self-review retained the existing authority and capsule
verifier contracts. It classified ambiguous overlapping usage as requiring
rejection, missing telemetry and cross-attempt allocation as explicit unknowns,
and live capture, API billing adapters, opaque-provider-state verification and
trial inference as later work. The unrelated untracked planning document was
preserved. Parent repository and submodule pointer changes remain out of scope.

## Verification

The focused suite covers read-only store/file invariance on success and error,
resealed extra-claim rejection, exact context/report/pin substitution, tight
budgets, byte-identical reports across arms, and staleness after actual P3
acceptance. Accounting tests cover failure/fallback costs, missing raw and
individual counters, duplicate/out-of-order snapshots, deltas, ambiguous
overlaps, counter resets, invalid counters, unverified semantics and exclusions.
The replay test compares two independent runs with the retained report and
checks content-addressed output hashes.

Run `python3 -m pytest`, `python3 -m ruff check .`, and the repository
doctor/demo/verify sequence. Validation results are recorded in the milestone
scope envelope after final verification. Host-specific filesystem guarantees
remain limited to the tested macOS environment.

Recorded on macOS/Python 3.14: **830 tests passed**, Ruff passed, doctor reported
no missing paths, and temporary demo/verify checked seven artifacts with no
errors. Both independent replay runs matched the retained report byte-for-byte.
Scope-schema, Markdown-link, syntax and diff checks passed. The quick Lugos
Audit passed. The wheel built and both new modules imported directly from it.
The environment lacked setuptools; its isolated build dependency required
approved network access after the sandbox could not resolve PyPI. No project
runtime dependencies changed.
