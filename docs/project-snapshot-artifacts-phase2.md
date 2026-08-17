# Project Snapshot Artifacts Phase 2

Status: implemented locally; final verification pending.

## Outcome

Phase 2 adds one narrow producer seam and one richer consumer. An
operator-selected Scribe command receives an immutable Evidence Bundle and
returns a candidate Project Snapshot. TORC validates that candidate with the
unchanged Phase 1 rules. Separately, TORC revalidates the accepted current
snapshot, its Evidence Bundle, and its Acceptance Receipt before Mission
Control renders them as a disposable read-only projection.

The scope record is
`docs/project-snapshot-artifacts-phase2-scope-envelope.json`. The authoritative
implementation host is `macos-primary`; the same contracts target both macOS hosts
and both Windows hosts in the Lugos inventory.

## Chosen boundaries

The producer adapter executes one explicit argv vector without a shell. It
writes one compact UTF-8 Evidence Bundle JSON object plus a newline to stdin.
The command must write exactly one Project Snapshot JSON object to stdout.
Diagnostic text belongs on stderr. TORC rejects timeouts, nonzero exits,
non-JSON output, non-object JSON, and candidates that fail the existing
validator. The adapter neither chooses a provider nor changes generator
provenance.

This command boundary was selected over an in-core provider SDK because it
keeps credentials, provider routing, prompts, and model-specific behavior
outside artifact identity and acceptance. A passive file-drop adapter was
also considered, but it would not prove which Evidence Bundle the producer
received. The explicit stdin boundary makes that input observable in a focused
contract test while remaining usable by a model wrapper, local script, or
human-authored tool.

The consumer boundary is a new TORC `artifact view` command. It resolves only
the accepted `current.ref`, loads its Evidence Bundle and accepted receipt,
reruns their Phase 1 integrity and semantic checks, checks all cross-record
identities, and then emits a noncanonical envelope marked `derived: true`,
`canonical: false`, and `trusted: true`. Invalid stored data fails closed and
produces no view.

Mission Control invokes that read command through a configured TORC binary.
It does not open the artifact store, duplicate canonical hashing, or call an
acceptance command. A server-side viewer-only GET route validates the envelope
fields the UI uses. The panel contains no form, editable field, mutation verb,
or writeback control.

Direct filesystem reading in Mission Control was rejected because it would
create a second integrity implementation. Publishing a new Lugos MCP tool was
also considered, but that would require a third repository and add no authority
or portability benefit to this local read boundary. The configured TORC CLI is
the smallest existing cross-platform executable seam.

## Contract details

`artifact produce` takes `--evidence`, an optional `--store` or `--out`, an
optional timeout, and the producer argv after `--`. A successful command
returns the candidate identity and path. Acceptance remains a separate
operator action through `artifact accept`; producing a candidate cannot
advance `current.ref`.

`artifact view` takes only `--store` and `--json`. Its output contains the full
Project Snapshot, Evidence Bundle, and accepted Acceptance Receipt so the
consumer can show source identity and validation results without further store
access. The envelope itself is derived transport data, not a fourth immutable
record and not a new authority surface.

Mission Control uses `LUGOS_TORC_BIN` and
`LUGOS_TORC_ARTIFACT_STORE`. An empty artifact-store setting disables the
surface. The server passes the configured store as a single argv element, so
spaces and Windows paths require no shell quoting rules.

## Platform lanes

The shared behavior is Python 3.11+ plus Node.js 22+, direct argv execution,
UTF-8 JSON, and portable content-addressed files. POSIX examples may name
`python3` and `torc`; PowerShell examples may name `py` and `torc.exe`. The
protocol contains no shell syntax, path separator assumption, signal contract,
or executable shebang requirement. macOS is verified in this phase; Windows
gets contract coverage and a separately documented smoke command, not a claim
of execution on this host.

## Test-first milestones

1. Prove the command adapter receives the exact bundle, returns a validated
   candidate, and fails closed on invalid output.
2. Prove the read envelope is trusted only when the current artifact, bundle,
   receipt, and their references all validate.
3. Capture the production TORC envelope and prove Mission Control's Zod
   contract accepts it while rejecting untrusted or mismatched shapes.
4. Add the viewer-only route and panel, including acceptance checks, projects,
   claims, blockers, decisions, activity, conflicts, and unknowns.
5. Run repository suites and static checks, then a real producer-to-acceptance-
   to-view smoke flow. Commit each repository locally; do not push or change
   the Lugos parent pointer.
