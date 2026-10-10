# ADR 0005: Separate control records from model-visible execution capsules

Status: accepted

## Context

The first TORC experiments delivered the full projection shape to the target.
That shape repeated source references beside individual values and included
projection and authority metadata needed by TORC rather than by the model. In
the corrected Sol calibration, this made the TORC payload 21.6 percent larger
than the compiled handoff by canonical JSON bytes.

Provider-native compaction solves a different problem. OpenAI's Responses API,
for example, can return encrypted compaction and agent-message items that a
compatible client carries into later calls. Multi-agent mode maintains separate
root and subagent contexts and compacts them independently. These artifacts are
useful within that provider and API, but are neither human-auditable evidence
nor a portable Codex-to-Claude lineage record.

References:

- [OpenAI Responses multi-agent guide](https://developers.openai.com/api/docs/guides/responses-multi-agent)
- [OpenAI compaction guide](https://developers.openai.com/api/docs/guides/compaction)

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
not parse, synthesize, translate, or treat them as canonical history. The
adapter records the provider, API, model, artifact type, integrity digest, and
the execution whose response produced the artifact. Possession of an opaque
artifact never grants lineage authority.

Native subagents remain an execution-layer facility. Their isolated contexts,
delegation calls, and usage records may be experiment evidence or adapter
artifacts, but they do not replace TORC handoff preparation, acceptance, or
lease transfer.

## Relation to ADR 0004

[ADR 0004](0004-torc-is-always-in-charge.md) assigns the receiver-facing carry
to TORC: the P5 compiler reads canonical history, derives the receiver's
budget from its descriptor, and decides what fits. This decision implements
the model-visible rendering of that carry; it does not replace it.

- Sizing happens in the projection compiler, before any capsule exists. A
  capsule is built from a projection's already-fitted sections and cannot
  recover an item the projection omitted for budget.
- Every claim handle resolves, through the control envelope, to a source
  reference that the projection recorded, so TORC can still verify a citation
  against canonical history.
- A capsule may be handed to a read-only observer, such as a critic, without
  granting lineage authority. An actual successor still receives every required
  continuity field through the ordinary handoff path and passes its acceptance
  gate; material held only in the control envelope does not satisfy that gate.

`tests/test_p5_capsule_contract.py` holds the contract test for this ordering.

## Consequences

- Canonical lineage and authority evidence remain complete without consuming
  target context.
- Cross-provider handoffs have a portable representation.
- Same-provider continuations may use native compaction alongside a minimal
  TORC delta.
- Cross-provider handoffs always use an explicit, content-addressed execution
  capsule plus control-envelope references; TORC does not invent an opaque
  interchange format.
- A native-agent benchmark must count the entire response, including root,
  subagent, retry, and synthesis work, rather than comparing only the final
  critic text. Separate per-agent attribution is diagnostic evidence when the
  selected API exposes it, not a prerequisite for total-cost accounting.
- Capsule size must be measured in actual rendered input tokens during live
  experiments; byte counts are only deterministic local design evidence.
- Acceptance and scoring must validate claim handles against the control
  envelope rather than accepting any non-empty citation string.
