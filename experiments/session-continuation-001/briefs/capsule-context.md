# Continue the existing-capsule integration

Implement `src/torc/continuation_context.py` against this repository snapshot.
TORC already owns capsule derivation, verification and authority. This task adds
a read-only binding between the exact delivered context and the separate
reconciliation report. It must not introduce another capsule format or grant
authority to a receiver.

## Retained investigation and decisions

The existing owners are `torc.p5_capsules.derive` and `verify`; inspect their
interfaces and the tests around them. The projection ID and expected record
SHA-256 are externally retained pins. A caller-supplied replacement projection
is not equivalent evidence. `Store.read_transaction()` supplies the consistent
read snapshot; `Store.get_lineage()` exposes the actual head.

The small receiver's capsule may omit uncertainties because of its budget.
The reconciliation report still contains uncertain operations and scope holds.
Do not merge recovery text into the capsule, expand its word budget or use a
short capsule as evidence that an omitted concern was resolved. Keep report,
capsule, control and composition separate. Standard canonical JSON and SHA-256
already exist; this task needs no new cryptography.

An earlier idea to let a context binding refresh a stale report was rejected.
Matching a newly made binding does not make old facts fresh. Actual P3 handoff
acceptance advances the lineage head; a caller accidentally reusing the old
base must not hide that change. An unchanged store is part of the contract on
both success and error paths.

## Required interface

Implement these public functions, using keyword-only arguments after `*`:

```python
bind_context(report, *, context_kind, context_identity, context)
verify_context(binding, report, *, expected_binding_id, context_kind,
               context_identity, context, current_bindings)
derive_capsule_context(store, projection_id, record_sha256, report)
verify_capsule_context(store, projection_id, record_sha256, bundle, report, *,
                       expected_binding_id, delivered_context, current_bindings)
```

`context_kind` is `torc_capsule`, `compiled_prompt`, `native_warm` or
`native_cold`. Identity is a nonempty string; context is nonempty bytes.
Native bytes are opaque owner-supplied handles, not portable provider state.
Accept only the existing reconciliation schema, its supported statuses, an
object `base_bindings`, `retry_authorized: false` and `quiescence: unknown`.

The binding is deterministic and includes `binding_id`, context identity/kind,
exact byte hash/length, canonical report hash and a copy of the report's base.
Its immutable fields include `authority_transferred: false` and
`retry_authorized: false`. Use `schema_version: torc.continuation_context.v0`
and a `sha256:`-prefixed canonical payload digest for the binding ID.

Verification rejects a changed binding, external pin, identity, context bytes
or report. Its result preserves the report's `hold_list`, `scope_holds` and
status, plus the binding/report hashes and the no-authority/no-retry/unknown-
quiescence declarations. A missing or mismatching current base makes status
`stale` and adds `bindings_stale`; an already-stale report remains stale.

`derive_capsule_context` must call the existing derive/verify owners, confirm
that the report names the composition's lineage and source revision, and return
`capsule`, `control`, `composition`, `binding`. Bind canonical UTF-8 capsule JSON
without a final newline; use canonical JSON of `[projection_id, record_sha256]`
as its context identity. Do not modify or independently reimplement the capsule.

`verify_capsule_context` must rerun the existing verifier, check the report's
base and exact delivered bytes, then verify the context binding using the
actual store head in place of caller-supplied lineage/revision observations.
Unrelated workspace observations remain caller-supplied. Reject mismatches
with `ValueError` where the new binding contract owns validation; retain errors
from the existing integrity/authority owners. Never silently repair evidence.

Preserve all existing files. The output is this new module, with no dependency,
CLI, provider or schema change. Useful existing checks include the P5 capsule,
carry and operator tests. Hidden acceptance will also exercise exact-byte
substitution, extra resealed claims, stale reports and real P3 acceptance.
