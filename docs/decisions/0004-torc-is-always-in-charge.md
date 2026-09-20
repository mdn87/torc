# ADR 0004: TORC is always in charge

- **Status**: Accepted
- **Date**: 2026-09-20

## Context

A review against `docs/concepts/0001-torc-original-concept.md` found that every phase after P0 built the passing side of TORC: leases, acceptance-gated handoff, recovery, rollback, branching, checkpoint authority, and verification. No roadmap phase returned to the center of the concept, a carried self that is "continuously self-redefining shaped and sized for optimized fit" into its next bearer. The projection compiler still ignores the receiving substrate's descriptor and reads only the head revision's state. Nothing revises the self-model.

During the same period the LIR design in the parent repository took the agent-facing resumption view for itself and listed TORC as the authority half only. Two components then produced what a receiving agent reads, with no rule for which one governs.

The operator's ruling was: "torc is always in charge."

## Decision

TORC owns what a lineage carries to its next bearer, as well as who holds the lineage.

- Shaping and sizing the carry for the receiving agent is TORC's responsibility. The carry is compiled for that receiver from canonical history. It is not a copy of the last bearer's summary.
- Revising the self-model at control boundaries is part of TORC's protocol. TORC asks for the revision, attributes it, and records it. The bearing agent does the thinking.
- Other components supply material to TORC and consume what TORC produces. None of them hands a lineage-bound agent its continuity around TORC. Where another component's agent-facing view overlaps a TORC projection, TORC governs.

## Unchanged

ADR 0001 still holds. "In charge" covers continuity, not execution. TORC performs no inference, proxies no tokens or tool calls, grants no tool or filesystem permissions, and needs no service process. The operator remains in charge of TORC.

This ADR does not move agent selection. The operator or the routing owner may still choose the next agent; TORC fits the lineage to that agent and records the choice.

## Consequences

- The projection compiler and the self-model become the main line of work, ahead of further authority mechanics.
- The P1b tie compared two fixed packets, so it counts neither for nor against this decision. The hypothesis and kill criteria in `docs/project-brief.md` apply to the shaped carry once it exists.
- Material for the carry may stay with its current owners. TORC references it and decides what the receiver gets.
- The LIR boundary documents in the parent repository describe the older split. They need to be brought into line once TORC's receiver-facing interface is defined.
