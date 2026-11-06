# Mirror first experiment

This is a local, deterministic prototype of concept TORC-0002. TORC resolves
interaction settings; native agents supply interpretations and substantive
results. Masq owns persona expression. Voice owns playback and interruption.
No model calls, daemon, durable interaction database, or permission changes are
introduced. The existing lineage/handoff mechanism carries accepted commitments.

## Version 1 records

`torc-response-settings-v1` is resolved before a response. It contains `settings_id`,
`binding`, `issued_at`, `expires_at`, `values`, and per-setting `provenance`.
The binding contains `conversation_id`, `task_id`, `turn_id`, and a positive integer
`response_revision`. Values are `language` (plain/technical), `explanation_depth`
(concise/detailed), `turn_length` (brief/normal/full), `interaction`
(answer/continue/repair), `screen` (unknown/available/away), and `persona_ref`
(a reference string, default `default`). These are presentation/context settings,
not execution instructions or authorization.

Resolver signals have `setting`, `value`, `kind` (request/preference/observation/
inference), `source` (user/surface/agent/quoted/uncertain_transcript), `evidence_refs`,
`scope`, `observed_at`, and `expires_at`. Scope uses binding identifiers, with
an empty scope allowed only for established explicit preferences. Inferences
must name the current task and expire. Quotes and uncertain transcription never
become user preferences. Current explicit requests, established preferences,
supported surface observations, inferences, then defaults win **per setting**.
Within a class, more specific scope then newer evidence wins. Equal-priority
contradictory evidence rejects instead of depending on arrival order. Repeated
evidence does not gain weight. Screen observations only describe a named surface
event; user absence is never inferred from silence.

`torc-response-delivery-v1` is produced after a substantive result exists:

```json
{
  "format": "torc-response-delivery-v1",
  "binding": {"conversation_id": "session-1", "task_id": "analysis", "turn_id": "turn-2", "response_revision": 1},
  "settings_id": "settings-<sha256>",
  "issued_at": "2026-11-06T12:00:00Z",
  "expires_at": "2026-11-06T12:05:00Z",
  "source": {"response_id": "assistant-message-id", "text_sha256": "<sha256 of trimmed written UTF-8 text>"},
  "result": {
    "status": "in_progress",
    "verification": "partial",
    "facts": [
      {"id": "outcome", "kind": "outcome", "text": "The analysis is written."},
      {"id": "checks", "kind": "verification", "text": "Playback is still unverified."}
    ]
  },
  "written": "The analysis is written. Playback is still unverified.",
  "speech": {
    "fact_ids": ["outcome", "checks"],
    "segments": ["The analysis is written. Playback is still unverified."],
    "target_chars": 240,
    "restyle": false
  }
}
```

Status is `in_progress`, `blocked`, or `complete`; verification is `not_run`,
`partial`, `passed`, or `failed`. Fact kinds are `outcome`, `verification`,
`limitation`, `decision`, `next_action`, and `detail`. Outcome and verification
facts are mandatory. Every non-detail fact must be spoken. Brief speech may
omit detail facts; normal/full includes them. Each fact must occur verbatim in
the original written result. Segments preserve the selected fact text and order
after whitespace normalization. The target length never licenses truncation;
an indivisible long word may exceed it. Version 1 does not paraphrase or restyle
protected speech. This intentionally measures selection before adding generation.

The result producer is responsible for truthful status and complete fact tagging.
Schema/content checks establish faithful rendering of supplied facts, not that
those facts are true or that the producer identified every material condition.

Consumers check version, shape, timestamps, source digest, and independently
known session/message identity. A live integration must additionally recheck
freshness through its existing delivery coordination. Absent/unsupported/invalid
contracts may use the independently bound original reply; stale contract speech
must never enter playback or recap. Contract presence never grants approval.

## Experiment and acceptance

Replay a detailed desktop turn, brief away-from-screen update, scope correction,
one accepted TORC handoff, then return to detailed text. Verify commitments survive
while temporary settings expire. Export text context, complete written results,
speech contracts, and measurements for the Windows consumer. Include quoted
input, repeated evidence, long decisions, expired and superseded replies.

Check settings calculated, adapter input delivered, and output fidelity separately.
Use native adapter integration tests with playback stubbed; hardware playback,
model compliance, and subjective usefulness remain separate unverified outcomes.
Record elapsed resolver/render time, retained required facts, and zero added model
calls. Do not label synthetic fixture results as completed real-world analysis.
