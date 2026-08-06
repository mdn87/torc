# ADR 0001: TORC is a control plane, not an agent runtime

- **Status**: Accepted for seed
- **Date**: 2026-08-06

## Context

The original concept placed TORC between an agent's changing model and changing execution environment. It could easily expand into a universal agent framework or shrink into a checkpoint file format.

## Decision

TORC owns lineage identity, authority, projection, succession, branching records, and provenance. It does not own inference, tool execution, workflow orchestration, memory recall, or provider routing.

"Plane" describes durable governance across executions. It does not require a standalone service.

## Consequences

- The first implementation may be a local library and CLI.
- Existing Lugos components remain authoritative in their domains.
- Adapters are preferred over replacement implementations.
- The architecture remains broader than the initial handoff slice.
