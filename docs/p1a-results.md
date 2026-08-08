# P1a Experimental Readiness Results

Status: P1a gate passed; P1b procedure ready

Date: 2026-08-08

## Implemented apparatus

- Five version 1 schemas with validating examples.
- A separated agent-visible fixture, runner-only oracle, and structural rules.
- Replay implementations for compiled-prompt, unavailable native-persistence,
  and TORC continuity lanes.
- Append-only target attempts, immutable stage receipts, atomic canonical JSON
  writes, visible-workspace manifests, and complete artifact manifests.
- Deterministic scoring with a timing-free `score_core` parity hash.
- Bounded Codex source and Claude Code target probes that fail closed when
  filesystem-read isolation cannot be evidenced.
- Prepare, source, target, score, inspect, and verify CLI commands.

## Automated and Windows replay evidence

`python -m pytest -q` passed 62 tests. `python -m ruff check .` passed.

| Lane | Disposition | Payload SHA-256 | Score-core SHA-256 |
|---|---|---|---|
| compiled-prompt | accepted | `29b5f0c93aae501ca224f61ff40d8f15f3f6fc51e3cfad19790cc9f77820a5fc` | `97fdafeb0a2680f5930cd304627cdf8b1d61ec75109e075e878b8ceb79457154` |
| native-persistence | unavailable | not scored | not scored |
| TORC | accepted | `57675150ea01a759fb8235622a92be74fd9a7499b5be9b7972f24ef6d76312cf` | `34fa96e4d98634f091415f0c17a8b95009fedd59dea4c319b420b36cf5a34bf1` |

All three run directories verified. Their best-effort credential scans reported
no findings. Lane B contains no target attempt, reconstruction, or score. Lane
C retained source authority until its accepted reconstruction was recorded.

The compiled-prompt source, target, score, and verify commands were repeated.
They returned idempotent results, created no additional attempt, and left the
artifact-manifest bytes unchanged. Automated tests also preserve an interrupted
attempt and reject changed stage inputs or a changed frozen payload.

Windows operator steps were five for Lane A, three for Lane B, and five for
Lane C. No background runtime process or manual artifact edit was used.

## macOS replay parity

On 2026-08-08, the deterministic replay suite was repeated headlessly on
`macos-secondary` with macOS, Python 3.12.4, and the synced P1a apparatus. All 56 tests
and Ruff passed. Fresh run directories under `.torc/p1a/macos-intel-{a,b,c}`
verified with no credential-scan findings.

| Lane | Disposition | Payload SHA-256 | Score-core SHA-256 |
|---|---|---|---|
| compiled-prompt | accepted | `29b5f0c93aae501ca224f61ff40d8f15f3f6fc51e3cfad19790cc9f77820a5fc` | `97fdafeb0a2680f5930cd304627cdf8b1d61ec75109e075e878b8ceb79457154` |
| native-persistence | unavailable | not scored | not scored |
| TORC | accepted | `57675150ea01a759fb8235622a92be74fd9a7499b5be9b7972f24ef6d76312cf` | `34fa96e4d98634f091415f0c17a8b95009fedd59dea4c319b420b36cf5a34bf1` |

The Lane A and C payload hashes and canonical score-core hashes are identical
to the Windows evidence, proving the required deterministic bytes match across
platforms. Lane B completed its verified unavailable path. macOS operator
steps were five for Lane A, three for Lane B, and five for Lane C.

## Isolated live smoke

The authoritative live smoke ran through WSL2 Ubuntu using native Linux
`codex-cli 0.147.0` and `2.1.226 (Claude Code)`. Run directories were outside
the repository hierarchy so neither harness could discover repository-level
instruction files before its assignment boundary was active.

Codex used a narrow permission profile. Its preflight proved `task.json`
readable and the repository `AGENTS.md` unreadable before model invocation;
network access remained denied to generated commands. Claude Code ran as a
fresh, non-persistent safe-mode session with an empty strict MCP configuration,
only the `Read` tool, sandbox fail-closed behavior, and explicit deny rules for
the repository and runner-only run areas. Stream evidence correlated the
canary `Read` tool-use ID to an error result while both visible fixture reads
succeeded. No unrestricted transcript was retained.

| Lane | Run | Disposition | Payload SHA-256 | Score-core SHA-256 |
|---|---|---|---|---|
| compiled-prompt | A-04 | accepted | `29b5f0c93aae501ca224f61ff40d8f15f3f6fc51e3cfad19790cc9f77820a5fc` | `b6766240007ac372944a82759b6ade58524db4de9373f62fd5540fb674f19282` |
| TORC | C-01 | accepted | `57675150ea01a759fb8235622a92be74fd9a7499b5be9b7972f24ef6d76312cf` | `45b35a724a3b2ba648a082a5d0eefdac7124595617dbebec0d97f39418a9e0e9` |

Both selected runs completed on their first target attempt, used six documented
operator stages, passed all field-recall and task-quality checks, reported zero
contradictions, verified their artifact manifests, and had no credential-scan
findings. Lane C passed all nine frozen continuity requirements; source
authority remained unchanged until acceptance, then transferred to
`p1a-target-attempt-0001` at revision `p1a-revision-0003`.

Earlier A-01 through A-03 apparatus-shakeout runs were preserved rather than
relabeled. They exposed WSL argument forwarding, Codex profile serialization,
native Claude authentication, denial-event parsing, and target-schema defects.
None was included in the readiness evidence or comparative results. The final
schema rejects unscorable assertion, review-area, and completion-status shapes
before target selection.

## Gate conclusion

P1a's replay, cross-platform parity, oracle-isolation, live A/C, provenance,
credential-scan, and verification gates pass. Cross-harness native persistence
remains explicitly unavailable, so the frozen P1b procedure is the registered
two-lane compiled-prompt versus TORC comparison. This result proves apparatus
readiness only; it is not evidence that TORC outperforms the baseline.

Credential scanning remains best-effort rather than proof of secret absence.
