# Project Snapshot Schema Reference

All three contracts use JSON Schema Draft 2020-12 and provider-neutral URNs:

- `schemas/evidence-bundle.v1alpha1.schema.json` —
  `urn:lugos:artifact:evidence-bundle:v1alpha1`
- `schemas/project-snapshot.v1alpha1.schema.json` —
  `urn:lugos:artifact:project-snapshot:v1alpha1`
- `schemas/acceptance-receipt.v1alpha1.schema.json` —
  `urn:lugos:artifact:acceptance-receipt:v1alpha1`

Matching Python contracts and the future producer protocol live in
`src/torc/artifacts/model.py`.

## Canonical identity

TORC reuses `torc.canonical.canonical_json`: UTF-8 JSON, Unicode preserved,
object keys sorted lexicographically, no insignificant whitespace, and no
trailing newline in the hashed bytes. This deterministic serializer is not a
claim of complete RFC 8785 numeric normalization.

An identity cannot hash itself. For each record, TORC removes only its identity
field (`bundle_id`, `artifact_id`, or `receipt_id`), hashes the remaining
canonical JSON bytes with SHA-256, and writes `sha256:<lowercase hex>` back to
that field. Every other field, including timestamps, warnings, generator
provenance, validation checks, and errors, participates in identity.

## Evidence Bundle

An Evidence Bundle contains one or more repository identities and commits,
the collection timestamp and collector version, explicit source records,
bounded Git state, and warnings. Each source embeds the selected UTF-8 content,
its repository-relative path, commit, selector, and SHA-256 content digest.
The initial collector supports whole-file and 1-based inclusive line-range
selectors.

Git state distinguishes modified and untracked paths, records clean or dirty
state explicitly, and includes a manifest-bounded recent-commit list. A dirty
worktree is evidence, not an error and not silently normalized.

## Project Snapshot Artifact

A Project Snapshot records its timestamp, repository scope, producer
provenance, Evidence Bundle reference, projects, claims, blockers, pending
decisions, recent activity, conflicts, unknowns, and metadata. `provider` and
`model` are optional arbitrary provenance strings. No core behavior branches on
them.

Claim status is exactly `verified`, `asserted`, `conflicted`, or `unknown`.
Every verified claim needs at least one evidence reference and every referenced
source identifier must resolve in the supplied bundle. Unsupported material is
asserted, conflicted, or unknown; it is never upgraded to verified.

Progress uses explicit milestones, statuses, gates, deliverables, or passed
checks. Numeric progress is valid only as a source-backed numerator and
denominator (`ratio`) or a source-backed authoritative percentage. The
validator never derives a percentage from prose.

## Acceptance Receipt

An Acceptance Receipt references the canonical snapshot and Evidence Bundle
digests, validator version, validation timestamp, named passed and failed
checks, warnings, errors, and `accepted` or `rejected` status. An accepted
receipt cannot contain errors or failed checks. A rejected receipt must contain
both an error and a failed check.

Acceptance never adds state to the candidate. A content-valid rejected
candidate remains in `candidates/`; a digest-mismatched input receives a
rejected receipt but is not installed as a content-addressed candidate. Only an
accepted receipt permits writing `accepted/` and atomically replacing
`current.ref`.
