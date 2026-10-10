"""Stable vocabulary established by the TORC seed."""

HANDOFF_REASON_CODES: tuple[str, ...] = (
    "capability_escalation",
    "task_phase_transition",
    "context_degradation",
    "environment_requirement",
    "independent_challenge",
    "policy_boundary",
    "model_succession",
    "failure_recovery",
    "operational_optimization",
    "lineage_branch",
)

TRACKED_CONTINUITY_SECTIONS: tuple[str, ...] = (
    "constraints",
    "commitments",
    "open_work",
)

# Every event type a lineage revision may carry; mirrors the revision schema.
REVISION_EVENT_TYPES: tuple[str, ...] = (
    "lineage_created",
    "checkpoint",
    "self_model_revised",
    "handoff_prepared",
    "handoff_accepted",
    "handoff_rejected",
    "rollback_applied",
    "branch_created",
    "lineage_retired",
)

# Revisions an activation appends through the ordinary checkpoint path. Every other
# event type is written by its own workflow, which supplies the context the
# verifier checks for it.
CHECKPOINT_EVENT_TYPES: tuple[str, ...] = (
    "checkpoint",
    "self_model_revised",
)

# Revisions TORC writes on a substrate's behalf. They record bookkeeping, not
# work the substrate authored.
BOOKKEEPING_EVENT_TYPES: tuple[str, ...] = ("handoff_accepted",)

RESOLUTION_DISPOSITIONS: tuple[str, ...] = (
    "completed",
    "superseded",
    "withdrawn",
)

CONTINUITY_INVARIANTS: tuple[str, ...] = (
    "canonical_history_is_append_only",
    "execution_projections_are_derived",
    "one_authoritative_lease_per_lineage_head",
    "handoff_preparation_does_not_transfer_authority",
    "rejected_acceptance_preserves_prior_authority",
    "authority_changes_are_attributable",
)
