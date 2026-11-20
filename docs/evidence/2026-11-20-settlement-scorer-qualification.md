# Tableforge browser scoring qualified

All eight frozen tasks now have an independent scorer that distinguished the historical
fix from the interrupted version. The first seven pairs ran on Windows. The eighth ran
in an Autowork-owned Linux job on the same Windows machine. The remaining prerequisite
for the comparison is per-call Claude usage accounting and paired analysis. Benchmark
runs, human judgments on benchmark outputs, experimental model calls and paid spend
are all zero. [Earlier seven pairs](2026-11-20-continuation-scorer-preparation.md)

## What the browser saw

Both versions built successfully. Chromium ran the same three frozen Playwright tests
against each version's own game server.

| Browser test | Historical fix | Interrupted version |
|---|---|---|
| Two players open the board, make a move, and reload the first player's seat | Passed, including the current board after reload | Failed when the first page did not show that it had joined |
| The alternate board offers edge AC and omits edge BE | Passed | Failed when the player page did not show that it had joined |
| A wrong token is refused and a display token cannot take a player seat | Passed | Failed when the page did not show that the token was refused |

All three failures came from assertions in the frozen game test. A missing browser,
an incomplete run or a failure to connect to the test server cannot by itself reject
a candidate. The report binds the two candidate manifests, the source tree, the
scorer-only tests, the built files, the Linux dependencies, the browser and the
Autowork receipts. [Machine-readable results](2026-11-20-settlement-scorer-qualification.json)

## What the isolation check established

The test process exchanged data with a server it created on loopback. Loopback was
the only network interface in the job. The host listener on loopback refused its
connection, and an IPv4 listener reachable from outside the job was unreachable from
inside. The test process could read its own input. Its attempt to open the host's
private test file failed, and the runtime and input packet both refused write access.
Autowork recorded the end of the probe, both builds and both browser jobs. The
browser runtime used Playwright 1.64.1, Chromium 156.0.8078.4 and Node 26.13.0.
[Execution owner](https://github.com/mdn87/lugos/pull/746)

## Retained evidence

The first replay produced all six test outcomes. Its final summary failed because
Linux Git could not read a Windows worktree pointer. The raw results were retained.
A Linux-readable checkout verified the owner revision and produced a complete report.
A fresh installation from the pinned image and lockfile reproduced every test outcome.
The published JSON is the receipt from that fresh installation.

The private archive at `.torc/settlement-scorer-20261120/control-evidence.zip`
contains 903 entries, including the process receipts, Playwright output, screenshots,
traces and compiled files from the published run. Its SHA-256 is
`5f9c21d14b58ca64aae32a459b6b4dc3c31383410f0348e1ce01f3d43193c21a`.
The SHA-256 of the published JSON is
`3a5b4d9083bdb62fbf09a63a1705511f497a86e9f483ad953e7bfb592698d689`.

## Reproduce the browser controls

Run from TORC on Linux with Python 3.12, bubblewrap and the private November 20
inputs. Set `TABLEFORGE` and `AUTOWORK` to the two source checkouts. The
Autowork checkout must be readable by Linux Git and contain the owner commit in the
receipt. Choose fresh directories for `SETUP`, `SCRATCH` and `EVIDENCE`. Use a
native Linux filesystem for setup and scratch. Set `NODE` to a Linux Node 22 or
later executable, and `WITNESS` to a non-loopback IPv4 address on this host.

Setup uses Docker to extract the pinned image. It downloads the locked dependencies
using trusted package manifests with lifecycle scripts disabled. The builds and tests
then run under Autowork with private loopback.

```bash
python3.12 experiments/continuation-review/prepare_settlement_runtime.py \
  --destination "$SETUP" --tableforge "$TABLEFORGE" --node "$NODE"

case_name=tableforge-settlement-renderer
PYTHONPATH=src python3.12 experiments/continuation-review/settlement_qualification.py \
  --owner "$AUTOWORK" --runtime "$SETUP/root" --dependencies "$SETUP/dependencies" \
  --prepared ".torc/stage2-20261120/sealed/$case_name" --controls .torc/q20f/taset \
  --normalizations ".torc/fixture-intake/2026-11-20/$case_name/feasibility/evaluation-line-ending-normalization.json" \
  --scratch "$SCRATCH" --evidence "$EVIDENCE" --outside-witness-address "$WITNESS"
```
