# Capsule collision correction and replay pins

The 2026-10-15 correction rejects duplicate generated claim handles before a
second claim can overwrite provenance. It adopts the source correction proposed
in `7b645e2`. Both section orders and the c11/c12 boundary are covered; overlapping
prefixes that generate distinct handles remain valid. The existing 24-handle
capsule and the noncolliding overlap fixture retain their exact bytes and hashes.

The compiler SHA-256 changes from
`3ebb1874f4a8a35ffea6dc1893ae9bdfaea9ca5c053ff51260766c626a76b986` to
`17c5dc9d7601831f560802697bf7e62d5813f741dd638ed658283aef9c6f782e`.
Eight plans pin that source. Their apparatus hashes and the dependent plan pins
in controls 007, replication 008 and the consumer smoke plan are re-frozen.
Following `307ee72`, matching `plan_sha256` values in the confirmation 004/005,
generalization 006, controls 007 and replication 008 probe-plan copies, the
transport 002 block state, the controls resume checkpoint and the existing test
literal now identify the corrected replay plans.

These updated pins establish reproducibility with the current compiler. They
do not say the historical provider calls ran this source. Original apparatus
revisions, timestamps, prompts, responses, usage records, findings and analyses
remain unchanged. Earlier probe-plan hashes that already differed from their
plans remain historical. The baseline tree is `932924f`; Git retains every
previous plan and pin. No provider call or historical resume command was run
for this correction.

The accompanying aggregate-usage correction changes the reference validator's
accepted field names; it does not change receipt schema version 1 or any stored
provider evidence. Its separate contract is in
[critic-batch-adapter-contract.md](critic-batch-adapter-contract.md).
