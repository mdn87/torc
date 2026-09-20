---
title: "TORC: Original Concept"
status: reference
created: 2026-09-20
owner: mdn87
project: torc
concept_id: TORC-0001
---

# TORC: Original Concept

## Why this document exists

The seed documents (`docs/project-brief.md`, `docs/architecture.md`,
`docs/domain-model.md`, ADRs 0001-0003) describe TORC's mechanisms. They were
distilled from a design conversation held on 2026-08-05/06. That conversation
is not stored in this repository.

On 2026-09-20 the operator went back to it and recovered the phrases the rest
was built around. They are recorded here so that later work can be judged
against what TORC is for, and not only against what its mechanisms do.

Text in quotation marks is the operator's wording as quoted back from that
conversation. Everything else is interpretation.

## The concept in the operator's words

What TORC carries is:

> "continuously self-redefining shaped and sized for optimized fit into the
> best available frontier agent"

How it moves:

> "lineage could be passed from agent to agent with a snapshot taken at the
> time of passing for provenance"

Where it sits:

> "in between the body and the mind."

## What the finished thing should feel like

One continuous working intelligence, even when the underlying agent changes.

The context carried forward is not a static dump or a restart packet. TORC
reshapes what it carries for the agent currently receiving it, and preserves
enough of the state at each transition to establish where that lineage came
from.

This is a broader target than "make agent handoffs better". The handoff is one
mechanism required to produce the experience. The experience itself is
continuity across replaceable or improving frontier agents.

## How the phrases map to the seed design

| Phrase | Seed construct |
|---|---|
| "continuously self-redefining" | The versioned self-model, re-evaluated and revised at control boundaries (`docs/architecture.md`, "Meaning of continuously self-redefining") |
| "shaped and sized for optimized fit" | The projection compiler: a target-specific execution image that may omit, compress, reorder, or reformat, compiled from canonical history that is never rewritten (ADR 0002) |
| "the best available frontier agent" | The substrate catalog and fit evaluator. The brief flags this phrase as underspecified until capability, policy, reliability, cost, and context evidence are defined |
| "passed from agent to agent with a snapshot ... for provenance" | Activation leases, the immutable handoff snapshot, acceptance-gated authority transfer, and the provenance verifier (ADR 0003) |
| "in between the body and the mind" | The Mind / TORC Plane / Body explanatory model in the seed README (ADR 0001). Explanatory only: it does not require TORC to proxy tokens or tool calls |

## Reading rule

The first phrase is the center. The second is the mechanism that makes the
first trustworthy. A TORC that passes lineage flawlessly but carries a fixed
packet has built the mechanism without the thing it was meant to protect.

The hypothesis and kill criteria in `docs/project-brief.md` still apply. This
document does not claim the concept is proven. It records what would have to
be demonstrated for it to be.

`docs/decisions/0004-torc-is-always-in-charge.md` records the ruling that the
center is TORC's own responsibility.
