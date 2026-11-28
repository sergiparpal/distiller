# Slice 3's runs rejected for their JUnit files, checked against their CI logs, 2026-11-28

Note 110 of `TASKS.md`: whether the 84 runs that Slice 3's replay rejected for
their JUnit files, 64 for `collection-error` and 20 for `unusable-input` with
`junit` (`2026-11-27-slice-3-replay.md`), failed for their pull requests' own
code. That they did was inferred from the errors of their full runs alone. This
note compares them with what each run's CI job saw, where GitHub still gives the
job's log. As the user approved on 2026-11-28, the rule below was written, and
committed, before any of those logs was read.

Labels: **FACT**; **INFERENCE**; **OPINION**, the agent's view.

## What GitHub gives of the 84

On 2026-11-28, through `gh`, reading only, for each of the 84 runs: its jobs,
and the log of its pilot's job, the one that `pilots/<project>.toml` names
(FACT):

- 81 runs: GitHub gives the run's jobs, and in each the pilot's job, in the
  run's latest attempt, is there once and failed.
- 3 runs of zha-device-handlers, #4499, #4622 and #4624, which started from
  2026-01-04 to 2026-01-07: GitHub answers HTTP 404 for their jobs.
- 21 of the 81: GitHub gives the job's log, which was saved, unread, in the
  session's scratchpad. They started from 2026-09-11 to 2026-11-20:
  zha-device-handlers 18, 13 rejected for `collection-error` and 5 for
  `unusable-input`; electricitymaps-contrib 1 and pydantic 1, for
  `collection-error`; and mitmproxy 1, for `unusable-input`. None of the 6 for
  `unusable-input` has a JUnit file (`"junit_sha256":null`).
- The other 60: GitHub answers HTTP 410 for the job's log. They are every run of
  the 84 that started up to 2026-08-27.

That GitHub keeps a job's log for some 90 days, so that the first of the 21, of
2026-09-11, goes around 2026-12-10, is an inference from the last log gone, of
2026-08-27, and the first given, of 2026-09-11.

## The rule

Written before any of the 21 logs was read (FACT, this note's first commit).

For each of the 21 runs:

- The replay's side, from its work directory, `~/code/distiller-replay/slice-3/`.
  For a run rejected for `collection-error`: the test modules that the full
  run's JUnit file gives as collection errors, each with its exception's class,
  the last one that its traceback names. For a run rejected for
  `unusable-input`, which has no JUnit file: the error at which the full run's
  output, in the pilot's log, stops, with its file and its exception's class.
- The CI's side, from the job's log: pytest's `ERROR collecting` sections, the
  `ERROR` lines of its short test summary, an `ImportError while loading
  conftest`, an `INTERNALERROR`, its last summary line, and the step of the job
  that failed.
- What is compared: each module's path, or the file's, and each exception's
  class, not the messages' text, which changes with the paths.

Each module of the replay's side, or the one file of a run with no JUnit file,
is then one of:

- (a) the CI's pytest could not collect it either, with the same exception's
  class;
- (b) the CI's pytest could not collect it, with another class;
- (c) the CI's pytest collected it with no error: the log shows its tests
  running, by their node ids or by its file in pytest's progress lines;
- (d) the log does not tell, as when the job failed before pytest ran.

And each run is in one class:

- **same**: every one is (a). The CI saw what the replay saw, so the rejection
  comes from the pull request, as note 110 infers.
- **different**: every one is (c). The error is the replay's, not the pull
  request's.
- **not comparable**: every one is (d).
- **partly**: any other mix.

Errors that only the CI shows are listed, and change no class. The CI tested
the merge of the head into the base branch, the replay the head alone (D-011),
so a run that is different or partly could be so for what the base branch had;
this note would name that as a possibility, without deciding it. For the 63
runs with no log, the note gives what the CSV and GitHub still give, the job's
outcome and, where GitHub gives them, its steps, and classifies none of them.
