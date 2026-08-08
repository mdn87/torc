# P1b Control Preflight

Status: passed; no comparative run started

Date: 2026-08-08

The frozen series manifest validates against the version 1 experiment-manifest
schema. The complete automated suite passed with 64 tests, and Ruff reported no
findings.

Native WSL2 preflight calls confirmed the exact installed harness versions and
accepted the frozen model controls:

| Harness | Version | Frozen controls | Result |
|---|---|---|---|
| Codex | `codex-cli 0.147.0` | `gpt-5.6-sol`, effort `high`, tier `fast` | `CONTROL_OK` |
| Claude Code | `2.1.226 (Claude Code)` | `claude-opus-4-7`, effort `high` | `CONTROL_OK` |

The Codex preflight reported the pinned model and reasoning effort while running
read-only; the service-tier override was accepted without configuration error.
The Claude preflight used safe mode, an empty strict MCP configuration, only the
`Read` tool, and no session persistence. These were minimal availability checks,
not experiment stages, and created no P1b run artifact.
