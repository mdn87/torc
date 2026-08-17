# Cold-Agent Project Snapshot Refresh

This is the canonical provider-independent workflow for Codex, Claude, a local
model, a deterministic producer, or a human. Repository evidence remains
authoritative throughout.

1. Read the repository's agent instructions and authoritative architecture and
   implementation documents before interpreting state.
2. Locate `.lugos/project-snapshot.sources.yaml` or the explicitly designated
   evidence-source manifest. Do not expand it into an arbitrary crawl.
3. Run `torc artifact collect` to create a fresh Evidence Bundle for the local
   Git worktree. Preserve dirty-state and collection warnings as evidence.
4. Inspect the bundle, its repository commit and Git state, and only the source
   contents embedded or explicitly referenced by that bundle.
5. Produce one candidate Project Snapshot from the supplied evidence. The
   producer boundary is `EvidenceBundle -> CandidateProjectSnapshot`; do not
   add provider-owned fields or acceptance state.
6. Mark claims `verified` only when at least one referenced source resolves and
   supports them. Mark unsupported interpretations `asserted`, disagreements
   `conflicted`, and missing knowledge `unknown`. Do not infer percentages from
   prose.
7. Run `torc artifact validate <candidate> --evidence <bundle>`. Inspect every
   failed check, warning, and unverified claim. Correct the candidate by
   producing a new immutable candidate, never by mutating an accepted record.
8. Run `torc artifact accept` only when the required checks are expected to
   pass. A rejected receipt is evidence of failure and must not advance current
   state.
9. Update current state only through the acceptance command. Never edit
   `current.ref` directly.
10. Run `torc artifact current`, then `torc artifact render --artifact current`
    to produce the read-only reference view.
11. Report the artifact, bundle, and receipt digests; collection warnings;
    unresolved conflicts; unknowns; asserted or otherwise unverified claims;
    and the renderer output path.

Provider-specific invocation examples belong in separate adapter notes. They
must not replace or weaken this workflow.
