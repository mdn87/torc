import importlib.util
from pathlib import Path

import pytest


def load_scorer():
    path = (
        Path(__file__).resolve().parents[1]
        / "experiments/continuation-review/settlement_qualification.py"
    )
    spec = importlib.util.spec_from_file_location("settlement_qualification", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_setup_failure_and_missing_test_cannot_reject_a_candidate():
    scorer = load_scorer()
    specs = [
        {
            "title": name,
            "file": "settlement.spec.ts",
            "tests": [
                {
                    "expectedStatus": "passed",
                    "projectName": "chromium",
                    "results": [{"status": "passed", "retry": 0, "errors": []}],
                }
            ],
        }
        for name in scorer.TESTS
    ]
    report = {"errors": [], "suites": [{"specs": specs}]}
    source = "  await expect(board).toHaveText('revision 2');\n  await page.goto(url);"
    assert scorer.browser_verdict(report, 0, source)["status"] == "accepted"
    result = specs[0]["tests"][0]["results"][0]
    result.update(status="failed", errors=[{"message": "Browser executable is missing"}])
    with pytest.raises(ValueError, match="assertion"):
        scorer.browser_verdict(report, 1, source)
    result["errors"] = [
        {
            "message": "Error: expect(locator).toHaveText(expected) failed",
            "location": {"file": "/work/tests/browser/settlement.spec.ts", "line": 2},
        }
    ]
    with pytest.raises(ValueError, match="assertion"):
        scorer.browser_verdict(report, 1, source)
    result["errors"][0]["location"]["line"] = 1
    assert scorer.browser_verdict(report, 1, source)["status"] == "behavior_failed"
    specs.pop()
    with pytest.raises(ValueError, match="three frozen"):
        scorer.browser_verdict(report, 1, source)
