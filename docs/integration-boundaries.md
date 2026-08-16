# Integration Boundaries

TORC must earn a narrow place in Lugos rather than duplicate existing modules.

| Lugos component | Existing ownership | TORC relationship | TORC must not do |
|---|---|---|---|
| Autowork | Task assignment, role, model and effort route, sandbox, capabilities, verification, review, outcome evidence | Consume assignment and outcome references; propose lineage needs or a substrate requirement; record which authorized execution bore the lineage | Grant tools, broaden assignment authority, bypass routing policy, or become a second worker orchestrator |
| Sulis | Durable memory capture, recall, browsing, and memory organization | Reference memory records and select relevant memory into projections | Replace semantic memory, duplicate note storage, or treat projection text as memory truth |
| agent-continuity | Human-readable cross-machine handoffs and allowlisted Syncthing mirror | Export or reference TORC lineage summaries and artifacts for operator continuity | Become a file-sync system or silently mutate shared continuity files |
| Omniroute | Model/provider gateway and route aliases | Receive approved target routes or supply runtime labels through an adapter | Call providers directly as a competing gateway or store provider credentials |
| Bran | Persona, skill, and source-pack custody | Reference approved persona, skill, and source-pack versions in lineage evidence | Import, approve, execute, or maintain skill and source-pack bodies |
| agent-mail | Agent messaging and delivery transport | Carry handoff notifications or artifact references | Treat message delivery as lineage authority or canonical storage |
| lugos-mcp and CLI | Shared command and tool surfaces | Expose a thin TORC surface after the local contract stabilizes | Reimplement TORC domain logic in every surface |
| HUD or mission-control | Read-oriented operator visibility | Render lineage head, active bearer, pending handoff, provenance, and fit rationale | Mutate lineage state without an explicitly designed and authorized command path |
| Harnesses such as Codex or Claude | Actual model execution and tool use | Implement adapters that load projections and return structured checkpoints or reconstructions | Define canonical lineage identity or silently claim authority |
| OGMI | Shared workgraph records, continuity checkpoints, orientation bundles, run and assignment identity | Validate/hash/orient through OGMI's public CLI and retain a reference from a Torc runtime binding and lineage revision | Copy the OGMI schema, synthesize an OGMI checkpoint, or reinterpret OGMI authority and spine semantics |

## Root-session continuity boundary

For an OGMI-enrolled root session, OGMI owns the checkpoint and orientation
record shapes while Torc owns lineage revisions, projections, runtime bindings,
activations, and leases. Torc invokes only fixed, non-shell OGMI commands under
a timeout and output ceiling:

```text
python -m ogmi validate CHECKPOINT --json
python -m ogmi hash CHECKPOINT
python -m ogmi orient PROJECT SPINE
```

Invalid, unavailable, timed-out, oversized, tampered, or identity-mismatched
OGMI input fails closed. A session outside an OGMI run must opt into
`torc_standalone`; Torc does not fabricate a workgraph record for it.

The context lifecycle commands are intentionally distinct from succession:

- `torc context attach` binds one exact harness, runtime session, and repository
  identity to an already-authoritative activation.
- `torc context checkpoint` is a convenience wrapper over the existing
  `torc lineage checkpoint` append path and compiles a same-substrate view.
- `torc context detach` retires only an exact external runtime binding, including
  a stale one; it does not mutate lineage history, activation, lease, or OGMI.
- `torc context hydrate` opens the store read-only and returns only a bounded,
  verified derived view. `unbound`, `stale`, and `invalid` results are explicit.
- A different authoritative session still uses `torc handoff prepare/resolve`;
  a durable alternate line still uses `torc lineage branch`.

### Read-only child request modes

`torc context hydrate --request-mode MODE` accepts four explicit intents. The
default `root` mode preserves the root hydration JSON contract. The other modes
only inspect an exact existing binding and verified Torc records; they never
create a binding, lineage, activation, handoff, branch, lease, or projection.

- `observer` returns the existing bounded Torc projection as non-authoritative
  context for an independently scoped child. It declares that lineage authority
  and checkpointing are unavailable. For an OGMI binding it exposes only the
  parent checkpoint ID and canonical hash as provenance, never the full
  assignment-specific checkpoint or orientation body.
- `successor` returns authoritative context only when the bound activation is
  the current lease holder and one verified, accepted Torc handoff result names
  that activation. A prepared, rejected, or mismatched handoff is insufficient.
- `branch` returns authoritative context only when the bound lineage's immutable
  root is an explicit `branch_created` revision whose child activation and lease
  match current authority.

An absent exact binding remains `unbound`; repository mismatch is `stale`; and
missing or mismatched successor/branch proof is `invalid`. AutoWork assignments
and subagent-start events are not Torc authority evidence.

## Assignment and lineage are different

An Autowork `AgentAssignment` is the immutable authority for one dispatch. A TORC lineage is the continuity identity spanning dispatches. TORC may link many assignments over time, but it cannot make one assignment larger or transfer its permissions to another activation.

A valid handoff requires both:

1. TORC continuity acceptance.
2. A separately valid target execution assignment and capability grant.

## Memory and lineage are different

Sulis answers what information should be recalled. TORC answers which lineage an execution represents, which commitments and authority survive, and why state moved.

A TORC projection may contain selected Sulis references or recalled text. The projection does not become the Sulis source of truth.

## Routing and fit are different

TORC may express that a next bearer requires repository write, image input, larger context, a local data boundary, or independent review. Autowork and Omniroute remain responsible for selecting and authorizing an actual route under their policies.

The first TORC fit evaluator uses synthetic candidates only. A real adapter must reconcile TORC requirements with the route that the authoritative Lugos policy actually grants.
