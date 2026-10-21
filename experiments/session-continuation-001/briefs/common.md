# Common continuation rules

This is a historical repository engineering task. The source is TORC at commit
`a798bbc4c45527952510a5f3d239f49c5b67a2de`, with the requested implementation
absent. The task briefing is operator-authored; it is not an exported agent
conversation. A native continuation comparison must separately establish and
retain a real provider session before using a native arm.

Read `CONTINUATION_TASK.md` and the repository instructions. Work only inside
this disposable workspace. Do not use network access, subagents, credentials,
parent/sibling directories, package installation or Git history. No commits,
sends, deploys, hooks, services or model calls from inside the task. The source
snapshot has no Git object database, later implementations or hidden scorer.

All strategies receive the same task, workspace, permitted history and tools.
The comparison varies continuation context, not access to the task's evidence.
The execution owner records the chosen model and environment separately.
Recovery evidence never grants retry or authority. Report incomplete work and
failed checks honestly. A completion claim must describe the checks actually run.

Only the task's named new module may differ in the submitted source snapshot.
Use temporary exploratory tests if useful, but retain their results in the
execution record and remove those temporary files before submitting. Existing
tests and production modules remain protected. There is no exact required
implementation, patch text or tool-call sequence. Independent acceptance tests
evaluate public behavior and preservation of the stated constraints.

An observer records repeated investigation using the preregistered rubric;
workers receive no progress feedback from hidden scoring. A failed run remains
in its originating arm, with all attempts and fallback costs retained.
