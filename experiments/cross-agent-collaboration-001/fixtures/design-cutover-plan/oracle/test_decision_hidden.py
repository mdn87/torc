from __future__ import annotations

import json
from pathlib import Path

EXPECTED_OPERATIONS = [
    "capture_initial_watermark",
    "shadow_copy",
    "verify_shadow",
    "freeze_tenant_writes",
    "capture_final_watermark",
    "copy_delta",
    "verify_final",
    "cas_route",
    "unfreeze_tenant_writes",
    "monitor",
]
ALL_CONSTRAINTS = {f"C{number}" for number in range(1, 8)}


def _decision() -> dict[str, object]:
    return json.loads(Path("decision.json").read_text(encoding="utf-8"))


def test_selects_the_only_feasible_strategy() -> None:
    decision = _decision()

    assert decision["selected_strategy"] == "shadow-copy-cas"
    assert set(decision["constraints_addressed"]) == ALL_CONSTRAINTS


def test_rejections_name_the_violated_constraints() -> None:
    rejected = _decision()["rejected_strategies"]

    assert set(rejected) == {
        "global-stop-rewrite",
        "dual-write-backfill",
        "cdc-mirror-cutover",
    }
    assert "C1" in rejected["global-stop-rewrite"]
    assert "C2" in rejected["dual-write-backfill"]
    assert "C6" in rejected["cdc-mirror-cutover"]


def test_plan_orders_every_required_operation_once() -> None:
    plan = _decision()["plan"]

    assert [step["operation"] for step in plan] == EXPECTED_OPERATIONS
    for previous, current in zip(plan, plan[1:], strict=False):
        assert previous["step_id"] in current["depends_on"]


def test_plan_assigns_the_safety_constraints_to_their_controls() -> None:
    by_operation = {
        step["operation"]: set(step["satisfies"])
        for step in _decision()["plan"]
    }

    assert "C3" in by_operation["shadow_copy"]
    assert {"C1", "C7"} <= by_operation["freeze_tenant_writes"]
    assert "C4" in by_operation["verify_final"]
    assert {"C2", "C4", "C5"} <= by_operation["cas_route"]
    assert ALL_CONSTRAINTS <= set().union(*by_operation.values())


def test_cutover_gate_and_pause_are_bounded() -> None:
    decision = _decision()

    assert decision["cutover_gate"] == {
        "mode": "compare_and_swap",
        "requires": [
            "legacy_route_version",
            "final_watermark",
            "verification_passed",
        ],
    }
    assert 0 < decision["max_tenant_write_pause_seconds"] <= 30


def test_rollback_never_restores_a_diverged_writer() -> None:
    assert _decision()["rollback"] == {
        "before_cutover": "resume_legacy_and_reuse_checkpoint",
        "after_cutover": "forward_repair_on_new_store",
    }
