# Session continuation: first local evidence slice

This slice parses synthetic Claude-shaped transcript prefixes and writes an
immutable capture manifest plus read-only reconciliation report. It makes no
model calls and changes no TORC authority state. It does **not** measure token
savings yet. The [protocol skeleton](protocol.md) defines how later trials will
measure the whole resumed task, including failed starts and fallbacks.

The accepted design is the [final plan](../../plans/2026-10-16-session-handoff-token-efficiency.md).
The [decision log](../../plans/2026-10-19-session-handoff-decisions.md) explains
why the retry coordinator was cut and answers all three round-5 findings.

## Manual replay on macOS

From the repository root, use the existing development Python environment:

```sh
PYTHONPATH=src python3 - <<'PY'
import json
import tempfile
from pathlib import Path
from torc.harness_capture.manifest import build_capture
from torc.harness_capture.persist import publish
from torc.harness_capture.reconcile import reconcile

fixture = Path('docs/experiments/session-continuation-001/fixtures/interrupted.jsonl')
raw = fixture.read_bytes()
bindings = {
    'lineage_id': 'synthetic-lineage',
    'lineage_revision_id': 'synthetic-revision',
    'accepted_checkpoint_ref': None,
    'accepted_checkpoint_sha256': None,
    'workspace_identity': {'evidence_bundle_digest': None},
}
manifest = build_capture(
    raw, prefix_length=len(raw), session_ref='fixture-session',
    session_incarnation='fixture-incarnation',
    observed_at='2026-10-19T12:00:00Z', bindings=bindings,
)
report = reconcile(manifest, {'base_bindings': bindings, 'verified_operations': []},
                   current_bindings=bindings)
output = Path(tempfile.mkdtemp(prefix='torc-capture-'))
capture_path = publish(output, 'capture', manifest)
report_path = publish(output, 'reconciliation', report)
print(json.dumps({'capture': str(capture_path), 'report': str(report_path),
                  'status': report['status'], 'hold_list': report['hold_list'],
                  'scope_holds': report['scope_holds'],
                  'retry_authorized': report['retry_authorized']}, indent=2))
PY
```

Expected: `held`, operation `fixture-incarnation/tool-1`, scope hold
`coverage_incomplete`, and `retry_authorized: false`. Inspect the manifest's
exact raw-prefix digest and its separate redacted-view digest. Output is in a
private temporary directory, outside the fixture files and any authority store.
The replay uses fixture bindings, not live Git or lineage inspection. Retain
or remove the returned directory under your normal local evidence policy.

## Input and trust contract

- Parse only the declared prefix and newline-terminated JSON object records.
  Stop at malformed/unterminated input and quarantine the remaining prefix.
- The supported synthetic subset is assistant `tool_use`, user `tool_result`,
  text blocks and a fixture `stop` event. Unsupported shapes produce coverage
  diagnostics. This is not a supported live Claude Code adapter.
- Tool IDs are scoped by caller-supplied session incarnation. IDs must use
  letters, digits, `_` or `-` and be 1–128 characters. Rotation needs a new
  incarnation. Duplicate IDs remain ambiguous even if a result later appears.
- Arguments, command bodies, path strings, outputs and prose are not retained.
  Path identity and exact arguments are hashed. Equal fingerprints do not prove
  a repeated logical operation; hashes are not secrecy or authentication.
- Caller-supplied bindings, timestamps and evidence references are trusted,
  allowlisted metadata. The builder cannot independently observe file changes,
  writer exit or freshness. It never upgrades missing observations.
- `verified_operations` is operation-specific independent fixture evidence,
  with an `evidence_ref` and matching `base_bindings`. Do not pass model claims
  or current-file equality as proof that a historical operation occurred.
- `observations_complete` is available only for explicitly complete fixtures.
  It grants no tools or retry. Live operation coverage and effect quiescence
  remain unknown. External sends, delayed ingress and A→B→A histories are not
  reconciled into automatic retries.

## Publication and hash boundaries

`capture_id` hashes the canonical manifest body without its own ID. The raw
prefix hash covers exactly the first declared N bytes. The redacted-view hash
covers canonical JSON of `tool_operations` and `collector_errors`, without a
newline. Artifact filenames hash the complete canonical JSON file bytes **with
the final newline**. These are intentionally distinct identities.

`publish` writes sanitized dictionaries to a caller-selected private ignored
output root. It uses a private temporary, file fsync and create-once hard-link
publication. Identical writers can converge; corrupt existing content is never
replaced. There is no latest pointer, locking protocol or retry claim. Process
exit may leave hidden staging directories; power-loss durability and shared/
network filesystems are not claimed. Never use the canonical state directory
as the output root or store raw transcript data through this metadata publisher.

## Verification

```sh
python3 -m pytest tests/test_harness_capture.py tests/test_harness_capture_persist.py
python3 -m pytest
python3 -m ruff check .
PYTHONPATH=src python3 -m torc doctor --json
```

Also run `torc demo --state-dir <temporary-directory> --json`, followed by
`torc verify` on that directory, as required by the repository. The new store
invariance test reuses `_unchanged` from `tests/test_p5_capsule_adapter.py` and
checks the SQLite dump and all state files across capture, reconciliation and
separate publication. Other tests cover malformed records, failure after a
possible effect, missing results, stale bindings, overlapping publication and
a hard process exit before publication. No live model comparison is run.

Validation recorded October 19, 2026 on macOS/Python 3.14: **38 focused tests,
794 total tests passed**; Ruff, doctor, temporary demo/verify, the documented
replay, scope-schema validation and Markdown links passed. The wheel built and
the new modules imported directly from it. The environment initially lacked
setuptools; an isolated build dependency was fetched for that packaging check.
Live hooks, other operating systems and actual token savings remain untested.
