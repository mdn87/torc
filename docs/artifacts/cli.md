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

Mission Control currently has a read-only TORC lineage contract but no project
snapshot contract. Phase 1 therefore uses this standalone renderer. A future
consumer should validate the same artifact and receipt schemas, resolve only
accepted current state, and remain read-only.
