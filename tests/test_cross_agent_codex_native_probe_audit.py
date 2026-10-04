from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import codex_native_probe_audit as audit  # noqa: E402


def test_preserved_native_probe_rejection_and_cost_are_reproducible() -> None:
    result = audit.audit_run()

    assert result["status"] == "capability_rejected_confirmed"
    assert result["quality"]["defect_area_recall"] == 1.0
    assert result["observability"]["one_child_activity_lifecycle"] is True
    assert result["observability"]["completed_spawn_agent_item_count"] == 0
    assert result["observability"]["child_prompt_observed"] is False
    assert result["observability"]["child_model_and_effort_observed"] is False
    assert result["usage"]["root"]["input_tokens"] == 38970
    assert result["usage"]["child"]["input_tokens"] == 11955
    assert result["usage"]["combined_input_tokens"] == 50925
    assert result["usage"]["direct_compact_baseline"]["median_input_tokens"] == 12587
    assert result["usage"]["combined_to_direct_compact_input_ratio"] > 4
    assert result["decision"]["plus_backed_series_allowed"] is False


def test_committed_native_probe_analysis_matches_recomputed_result() -> None:
    committed = json.loads(audit.DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert committed == audit.audit_run()
