# P1a Experimental Readiness Results

Status: implementation complete; P1a gate pending isolated live smoke

Date: 2026-08-06

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

`python -m pytest -q` passed 56 tests. `python -m ruff check .` passed.

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

## Live adapter probe

The installed harnesses were:

- `codex-cli 0.146.1`
- `2.1.195 (Claude Code)`

Both version probes succeeded using argument-list subprocess invocation from
the staged role workspace. Neither CLI probe evidenced a filesystem read
boundary that prevents access to the parent repository. The adapters therefore
return `contaminated` and do not launch or score a live activation. This is the
required fail-closed behavior; it is not a completed live smoke.

## Remaining P1a gate items

- Supply an operator-authorized assignment mechanism that can enforce and
  evidence parent-repository read isolation.
- Explicitly invoke and complete the live Codex-to-Claude Code compiled-prompt
  and TORC smoke runs under that boundary.

Until those items pass, P1a does not authorize P1b execution. Credential
scanning remains documented as best-effort rather than proof of secret absence.
