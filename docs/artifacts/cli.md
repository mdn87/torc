# Project Snapshot CLI

Run from the TORC repository after `python -m pip install -e '.[dev]'`. The
examples use repository-relative paths so they work on macOS and Windows.

## Collect evidence

```bash
python -m torc artifact collect \
  --repository . \
  --config .lugos/project-snapshot.sources.yaml \
  --store .lugos/artifacts/project-snapshot \
  --json
```

PowerShell uses the same arguments on one line or backtick continuations. Use
`--out <evidence-directory>` instead of `--store` when only a bundle file is
needed at an explicit location.

The YAML manifest has `version`, a stable repository label, a recent-commit
limit, and explicit source entries:

```yaml
version: 1
repository: mdn87/torc
recent_commits: 10
sources:
  - id: readme
    path: README.md
    required: true
  - id: optional-status
    path: STATUS.md
    required: false
```

Missing required sources fail collection. Missing optional sources become
warnings. Absolute paths, traversal, Git internals, environment files, key and
credential paths, dependency trees, build output, virtual environments, and
the generated artifact store are excluded. Collection never broad-crawls the
repository.

## Validate and accept

An optional Phase 2 Scribe adapter can invoke any operator-selected local
executable that follows the provider-neutral stdio contract. Put the direct
argv after `--`; TORC does not invoke a shell:

```bash
python -m torc artifact produce \
  --evidence evidence-bundle.json \
  --out candidate.json \
  --timeout-seconds 120 \
  --json \
  -- scribe-wrapper --mode project-snapshot
```

The executable receives one compact Evidence Bundle JSON object on stdin and
must write exactly one candidate JSON object to stdout. It may write
diagnostics to stderr, but TORC does not copy those diagnostics into its error
payload. A nonzero exit, timeout, invalid JSON, or candidate-validation failure
returns nonzero and creates no candidate. Omit `--out` to write the validated
candidate and its Evidence Bundle into the selected `--store`. Producing never
accepts the candidate or changes `current.ref`.

PowerShell uses the same argv boundary, for example `-- py
scribe-wrapper.py`. No quoting convention is embedded in the protocol because
TORC passes each argument directly to the process.

Manual and produced candidates share the unchanged validation and acceptance
commands:

```bash
python -m torc artifact validate candidate.json \
  --evidence evidence-bundle.json \
  --json

python -m torc artifact accept candidate.json \
  --evidence evidence-bundle.json \
  --store .lugos/artifacts/project-snapshot \
  --json
```

Both commands return nonzero on failure. `validate` is read-only. `accept`
writes the Evidence Bundle, content-valid candidate, and receipt; it writes an
accepted copy and changes `current.ref` only when all checks pass.

## Inspect and render current

```bash
python -m torc artifact current \
  --store .lugos/artifacts/project-snapshot \
  --json

python -m torc artifact view \
  --store .lugos/artifacts/project-snapshot \
  --json

python -m torc artifact render \
  --artifact current \
  --store .lugos/artifacts/project-snapshot \
  --format html \
  --out .lugos/artifacts/project-snapshot/render/index.html \
  --json
```

The standalone HTML displays snapshot time, repository commits, project
status, claims, blockers, decisions, activity, conflicts, unknowns, evidence
provenance, and receipt checks. It contains no edit form, task mutation, or
writeback behavior. For an explicit artifact path, pass `--artifact <path>` and
either keep its accepted receipt in the selected store or add `--receipt
<path>`.

`artifact current` returns only accepted identities and status. `artifact
view` is the fail-closed consumer contract: it reloads and validates the
current Project Snapshot, Evidence Bundle, and accepted Acceptance Receipt,
checks their cross-record identities, and returns all three in a derived,
noncanonical, trusted envelope. Mission Control consumes this command; it does
not read the store or recompute content hashes independently.

## Storage and retention

Generated state is ignored by Git under
`.lugos/artifacts/project-snapshot/`. Schemas, fixtures, documentation, and the
source manifest are committed; runtime bundles, candidates, accepted copies,
receipts, `current.ref`, and HTML are not repository truth and are not
automatically committed.

Retain runtime stores as long as their audit trail is operationally useful.
Back them up as an atomic directory when needed. Do not edit content-addressed
JSON in place. Produce a new record instead. Pruning is an operator retention
decision; keep the current accepted artifact, its Evidence Bundle, and its
Acceptance Receipt together.

Mission Control's Phase 2 adapter calls `artifact view` through a configured
TORC binary and renders only its trusted envelope. The standalone renderer
remains useful for a portable file with no running dashboard.
