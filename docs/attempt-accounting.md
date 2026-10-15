# Experiment attempt preparation and usage evidence

The two compact critic runners validate their frozen manifest, provider settings,
effort, timeout and reservation records before querying usage or creating a run
directory. The probe also validates its matched baseline first. Invalid input
raises a JSON-compatible `preflight:` error and consumes no attempt. Host lookup
and harness failures retain the existing excluded-attempt behavior. Process kills
and unexpected failures after dispatch still need operator reconciliation; the
runners do not retry or reuse attempt identities.

The four dependent plan files have updated apparatus hashes. Historical files
under `runs/` retain the exact hashes recorded when those runs occurred. Their
results, failed quality gates and analysis have not been rewritten.

The consumer smoke requires an execution-owner capture before linking usage. It
checks attempt identity, prompt, raw output and the five-counter projection of
the owner's original usage. Recomputing `usage.json` and a matching receipt is
insufficient. Missing counters remain missing; the accounting reader includes
rejected attempts and flags unavailable or damaged evidence.

`OwnerLedger` is an in-process stand-in used only by the recorded replay and its
tests. It is neither durable nor an access-control boundary. A production caller
must inject a durable execution-owner reader outside the consumer's write scope.
Autowork owns that eventual provider capture; Torc does not gain provider routing
or execution authority. The replay makes no live calls and does not establish
trusted live spend, savings, provider attestation or authenticated hostile-writer
protection. Consumer-authored timestamps and disposition outcomes remain unbound.
