# Continuation review practice

Practice the human scoring rubric on two written examples, exporting a reading list and
rescheduling a pickup reminder. Each case gives the original request, the interruption point,
success criteria and the same input for both results. Open **Changes and evidence** to inspect
what each result does. Both examples are independent of the eight recovered benchmark tasks.

## Open the page

From the TORC checkout on Windows, run this command with the project's Python environment.

```powershell
.\.venv\Scripts\python.exe experiments/continuation-review/practice_review.py --reviewer Matt --open
```

With the project environment active, use `python` for the same command on other platforms.
The launcher prints the local address and database path. Leave it running while reviewing.
Ctrl+C stops a foreground launcher. Run the same command to resume. If the launcher is
already running, open its [local practice page](http://127.0.0.1:8773/).

New databases use questions written for each case. An existing database reopens with
the questions, evidence, side assignments and answers from that batch. If a description is
clarified after locking, **Wording shown during scoring** opens the original text.
To see the revised questions alongside the first batch, use a second database and port.

```powershell
.\.venv\Scripts\python.exe experiments/continuation-review/practice_review.py --reviewer Matt --db .torc/continuation-review/practice-v2.sqlite3 --port 8774 --open
```

The two examples can be inspected without entering another rating.

## Score a case

1. Read the request and success criteria, then inspect A and B. The page randomly assigns
   sides independently on first launch and keeps them fixed in this batch.
2. Read the question under each result and inspect the cells or rows it names.
   For the reading list, check whether the first Title cell holds the whole title
   “Winter, Again”. For reminders, read across the original, requested and returned
   pickups. The downloaded CSV and the raw reminder output are in **Changes and evidence**.
3. Choose an overall preference. Give a short reason for **Cannot judge**, **Neither** or
   **Insufficient evidence**. You can also use the reason field to flag confusing wording.
4. Wait for **Saved** before closing. **Submit review** advances to the next unfinished case.
   **Revise answers** reopens a submitted case and retains its earlier revisions.
5. After both submissions, **Lock practice batch** closes editing. **Export answers**
   downloads the blinded record, including drafts and revisions, before or after locking.

## How records are kept

The launcher serves loopback requests and writes to
`.torc/continuation-review/practice.sqlite3`. Each save records the launcher's reviewer
name, UTC time, revision number and exact card binding. This reviewer name is a local
attribution label. Each card binds the batch, rubric version and content, task context,
side placement, and SHA-256 of each displayed result including its evidence. The export
includes those materials so the judgment can be interpreted on its own.

If another tab has saved a newer answer, the page preserves what you entered on screen
and asks you to reload. Copy any unsaved notes you want to keep before reloading.
Reopening with a different reviewer or changed practice evidence requires a separate
database. Use `--db .torc/continuation-review/second-practice.sqlite3` for another batch.
Keep the original database and its source version to resume the original review.

The page records human judgments only. Automated correctness comes from the independent
scorer. Measured efficiency comes from the execution owner's usage ledger. A human
preference cannot change either outcome. The practice batch contains no arm identities,
test verdicts or usage measurements. Scorer qualification and benchmark admission remain open.

## Verify the interface

The storage and submission checks run with the TORC test suite. The browser test uses
an isolated database and reviewer, restarts the launcher, and opens a fresh browser
context. With Playwright and its Chromium binary available in the test interpreter, run
`python -m pytest tests/test_practice_review_browser.py -rs`. Its temporary test directory
contains desktop and mobile viewport captures. Running the page itself uses the existing
TORC installation and Python standard library.
