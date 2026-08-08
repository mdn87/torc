# P2 Session-Handoff Pilot

Status: **successful and closed**. P2 used one real TORC-governed implementation-to-review transition to prove the bounded mechanism on actual work. No additional handoff evaluation is required to advance the roadmap.

## Boundary

TORC governs only its lineage head and lease. The source activation is the only activation allowed to checkpoint or prepare a handoff. Preparation binds the immutable snapshot to one pending target activation. Operator mutations fail closed when stored provenance or exported-artifact integrity is invalid. The target receives lineage authority only after its reconstruction satisfies every frozen continuity requirement.

This does not grant repository, tool, Autowork, model, or operating-system authority. Those permissions remain external to TORC. The operator still decides when every checkpoint and handoff occurs.

## Operator flow

Run from the repository root. The ignored `.torc/p2-pilot` directory contains the SQLite store and generated artifacts.

```powershell
python -m torc lineage create --state-dir .torc/p2-pilot --lineage torc-dev --state-file examples/p2-canonical-state.json --substrate-file examples/p2-source-substrate.json --activation-id activation-p2-implementation --json
python -m torc lineage status --state-dir .torc/p2-pilot --lineage torc-dev --json
python -m torc handoff prepare --state-dir .torc/p2-pilot --lineage torc-dev --source-activation activation-p2-implementation --plan-file examples/p2-handoff-plan.json --json
```

Preparation writes a markdown brief and an exact JSON reconstruction template under `.torc/p2-pilot/artifacts/`. The brief is visibly marked as a derived execution artifact. The recipient copies—not edits—the hashed template, preserves required fields exactly, and records new conclusions only in the copy's `new_inferences`.

```powershell
python -m torc handoff resolve --state-dir .torc/p2-pilot --handoff <handoff-id> --target-activation activation-p2-review-claude --reconstruction-file <reconstruction-path> --json
python -m torc verify --state-dir .torc/p2-pilot --lineage torc-dev --json
```

Use `lineage checkpoint` with a complete canonical-state JSON file for later real boundaries. A rejected reconstruction is an immutable result, returns a non-zero process status, leaves source authority unchanged, and requires a newly prepared handoff for another attempt.

## Disposition

The pilot is accepted as successful. It proved that the implemented lineage, projection, intended-recipient binding, integrity checks, reconstruction gate, rejection preservation, and transactional authority transfer work together on a real agent transition. TORC moves forward from this result; no repeated pilot, paired comparison, or provisional keep/remove decision remains scheduled.

## First dogfood result

On 2026-08-08, the Codex Windows implementation activation prepared the uncommitted P2 batch for a read-only Claude Code 2.1.226 review in WSL2 (`claude-opus-4-7`, high effort). The reviewer returned in 256.196 seconds, reported $1.953871 in model cost, found no required changes, and identified two optional low-severity improvements. Before acceptance, the implementation made rejected handoffs return a non-zero CLI status and added an end-to-end handoff CLI test.

The target reconstruction passed all nine frozen continuity requirements. TORC transferred the lease only to the bound Claude activation, recorded the accepted result and new lineage revision, and verified both generated artifacts with no integrity errors. This is the accepted production-parity evidence for closing the P2 pilot successfully.
