# Three-arm continuation diagnostic: October 21, 2026

The authorized diagnostic finished all six scheduled comparisons and both native
seeds. **2 of six comparisons passed the frozen acceptance gate.** This is a
small, amended apparatus diagnostic, with no supported savings or adoption claim.
The complete machine-readable summary is [diagnostic-results.json](diagnostic-results.json).

## Results

Input and cached-input counters below are separate reported fields; they must
not be added together. Native-fork increments subtract the explicit seed baseline.
Elapsed time covers admission through the original terminal disposition, including
owner preparation and scoring, but excludes gaps between trials and the first
model-free rescore. Seeds are reported separately in the JSON and counted once
in its observed whole-pilot totals.

| Workload | Arm | Frozen acceptance | Elapsed seconds | Reported input | Reported cached input | Reported output |
|---|---|---|---:|---:|---:|---:|
| `whole-task-usage` | `native_warm` | Fail | 236.5 | 487,865 | 437,120 | 13,334 |
| `whole-task-usage` | `compiled_prompt` | Scope hold; unscored | 290.5 | 646,945 | 586,752 | 16,057 |
| `whole-task-usage` | `torc_capsule` | Fail | 200.8 | 332,935 | 292,608 | 12,330 |
| `capsule-context` | `native_warm` | Fail | 146.1 | 635,797 | 568,064 | 9,414 |
| `capsule-context` | `compiled_prompt` | Pass | 145.7 | 578,622 | 525,312 | 8,904 |
| `capsule-context` | `torc_capsule` | Pass | 159.9 | 834,771 | 755,200 | 10,260 |

The accounting-task failures in the native and capsule arms were two exact
error-message assertions: both candidates rejected the tested invalid cases,
but used different wording. The native capsule-context candidate likewise
rejected the mismatched binding with different wording. The fixed tests were
not relaxed after seeing outputs. These results therefore establish strict
test outcomes, not three demonstrated failures of the underlying rejection
behavior, and do not justify ranking the arms.

The compiled-prompt accounting candidate failed the owner's scope gate because
its pytest run left untracked scratch files and links outside its one allowed
source path. It received no independent score and counts as unsuccessful. Its
candidate, original result and scope violations remain retained. No scratch
files were deleted to rescue it, and no replacement worker ran.

## Procedure corrections retained

1. The first scorer callback accidentally ran the whole historical repository
   suite instead of the qualified hidden-test command. Admissions paused, the
   original failed score was retained, and the same frozen candidate was scored
   with the correct command. This used zero new model calls and still failed
   the two assertions above. Later trials used the corrected command. The
   original and corrected runner hashes and score records remain in the archive.
2. The next worker's scope failure initially stopped the adapter because no
   score existed. Inspection proved terminal capture, process-tree absence,
   an unambiguous native session, no protected tracked-source change, and only
   contained pytest scratch paths outside the allowed module. An append-only
   disposition records an ordinary unsuccessful task, preserving the scope gate
   and every original artifact. A pinned procedure amendment allowed the
   remaining existing schedule to continue without scoring or replacing it.

These corrections make this an amended diagnostic, not an untouched preregistered
effectiveness study. They change no TORC authority, provider policy, candidate,
hidden-test content, task prompt or original admission budget.

## Resource and evidence reconciliation

- Eight admissions completed: two seeds and six comparisons; no pending worker,
  automatic retry, fallback or replacement. The ceiling was nine, with 600 seconds
  per worker. The unused ninth admission is not spent automatically.
- No paid API route was used. The operator's $2 ceiling was respected; no actual
  subscription dollar cost is inferred. Separate development dispatches are not
  treated as experimental observations.
- The original qualification root remains six of nine used, three remaining.
  It was neither copied nor reset to supply this comparative allowance.
- Execution used Codex 0.163.0, `gpt-5.6-sol` with medium effort, and the existing
  Autowork owner at `ffda6e1cf6810605f24cf96a638d82bcc00fdae1`. Comparative source
  was frozen at `17e4c0b8452a7cedc81c9f182b336ccaae7ee7c3`.
- The current scorer controls passed before admission. The separate
  [qualification report](scoring-qualification-report.json) retains all 74 old
  and new model-free process attempts, including failed controls.
- The private cohort export contains **9,236 hash-verified members**.
  Its SHA-256 is `22c47eb3b67b374cb6779269151c154b381f5fe6787895bd5e7173cbd64dbbfb`. It includes owner records, raw child
  output, frozen candidates, scores, procedure versions and corrections. Credentials
  and provider-native session state stay with the original execution owner.

Reported completion counters do not enumerate hidden provider retries or failed
requests. Input/cache overlap and actual API charges remain unknown. The public
observation packets omit raw commands, paths, arm-revealing content and owner
identifiers; private provenance binds them to the retained traces. Across scored
traces, 2 malformed JSONL lines remain retained rather than silently repaired.
Action times are absent and stay null. Operator active time and repeated-
investigation rates remain unknown; a repeated read is not classified as waste.

## Reproduction and next-study limits

An authorized holder of the private archive can reproduce the sanitized report
without launching a worker or executing candidate code:

```sh
PYTHONPATH=src python experiments/session-continuation-001/diagnostic_report.py \
  <private-owner-archive.zip> \
  --sha256 22c47eb3b67b374cb6779269151c154b381f5fe6787895bd5e7173cbd64dbbfb \
  --private-provenance <new-private-provenance.json> > diagnostic-results.json
```

The importer verifies the external archive pin and every member before consuming
it. Changing that pin or any member fails closed. Raw provenance belongs outside
the public repository.

No user decision remains for this completed diagnostic. A subsequent study should
resolve whether exact exception wording is a public requirement or a test artifact,
make the worker scratch-directory contract explicit, and freeze that revised
design before gathering new outcomes. Representative workloads, complete usage
coverage, Experiment B and adoption remain separate, unapproved follow-on work.
