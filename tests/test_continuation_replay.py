"""The retained report must reproduce with independently created stores."""

import hashlib
import json
from pathlib import Path

from torc.retained_replay import retained_runtime


def test_offline_replay_matches_retained_report_and_artifact_hashes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    experiment = root / "docs/experiments/session-continuation-001"
    expected = (experiment / "offline-report.json").read_bytes()
    with retained_runtime(root) as runtime:
        for name in ("first", "second"):
            output = tmp_path / name
            result = runtime.replay("offline", output)
            assert result.stdout == expected
            report = json.loads(result.stdout)
            assert report["state_store_unchanged"] is True
            assert report["live_model_trials"] == 0
            refs = [*report["artifacts"].values(), *(c["artifact"] for c in report["usage_cases"])]
            for ref in refs:
                path = output / ref
                assert hashlib.sha256(path.read_bytes()).hexdigest() == path.stem
