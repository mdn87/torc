# Domain Model

## Identifier types

| Identifier | Meaning |
|---|---|
| `lineage_id` | Stable identity of the enduring lineage |
| `revision_id` | Immutable canonical lineage revision |
| `activation_id` | One transient execution that bears a revision |
| `lease_id` | Exclusive authority grant for one lineage head |
| `substrate_id` | Registered model, harness, tools, environment, and policy combination |
| `fit_decision_id` | Recorded comparison and selection decision |
| `projection_id` | Derived execution image for one target and source revision |
| `handoff_id` | Immutable handoff preparation record |
| `handoff_result_id` | Separate acceptance or rejection record |
| `artifact_id` | Content-addressed or otherwise immutable referenced artifact |

Do not overload `agent_id` to mean all of these. A future adapter may map an external `agent_id` to a TORC lineage, but the mapping must be explicit.

## Lineage

A lineage has:

- stable identity
- optional parent lineage when branched
- creation metadata
- lifecycle status
- current canonical head
- current authoritative activation and lease, if any

The head changes only through a recorded transaction that appends the corresponding lineage revision.

## Lineage revision

A revision is immutable and includes:

- lineage and parent revision identifiers
- event type and timestamp
- actor and activation attribution
- structured canonical state or canonical references
- evidence and artifact references
- deterministic integrity fields

Multiple parent revisions are reserved for a future explicit merge design. The first slice supports zero or one parent revision.

## Self-model

The self-model is structured state carried by a lineage revision:

- role and purpose
- current goals
- commitments
- active work
- constraints and prohibitions
- methods and preferences
- assumptions and uncertainties
- capability claims with evidence
- relationships and delegated responsibilities

Required commitments and constraints must not be silently dropped by projection.

## Substrate descriptor

A substrate descriptor identifies the actual execution combination:

- model or agent label
- provider or local runtime label
- harness and adapter version
- context budget and accepted representation
- capabilities, tools, workspace, and modality
- policy and data-handling labels
- availability, reliability, latency, and cost evidence

The descriptor is evidence about a possible bearer. It is not an authority grant.

## Fit decision

A fit decision records:

- work requirements
- candidate descriptors and eligibility
- hard disqualifications
- scored factors and evidence
- selected candidate or no-selection result
- decision policy version
- decision timestamp and actor

The score is explainable and replayable. A selected target still requires an independently valid execution assignment.

## Projection

A projection records:

- source lineage and revision
- target substrate and budget
- policy and compiler versions
- included sections with canonical source references
- omitted sections with reasons
- redactions
- estimated size
- deterministic content hash

Changing a budget or target creates another projection. It does not alter the canonical revision.

## Activation

An activation records:

- lineage and source revision
- substrate descriptor
- external runtime or session references
- start and end timestamps
- state: pending, active, suspended, completed, failed, or retired
- lease reference when authoritative

An activation without a valid lease may inspect or propose. It may not advance the authoritative lineage head.

## Lease

A lease records:

- lineage and revision head
- activation holder
- issuance and expiration
- status
- acquisition or transfer transaction

The store enforces at most one active authoritative lease per lineage head.

## Handoff snapshot

The immutable preparation record includes:

- source lineage, revision, activation, and lease
- target substrate
- handoff reason and rationale
- fit decision
- target projection
- continuity requirements
- source authority state at freeze time
- artifact hashes and creation timestamp

It contains no post-handoff mutation.

## Handoff result

The separate resolution record includes:

- handoff snapshot reference
- target reconstruction
- per-requirement acceptance checks
- accepted or rejected disposition
- reason for rejection when applicable
- resulting authority transaction when accepted
- target activation and lease references when accepted

## Branch

A branch creates a new lineage with explicit parent lineage and revision. It is not two active processes silently claiming the same lineage identity.

Branching is represented in schemas and vocabulary but is not implemented in the first vertical slice.
