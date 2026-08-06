# P0 Results

## What was proven

The local deterministic scenario moved `demo-lineage` from
`activation-source` on `substrate-a` to `activation-target` on `substrate-b`.
Preparation retained the source lease. Acceptance appended
`revision-demo-0004`, closed `lease-source`, and created `lease-target` in one
SQLite transaction.

The test suite proves:

- one active authoritative lease is enforced by a partial unique SQLite index;
- canonical revisions are append-only and projections do not mutate their source;
- required continuity fails closed when it cannot fit the target budget;
- rejected reconstruction leaves source authority unchanged;
- accepted reconstruction creates a separately hashed result and authority transition;
- revision, projection, snapshot, result, and exported-file tampering is detected;
- missing or mismatched handoff targets cannot resolve or gain authority;
- the version 0 to version 1 migration is repeatable and idempotent;
- all five seed schema examples remain valid.

## Demonstration evidence

`torc demo --state-dir .torc/demo --json` uses a 70-word projection budget. The
observed estimate is 65 words. Required sections are `identity-role`,
`constraints`, `commitments`, `open-work`, and `handoff-purpose`. Optional
`artifact-refs` and `memory-refs` fit; `goals`, `settled-decisions`,
`uncertainties`, and `methods` are omitted with reason `budget`.

The command exports seven JSON files under `.torc/demo/artifacts/`. `torc
inspect` exposes the head, history, authority, activations, projections,
handoffs, results, and artifact metadata. `torc verify` checks their hashes,
links, and authority transition.

## Observed scope

The implementation remained one local CLI process with SQLite and no runtime
dependencies. Production size reached the scope envelope's 1.5-times warning,
so P0 kept persistence in one store module and did not add separate service,
adapter, model, or lease-controller layers. It remained below the 2-times stop
threshold and introduced no new architecture trigger.

## Accepted operational risk

SHA-256 is tamper evidence, not authentication. A malicious local process can
change both data and verification code. Word estimates do not model provider
tokenization. Synthetic substrates do not prove continuity across real models.
SQLite provides local transactional authority, not cross-host consensus.

## Intentionally unimplemented

P0 does not include provider or model calls, routing adapters, daemons, network
APIs, background work, cross-host state, branch or merge semantics, automatic
fit learning, rollback, production authorization, or comparison against the
compiled-prompt and runtime-persistence baselines.
