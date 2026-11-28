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

## The 21 runs, compared

Read on 2026-11-28, after the rule's commit, c41b4d8. All 21 are **same**
(FACT, by the rule; two of them by a reading that the rule did not foresee,
below). Each job is its run's first attempt, and every zha-device-handlers job
failed in its step "Run pytest".

| Pilot | Pull request | Run | Started | Rejected for | The replay's full run | The CI's job | Class |
|---|---|---|---|---|---|---|---|
| electricitymaps-contrib | #8897 | 40842769724 | 2026-10-29 | `collection-error` | 89 modules, `pydantic.error_wrappers.ValidationError` | the same 89, the same class; step "Run tests", exit 2 | same |
| mitmproxy | #8598 | 43512433510 | 2026-11-13 | `unusable-input` | pytest's usage error on `pyproject.toml`, exit 4 | the same, on the same file; step "Run tox -e py3.12", exit 4 | same |
| pydantic | #14189 | 41432004177 | 2026-11-02 | `collection-error` | 1 module, `tests/pydantic_core/test_streaming_json.py`: duplicate parametrization IDs | the same module, the same message; step "Run pytest", exit 2 | same |
| zha-device-handlers | #5324 | 34648636986 | 2026-09-11 | `collection-error` | 51 modules, `NameError` | the same 51, the same class; exit 1 | same |
| zha-device-handlers | #5331 | 34927566906 | 2026-09-15 | `unusable-input` | `tests/conftest.py`, `AttributeError`, exit 4 | the same; exit 4 | same |
| zha-device-handlers | #5456 | 38588393870 | 2026-10-14 | `collection-error` | 54 modules, `ModuleNotFoundError` | the same; exit 1 | same |
| zha-device-handlers | #5480 | 39469597911 | 2026-10-20 | `collection-error` | 54 modules, `ImportError` | the same; exit 1 | same |
| zha-device-handlers | #5482 | 39469621022 | 2026-10-20 | `collection-error` | 54 modules, `ImportError` | the same; exit 1 | same |
| zha-device-handlers | #5483 | 39469633210 | 2026-10-20 | `collection-error` | 54 modules, `ImportError` | the same; exit 1 | same |
| zha-device-handlers | #5485 | 39469661770 | 2026-10-20 | `unusable-input` | `tests/conftest.py`, `ImportError`, exit 4 | the same; exit 4 | same |
| zha-device-handlers | #5486 | 39469677155 | 2026-10-20 | `unusable-input` | `tests/conftest.py`, `ImportError`, exit 4 | the same; exit 4 | same |
| zha-device-handlers | #5488 | 39469700188 | 2026-10-20 | `unusable-input` | `tests/conftest.py`, `ImportError`, exit 4 | the same; exit 4 | same |
| zha-device-handlers | #5489 | 39469713320 | 2026-10-20 | `unusable-input` | `tests/conftest.py`, `ImportError`, exit 4 | the same; exit 4 | same |
| zha-device-handlers | #5201 | 39888964692 | 2026-10-23 | `collection-error` | 52 modules, `ModuleNotFoundError` | the same; exit 1 | same |
| zha-device-handlers | #5548 | 40373442127 | 2026-10-26 | `collection-error` | 1 module, `tests/test_xbee.py`, `NameError` | the same; exit 1 | same |
| zha-device-handlers | #5273 | 40399653968 | 2026-10-26 | `collection-error` | 55 modules, `ImportError` | the same; exit 1 | same |
| zha-device-handlers | #5410 | 40584656990 | 2026-10-27 | `collection-error` | 54 modules, `ImportError` | the same; exit 1 | same |
| zha-device-handlers | #5685 | 42580387356 | 2026-11-09 | `collection-error` | 57 modules, `TypeError` | the same; exit 1 | same |
| zha-device-handlers | #5293 | 42840667862 | 2026-11-10 | `collection-error` | 57 modules, `SyntaxError` | the same; exit 1 | same |
| zha-device-handlers | #5734 | 43954971404 | 2026-11-16 | `collection-error` | 63 modules, 62 `ImportError` and 1 `ModuleNotFoundError` | the same; exit 1 | same |
| zha-device-handlers | #5760 | 44687023899 | 2026-11-20 | `collection-error` | 63 modules, 62 `ImportError` and 1 `ModuleNotFoundError` | the same; exit 1 | same |

- In the 15 runs rejected for `collection-error`, the replay's full runs could
  not collect 759 modules. Each of them the CI's pytest could not collect
  either, with the same exception's class, (a), but for pydantic's one, whose
  error names no class (below). No CI log names a collection error that its
  run's replay did not have (FACT).
- In the 6 runs rejected for `unusable-input`, which have no JUnit file, the
  CI's pytest stopped where the replay's full run did, with the same exit code,
  4: at zha-device-handlers' `tests/conftest.py`, through `ImportError while
  loading conftest`, with `AttributeError` at #5331, and with `ImportError`, a
  name that `zha.application.platforms.event.const` does not define, at #5485,
  #5486, #5488 and #5489; and at mitmproxy's `pyproject.toml`, below (FACT).
- The reading that the rule did not foresee. In two runs, neither side names an
  exception's class: pydantic's #14189, whose module stops at pytest's
  collection failure "Duplicate parametrization IDs detected, but
  strict_parametrization_ids is set.", and mitmproxy's #8598, whose run stops
  at pytest's usage error, that its `pyproject.toml` sets both `[tool.pytest]`
  and `[tool.pytest.ini_options]` (FACT). On both sides the same module, or
  the same file, stops pytest with the same message, which holds no path. The
  note takes each as (a), and both runs as same, since the rule compares
  classes rather than messages only because messages change with the paths
  (OPINION). Taken as not comparable, they would give 19 same and 2 not
  comparable; the user may read them so.
- Besides their collection errors (FACT): zha-device-handlers' CI runs pytest
  under pytest-xdist, its log saying "bringing up nodes", and in each of its 13
  runs with collection errors the CI and the replay ran the same number of the
  tests that they could collect, from 19, at #5456 and five others, to 4,811,
  at #5548; at #5685, 10 of them, all in `tests/test_tuya_spm01v2.py`, failed
  on both sides. In #5324, #5548 and #5685 the CI's log gives each collection
  error four times; that it is once for each of four workers is an inference.
  electricitymaps-contrib's and pydantic's runs stopped at their collection
  errors on both sides, the CI's log saying "collected 62 items / 89 errors"
  and "collected 13817 items / 1 error / 3 skipped". The SPEC's prose says
  that after a collection error pytest by default runs no test, so that the
  JUnit holds only such errors; under zha-device-handlers' pytest-xdist it ran
  the others too. The SPEC rejects a full run whose JUnit holds a collection
  error whatever else it holds, so #5685's 10 failed tests count in no figure
  (note 112 of `TASKS.md`).

## What it says of note 110

- For the 21 runs whose CI log GitHub still gave, 15 rejected for
  `collection-error` and 6 for `unusable-input` with `junit`, the CI's job
  failed as the replay's full run did, at the same modules or the same file,
  with the same exception's class or, in two runs, the same message (FACT). So
  for them note 110's inference holds: what stopped each full run was there in
  the CI's own run of the pull request, and was not the replay's.
- The other 63 can no longer be checked so: GitHub has dropped 60 of their logs
  and 3 of their runs. Of the 63, the CSV of 2026-11-21 gives 18 jobs as failed
  in a test step and 45 with their steps no longer given; on 2026-11-28 GitHub
  gave the steps of 16 of the 18, each failed in its test step again, and of
  none of the 45 (FACT). For them the inference stays an inference.
- The 21 are no random sample: they are the newest, whose logs GitHub keeps,
  and 18 of them are zha-device-handlers', which holds 50 of the 84 (FACT).
  That every one of them agrees makes it likely that most of the 63 are the
  pull requests' too, and says least of click's 10, pydantic's other 13 and
  chonkie's 4, none of which could be checked (OPINION).
- The check changes no record and no figure: Slice 3's records stand as
  replayed, and the Next bet's bound stays 5.5%, 10 missed pull requests out of
  306 with a red run (FACT).

## Where the evidence is

- The lines of the 21 CI logs that the rule reads are in
  `2026-11-28-rejected-junit-ci-excerpts.txt`, beside this note, cleaned of
  their timestamps, ANSI codes and control characters, each repeated line kept
  once with its count. The whole logs, and the scripts that fetched and read
  them, are in the session's scratchpad, which may be gone (FACT).
- The replay's side is in its work directory, `~/code/distiller-replay/slice-3/`:
  each run's `junit.xml`, and the pilot's log, which holds each step's output
  (FACT).
