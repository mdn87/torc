# LIR Thread Checkpoint Authority

TORC owns checkpoint acceptance for a LIR thread; LIR owns only the disposable
resumption view. A checkpoint body remains in OGMI and its referenced owner
stores. TORC retains its decision, the checkpoint reference and hash, and the
lineage authority that made the decision.

## Records

`thread_lineage_bindings` stores one immutable
`thread_carried_by_lineage` link for a thread. Creating it requires the current
lineage activation and expected lineage head. The link is evidence of a
relationship and does not grant, move, or broaden authority.

`thread_checkpoint_decisions` stores immutable accepted and rejected decisions.
Every record identifies the active TORC lease and lineage head, the exact OGMI
checkpoint reference and SHA-256, policy version, reason codes, and evidence.
The portable record shape is
`schemas/thread-checkpoint-decision.schema.json`.

`thread_accepted_heads` is TORC's mutable pointer to the latest accepted
decision. `record_checkpoint_decision` updates it only when all of these checks
hold in one immediate SQLite transaction:

- the thread has an immutable primary-lineage binding;
- the caller names the activation holding the current lineage lease;
- the stored accepted checkpoint equals the caller's expected head; and
- the new decision is `accepted`.

A stale expected head appends no decision. A rejected decision is retained but
does not move the head. Replaying the same decision ID and content returns the
existing record; reusing the ID for different content fails closed.

## Integrity and migration

Database schema version 2 adds these three tables and no service process or
network dependency. Opening an older writable schema-version-1 database applies
the forward migration. Immutable-table triggers reject update and delete, and
`verify_store` checks record hashes, column-to-payload agreement, the accepted
decision chain, and the current accepted-head pointer.

These checks protect against accidental or post-hoc corruption under TORC's
documented local-process threat model. They do not authenticate a malicious
process with direct database access.
