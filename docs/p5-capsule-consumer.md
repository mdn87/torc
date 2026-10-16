# Verified P5 capsule consumer

`torc projection capsule` renders an existing P5 carry into the v1 claim
capsule and control envelope. It also returns a composition record containing
the projection binding, budget, omissions, redactions, remaining content and
the exact projection field path for each claim. It opens the store read-only.

First obtain a carry through the existing operator command:

```sh
python -m torc lineage carry --state-dir <store> --lineage <lineage> \
  --substrate-file <receiver.json> --json
```

Keep `projection.projection_id` and
`projection.integrity.canonical_payload_sha256` from that response. Pass them
to the consumer; do not replace the expected hash with a fresh store lookup:

```sh
python -m torc projection capsule --state-dir <store> \
  --projection <projection-id> --record-sha256 <carried-record-hash> --json
```

Success returns `report_kind: projection_capsule`, `trusted: true`, the
`capsule`, `control`, and `composition`. Rejection exits nonzero with
`trusted: false`, a detail, and a named `code` for composition failures.
No capsule is returned on rejection. A missing store is not created or migrated.

The Python boundary is `torc.p5_capsules.derive(store, projection_id, hash)`.
Before publishing a supplied triple, call
`verify(store, projection_id, hash, capsule, control, composition)`. Both use
one SQLite read snapshot. They check row/payload agreement, the sealed hash,
the expected hash, matching compiler/policy pairs `p5-1` or `p5-2`, and the whole lineage integrity
gate used by carry. Verification compares the full objects with a fresh
rendering, including section placement, source mappings and extra keys.

## Rendering contract

- Identity label, role and session/handoff purpose become capsule headers.
- Constraints, commitments, open work, goals, settled decisions, uncertainties,
  methods, artifact references and memory references become claims in stored
  order. Empty lists remain listed in the composition inventory with zero claims.
- Unaccounted history items and removed items become history claims. Their
  dispositions remain visible in the section names. Repeated items in different
  selected sections remain repeated.
- Every remaining content field stays in `composition.recorded_fields`,
  including receiver fit, self-model provenance, authority context, extra
  identity fields and added-item history. The renderer does not restore omitted
  content or select a different budget. Unknown sections or invalid claim items
  reject instead of being silently discarded.

The capsule uses the existing v1 formats. Its source map resolves to the
projection's references. A removed item's reference can name a revision that
lacks its text; the composition proves faithful rendering of the stored P5
projection, not a stronger history attribution than that projection supplies.

## Testing and limits

The contract tests exercise small and large receivers, a capped budget, returning
receivers, handoff projections, altered records and resealed output substitutions.
They compare both the database dump and every state-directory file before and
after consumption. The original capsule compiler and frozen experiment fixtures
remain unchanged.

The expected ID/hash pair is the caller's trust anchor. A hostile filesystem
writer who can replace both a record and the caller's expected pair is outside
this boundary. Older correctly bound projections remain readable after the
lineage advances; this action makes no freshness claim. Carry and composition
grant no authority and do not demonstrate improved receiving-model outcomes.

Lugos exposes this through `lugos.torc` action `projection.capsule`. The parent
repository's `scripts/torc_testing.py` creates a fresh fixture store and exercises
discovery, explanation, composition and rejection through a real local MCP stdio
session. Deployment of shared host state is separate from this local test path.
