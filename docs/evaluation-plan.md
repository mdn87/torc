# Evaluation Plan

## Goal

Determine whether TORC's lineage, projection, and controlled succession improve real continuity enough to justify a subsystem.

The comparison begins only after the experimental apparatus passes the P1a
gate in `p1a-experimental-readiness-spec.md`. P1a proves repeatability and
evidence capture; it does not produce or interpret comparative results.

## Compared approaches

### Baseline A: compiled prompt

A source agent produces a carefully structured handoff prompt. The target receives the prompt and relevant files. No canonical lineage store or authority protocol is used.

### Baseline B: existing runtime persistence

Use the closest available existing agent checkpoint or session-resume feature with minimal Lugos glue.

If the chosen source-to-target pair has no equivalent native continuation, the
P1b manifest must either add a same-harness pair for this baseline or
pre-register Baseline B as unavailable and narrow the comparison. It may not
substitute a different mechanism after runs begin.

### Candidate C: TORC

Use canonical lineage records, target-fit projection, immutable handoff snapshot, structured target reconstruction, acceptance checks, and explicit authority transfer.

## Test task

Choose one real Lugos subsystem with enough history to contain:

- settled architectural decisions
- active constraints
- unresolved work
- evidence references
- at least one misleading but superseded direction
- a task-phase transition such as implementation to review

Run the same source-to-target transition under all approaches.

## Measures

- Required commitment retention
- Constraint and prohibition retention
- Settled-decision accuracy
- Unresolved-work accuracy
- Correct distinction between inherited facts and new inference
- Provenance recoverability
- Contradiction or unauthorized-change rate
- Context size delivered to target
- Preparation and acceptance overhead
- Operator correction count
- Ability to roll back or explain a failed transfer

## Initial pass criteria

TORC should not proceed to provider integration unless it shows:

- zero loss of required commitments and hard constraints in the test set
- complete provenance for every accepted authority transfer
- no duplicate authoritative activation
- equal or better target task quality than the best baseline
- a measurable reduction in irrelevant context or operator correction
- acceptable added operational steps for the sole operator

These criteria can be revised only before the comparison starts, not after seeing results.

The exact fixture, harness identities, settings, scorer version, normalization
rules, and thresholds must be frozen in the P1b manifest before its first live
run.

## Existing-system adoption rule

If an existing runtime satisfies the required semantics, TORC should wrap or configure it rather than rebuild it. The repository may become a contract, adapter, and evaluation package instead of a standalone runtime.

## Failure interpretation

- If projections fail, narrow the compiler before adding more state.
- If authority semantics add no value, remove them rather than preserving the plane metaphor.
- If the target cannot reconstruct required continuity, inspect source structure and acceptance criteria before blaming model quality.
- If a simpler baseline wins, record the result and stop expansion.
