# Execution goals for the continuation measurement plan

Status: execution authorized by the operator on 2026-10-21. The $2 paid-spend
ceiling remains unchanged. Prefer subscription execution. The reviewed maximum
is 34 experimental assignments / 68 CLI starts; development assignments are
tracked separately and must not be presented as experimental observations.

## Goals and acceptance

1. **Recover real continuation fixtures.** Establish source history, exact starting
   tree, unresolved requirement, permitted files, independent acceptance checks
   and development exposure. The effectiveness target is eight tasks across three
   repositories; candidate counts alone do not satisfy it.
2. **Make accounting and analysis executable.** Autowork must retain every worker
   and checker start, streamed usage and terminal/partial outcomes. TORC must
   analyze the new endpoint under a separate version without changing the old
   study. Offline tests and two bounded live qualification assignments must pass
   before any comparison is admitted.
3. **Produce an honest measured result.** Run the frozen comparison, retain every
   outcome, independently score candidates, and publish input, cache categories,
   estimated cost, elapsed time and acceptance. A regression or inconclusive
   result still completes the measurement goal; a savings claim is not required.

## Initial fixture inventory and operator decision

The initial inventory inspected 326 retained local Autowork request records,
38 top-level Claude interruption boundaries on the workstation, seven Codex
boundaries there, and 34 interruption boundaries across 585 transcripts on an
inventoried peer. It also searched explicit WIP/checkpoint commits in 66 local
repositories. These sources overlap; the counts are not independent task counts.

Most inspected boundaries concern desktop actions, deployments, credentials,
approval tests or completed conversational work. WIP labels and synthetic
canaries do not by themselves establish eligible continuations. Missing task
history or missing interrupted tree also prevents admission.

One strong candidate is the Cormac PowerShell quotation fix:

- Natural transcript interruption: `2026-10-15T06:18:40.431Z`; private prefix
  identity `37fc0dfc9e1a236e`.
- Retained unfinished checkpoint: `b32aaae627d8181c1d182473744ecf233941754c`.
- Later reference implementation: `915b8003718a0a457fdecba5396fcc95c536ad77`,
  reserved for scorer qualification and unavailable to continuation workers.
- The pre-interruption transcript records creation of the new quote tests;
  the checkpoint explicitly states that implementation remains pending.
- Required behavior is local, deterministic command parsing. It can be changed
  through literal source files without a child shell or external service.
- Qualification must still demonstrate the unfinished checkpoint fails the
  relevant behavior and the reference passes, before admitting the fixture.

The eight-task cohort is not established. The operator explicitly selected:
**keep the eight-real-task requirement and collect more cases first**. Do not
substitute a smaller pilot, seeded tasks, conversational interruptions or arbitrary
historical commit cut points. Continue collecting and assessing real interrupted
work, preserving exact starting trees and source history before further development.

Stages 2–4 wait for eight eligible tasks across at least three repositories.
Candidate discovery is not admission; qualification still needs source custody,
recoverable unfinished state and independently testable acceptance criteria.
Record development exposure, reject duplicates from the same underlying task,
and keep solutions unavailable to future continuation workers.

## Collection results and remaining evidence

The additional collection pass inspected 38 owner records on the peer, 517
archived handoff notes locally, and two transcripts on the utility host. The
utility transcripts contained no interruption boundaries. Archived notes mostly
describe completed milestones or operational work; a planned next feature does
not establish an interrupted implementation.

Three candidate starting states are now preserved privately: one Cormac
checkpoint and two AETA partial runs. **Zero fixtures are admitted.** These are
three candidate records in two repositories, not three qualified independent
tasks. Their existence does not reduce the required cohort to three.

| Candidate | Preserved evidence | Still needed |
|---|---|---|
| Cormac PowerShell quotation fix | Exact checkpoint archive; pre-interruption transcript prefix identity; later reference commit | Bind the checkpoint to the transcript's final writes; qualify independent behavioral acceptance and record exposure |
| AETA concept-search partial run `20260808-230756-286345a7f230` | Base `2a71fb3ad12be2a1d9795aa199520818eeb27de4`, tracked patch, eight changed source/test files including the new untracked module, owner records | Original request and usable pre-stop history; concrete unfinished requirement; acceptance and independence from the other AETA case |
| AETA quality partial run `20260809-052506-7c1f44141c74` | Base `481f3101c51d2352e7e0a648a849a35aa19065f9`, tracked patch, three changed source files, owner records | Original request and usable pre-stop history; concrete unfinished requirement; acceptance and independence from the other AETA case |

For both AETA candidates, reconstruction of Autowork's inventory digest exactly
matches the retained stop-time digest, including the untracked module where
present. Transfer hashes were checked for 25 artifacts, and all three Git base
trees were archived locally. This establishes recoverable source custody; it
does not establish task completion criteria or effectiveness evidence.

Two other AETA runs were held for policy violations after their recorded tests
passed (63 and 13 tests). They are not admitted as unfinished coding tasks merely
because their owner status was held. Local synthetic canaries, approval and
desktop tests, old TORC diagnostic tasks, and duplicate interruptions are also
excluded. The Lugos and MCP WIP snapshots remain leads only: their labels do not
establish original task history and an unresolved requirement.

The AETA source-history search found a later branch inventory, not the original
assignments. Neither corresponding child transcript was found in the retained
session locations inspected. Do not reconstruct a purported original prompt
from a solution diff or substitute a task hash for its missing contents.

Private collection receipts and inventories are retained under
`.torc/fixture-intake/2026-10-21/` and `.torc/takeover-evidence/`; raw histories,
source archives and local machine paths are not publication artifacts.

## Collection procedure before restarting the study

Continue collecting naturally stopped code work until eight distinct tasks from
at least three repositories satisfy the manifest requirements. A failed worker,
genuine context-limit handoff or user pause may supply a boundary. Do not create
pauses or extra coding assignments solely to manufacture eight observations.

For each candidate, preserve these items before the original task resumes:

1. The exact user requirement and authorized scope, with the existing task/run
   identity and actual reason/time work stopped.
2. A recoverable starting tree: base commit, binary tracked patch, and any
   relevant untracked source files. Hash and retain all of them; a commit hash
   alone is insufficient for a dirty worktree.
3. The pre-stop history prefix with byte count and digest. Keep private source
   custody separate from the sanitized material delivered to workers. Exclude
   credentials, hidden reasoning, and later solution or verification content.
4. The unresolved behavior, literal editable files, dependencies and independent
   acceptance checks. Record exposure and related cases so one underlying task
   cannot inflate the task count.

Root can perform inventory, preservation, deduplication and eligibility review
without model calls. Recovering missing historical requests requires a retained
source, not an operator guess. When a source cannot be recovered, leave that
candidate unadmitted and collect a different natural case. This procedure does
not install a watcher or claim background collection is running.

The next admission decision is mechanical: eight complete candidate records,
three or more repositories, no excluded diagnostic/development tasks, and tasks
that fit the installed Windows file-edit lane. Scorer qualification follows
fixture feasibility; accounting development and experiment calls remain deferred.

## Owner work

- **TORC:** fixture manifest and source custody, frozen compiled/capsule prompts,
  independent scoring, versioned consumer and analyzer, result publication.
- **Autowork:** command/preflight stream contract, durable per-call capture through
  completion checking and termination, ledger export and bounded execution.
- **Root:** integrate and validate both owners' changes, qualify the experiment,
  admit only the declared calls and preserve the old cohort.

No API-auth route or billing-account integration is needed for this feasibility
run. Any later billed cohort needs its own qualified owner route and appropriate
reporting access; estimated list-price dollars remain estimates.
