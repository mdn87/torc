# ADR 0003: Handoff is explicit and acceptance-gated

- **Status**: Accepted for seed
- **Date**: 2026-08-06

## Context

Continuously hopping between models would degrade continuity and make authority ambiguous. Loading a projection is not proof that a recipient understood the lineage.

## Decision

Evaluate fit repeatedly, but move authority only at meaningful control boundaries. Handoff preparation freezes an immutable snapshot. The target returns a structured reconstruction. A separate result records acceptance or rejection. Authority transfers transactionally only after acceptance.

## Consequences

- The current bearer can continue normal work without TORC mediating every action.
- Failed or rejected handoffs leave authority unchanged.
- Transfers are slower than ungoverned prompt forwarding.
- The history can explain why and how succession occurred.
