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
