# Reproducing retained reports after the runtime changes

The three retained continuation reports record exact historical source hashes.
Use the archival entrypoint to reproduce those reports from a current checkout:

```sh
python -m torc.retained_replay offline --repository . --output-dir /tmp/torc-offline
python -m torc.retained_replay comparison --repository . --output-dir /tmp/torc-comparison
python -m torc.retained_replay contexts --repository . --output-dir /tmp/torc-contexts
```

Run with the project's development environment, where `torc` is importable.
An editable install or `PYTHONPATH=src` is sufficient. On Windows use the project
virtual environment's `Scripts/python.exe`, with suitable local output paths.
Use a fresh output directory for each independent run. JSON goes to stdout;
stderr identifies the historical source commit. The exact retained reports are:

- `docs/experiments/session-continuation-001/offline-report.json`
- `docs/experiments/session-continuation-001/comparison-report.json`
- `experiments/session-continuation-001/contexts-report.json`

The tool uses commit `45fae25a6db0ea393dd6e997ed51c575184cb1e4`, whose source
digests match those reports. It creates a temporary local shared clone with its
own refs, index, and detached working tree. Objects are read from the existing
local repository; no history is fetched, branch is switched in the source
checkout, or model is called. Checkout hooks and submodule recursion are disabled.
Full local Git history is required, including the older task commits used by the
historical workload scripts. Missing history fails explicitly.

Before execution, the recorded source hashes are verified against the historical
snapshot. Current copies of the retained reports, source scripts, fixtures, and
task briefings must still match the pinned originals. Changed historical evidence
fails verification. Current production modules may evolve; their newer bytes are
never relabeled with an old hash. The original reports and replay scripts are
unchanged. Python and third-party dependencies come from the invoking development
environment; this is a pinned source replay, not a containerized environment.

## Callable interface

The context manager also supports historical preparation, analysis, and verification
using the original command arguments:

```python
from pathlib import Path
from torc.retained_replay import retained_runtime

with retained_runtime(Path(".")) as runtime:
    result = runtime.replay("contexts", Path("/tmp/torc-contexts"))
    # result.stdout contains the original JSON report bytes.
    # runtime.run("contexts", ["verify", "--root", absolute_task_directory,
    #                          "--expected-manifest-id", retained_manifest_id])
```

Use absolute file paths in `runtime.run` arguments: its working directory is the
temporary historical checkout. The snapshot exists only within the context manager.

## Current-runtime checks remain separate

Calling the original scripts directly still exercises the **current** implementation.
Their source hashes honestly describe that implementation, so the resulting reports
are not expected to equal an older retained source manifest. Current-runtime tests
run each replay twice, require identical outputs, verify published artifact hashes,
check source digests against current files, and check the expected behavior and
public context-verification command. Existing context, usage, handoff, and projection
tests also continue using current production code.

Only the assertions claiming exact historical reproduction use the archival
entrypoint. This keeps both promises testable: historical evidence remains
reproducible, and changes to the current implementation remain covered.

## Why the old assertions failed

Commit `c20487c` added Tuan correlation handling to `src/torc/store.py`. Its source
hash changed while the retained reports correctly kept their original hash. That
changed the enclosing content-addressed report, plan, and manifest identifiers.
The prior tests ran the current source but compared its provenance to the historical
source, so legitimate runtime evolution made them fail even when behavior matched.
The archival source pin resolves that mismatch without replacing or weakening the
retained evidence.
