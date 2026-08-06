# Architecture

## Purpose

The TORC Plane governs continuity across transient agent activations. It is a control plane, not the cognition engine and not the execution body.

The full plane answers:

- Which lineage is this execution acting for?
- Which activation currently has authority?
- Which execution substrate best fits the next bounded work?
- What canonical state and evidence should survive?
- What target-specific projection should the recipient receive?
- When should authority remain, transfer, branch, roll back, or retire?
- Why did each decision occur, and can the lineage be reconstructed later?

## Deployment shape

The initial implementation is a Python library and CLI backed by a local SQLite file. It creates no daemon or network service.

A later production deployment may expose TORC through an existing Lugos surface, but a new always-on process requires separate evidence and operator approval. The term "plane" describes ownership and governance, not a requirement for a standalone server.

## Representations

### Canonical lineage

The canonical lineage is append-only and model-independent. It stores or references:

- identity and parentage
- decisions and commitments
- goals, constraints, and unresolved work
- checkpoints and outcomes
- artifact and memory references
- fit decisions
- projections
- handoff snapshots and results
- authority changes
- integrity evidence

Compression never replaces canonical evidence. A later model can reinterpret old evidence without being limited to the prior model's summary.

### Current self-model

The self-model is the lineage's current structured interpretation of itself. It includes role, goals, methods, assumptions, capabilities, relationships, active priorities, and known limitations.

It is mutable only by appending a new self-model revision. Prior self-models remain attributable and inspectable.

### Execution projection

A projection is a derived, target-specific execution image. It is compiled from one canonical revision for one substrate descriptor, policy envelope, task phase, and context budget.

A projection may omit, compress, reorder, or reformat material. It must record what was included, what was omitted, why, and which canonical sources support each section.

A projection is never the lineage source of truth.

## Components

### Lineage store

Owns append-only revisions, lineage heads, artifact metadata, and transactional authority state. The first slice uses SQLite because Python includes it, transactions are cross-platform, and exclusive leases require atomic updates.

### Projection compiler

Builds deterministic target-fit projections from canonical sections. Required identity, constraints, commitments, and open work are included before optional context. The first slice uses a documented character or word estimate rather than provider-specific tokenization.

### Substrate catalog and fit evaluator

A substrate is the combined execution environment, not merely a model name. A descriptor may include:

- model or agent label
- harness and adapter
- capabilities and modalities
- tool and workspace availability
- context limits and accepted projection formats
- policy and data-boundary labels
- reliability, latency, and cost evidence

The first slice uses static synthetic descriptors and deterministic scoring. It does not claim to identify the objectively best frontier agent.

### Activation and lease controller

An activation is one temporary bearer of a lineage revision. A lease grants authority to advance one lineage head. Lease acquisition and transfer are transactional.

Only one unexpired authoritative lease may exist for a lineage head. Read-only observers do not need an authoritative lease.

### Handoff controller

A handoff is a two-stage protocol:

1. **Prepare**: freeze the source revision, selection evidence, target projection, reason, and continuity requirements into an immutable snapshot.
2. **Resolve**: store a separate target reconstruction and acceptance result, then transfer authority only when required checks pass.

The snapshot is not mutated after target acceptance. Acceptance is a new artifact.

### Provenance verifier

Recomputes deterministic hashes, checks parent links, detects missing artifacts, verifies authority transitions, and confirms that projections point to existing canonical sources.

SHA-256 supplies tamper evidence only. It is not authentication, encryption, or protection from a malicious local process.

### Adapters

Adapters connect TORC to agent harnesses and Lugos modules. They translate records and events. They do not move ownership of inference, memory, routing, tool execution, or transport into TORC.

## Control flow

```text
canonical lineage revision
        |
        v
fit requirements + substrate evidence
        |
        v
fit decision
        |
        v
target-specific projection
        |
        v
immutable handoff snapshot
        |
        v
target reconstruction and acceptance result
        |
        v
transactional authority transfer
        |
        v
new lineage revision and provenance links
```

## Meaning of continuously self-redefining

TORC does not rewrite itself after every model response. It repeatedly re-evaluates and revises the self-model at meaningful control boundaries:

- activation
- checkpoint
- task-phase transition
- handoff
- branch creation
- failure recovery
- model or environment change
- completion or retirement

The execution projection may be recompiled whenever the target or budget changes. The invariants, history, and authority rules remain outside that projection.

## Handoff reasons

Every handoff uses a controlled reason code:

- capability escalation
- task-phase transition
- context degradation
- environment requirement
- independent challenge
- policy boundary
- model succession
- failure recovery
- operational optimization
- lineage branch

A new model becoming available is evidence to evaluate, not sufficient reason by itself.

## Failure behavior

- Projection failure leaves the current authority unchanged.
- Handoff preparation failure leaves the current authority unchanged.
- Acceptance rejection leaves the current authority unchanged.
- Target failure after preparation can expire or cancel the pending handoff without changing canonical history.
- Integrity failure stops authority-changing operations and reports the smallest failing artifact or link.
- Lease conflict fails closed.

## Security and authority boundary

TORC records and enforces lineage authority inside its state store. It does not grant filesystem, network, model, or tool permissions. Those remain bound by Autowork assignments, harness sandboxes, and operator policy.

A TORC handoff cannot broaden an execution assignment. The target projection and acceptance requirements must fit inside the target's independently authorized assignment.

## Non-goals

- Continuous interception of model tokens or tool calls
- General event bus or workflow engine
- Provider gateway
- Vector database or semantic-memory replacement
- Persona system
- Skill custody
- Multi-host consensus
- Automatic lineage merging
- Autonomous modification of policy or continuity invariants
