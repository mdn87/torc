# Mirror native response adapter

TORC prepares response settings for Claude Code and projects its final response
into the existing delivery contract. The native harness continues to execute
the task. The voice runtime continues to listen, queue speech, interrupt, and
play audio. These commands start no model, daemon, listener, or playback process.

## Prepare a turn

The native `UserPromptSubmit` adapter creates a trusted current binding and a
unique sidecar path. A sidecar is a JSON file the native agent writes alongside
its final reply, containing the written answer and its protected facts.

```sh
torc mirror prepare --input-file prepare.json --json
```

Input fields:

| Field | Meaning |
| --- | --- |
| `binding` | Current `conversation_id`, `task_id`, `turn_id`, positive integer `response_revision` |
| `signals` | Approved evidence using the existing Mirror signal schema |
| `now` | Current UTC RFC 3339 timestamp |
| `sidecar_path` | Adapter-owned path supplied as a nonempty string without control characters |
| `ttl_seconds` | Optional settings lifetime, 1–3600 seconds; default 300 |

The output is exactly `{settings, context}`. Inject `context` through the native
hook's `hookSpecificOutput.additionalContext`. It includes the existing Mirror
context and instructions to complete the authorized work, write exactly
`{written, result}` to the sidecar, then emit exactly `written` as the final reply.
TORC does not create or read the sidecar. The adapter selects a safe unique path
and reads the resulting JSON under its existing filesystem permissions.

The instructions require truthful status and verification, with verbatim facts
covering the outcome, checks, material limitations, decisions, conditions,
instructions, and next actions. `detail` is reserved for optional elaboration.
Short speech does not reduce the work or the complete written answer. No setting
or sidecar grants permission or transfers lineage authority.

## Project the observed final response

At `Stop`, obtain the final text and message identity independently from the
native harness, then read the sidecar. Do not obtain the trusted binding or
response identity from model-authored JSON.

```sh
torc mirror native-project --input-file native-project.json --json
```

Input fields:

| Field | Meaning |
| --- | --- |
| `settings` | Original settings returned by `prepare` |
| `binding` | Independently known current binding; must match original settings |
| `signals` | Currently approved evidence to resolve at delivery time |
| `sidecar` | Exactly `{written, result}` authored by the native agent |
| `written` | Final text independently observed from the native harness |
| `response_id` | Message identity independently obtained by the adapter |
| `now` | Current UTC RFC 3339 timestamp |
| `ttl_seconds` | Optional fresh settings lifetime; default 300 |
| `target_chars` | Optional speech segment target, 40–2000; default 240 |

The output is exactly `{delivery, settings, prior_settings_id}`. `delivery` is
the normal `torc-response-delivery-v1` object for the voice consumer. `settings`
contains the fresh delivery-time resolution, and `prior_settings_id` links back
to the original preparation. Persist both settings records with the receipt.

The command validates the original settings' integrity and binding at their
issuance time, and rejects issuance in the future. Expired original settings
are allowed because a long task can outlast the initial lifetime. The command
always resolves the supplied evidence again at delivery time; it does not
extend or relabel the old record. Expired observations fall out, and fresh
provenance records the resulting choice. Resolution remains deterministic: the
same inputs at the same timestamp can produce the same settings ID.

The sidecar's written text must exactly equal the observed final response,
including whitespace. After that comparison, the existing delivery contract
trims outer whitespace and hashes the trimmed text. Missing mandatory facts,
invented fact kinds, malformed evidence, changed bindings, and corrupted
settings fail validation. The command preserves native status and verification
without inventing successful execution or checks.

## Responsibilities outside this boundary

The native hook must reject superseded turns before projection and before
playback, enforce session identity, and keep its binding/path registry outside
model-authored content. Matching an old binding does not prove that it remains
current. Re-resolution accepts evidence from that trusted adapter; it does not
authenticate the source of a signal or authorize new requests.

The result producer remains responsible for truthful claims and complete fact
tagging. Verbatim text validation cannot establish truth or detect an omitted
material fact. A completed native turn is not proof of completed task work.
The harness adapter should retain actual tool/check receipts alongside native
claims. TORC's synthetic harness capture is not a live effect verifier.

Missing or rejected sidecars must use the voice runtime's existing fallback;
never manufacture `complete` or `passed`. A structured-output JSON envelope may
differ from the native final message: use the independently observed final text
and reject a mismatch. Native session references support resumption, while TORC
checkpoint and accepted handoff records retain durable commitments. Transient
screen and interaction observations remain scoped and expiring.

## Verify the adapter

```sh
python -m pytest tests/test_mirror_native.py tests/test_mirror.py tests/test_mirror_cli.py tests/test_mirror_experiment.py
```

These tests exercise the local boundary and CLI. They do not establish model
compliance, continuous native availability, microphone listening, or audible
playback. A live trial must separately retain settings receipt, native final
response, projection, and actual speech start/completion evidence. One bounded
native call proves one turn; ongoing hook wiring must also be exercised across
multiple turns and interruption.
