# Cloudflare Computer borrow boundary

Status: accepted as future design guidance

Date: 2026-08-08

Evidence: [AETA Cloudflare Computer to TORC ingest](https://github.com/mdn87/aeta/pull/16)

## Context

Cloudflare Computer demonstrates a useful separation between a durable workspace and the execution environment used for an individual operation. TORC can borrow that architectural distinction without adopting Cloudflare Computer, its virtual filesystem, or its runtime model.

This decision records the boundary before P1b so the useful ideas remain available without expanding P1a or changing the scope of the current implementation.

## Decision

TORC may consider the following after P1a, and only when evidence supports them:

1. Separate durable activation or workspace evidence from per-operation execution-backend evidence.
2. Support workspace-shaped projections with hash manifests as an optional projection form after P1b.
3. Model task completion, state reconciliation, continuity acceptance, and authority transfer as distinct events or checks where later recovery work requires that distinction.

TORC will not:

- adopt Cloudflare Computer's virtual filesystem or runtime;
- become an execution-backend router;
- own tool execution, model inference, or workspace synchronization;
- add Cloudflare Computer as a P1a dependency;
- change the P1a schemas or implementation solely because of this comparison.

## Evidence gates

- Split workspace and backend descriptors when a real adapter needs independent lifetimes or provenance for them.
- Add workspace-shaped projections only if P1b shows that the existing compiled payload is insufficient for a target runtime.
- Add explicit reconciliation state when P3 recovery work or a reproduced failure demonstrates that completion and durable state can diverge.
- Preserve separate continuity acceptance and authority transfer whenever later implementation work touches those stages.

## Immediate effect

This decision changes documentation only. P1a and PR #6 remain unchanged. The earliest implementation review point is after P1b evidence exists.
