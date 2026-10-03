# Native context follow-up

Series 002 reduced explicit critic prompt bytes by 56.1 percent but reduced
provider-reported input by only 7.0 percent. The next experiment therefore
tests whether provider-native agent isolation and inherited context change the
actual usage total, not merely the serialized payload.

The preregistration is `native-context-series-003-plan.json`. It compares three
Responses API arms under one exact model: a direct portable capsule, an isolated
native subagent given that capsule, and an inheriting native subagent whose root
receives the full bundle. The complete response usage counts; agent-attributed
output items verify that exactly one child ran. Quality remains governed by the
frozen deterministic defect scorer.

This is deliberately not active. Responses API use has separate API billing,
so an operator must authorize a budget before the three-call pilot. The pilot
stops the series unless usage is complete, agent count is bounded, and all arms
remain scoreable. A native arm must eventually save at least 15 percent of
total uncached input without losing defect recall to count as a win.

Responses multi-agent documents only response-level usage. Separate root and
subagent turn usage is documented for the distinct Agents API. The pilot must
therefore validate that the response usage represents the complete hosted run;
the experiment will not combine accounting from the two APIs.

Before authorization, inspect a request plan without making a model call:

```text
python experiments/cross-agent-collaboration-001/native_context_request.py \
  --candidate refactor-baseline-v1 \
  --arm portable_direct \
  --model gpt-6.1-sol
```

Use `native_isolated` and `native_inherited` for the other arms. The planner
verifies the candidate fixture against Series 002, reconstructs the selected
capsule and visible bundle, and prints only hashes, byte counts, and a redacted
request shape by default. It has no execution mode.

`native_context_response.py` is the corresponding offline validator. It checks
the exact model, complete usage shape, one-child topology, requested
`fork_turns`, final critic contract, and claim identifiers. Encrypted message
content is reduced to byte length and SHA-256 evidence in its output.

After one sanitized result exists for each arm,
`native_context_pilot_report.py` checks that candidate, model, plan, usage, and
topology stayed matched. It continues only native arms that preserve quality,
remain within 10 percent of direct uncached input, and remain within 50 percent
of direct completion time. The stricter 15-percent input saving and 20-percent
time ceiling still determine a full-series win.

OpenAI documents encrypted agent messages and independently compacted root and
subagent contexts in its [Responses multi-agent guide](https://developers.openai.com/api/docs/guides/responses-multi-agent).
Its [compaction guide](https://developers.openai.com/api/docs/guides/compaction)
describes compaction items as opaque provider output to carry forward. TORC can
reference those same-provider artifacts through an adapter; it cannot recreate
them for Claude or treat them as canonical lineage history.
