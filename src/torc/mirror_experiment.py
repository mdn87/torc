"""Reproducible local Mirror fixtures with one real acceptance-gated TORC handoff."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter

from .canonical import utc_now
from .errors import InvalidInputError
from .mirror import project_response, render_context, render_text, resolve_settings
from .operator import create_operator_lineage, prepare_operator_handoff, resolve_operator_handoff
from .store import Store
from .verify import verify_store

LINEAGE = "mirror-experiment"
COMMITMENTS = [
    "Complete the full comparison and retain verification limitations.",
    "Brief delivery must not reduce analysis work.",
]


def _write(path: Path, value: str | dict) -> None:
    text = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _substrate(name: str, phase: str) -> dict:
    return {
        "schema_version": 1, "substrate_id": name, "label": f"Synthetic {name}",
        "adapter": "fixture", "capabilities": ["repository_read", "verification_execute"],
        "policy_labels": ["local-workspace"], "context_budget": {"unit": "words", "limit": 10000},
        "task_affinities": [phase],
    }


def _state() -> dict:
    return {
        "identity": {"label": "Synthetic Mirror analysis"},
        "self_model": {"role": "Complete the synthetic architecture comparison",
                       "settled_decisions": ["TORC owns response settings"],
                       "methods": ["Preserve task obligations independently of response length"]},
        "goals": ["Compare all three synthetic alternatives"],
        "commitments": list(COMMITMENTS), "constraints": ["Do not make model or network calls"],
        "open_work": ["Retain the full report and disclose unverified behavior"],
        "uncertainties": ["Hardware playback and native model behavior are unverified"],
        "artifact_refs": [], "memory_refs": [],
    }


def _handoff(store: Store) -> dict:
    prepared = prepare_operator_handoff(
        store, lineage_id=LINEAGE, source_activation_id="mirror-source",
        plan={
            "target_substrate": _substrate("mirror-receiver", "review"),
            "target_activation_id": "mirror-target", "task_phase": "review",
            "requirements": {"capabilities": ["repository_read", "verification_execute"],
                             "policy_labels": ["local-workspace"], "minimum_context_units": 500},
            "budget_limit": 2000,
            "target_responsibility": "Preserve and inspect the full synthetic comparison",
            "reason_code": "task_phase_transition",
            "rationale": "Exercise a receiver handoff while delivery preferences change.",
        },
    )
    before = store.current_authority(LINEAGE)["activation_id"]
    reconstruction = json.loads(
        (store.state_dir / prepared["reconstruction_template_path"]).read_text(encoding="utf-8")
    )
    resolved = resolve_operator_handoff(
        store, handoff_id=prepared["handoff_id"], target_activation_id="mirror-target",
        reconstruction=reconstruction,
    )
    authority = store.current_authority(LINEAGE)
    state = store.get_revision(authority["lineage_head_revision_id"])["canonical_state"]
    return {
        "handoff_id": prepared["handoff_id"], "projection_id": prepared["projection_id"],
        "before_acceptance": before, "after_acceptance": authority["activation_id"],
        "disposition": resolved["disposition"], "verification": resolved["verification"],
        "commitments_preserved": state["commitments"] == COMMITMENTS
        and reconstruction["active_commitments"] == COMMITMENTS,
        "reconstruction_is_synthetic": True,
    }


def _result() -> dict:
    return {
        "status": "in_progress", "verification": "partial",
        "facts": [
            {"id": "outcome", "kind": "outcome",
             "text": "The synthetic report compares all three architectures."},
            {"id": "checks", "kind": "verification",
             "text": "Only deterministic fixture checks have run."},
            {"id": "limit", "kind": "limitation",
             "text": "Live playback and native model behavior remain unverified."},
            {"id": "decision", "kind": "decision",
             "text": "Before enabling live adaptation, check that the intended settings reached "
                     "the receiving agent, that it completed every original task obligation, "
                     "and that actual speech preserved all decision conditions. A successful "
                     "schema check or rendered text alone is insufficient evidence to approve it."},
            {"id": "comparison", "kind": "detail",
             "text": "Alternative A keeps a local callable resolver; B adds a daemon; "
                     "C duplicates policy across adapters. The fixture selects A for its "
                     "single policy owner and absence of a new background process."},
        ],
    }


def _signal(setting, value, observed, expires, *, kind="request", source="user", scope=None):
    return {
        "setting": setting, "value": value, "kind": kind, "source": source,
        "evidence_refs": [f"fixture:{observed}:{setting}"],
        "scope": {"task_id": "architecture-analysis"} if scope is None else scope,
        "observed_at": observed, "expires_at": expires,
    }


def _rejected(record, *, now, binding=None) -> bool:
    try:
        render_text(record, binding=binding or record["binding"],
                    response_id=record["source"]["response_id"], now=now)
    except InvalidInputError:
        return True
    return False


def run_experiment(output_dir: Path, *, now: str | None = None) -> dict:
    """Write a new evidence run. Existing output is rejected, never overwritten.

    The result facts and target reconstruction are synthetic. The lineage and
    handoff are real local TORC operations; no agent or speech engine is invoked.
    """
    started = perf_counter()
    now = utc_now() if now is None else now
    initial_binding = {"conversation_id": "mirror-session", "task_id": "architecture-analysis",
                       "turn_id": "desktop", "response_revision": 1}
    # Validate the supplied clock before creating any output directory.
    resolve_settings(initial_binding, [], now=now)
    clock = datetime.fromisoformat(now.replace("Z", "+00:00"))

    def at(seconds):
        return (clock + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")

    output_dir = Path(output_dir)
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise InvalidInputError("Mirror experiment requires a new or empty output directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write(output_dir / "run.json", {"format": "torc-mirror-run-v1", "synthetic": True, "now": now})
    facts = _result()
    written = "# Synthetic architecture comparison\n\n" + "\n\n".join(
        fact["text"] for fact in facts["facts"]
    )
    preferences = [
        _signal("explanation_depth", "detailed", at(-1), None, kind="preference", scope={}),
        _signal("persona_ref", "masq:dean", at(-1), None, kind="preference", scope={}),
    ]
    away = [_signal("screen", "away", at(1), at(600)),
            _signal("turn_length", "brief", at(1), at(600))]
    repair = _signal("interaction", "repair", at(2), at(120), kind="inference", source="agent")
    stages = [
        ("desktop", preferences + [
            _signal("screen", "available", at(0), at(300)),
            _signal("turn_length", "full", at(0), at(300)),
        ]),
        ("away", preferences + away),
        ("repair", preferences + away + [repair]),
        ("handoff", preferences + away + [repair]),
        ("returned", preferences + away + [repair,
            _signal("screen", "available", at(4), at(600)),
            _signal("turn_length", "full", at(4), at(600)),
            _signal("interaction", "continue", at(4), at(600)),
        ]),
    ]
    turns, deliveries, resolved_settings = [], [], []
    required_expected = required_retained = 0
    with Store(output_dir / "lineage") as store:
        create_operator_lineage(
            store, lineage_id=LINEAGE, canonical_state=_state(),
            substrate=_substrate("mirror-origin", "analysis"), activation_id="mirror-source",
        )
        for index, (name, signals) in enumerate(stages):
            if name == "handoff":
                handoff = _handoff(store)
            binding = initial_binding | {"turn_id": name}
            resolve_started = perf_counter()
            settings = resolve_settings(binding, signals, now=at(index))
            resolver_ms = (perf_counter() - resolve_started) * 1000
            render_started = perf_counter()
            context = render_context(settings, binding=binding, now=at(index))
            record = project_response(settings, facts, written, f"mirror-reply-{name}",
                                      now=at(index))
            text = render_text(record, binding=binding,
                               response_id=record["source"]["response_id"], now=at(index))
            render_ms = (perf_counter() - render_started) * 1000
            stage_dir = output_dir / "turns" / name
            stage_dir.mkdir(parents=True)
            files = {
                "settings_file": f"turns/{name}/settings.json",
                "context_file": f"turns/{name}/context.txt",
                "delivery_file": f"turns/{name}/delivery.json",
                "written_file": f"turns/{name}/written.md",
            }
            for key, value in zip(files, [settings, context, record, text], strict=True):
                _write(output_dir / files[key], value)
            required = [fact for fact in facts["facts"] if fact["kind"] != "detail"]
            normalized_speech = " ".join(record["speech"]["segments"])
            required_expected += len(required)
            required_retained += sum(fact["text"] in normalized_speech for fact in required)
            turns.append({
                "name": name, "binding": binding, "response_id": record["source"]["response_id"],
                "now": at(index), "resolver_ms": resolver_ms, "render_ms": render_ms,
                "settings_values": settings["values"], **files,
            })
            deliveries.append(record)
            resolved_settings.append(settings)
        verification = verify_store(store, LINEAGE)
        canonical_states = [
            revision["canonical_state"] for revision in store.lineage_revisions(LINEAGE)
        ]
    expiry_binding = initial_binding | {"turn_id": "after-expiry"}
    expired = resolve_settings(expiry_binding, preferences + away + [repair], now=at(601))
    echo_settings = resolve_settings(initial_binding | {"turn_id": "repair"},
                                     stages[2][1] + [repair] * 3, now=at(2))
    quoted = _signal("language", "technical", at(0), at(300), source="quoted")
    quote_settings = resolve_settings(initial_binding, [quoted], now=at(0))
    checks = {
        "required_facts_preserved": required_retained == required_expected,
        "complete_written_result_preserved": all(d["written"] == written for d in deliveries),
        "temporary_inference_expired": expired["values"]["interaction"] == "continue"
        and expired["values"]["screen"] == "unknown",
        "temporary_settings_not_canonical": all(
            "screen" not in json.dumps(state) and "repair" not in json.dumps(state)
            for state in canonical_states
        ),
        "expired_delivery_rejected": _rejected(deliveries[1], now=at(601)),
        "superseded_delivery_rejected": _rejected(
            deliveries[1], now=at(2), binding=deliveries[1]["binding"] | {"response_revision": 2}),
        "echoed_evidence_deduplicated": echo_settings == resolved_settings[2],
        "quoted_input_ignored": quote_settings["values"]["language"] == "plain",
        "handoff_verified": verification["valid"] and handoff["disposition"] == "accepted"
        and handoff["before_acceptance"] == "mirror-source"
        and handoff["after_acceptance"] == "mirror-target" and handoff["commitments_preserved"],
    }
    report = {
        "format": "torc-mirror-experiment-v1", "synthetic": True, "passed": all(checks.values()),
        "started_at": now, "checks": checks, "turns": turns, "handoff": handoff,
        "measurements": {
            "added_model_calls": 0, "required_facts_expected": required_expected,
            "required_facts_retained": required_retained,
            "resolver_total_ms": sum(turn["resolver_ms"] for turn in turns),
            "render_total_ms": sum(turn["render_ms"] for turn in turns),
            "elapsed_ms": (perf_counter() - started) * 1000,
        },
        "unverified": ["hardware_playback", "native_model_behavior", "subjective_usefulness"],
        "limitations": [
            "Supplied facts and reconstruction are synthetic; this is not a live agent trial.",
            "Timing measures local fixture processing, not model or speech latency.",
            "No audio was played and no native context injection was performed.",
        ],
    }
    _write(output_dir / "report.json", report)
    return report
