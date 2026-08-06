# ADR 0002: Canonical lineage and execution projection are separate

- **Status**: Accepted for seed
- **Date**: 2026-08-06

## Context

A lineage must fit agents with different context limits, tools, instruction behavior, and policy boundaries. Storing only the latest compressed prompt would make the prior model's omissions permanent.

## Decision

Maintain append-only canonical evidence and state separately from target-fit projections. A projection records its source revision, selection rules, inclusions, omissions, redactions, budget, and hash.

The self-model is versioned canonical state. It may evolve, but it does not replace the underlying evidence history.

## Consequences

- New models can reinterpret older evidence.
- Projection compilers can improve without rewriting history.
- Storage is larger than a single prompt summary.
- Provenance verification is mandatory.
