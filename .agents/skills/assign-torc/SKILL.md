---
name: assign-torc
description: Assign, find, remove, take or pass a project torc in Dias when someone says “put the torc on this board,” names a Work Trail, or asks who holds the torc. Use for TORC lineage holders and Board assignments.
---

# Assign a torc

Act on the user's words. A Dias project Board follows one torc. Linked Work Trails open that Board. A session holds the actual TORC lease.

Use the TORC checkout's project Python (`.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on Unix) with `-m torc`. In a project installation this skill is under `<checkout>/.agents/skills/assign-torc`. An installed `torc` with `board --help` also works. Keep the operator's workspace as the working directory when resolving “here.” Read the JSON receipts yourself.

## Choose what the Board shows

- “Put the torc on this project.” Run `board assign --here --json`. The default **Project torc** belongs to that particular Board. Assignment can succeed before a session starts it.
- “Put Release review on the Atlas board.” Run `board assign --board "Atlas" --source "Release review" --json`. Use `board list --json` to see available names and exact IDs. If the user explicitly says to replace the current torc, add `--replace`. If replacement is necessary and their intent is unclear, name both torcs in one short question.
- “Show it on the Build trail.” Use `--trail "Build"` in place of `--board`. The adapter resolves its name, ID or full `namespace/id` through current Work Trails. If several match, ask which one using the choices in the response. If the trail has no single linked Board, ask which Board should follow the torc.
- “Remove the torc from Atlas.” Use `board remove --board Atlas --json`. This removes its display link.
- “Who holds this project's torc?” Use `board show --here --json` or the named Board/trail. Give the reported public name, short tag and lease time. A null source means the Board has no assignment. A source with a null holder means Dias has no current holder report to show. Only a verified canonical store can establish authority.
- “Let me drag it.” Open the local Dias Board and choose **Assign a torc**, or open `/?torc=assign` on the local Dias display. Drag the ring onto the Board. Tapping or focusing and pressing Enter on the ring and then the Board works too.

If the user names their current, real lineage before it appears in Dias, use its known state directory and lineage ID with `board offer --state-dir <directory> --lineage <id> --label "<public name>" --json`. Use the returned source ID to assign it. Use a public name the operator has supplied or clearly established. If the actual store or lineage is unknown, identify what is missing. Sample stores and research fixtures cannot identify an operator's lineage.

Use the confirmed Board name in your reply. When Dias is unavailable or the assignment changed concurrently, read the Board again before reporting success. If the user wants a display assignment, finish there.

## Take or pass the lease

Use this section when the user explicitly asks a session to take or pass the torc. Read `docs/p2-pilot.md` in the TORC checkout for the canonical commands and required inputs.

1. Read the assignment. If the user asked to start this project's torc and the Board is unassigned, reserve **Project torc** first. For that choice, `board workspace --project <exact projectId> --json` identifies its private state directory and lineage. For a named torc use its known source store. If Dias is absent, a session can still use its known canonical store for passage.
2. For an explicitly requested first activation, use the current task, real decisions and the session's actual capabilities to prepare canonical state and substrate inputs. The example files document their shapes. Use `lineage create` only for a new lineage. Save its activation receipt for this session, run `lineage publish-holder`, and verify the Board's reported holder. If the lineage already exists, read `lineage explain` and continue from the verified authority.
3. For passage, the actual holding session prepares the handoff, the intended recipient reconstructs the state, and its accepted `handoff resolve` transfers the lease. Require evidence binding the acting session to its activation. A matching name, a Board assignment or a focused window cannot establish that binding. After acceptance, read the published report. If publication needs repair, rerun `lineage publish-holder` against that lineage.

Report the action that occurred, such as “Atlas now follows Release review” or “Atlas is waiting for its first holder report.” Keep display assignment, lease transfer and Lugos thread linkage distinct.
