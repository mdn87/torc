# PR #25 assessment: reproducibility bundle

Scripts, raw results and cross-review records that support
[`docs/pr-25-receiver-fitted-carry-assessment.md`](../../pr-25-receiver-fitted-carry-assessment.md).
The subject is the P5 receiver-fitted carry at commit `a056c61be4dddce8a71fd9cb31f585b70a3b510d`
(branch `agent/p5-receiver-shaped-carry`). Nothing here is part of the `torc` package or its test suite.

## Environment

| | |
|---|---|
| OS | macOS 26.6.2 (build 25G83), arm64 |
| Python | CPython 3.14.4, SQLite 3.53.2 |
| Libraries seen | jsonschema 4.26.0, PyYAML 6.0.3, pytest 9.1.1 (mutation driver only), ruff 0.16.3 (lint check only) |
| Interpreter caveat | The default `python3` on the host that produced this bundle is another project's virtualenv. TORC is not installed in it, so every command sets `PYTHONPATH=src` and runs from the repository root. |

## Conventions

Every command below is run from the repository root (the directory that contains `pyproject.toml`):

```bash
cd <torc root>
export PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1
SCRATCH="$(mktemp -d)"     # any directory outside the repository
```

- No script writes inside the repository. State directories, work copies and generated results go under
  `$SCRATCH`. `PYTHONDONTWRITEBYTECODE=1` keeps `__pycache__` out of the tree.
- `scripts/replay.py` (and the two scripts that import it) and `scripts/scaling/probe.py` find
  `examples/p5-dropped-work` through the current directory, so they must be started from the repository root.
- Revision identifiers (`revision-` plus 32 hex digits) are random per run, so any output that prints one
  differs between runs on those lines. Timings in the scaling results are machine dependent.

## Layout

```text
docs/evidence/pr-25-assessment/
  README.md                         this index
  ruff.toml                         keeps scripts/ out of the repository lint run (see the last section)
  scripts/
    replay.py                       fixture replay (also imported by the next two scripts)
    rank_sweep.py                   carry_limit sweep for the small receiver
    adjudicate_codex_findings.py    reproductions of CR-001, CR-002, CR-003
    review/                         independent-review probes (common.py + 7 probe_* + 4 repro_*)
    mutation/                       run_mutations.py, probe_scenarios.py, probe_missed.py
    scaling/                        probe.py, fit.py, compare.py
  results/
    replay-output.txt               stdout of scripts/replay.py
    rank-sweep-output.txt           stdout of scripts/rank_sweep.py
    adjudicate-output.txt           stdout of scripts/adjudicate_codex_findings.py
    mutation-results.json           output of one full run of run_mutations.py
    scaling-results.json            output of one full run of scaling/probe.py
    cross-review/                   findings and result records of three cross-review runs
    fusion/                         the panel prompt, the panel configuration, and the judge's analysis
    roundtable/                     the shared-document records of the two roundtable sessions
  v1-assessment.md                  version 1 of the assessment, as it stood before the review campaign
```

## 1. Fixture replay, budget sweep, finding reproductions

| Script | What it does | Captured stdout |
|---|---|---|
| `scripts/replay.py` | Replays the `examples/p5-dropped-work` fixture (create plus three checkpoints), prints the P5 carry for the small and large receiver descriptors, compares it with the P0 compiler and the P1 compiled-prompt shape from the same head, finds the smallest receiver budget that compiles, then runs three review scenarios (S1 to S3). Also writes the rendered carries to its state root. | `results/replay-output.txt` |
| `scripts/rank_sweep.py` | Sweeps the small receiver's `carry_limit` over 55, 68, 69, 70, 83, 84 and 100 and prints which optional sections are included and omitted. | `results/rank-sweep-output.txt` |
| `scripts/adjudicate_codex_findings.py` | Reproduces three findings of the `codex-sol` cross-review (CR-001, CR-002, CR-003) against the P5 carry. | `results/adjudicate-output.txt` |
| `scripts/round2_findings.py` | Reproduces the two round-2 attack findings against version 2: a `rollback_applied`-labeled checkpoint through the Python API poisons the lineage (later checkpoints and carries are refused), and the handoff reconstruction template delivers optional head state in full while the fitted projection omits it. Same invocation shape as `replay.py`. | `results/round2-findings-output.txt` |

```bash
python3 docs/evidence/pr-25-assessment/scripts/replay.py "$SCRATCH/replay"
python3 docs/evidence/pr-25-assessment/scripts/rank_sweep.py "$SCRATCH/rank"
python3 docs/evidence/pr-25-assessment/scripts/adjudicate_codex_findings.py "$SCRATCH/adjudicate"
```

Each takes one argument, a scratch state root that it creates. Status on `a056c61`: all three ran cleanly
(exit 0, empty stderr). Each was run twice: `rank-sweep-output.txt` was byte-identical between runs;
`replay-output.txt` (lines 5 and 85) and `adjudicate-output.txt` (line 2) differed only in revision
identifiers. The rendered carry files that `replay.py` writes (`carry-receiver-*.json.md`) matched the
review-session run once those identifiers were masked.

## 2. Independent-review probes (`scripts/review/`)

`common.py` holds shared builders and is not run on its own. The other eleven scripts take no arguments and
build throw-away stores in a `tempfile.TemporaryDirectory()` (set `TMPDIR="$SCRATCH"` to redirect it).

```bash
python3 docs/evidence/pr-25-assessment/scripts/review/probe_budget_fitting.py
python3 docs/evidence/pr-25-assessment/scripts/review/probe_changes_since_edges.py
python3 docs/evidence/pr-25-assessment/scripts/review/probe_handoff_provenance.py
python3 docs/evidence/pr-25-assessment/scripts/review/probe_partial_fit.py
python3 docs/evidence/pr-25-assessment/scripts/review/probe_resolution_cycles.py
python3 docs/evidence/pr-25-assessment/scripts/review/probe_rollback_and_branch.py
python3 docs/evidence/pr-25-assessment/scripts/review/probe_verify_ancestors.py
python3 docs/evidence/pr-25-assessment/scripts/review/repro_changes_since_stale_disposition.py
python3 docs/evidence/pr-25-assessment/scripts/review/repro_handoff_prepare_not_atomic.py
python3 docs/evidence/pr-25-assessment/scripts/review/repro_section_id_shift.py
python3 docs/evidence/pr-25-assessment/scripts/review/repro_self_model_revised_identical.py
```

| Script | Subject (from its docstring) | Ran on `a056c61` | Stdout lines |
|---|---|---|---|
| `probe_budget_fitting.py` | Budget derivation and the item-level fitting loop, including the characters unit. | yes, exit 0 | 29 |
| `probe_changes_since_edges.py` | `changes-since-receiver` edges: a bearer that never authored, and the acceptance role copy. | yes, exit 0 | 11 |
| `probe_handoff_provenance.py` | Self-model provenance across `handoff_accepted` and `rollback_applied`, and the observer flag. | yes, exit 0 | 43 |
| `probe_partial_fit.py` | Item-level fitting under tight words and characters budgets. | yes, exit 0 | 8 |
| `probe_resolution_cycles.py` | Resolution semantics across repeated drop/restore cycles, and transaction atomicity. | yes, exit 0 | 11 |
| `probe_rollback_and_branch.py` | Three probes that matched the spec's letter: rollback to a dropping revision, branch root attribution, branch source counted as author. | yes, exit 0 | 20 |
| `probe_verify_ancestors.py` | Whether a `p5-1` projection can cite a revision it should not, under `verify`'s ancestor allowance. | yes, exit 0 | 4 |
| `repro_changes_since_stale_disposition.py` | `changes_since_substrate` reports a stale resolution instead of the current removal (scenarios A and B). | yes, exit 0 | 37 |
| `repro_handoff_prepare_not_atomic.py` | A handoff carry that cannot fit leaves a fit decision and a registered descriptor behind. | yes, exit 0 | 5 |
| `repro_section_id_shift.py` | `unaccounted-*` section ids are list positions, so they shift when an older drop is resolved. | yes, exit 0 | 3 |
| `repro_self_model_revised_identical.py` | Self-model authorship follows a content diff, not the `self_model_revised` event. | yes, exit 0 | 17 |

All eleven wrote nothing to stderr. Output of the three shortest, as captured:

```text
$ python3 docs/evidence/pr-25-assessment/scripts/review/probe_verify_ancestors.py
(a) p5 cites ancestor         -> []
(b) p5 cites later revision   -> [('projection_source_ref_invalid', 'p-later')]
(c) p5 on child cites parent  -> [('projection_source_ref_invalid', 'p-parent')]
(d) p0 cites ancestor         -> [('projection_source_ref_invalid', 'p-later'), ('projection_source_ref_invalid', 'p-p0')]

$ python3 docs/evidence/pr-25-assessment/scripts/review/repro_section_id_shift.py
carry 1: {'unaccounted-open_work-2': 'B', 'unaccounted-open_work-1': 'A'}
carry 2 (after resolving A, no new drops): {'unaccounted-open_work-1': 'B'}
`unaccounted-open_work-1` named A, now names B.

$ python3 docs/evidence/pr-25-assessment/scripts/review/repro_handoff_prepare_not_atomic.py
before: {'fit_decisions': 0, 'projections': 0, 'activations': 1, 'handoffs': 0, 'substrates': 1}
raised: required continuity needs 32 words but the receiver budget is 10
after:  {'fit_decisions': 1, 'projections': 0, 'activations': 1, 'handoffs': 0, 'substrates': 2}
verify still valid: True
EXPECTED (spec): fit_decisions unchanged (0), nothing stored; ACTUAL fit_decisions = 1 and 'tiny' stays registered
```

## 3. Mutation analysis (`scripts/mutation/`)

`run_mutations.py` applies each of 24 source mutations (ids H1 to H10, P1 to P9, V1, V2, O1, O2, S1) to a
copy of a pristine checkout, runs `pytest` in the copy and reports `CAUGHT` (the suite fails) or `MISSED`
(all tests still pass). `CTRL` is the unmutated control copy, so its `MISSED` verdict only means the suite
passes unmodified. `MISSED` requires exactly 265 passing tests, the size of the suite at `a056c61`.
`probe_scenarios.py` holds behaviour probes for scenarios the suite does not cover; `probe_missed.py` runs
it against the pristine tree and against each of the seven mutants the suite missed, and prints every probe
whose result differs.

The driver never touches the repository. It needs a scratch directory, passed as `MUTATION_SCRATCH`,
that holds `pristine/` (a copy of the checkout under test; `git archive HEAD` exports the committed
tree). It writes `work-*/` copies and `results.json` there.

```bash
export MUTATION_SCRATCH="$SCRATCH/mutation"
mkdir -p "$MUTATION_SCRATCH/pristine"
git archive HEAD | tar -x -C "$MUTATION_SCRATCH/pristine"

# control plus 24 mutants, about 2 minutes (3 to 4 s per copy); ids select a subset and the output
# is then written to results.partial.json
python3 docs/evidence/pr-25-assessment/scripts/mutation/run_mutations.py
python3 docs/evidence/pr-25-assessment/scripts/mutation/run_mutations.py CTRL H1

# behaviour probe for the seven mutants the suite missed (H5 H6 H10 P5 P9 V1 V2), about 2 s
python3 docs/evidence/pr-25-assessment/scripts/mutation/probe_missed.py

# the scenario probe on its own: arguments are a tree root and its examples directory
python3 docs/evidence/pr-25-assessment/scripts/mutation/probe_scenarios.py . examples
```

`results/mutation-results.json` is the recorded output of the full run: the control passes 265 tests;
17 of the 24 mutants are `CAUGHT` and 7 are `MISSED` (H5, H6, H10, P5, P9, V1, V2).

Status for this bundle: all three scripts pass `py_compile`. `probe_scenarios.py` ran against this checkout
and matched the review-session output (revision identifiers masked). `probe_missed.py` ran (exit 0) and
reported a behaviour difference for all seven mutants. `run_mutations.py` was smoke-run for `CTRL H1` only
(control 265 passed; H1 failed `tests/test_carry.py::test_rollback_accounts_for_what_it_removes`); the full
25-copy run was not repeated.

## 4. Scaling probe (`scripts/scaling/`)

`probe.py` builds synthetic lineages (series `drops`: N = 25, 100, 400, 1600 revisions with unresolved
removals; series `resolved`: N = 400, 1600 with a `completed` resolution per removal), then times
checkpoint, carry for the large and small receivers, status and `verify_store` on pristine copies of each
store, 5 repetitions each. It only calls TORC; nothing is patched. `fit.py` fits constant, linear and
quadratic models to the median timings; `compare.py` checks that the structural fields of two result files
match exactly and prints timing deltas.

```bash
# full protocol, about 5 minutes; writes $SCRATCH/scaling/results.json and $SCRATCH/scaling/state/
python3 docs/evidence/pr-25-assessment/scripts/scaling/probe.py --out-dir "$SCRATCH/scaling"

# pilot (note the "=" in --tag, the value starts with an underscore)
python3 docs/evidence/pr-25-assessment/scripts/scaling/probe.py --out-dir "$SCRATCH/scaling" --ns 25,100 --resolved-ns 100 --reps 2 --tag=_pilot

# model fit on the recorded run
python3 docs/evidence/pr-25-assessment/scripts/scaling/fit.py docs/evidence/pr-25-assessment/results/scaling-results.json

# recorded run against a fresh one: structure must match exactly, timings will differ
python3 docs/evidence/pr-25-assessment/scripts/scaling/compare.py docs/evidence/pr-25-assessment/results/scaling-results.json "$SCRATCH/scaling/results.json"
```

`results/scaling-results.json` is one full run (Python 3.14.4, SQLite 3.53.2, macOS arm64, 12 CPUs, 5
repetitions, no failures). Timings are wall-clock on that machine and will not reproduce exactly. The
`env.torc_module` path was normalised to `<torc-root>` (see the last section); a fresh run records the
absolute path.

Status for this bundle: all three scripts pass `py_compile` and `probe.py --help` works. The pilot command
above ran in a few seconds with every sanity check true. `fit.py` ran on the recorded results and matched
the review-session output. `compare.py` ran on the recorded file against that fresh pilot: 0 structural or
sanity mismatches for N = 25 and 100, and median timings within 18% of the recorded run. The full run was
not repeated.

## 5. Cross-review records (`results/cross-review/`)

| Route | Model | Run id | Findings | Findings file | Result file |
|---|---|---|---|---|---|
| `codex-sol` | `gpt-5.6-sol` | `20261008-060757-cross-review` | 8 (CR-001 to CR-008) | `findings-codex-sol-20261008-060757.jsonl` | `result-codex-sol-20261008-060757.json` |
| `codex-astra` | `gpt-6-astra` | `20261008-060918-cross-review` | 8 (F1 to F8) | `findings-codex-astra-20261008-060918.jsonl` | `result-codex-astra-20261008-060918.json` |
| `claude-opus` | `opus` (resolved to `claude-opus-5`) | `20261008-061413-cross-review` | 23 (CR-001 to CR-023) | `findings-claude-opus-20261008-061413.jsonl` | `result-claude-opus-20261008-061413.json` |
| `codex-astra` (attack round 1 on version 2) | `gpt-6-astra` | `20261008-063145-cross-review` | 6 (AR2-01 to AR2-06) | `findings-codex-astra-attack1-20261008-063145.jsonl` | `result-codex-astra-attack1-20261008-063145.json` |
| `codex-astra` (attack round 2) | `gpt-6-astra` | `20261008-063954-cross-review` | 2 (R2-01, R2-02) | `findings-codex-astra-attack2-20261008-063954.jsonl` | `result-codex-astra-attack2-20261008-063954.json` |
| `codex-astra` (attack round 3) | `gpt-6-astra` | `20261008-064903-cross-review` | 2 (R3-1, R3-2) | `findings-codex-astra-attack3-20261008-064903.jsonl` | `result-codex-astra-attack3-20261008-064903.json` |
| `codex-astra` (attack round 4, convergence check) | `gpt-6-astra` | `20261008-065444-cross-review` | 1 (R4-01, "no new material weakness") | `findings-codex-astra-attack4-20261008-065444.jsonl` | `result-codex-astra-attack4-20261008-065444.json` |

All runs: mode `adversarial`, effort `high`, subject kind `implementation`, status `succeeded`. The files
are copies of `findings.jsonl` and `result.json` from the autowork run directories
(`~/.local/state/lugos/autowork/runs/<run id>/`). The review packets, adjudications, reviewer responses and
logs were not copied and stay in those directories. The `codex-sol` and `claude-opus` findings were
auto-accepted by Autowork's guardrail; the `codex-astra` findings were auto-rejected as
`vague_no_evidence` because their evidence field is a list, and were adjudicated on content by the
orchestrator (see the assessment's "Review provenance" section). Each Codex reviewer numbers its own
findings from 1, so `CR-001` means a different finding in the `codex-sol` and `claude-opus` files.

## 6. Fusion panel (`results/fusion/`)

One `python -m autowork.main fusion-ask --return-mode analysis` run on 2026-10-08. `verdict-prompt.md` is
the question put to every panelist; `autowork-fusion.toml` is the panel configuration (Codex `gpt-6-sol`
at high effort through `codex exec`, Claude `fable` and `opus` through `claude -p`, judge Claude `sonnet`);
`verdict-analysis.json` is the judge's structured comparison (consensus, disagreements, partial coverage,
unique insights, blind spots). The one-shot command does not persist the panelists' raw answers.

## 7. Roundtable sessions (`results/roundtable/`)

`pr25-v2-review.md` is the converged shared document of the `dimensional-review` session (reviewers
`codex` and `claude`, synthesizer `orchestrator`): the CONTROL block, each reviewer's committed findings
with run provenance, the synthesis rationale, and version 2 as the ARTIFACT. `pr25-v2-refine.md` is the
`adversarial-refine` session that attacked version 2 (attacker `codex`, defender `claude`): three attack
rounds (6, 2, and 2 findings), each answered by a rebuttal carrying the revised artifact; it reached its
six-move cap and was closed with a note pointing at `pr25-v2-refine-b.md`, where attack round 4 reported
no new material weakness and the defender finalized (status `converged`). All were driven with
`python -m roundtable.cli` from the parent Lugos checkout; attacker moves were produced by the Autowork
runs above and relayed into the documents by the orchestrator.

## Edits relative to the review-session originals

All other scripts and result files are byte-identical to the originals.

| File | Change | Why |
|---|---|---|
| `scripts/scaling/probe.py` | Output goes to a required `--out-dir` instead of next to the script; `REPO` is the current directory instead of a hard-coded absolute path; docstring usage updated. | The old defaults would write into the repository and hard-coded a personal path. |
| `scripts/mutation/run_mutations.py` | `BASE` (pristine copy, work copies, results) comes from `MUTATION_SCRATCH` instead of the script's directory; added `import os`; docstring usage. | The pristine copy and work directories must stay out of the repository. |
| `scripts/mutation/probe_missed.py` | Sibling scripts are found through the script's directory; pristine and work directories through `run_mutations.BASE`. | Follows from the change above. |
| `results/scaling-results.json` | `env.torc_module`: absolute checkout path replaced by `<torc-root>`. | The repository's host-identifiers CI check rejects personal paths. |
| `results/cross-review/result-*.json` | `packet_path`, `stats_path`: absolute home prefix replaced by `$HOME`. | Same check. |
| `ruff.toml` (added) | `exclude = ["scripts"]` for this directory tree. | CI runs `ruff check .`. Under the repository rules the scripts have 176 findings (mostly E501 line length); they are kept as run rather than reformatted. |
