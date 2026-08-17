# Provider-Agnostic Project Snapshot Artifacts

Status: implemented locally; final verification evidence is recorded in the
task's commits and completion report.

## Outcome and boundary

TORC will gain a local, provider-neutral artifact path that turns an explicit,
bounded set of repository evidence into an immutable candidate project
snapshot, validates it, records acceptance separately, advances a portable
current pointer only after acceptance, and renders the accepted projection as
read-only HTML.

Repository sources remain authoritative. Evidence Bundles preserve collected
facts and source material. Project Snapshot Artifacts are disposable
projections. Acceptance Receipts are immutable validation records. The
`current.ref` file is mutable routing state and is not part of any immutable
record. The renderer is not a task database and never writes back.

The scope envelope is
`docs/project-snapshot-artifacts-scope-envelope.json`. The supported platform
matrix is macOS (`applemac`, `intelmac`) and Windows (`4070pc`, `3060pc`), with
`applemac` as the authoritative implementation and verification host. The
Python contracts and storage layout are platform-neutral; only shell command
syntax differs between PowerShell and POSIX shells.

## Reconnaissance findings

The following repository evidence was inspected before implementation:

- `AGENTS.md`, `CLAUDE.md`, `README.md`, `pyproject.toml`, the architecture,
  domain model, vertical slice, integration boundaries, roadmap, P2 pilot, P4
  visibility contract, schemas, examples, CLI, storage, provenance verifier,
  canonical serializer, and test suite.
- TORC already separates canonical lineage from derived projections and treats
  handoff preparation and acceptance as distinct immutable records. Rejected
  acceptance preserves prior authority. The new records extend these existing
  invariants rather than define a parallel authority model.
- `torc.canonical.canonical_json` and `payload_sha256` already provide compact,
  UTF-8, stable-key JSON and SHA-256 digests. The artifact slice will reuse
  them. This is deterministic JSON serialization, not a claim of complete RFC
  8785 number normalization. Artifact identity is computed over the canonical
  record with its self-referential identity field omitted, then stored as
  `sha256:<hex>`.
- `torc.experiment_runs.write_canonical_artifact` already supplies atomic
  canonical JSON writes with file flush, `fsync`, and `os.replace`. The new
  filesystem store will reuse this primitive rather than create another file
  writer. Its existing experiment stage receipts are workflow-specific and do
  not match the required artifact acceptance receipt contract.
- `Store` and `verify_store` implement SQLite-backed lineage authority and
  immutable exported-artifact metadata. Project snapshots do not transfer
  lineage authority and need content-addressed, portable repository files, so
  they will not add a SQLite migration or overload the lineage artifact table.
- The CLI uses nested `argparse` commands, structured `TorcError` failures,
  `--json` machine output, and nonzero domain-failure exits. The new
  `torc artifact` family will follow that convention.
- Schemas use JSON Schema Draft 2020-12 and tests use `jsonschema` with format
  checking. The artifact validator needs that library at runtime, so the
  existing development-only dependency will become a core dependency.
- Tests are pytest-based, use temporary directories and injected clocks, and
  validate both schemas and behavioral invariants. The baseline before changes
  was 139 passing tests, a clean Ruff run, and a healthy `torc doctor --json`.

## Mission Control boundary

The existing Mission Control integration consumes TORC's read-only lineage
explanation through a published contract and explicitly refuses to open TORC's
SQLite store or recompute authority. It has no project-snapshot artifact
contract today. TORC repository rules also prohibit cross-repository edits in
this slice. Therefore Phase 1 will ship the standalone renderer plus a concise
consumer note; it will not guess at a Mission Control route or modify Mission
Control.

A future Mission Control adapter should validate the same Project Snapshot and
Acceptance Receipt schemas, resolve only an accepted `current.ref`, and render
without writeback or independent provenance inference.

## Three immutable records

1. An **Evidence Bundle** freezes repository identity, commit and branch, clean
   or dirty state, modified and untracked paths, bounded recent commits,
   explicitly configured source contents and hashes, collection warnings, and
   collection provenance.
2. A **Project Snapshot Artifact** is a producer-neutral projection of projects,
   claims, blockers, decisions, activity, conflicts, unknowns, and metadata.
   It references exactly one Evidence Bundle and evidence source identifiers.
3. An **Acceptance Receipt** references immutable artifact and bundle digests
   and records every required check, warning, error, validator version,
   timestamp, and accepted or rejected status. It never modifies the artifact.

Provider and model labels are optional generator provenance. Collection,
schema validation, evidence resolution, acceptance, storage, current-pointer
behavior, and rendering do not branch on either value.

## Storage and identity

Runtime state uses this portable layout:

```text
.lugos/artifacts/project-snapshot/
  evidence/<digest>.json
  candidates/<digest>.json
  accepted/<digest>.json
  receipts/<digest>.json
  current.ref
```

The `<digest>` path component is the lower-case hexadecimal part of the
record's `sha256:<hex>` identity. Candidate and accepted files have identical
canonical content. Acceptance copies content into the accepted namespace; it
does not add acceptance state to the hashed artifact. `current.ref` contains
only the accepted artifact identifier and is updated atomically after an
accepted receipt is durable. Rejected acceptance may preserve the candidate
and rejected receipt but cannot write `accepted/` or update `current.ref`.

Schemas and fixtures are version-controlled. Generated runtime bundles,
candidates, receipts, accepted copies, pointers, and HTML are ignored by
default. Operators may retain or back up a runtime store separately, but should
not commit it as repository truth.

## Evidence collection safety

Collection starts from `.lugos/project-snapshot.sources.yaml` (or an explicitly
supplied manifest), never from a broad crawl. Each source is repository-relative
and must remain inside the selected Git worktree. Absolute paths, traversal,
symlinks escaping the repository, `.git`, environment files, credential/key
paths, dependency trees, build output, and generated artifact stores are
rejected even when explicitly named. Missing required sources fail collection;
missing optional sources produce warnings.

The collector invokes local Git without a shell, records failures as bounded
diagnostics, and allows an injected UTC clock for deterministic tests. Repeated
collection against the same repository state, manifest, recent-commit limit,
and timestamp produces the same canonical bundle and digest.

## Validation and acceptance

Validation is fail-closed and returns named checks for:

- Draft 2020-12 schema validity;
- artifact and Evidence Bundle canonical digest correctness;
- parseable, timezone-aware timestamps;
- presence of the supplied Evidence Bundle and exact bundle reference;
- resolvable evidence source identifiers;
- at least one evidence reference on every verified claim; and
- no verified representation of claims explicitly marked conflicted or
  unknown.

An unsupported claim may be `asserted`, `conflicted`, or `unknown`, but not
`verified`. Progress fields allow only explicit source-backed status, gates,
deliverables, checks, blockers, decisions, or an authoritative numeric
numerator/denominator or percentage. The producer protocol is simply
`EvidenceBundle -> ProjectSnapshot`; all candidates pass through the same
validator and acceptance path.

## Implementation milestones and checks

1. Add the three schemas, native immutable types, fixtures, identity helpers,
   and a focused early vertical slice proving valid fixture validation,
   accepted receipt creation, current-pointer advancement, and HTML rendering.
2. Add manifest loading, safe deterministic Git evidence collection, complete
   semantic validation, filesystem storage, and rejection behavior.
3. Add the nested CLI surface, renderer output, remaining fixtures and tests,
   and operational documentation including cold-agent refresh.
4. Run the complete pytest suite, Ruff, doctor, a temporary-repository CLI
   collect/validate/accept/current/render flow, schema validation, and a final
   diff inspection. Create the requested logical local commits; do not push or
   open a pull request.

No delegated workstream is planned: the schemas, canonical identity,
validation, storage transaction ordering, CLI, and tests are tightly coupled,
and direct implementation keeps one authority for the early vertical slice.

## Phase 2 recommendation

After real snapshot refreshes demonstrate stable claims and useful evidence,
add one narrow Scribe producer adapter implementing the provider-neutral
producer protocol. Keep provider invocation outside the artifact core and pass
its candidate through the same validation and acceptance commands. In
parallel, define a Mission Control read contract for accepted snapshots and
receipts, then render it as a richer read-only view. Do not add scheduling,
writeback, or provider-aware acceptance until separate evidence justifies those
capabilities.
