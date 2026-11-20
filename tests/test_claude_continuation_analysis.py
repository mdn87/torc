from fractions import Fraction

import pytest

from torc.claude_continuation_analysis import paired_report


def observations():
    rows = []
    for case in range(8):
        for rep in (1, 2):
            for position, arm in enumerate(
                ("compiled", "torc") if rep == 1 else ("torc", "compiled"), 1
            ):
                usage = (100 if rep == 1 else 300) if arm == "compiled" else 125
                rows.append(
                    dict(
                        case=str(case),
                        arm=arm,
                        repetition=rep,
                        position=position,
                        trial_id=f"{case}-{arm}-{rep}",
                        total_context_tokens=usage,
                        observed_input_lower_bound=usage,
                        first_request_input=10,
                        verified_success=True,
                        critical_failures=[],
                        deviations=[],
                    )
                )
    return rows


def test_pool_repetitions_before_reduction_and_retain_failed_arms():
    rows = observations()
    rows[1]["verified_success"] = False
    report = paired_report(rows)
    assert report["median_reduction"] == 0.375
    assert report["sign_test"]["p_two_sided"] == 2 / 256
    assert report["acceptance"]["torc"] == {"passed": 15, "scheduled": 16, "unscored": 0}
    assert report["decision"] == "no_advance"
    assert report["by_task"][0]["usage"]["torc"] == 250


def test_partial_task_suppresses_cohort_decision_but_retains_its_lower_bound():
    rows = observations()
    rows[0]["total_context_tokens"] = None
    report = paired_report(rows)
    assert report["unresolved_tasks"] == 1 and len(report["by_task"]) == 8
    assert report["median_reduction"] is report["sign_test"] is None
    assert report["by_task"][0]["observed_input_lower_bounds"]["compiled"] == 400
    assert report["decision"] == "incomplete_usage"


def test_ties_deviations_and_feasibility_are_explicit():
    rows = observations()
    rows[1]["total_context_tokens"] = 275
    report = paired_report(rows)
    assert report["sign_test"] == {
        "positive": 7,
        "negative": 0,
        "ties": 1,
        "p_two_sided": float(Fraction(2, 128)),
    }
    rows[1]["deviations"] = ["unexpected_main_model"]
    assert paired_report(rows)["decision"] == "protocol_deviation"
    for row in rows:
        row["verified_success"] = False
    assert paired_report(rows)["decision"] == "failed_feasibility"
    with pytest.raises(ValueError):
        paired_report(rows + [rows[0]])


def test_seven_of_eight_and_zero_control_denominator():
    rows = observations()
    rows[1]["total_context_tokens"] = 500
    assert paired_report(rows)["sign_test"]["p_two_sided"] == 18 / 256
    for row in rows:
        if row["case"] == "0" and row["arm"] == "compiled":
            row["total_context_tokens"] = 0
    result = paired_report(rows)
    assert result["unresolved_tasks"] == 1 and result["median_reduction"] is None
