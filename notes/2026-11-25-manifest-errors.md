# The window manifest's two errors, checked, 2026-11-25

Note 104 of `TASKS.md` found two errors in the window's manifest,
`2026-11-17-window-red-runs.csv`, when the funnel of note 103 counted urllib3's
red pull requests again (`2026-11-21-new-pilot-search.md`). On 2026-11-25, as
the user asked, the agent checked both on GitHub, reading only, through
`gh api`, and the user chose what to do about them (D-029): the Bet's figure
stays the report over the manifest's pull requests, and #3758, which the
manifest lacks, is replayed apart, its result written beside the figure
whatever it is. This note holds what the checks found and the rule, both
written before the replay; its last section holds the replay once it has run.

Labels: **FACT**; **INFERENCE**; **OPINION**, the agent's view.

## Run 25715213323 is #5007's

- The run, of the workflow "CI", was created on 2026-05-12 at 05:24:29Z for a
  `pull_request` event, from a fork's branch
  `codex/normalize-folded-response-headers`, at 0c05768646b4; GitHub gives it
  no pull request number (FACT).
- #5007 was opened from that fork and branch at 05:24:26Z, 3 s before the run,
  and closed unmerged on 2026-05-29. Its timeline holds two force-pushes, from
  0c05768646b4 to 022221686120 at 05:30:03Z and from there to 9b2e038c02ca at
  05:38:06Z (FACT, GraphQL's `HeadRefForcePushedEvent`). So 0c05768646b4 was
  #5007's head when the run was created (INFERENCE, from those events and
  times); neither pull request lists it among its commits today (FACT).
- #5047 was opened on 2026-05-22, ten days after the run, from another fork's
  branch of the same name, and closed unmerged the same day (FACT).
- The window's record of that run, line 16 of
  `2026-11-19-window-records-urllib3.jsonl`, says `"pr":5047` and `green`
  (FACT). It is not among the 52 pull requests with a red run, and no other row
  of the manifest holds 5047 or 5007, so no figure of the report changes (FACT).
  The manifest's row and the record stay as they are, since they are what the
  replay read and wrote (D-029).

## #3758 is missing

- #3758 was opened on 2026-01-17 at 15:47:46Z from a fork's branch
  `hypothesis-tests`, against `main`, and closed unmerged on 2026-01-19 (FACT).
- Five runs of "CI" came from that fork and branch on 2026-01-17, from 15:47:51Z
  to 16:11:28Z, all failed (FACT). The last, 21097199737, created at 16:11:28Z
  at 0904e7a8f5bd, #3758's last head, failed in its job "Ubuntu 3.12", whose
  steps GitHub no longer gives (FACT). It started inside the Bet's window, so
  the Bet's hypothesis takes #3758 in, and it is the run chosen for it: the
  latest of its runs whose job failed.
- Eight more runs of "CI" came from the same fork and branch, all failed, from
  2026-01-20 at 12:06:46Z, 8 s after #3761 was opened from them, to 2026-01-21
  at 06:08:22Z, run 21199215062, which the manifest gives #3761 (FACT). The two
  pull requests share a fork and a branch, open at different times.
- The window's scripts are gone, so why the manifest left #3758 out is not
  known. GitHub gives none of these runs a pull request number (FACT), and a
  pairing of runs with pull requests by branch alone would give all thirteen
  runs of `hypothesis-tests` to one of the two, and #5007's run to #5047
  (INFERENCE). The funnel of note 103, which wrote the new pilots' CSVs, pairs
  a run only with a pull request from its fork and branch that was open when
  the run was created (`number_of` and `was_open` in `pilot-search/funnel.py`),
  and found both right (FACT).
- 0904e7a8f5bd was not in urllib3's clone, `~/code/distiller-pilots/urllib3`
  (FACT, 2026-11-25).

## The bounds

By `clopper_pearson_upper`, rounded as the report rounds (FACT, 2026-11-25):

| Pull requests with a red run | Missed | Bound |
|---|---|---|
| 52, the manifest's | 3 | 14.2% |
| 53, with #3758 caught | 3 | 14.0% |
| 53, with #3758 missed | 4 | 16.4% |

Green, rejected or not replayed, #3758 leaves 52 and 14.2%.

## The Python of the builds (note 105)

- In `~/code/distiller-replay/urllib3.log`, the window's log, each of the 92
  lines in which uv names the interpreter it builds with names
  `/usr/bin/python3.12`, CPython 3.12.3 (FACT).
- uv is 0.11.23, at `~/.local/bin/uv`, a file of 2026-06-19 (FACT). uv's own
  CPython 3.12.13 is in `~/.local/share/uv/python`, in a folder of 2026-11-22,
  after the window's replay (FACT). From a folder with no project,
  `uv python find --no-project 3.12` gives that CPython 3.12.13, and with
  `UV_PYTHON_PREFERENCE=only-system` it gives `/usr/bin/python3.12` (FACT,
  2026-11-25).
- Rule 4 builds an environment without the harness's `PYTHONPATH` and
  `VIRTUAL_ENV`, so that variable, set when the harness starts, reaches
  `uv sync` (INFERENCE from the SPEC; the replay's log shows which interpreter
  uv took).

## The rule, written before the replay

D-029, as the user chose on 2026-11-25:

- The Bet's figure stays the report over the manifest's records: 3 missed
  pull requests out of 52 with a red run, and a bound of 14.2%.
- #3758 is replayed apart, at the head of run 21097199737, 0904e7a8f5bd, kept
  in urllib3's clone at `refs/window/21097199737`, from a manifest of its own,
  `2026-11-25-pr-3758-manifest.csv`; with `pilots/urllib3.toml` and the tool's
  checkout at 6763be8, as the window had them, and the harness at bccf738, whose
  `src/replay` differs from the window's, 2301238, by note 93's structural
  commit, abc81c3, and by two commits that change only comments and docstrings,
  13201b8 and e75eeee (FACT, their syntax trees compared); in a work directory
  and a record file of its own, under `~/code/distiller-replay/pr-3758/`, since
  the harness starts no replay over another manifest's log; and with
  `UV_PYTHON_PREFERENCE=only-system`.
- The replay counts only if its log shows both environments built with
  `/usr/bin/python3.12`; if not, it is run again with nothing else changed.
- Its record stands as replayed, by the window's rules, D-017's and D-019's
  included, and its result is written here and beside the Bet's figure,
  whatever it is.

## The replay of #3758

Run by the agent on 2026-11-25, as D-029 says, once #6, the pull request of
the rule, was open: `refs/pull/3758/head`, fetched into urllib3's clone as
`refs/window/21097199737`, gave 0904e7a8f5bd, and the harness ran from this
repository at 2b816d8, the rule's commit, whose `src/` is bccf738's (FACT):

```
UV_PYTHON_PREFERENCE=only-system PYTHONPATH=src .venv/bin/python -P -m replay run
  --pilot pilots/urllib3.toml --manifest notes/2026-11-25-pr-3758-manifest.csv
  --clone ~/code/distiller-pilots/urllib3 --work ~/code/distiller-replay/pr-3758
  --records ~/code/distiller-replay/pr-3758/records/urllib3.jsonl
  --tool ~/code/distiller-tool
```

- Its steps took 67 s, and it ended at 22:58:06Z; #6 merged 2 s later, at
  22:58:08Z (FACT).
- Both environments, at M and at the head, were built from the same `uv.lock`,
  SHA-256 48f298e0ae45, and for each uv said
  `Using CPython 3.12.3 interpreter at: /usr/bin/python3.12` (FACT): the
  variable reached `uv sync`, and the replay counts.
- M is the base commit, bd37a23af455 (FACT, the tool's `--base` and
  `--coverage-commit`).
- The coverage at M: 1921 passed, 2 failed, 335 skipped and 4 xfailed. The two
  failures are `test_http2_probe_blocked_per_thread` of `TestHTTPS_TLSv1_2` and
  of `TestHTTPS_TLSv1_3`, in `test/with_dummyserver/test_https.py`, the flaky
  test of D-017 (FACT).
- The full run at the head stopped in collection, with 8 errors and 1 test
  skipped, exit 2: each of the 8 test modules that #3758 adds,
  `test/test_hypothesis_*.py`, imports `hypothesis`, which the environment
  built from its lock file lacks, and raised `ModuleNotFoundError` (FACT). No
  test ran, and no rerun followed (FACT).
- The tool rejected the run, exit 3, with `collection-error` and `junit`, and
  appended one record, copied here as
  `2026-11-25-pr-3758-records-urllib3.jsonl`. The summary:
  `urllib3: replayed 1, not replayed 0, red 0, inherited failures 0` (FACT).
- The clone was left as it was: `main` checked out at d9f9b0ad, a clean work
  tree and no worktree but its own (FACT).
- CI's run 21097199737 likely failed the same way, since urllib3's nox session
  builds its environment from the same lock file (INFERENCE; GitHub no longer
  gives that job's steps or log).

What it gives, by the rule written before it:

- #3758 is not red: its record says `rejected`, neither `caught` nor `missed`.
- The report over the window's two copies and this record,
  `2026-11-25-report-with-pr-3758.txt`, gives the window's first line, 3 missed
  PRs out of 52 with a red run and a bound of 14.2%, and differs from
  `2026-11-19-window-report.txt` in one line alone: 4 runs rejected for
  `collection-error` with `junit` instead of 3 (FACT, by `diff`).
- So the Bet's figure, over the manifest's pull requests, is the same over them
  and #3758 (FACT). The funnel's recount of 2026-11-21, the only check of the
  manifest, could not see the runs that GitHub had dropped by then, #3720's of
  2025-12-03 and #3729's of 2025-12-05 among them; whether the manifest lacks a
  pull request of the window's first days is not known.
