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

The pilot freezes `gpt-6.1-sol`, low reasoning effort, at most one concurrent
subagent, no response storage, and a 2,000-token output ceiling. This is a new
API-only comparison; it is not merged with the older `gpt-6-sol` CLI results.

This is deliberately not active. Responses API use has separate API billing,
so an operator must authorize a budget before the three-call pilot. The pilot
stops the series unless usage is complete, agent count is bounded, and all arms
remain scoreable. A native arm must eventually save at least 15 percent of
total uncached input without losing defect recall to count as a win.

Before buying API usage, `codex-native-capability-001-plan.json` specified a
one-call local Codex probe under the existing Plus allowance. That probe is now
complete and rejected without retry. It exposed exactly one child activity
lifecycle and separate root/child usage, but it did not emit a `spawnAgent`
item, child settings, or the child prompt. The local surface therefore cannot
prove the frozen transport controls well enough to replace the API pilot.

The child produced the correct critique at full deterministic recall and used
11,955 input tokens, 5.0 percent less than the matched direct compact median.
Root orchestration used another 38,970 input tokens, making the combined total
50,925, or 4.05 times direct. Native completion was 3.46 times the direct
median. `codex-native-capability-001-analysis.json` is reproducible with
`codex_native_probe_audit.py`. This single call is a cost warning, not a repeated
performance estimate.

Responses multi-agent documents only response-level usage. Separate root and
subagent turn usage is documented for the distinct Agents API. The pilot must
therefore validate that the response usage represents the complete hosted run;
the experiment will not combine accounting from the two APIs.

The API pilot remains budget-gated rather than recommended by default. Its
value is now narrow: determine whether the hosted opaque Responses transport
behaves materially differently from local Codex delegation. It should not be
run merely to seek token savings, because the observed root orchestration cost
overwhelmed the child's small context reduction.

A cheaper provider-neutral optimization has now shown more promise. The
two-candidate `critic-batch-capability-001` call shared one Codex harness context
while keeping each TORC capsule and result isolated. Both candidates retained
full deterministic recall, batch input was 42.7 percent below the summed direct
medians, and completion time was 35.8 percent lower than the summed medians.
This single call does not establish a safe general batch size, but it moves the
next Plus-backed work from native delegation to repeated counterbalanced
batching.

That confirmation is now frozen as `critic-batch-confirmation-004`: four fresh
tool-free batches ordered `AB, BA, BA, AB`. The exploratory result is excluded,
each candidate must pass twice in each position, and live calls stop at 60%
current-window usage so the series can continue in a later session without
reset credits.

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
