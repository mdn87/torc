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

### Show who holds the torc on the Dias Board

Say **“Put the torc on this project”** in a session with the `assign-torc` skill. In Dias, choose **Board → Assign a torc** and drag **Project torc** onto the project Board. You can also select the ring and then the Board with touch or the keyboard. A linked Work Trail opens the same Board. The assignment is saved immediately. The first holder appears when a session takes the lease and publishes its report.

For an existing lineage, say **“Put the Release review torc on Atlas.”** The skill can offer a known lineage under that public name, then assign it. Say **“Who holds the torc on Atlas?”** to read the last report. To take or pass authority, tell the holding or receiving session what you want to do. The skill uses the handoff flow above.

For a manually managed or synchronized report, publish the existing lineage on the machine that owns its TORC store.

```powershell
python -m torc lineage publish-holder --state-dir .torc/p2-pilot --lineage torc-dev --json
```

Existing private registry entries using `torcHolderFile` continue to work and appear as choices in Dias. For a separately synchronized file, configure its absolute path there and reload the host. The Board shows an open ring, the last reported holder, a short session tag and the UTC time that session received the lease.

To name a session on the Board, add an optional public `"board_label": "Codex"` to its substrate descriptor before registration. Do the same for the recipient in the handoff plan, for example `"board_label": "Claude Code"`. Use up to 32 letters, numbers, spaces or hyphens. An existing descriptor without a public name displays as `Session` with its own tag. Keep personal information and session identifiers out of public labels.

Run the usual prepare and resolve commands for each passage. Preparation and rejection keep the existing report. Acceptance of a handoff or failure recovery automatically publishes the new lease. A branch has its own lineage and can be enrolled separately. The project Board and the TORC store can be on different machines if the host can read a synchronized copy of the report.

If publication fails after acceptance, TORC logs a warning and retains the committed transfer. Run the same `publish-holder` command after restoring access. It verifies the store and rebuilds the report from the current lease. Repeating it for the same lease produces identical bytes. The display describes the last report it could read. To verify authority at the source, run `torc lineage explain` for that lineage.

### Planned fallback for sessions without Dias

A CLI with a status bar can use the same report to show `TORC · Claude Code · a1b2c3d4` throughout the session. A harness without a status bar can announce “Claude Code took the torc at 14:05 UTC” at the start of its first turn and the first turn after the tag changes. Scope the cached tag to the lineage so switching projects refreshes the announcement. If the report cannot be read, show “TORC holder unavailable” and check again on the next turn. A session should say “you hold the torc” only after matching its own activation to the authoritative lease. These client integrations are planned.

## Disposition

The pilot is accepted as successful. It proved that the implemented lineage, projection, intended-recipient binding, integrity checks, reconstruction gate, rejection preservation, and transactional authority transfer work together on a real agent transition. TORC moves forward from this result; no repeated pilot, paired comparison, or provisional keep/remove decision remains scheduled.

## First dogfood result

On 2026-08-08, the Codex Windows implementation activation prepared the uncommitted P2 batch for a read-only Claude Code 2.1.226 review in WSL2 (`claude-opus-4-7`, high effort). The reviewer returned in 256.196 seconds, reported $1.953871 in model cost, found no required changes, and identified two optional low-severity improvements. Before acceptance, the implementation made rejected handoffs return a non-zero CLI status and added an end-to-end handoff CLI test.

The target reconstruction passed all nine frozen continuity requirements. TORC transferred the lease only to the bound Claude activation, recorded the accepted result and new lineage revision, and verified both generated artifacts with no integrity errors. This is the accepted production-parity evidence for closing the P2 pilot successfully.
