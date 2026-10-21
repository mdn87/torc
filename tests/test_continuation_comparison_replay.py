"""Exercise the public preparation/analysis path with immutable replay artifacts."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def test_comparison_reproduces_retained_report_and_cli_analysis(tmp_path):
    root = Path(__file__).resolve().parents[1]
    experiment = root / "docs/experiments/session-continuation-001"
    script = experiment / "comparison.py"
    expected = (experiment / "comparison-report.json").read_bytes()
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}

    def run(*args):
        return subprocess.run([sys.executable, str(script), *map(str, args)], env=environment,
                              capture_output=True, check=True).stdout

    for name in ("first", "second"):
        output = tmp_path / name
        result = run("demo", "--output-dir", output)
        assert result == expected
        report = json.loads(result)
        assert report["live_model_trials"] == 0
        assert not report["launch_authorized"]
        for case in report["cases"].values():
            for field in ("results", "analysis"):
                artifact = output / case[field]
                assert hashlib.sha256(artifact.read_bytes()).hexdigest() == artifact.stem
        complete = report["cases"]["complete_synthetic"]
        assert complete["trial_count"] == 8
        assert complete["attempt_count"] == 24
        assert complete["fallback_attempt_count"] == 8
        assert not complete["comparisons"][0]["success_noninferiority_passed"]
        for case in ("missing_trial", "missing_usage"):
            assert report["cases"][case]["comparisons"][0]["median_savings_fraction"] is None
        assert report["cases"]["false_completion"]["critical_failure_count"] == 1
        reanalyzed = run("analyze", "--manifest", output / report["manifest"],
                         "--expected-manifest-id", report["manifest_id"],
                         "--results", output / complete["results"], "--asset-root", output,
                         "--output-dir", output)
        assert json.loads(reanalyzed) == json.loads((output / complete["analysis"]).read_text())
        prepared = run("prepare", "--plan", output / report["plan"], "--asset-root", output,
                       "--output-dir", output)
        assert json.loads(prepared)["manifest_id"] == report["manifest_id"]
