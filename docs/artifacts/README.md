# Project Snapshot Artifact Operations

TORC's project snapshot artifact slice is a local, provider-neutral path from
repository evidence to a disposable read-only projection. Source repositories
remain authoritative. Accepted artifacts and receipts are immutable;
`current.ref` is mutable routing state.

- `../project-snapshot-artifacts.md` records architecture, reconnaissance,
  storage policy, scope, platform support, Mission Control boundary, and Phase
  2 guidance.
- `../project-snapshot-artifacts-phase2.md` fixes the command-producer and
  trusted Mission Control read contracts and their cross-platform lanes.
- `schema-reference.md` defines the v1alpha1 record contracts and canonical
  identity rules.
- `cli.md` documents collection, command production, validation, acceptance,
  trusted current lookup, rendering, retention, and cross-platform invocation.
- `cold-agent-refresh.md` is the canonical provider-independent refresh
  procedure.

The core imports no Anthropic, OpenAI, or other provider SDK. A producer may be
a model adapter, deterministic script, or human. The optional command adapter
passes canonical evidence over stdin and accepts one candidate over stdout,
but every candidate still uses the same schema, provenance, acceptance,
storage, and rendering path.
