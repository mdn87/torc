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

OpenAI documents encrypted agent messages and independently compacted root and
subagent contexts in its [Responses multi-agent guide](https://developers.openai.com/api/docs/guides/responses-multi-agent).
Its [compaction guide](https://developers.openai.com/api/docs/guides/compaction)
describes compaction items as opaque provider output to carry forward. TORC can
reference those same-provider artifacts through an adapter; it cannot recreate
them for Claude or treat them as canonical lineage history.
