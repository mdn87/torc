# 0004: Separate control records from model-visible execution capsules

Status: accepted for experiment

## Context

The first TORC experiments delivered the full projection shape to the target.
That shape repeated source references beside individual values and included
projection and authority metadata needed by TORC rather than by the model. In
the corrected Sol calibration, this made the TORC payload 21.6 percent larger
than the compiled handoff by canonical JSON bytes.

Provider-native compaction solves a different problem. It preserves one
provider's conversation in an opaque representation that must be passed back
unchanged. It is useful within a compatible harness, but it is not a portable
Codex-to-Claude lineage record.

## Decision

TORC will maintain two derived handoff representations:

1. The **control envelope** retains the projection identifier, target
   substrate, full canonical source references, omissions, integrity evidence,
   and authority state. It remains outside model-visible context.
2. The **execution capsule** contains only the identity, current
   responsibility, handoff purpose, and selected claim text needed by the
   target. Claims use short, deterministic handles such as `c1` and `x2`.

The target cites claim handles. TORC resolves them through the control envelope
and rejects unknown handles. The capsule hash binds the two representations.

Provider-created opaque continuation artifacts may be referenced by the
control envelope and passed through by a compatible harness adapter. TORC does
not parse, synthesize, or treat them as canonical history.

## Consequences

- Canonical lineage and authority evidence remain complete without consuming
  target context.
- Cross-provider handoffs have a portable representation.
- Same-provider continuations may use native compaction alongside a minimal
  TORC delta.
- Capsule size must be measured in actual rendered input tokens during live
  experiments; byte counts are only deterministic local design evidence.
- Acceptance and scoring must validate claim handles against the control
  envelope rather than accepting any non-empty citation string.
