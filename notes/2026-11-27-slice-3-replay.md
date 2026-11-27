# Slice 3's nine pilots replayed, 2026-11-26 and 2026-11-27

Task 2 of Slice 3: K18, pydantic's #14290, replayed as the slice's acceptance;
then the 506 pull requests of the nine pilots' CSVs,
`pilot-search/<project>-red-runs.csv`, replayed by the harness `replay` into
each pilot's record file; and Slice 1's report over the nine, which gives the
Next bet's bound (D-031). The records are copied here,
`2026-11-27-slice-3-records-<project>.jsonl`, and the report over those copies
is `2026-11-27-slice-3-report.txt`, the same, byte for byte, as the report over
the work directory's own record files.

Labels: **FACT**; **INFERENCE**; **OPINION**, the agent's view.

## How it ran

- The harness: this repository at 0d60bf4, `main` with task 1's change,
  started as `PYTHONPATH=src .venv/bin/python -P -m replay run ...` by the
  agent, as the user asked: K18 alone first, with `--only 14290`; then the
  nine one after another, from a loop detached from the agent's session with
  `setsid nohup`, from the fastest pilot at step 3's pace to pydantic, whose
  run went on after #14290 (FACT).
- The tool: `~/code/distiller-tool` at 6763be8, as for the window (FACT).
- The pilots: task 0's nine configurations, with D-024's 148 deselections, whose
  builds run uv 0.13.8 with `/usr/bin/python3.12`; the plugins installed by the
  user's uv 0.11.23 from the folder that holds each worktree, as task 1 made it
  (FACT).
- The work directory: `~/code/distiller-replay/slice-3/`, with each pilot's
  log, each pull request's kept inputs and the summary, and the record files in
  its `records/` (FACT).
- The time: from 2026-11-26 at 15:04:48Z to 2026-11-27 at 06:21:27Z, 15 h 17
  min for the nine, against the 7 h that Slice 3's Constraints estimated. By
  pilot: click 11 min, pydantic-settings 4, verifiers 20, mitmproxy 44,
  electricitymaps-contrib 39, rally 37, zha-device-handlers 1 h 42 min, chonkie
  3 h 16 min and pydantic 7 h 43 min. K18 alone took 283 s of steps, 159 of them
  for the coverage at M (FACT).

## K18

pydantic's #14290, at its tested head fe5c2e511f1d, whose `pyproject.toml` asks
for `required-version = '>=0.13.0'`, replayed on 2026-11-26 with uv 0.11.23 on
the `PATH` (FACT): both of its environments were built, with
`uv pip install ... coverage==7.16.2 pytest-cov==7.1.0 pytest-timeout==2.4.0`
among the steps at M and `uv pip install ... pytest-timeout==2.4.0` at the head,
and no `required-version` refused them; one record was appended to pydantic's
record file, `caught`, one test failing in the full run and again in the rerun,
none left out. K18's then holds.

## The summary

```
chonkie: replayed 39, not replayed 1, red 15, inherited failures 0
chonkie: not replayed, environment at the head not built: 1
click: replayed 36, not replayed 0, red 25, inherited failures 0
electricitymaps-contrib: replayed 20, not replayed 6, red 13, inherited failures 7
electricitymaps-contrib: not replayed, environment at M not built: 6
mitmproxy: replayed 24, not replayed 0, red 16, inherited failures 0
pydantic-settings: replayed 19, not replayed 1, red 4, inherited failures 0
pydantic-settings: not replayed, environment at the head not built: 1
pydantic: replayed 146, not replayed 17, red 121, inherited failures 7
pydantic: not replayed, environment at the head not built: 17
rally: replayed 24, not replayed 1, red 18, inherited failures 0
rally: not replayed, environment at the head not built: 1
verifiers: replayed 25, not replayed 0, red 4, inherited failures 0
zha-device-handlers: replayed 145, not replayed 2, red 90, inherited failures 0
zha-device-handlers: not replayed, environment at M not built: 2
both: replayed 478, not replayed 28, red 306, inherited failures 14
both: not replayed, environment at M not built: 8
both: not replayed, environment at the head not built: 20
```

The line `both` sums the nine pilots' logs, as the summary's rule says: every
log of the work directory (FACT). That answers the [VERIFY] of Slice 2's
technical sheet.

The records, by pilot, with the share of the evaluated runs' tests that the
report treats as unmeasured (FACT):

| Pilot | Records | Caught | Missed | Green | Rejected | Unmeasured |
|---|---|---|---|---|---|---|
| zha-device-handlers | 145 | 88 | 2 | 5 | 50 | 81.0% |
| pydantic | 146 | 114 | 7 | 4 | 21 | 50.4% |
| click | 36 | 25 | 0 | 1 | 10 | 3.0% |
| rally | 24 | 18 | 0 | 5 | 1 | 1.2% |
| mitmproxy | 24 | 15 | 1 | 5 | 3 | 2.2% |
| electricitymaps-contrib | 20 | 13 | 0 | 5 | 2 | 6.0% |
| verifiers | 25 | 4 | 0 | 21 | 0 | 5.3% |
| chonkie | 39 | 15 | 0 | 20 | 4 | 14.2% |
| pydantic-settings | 19 | 4 | 0 | 0 | 15 | 2.8% |

## The report

Its first line: "Miss rate: 10 missed PRs out of 306 PRs with a red run (306
red runs), with a one-sided 95% Clopper-Pearson upper bound of 5.5%."

Against the Next bet, as measured (FACT): the bound, 5.5%, is below 10%, over
306 pull requests with a red run, at least the 200 it asks; and the harness
could not build the environment of 28 of the 506, 5.5%, below the 20% of its
Kill signal. The bet's outcome, on 2026-12-10, is the user's to write.

Its line on savings, 46.9%, does not apply: Slice 3 gives no savings figure,
since only the pull requests whose job failed were replayed (Non-goals).

By pilot, each computed by `clopper_pearson_upper`; the bet's bound is the
pooled one (FACT):

| Pilots | Missed | Red | Bound |
|---|---|---|---|
| zha-device-handlers | 2 | 90 | 6.8% |
| pydantic | 7 | 121 | 10.6% |
| click | 0 | 25 | 11.3% |
| rally | 0 | 18 | 15.3% |
| mitmproxy | 1 | 16 | 26.4% |
| electricitymaps-contrib | 0 | 13 | 20.6% |
| verifiers | 0 | 4 | 52.7% |
| chonkie | 0 | 15 | 18.1% |
| pydantic-settings | 0 | 4 | 52.7% |
| all nine | 10 | 306 | 5.5% |
| all nine but zha-device-handlers | 8 | 216 | 6.6% |
| all nine but zha-device-handlers and pydantic | 1 | 95 | 4.9% |

## What the replay found

- Unmeasured tests. The report treats 52.7% of the tests as unmeasured, and
  the selector picks every unmeasured test (FACT). In three of zha-device-handlers' caught
  pull requests, #4123, #4612 and #4604, the coverage at M holds 736 test
  contexts for some 4,600 test cases in the full run's JUnit file, and 3,864 to
  3,906 of the tests, some 84%, have no row; most are parametrized over each
  quirk, as `tests/test_quirks.py::test_signature[...]` and
  `test_quirk_replacements[...]` (FACT). That those tests run no line of
  `zhaquirks` while they run, since they read classes that the quirks define
  when they are imported, at collection, is an inference. In zha-device-handlers
  and pydantic, which hold 211 of the 306 pull requests with a red run, the
  all-affected selector so selects most of the suite: the bound holds for it as
  Slice 1 defines it, and says less of a selector that left those tests out
  (OPINION). Note 109 of `TASKS.md`.
- The coverage at M made 22 runs unusable, so rejected with `unusable-input`
  and `coverage` (FACT):
  - pydantic-settings, 15 of its 19 pull requests replayed: 16 of its 20
    coverage runs at M stopped with `coverage.exceptions.CoverageWarning:
    --include is ignored because --source is set (include-ignored)`, raised as
    an error, and wrote no coverage file (FACT). That the pilot's own pytest
    configuration turns that warning into an error, as the harness's
    `--cov=<source>` meets the pilot's own include, is an inference. So 4 of its
    pull requests were evaluated, against some 14 with a red run expected, for a
    cause of the replay's and not of the pull requests' (INFERENCE).
  - pydantic, 7, at #12593, #12635, #12660, #12662, #12680, #12692 and #12693:
    each coverage run at M ended with `Fatal Python error: Segmentation fault`,
    exit 139 (FACT); likely step 3's test of deep recursion, under coverage's C
    tracer (INFERENCE).

  Note 108 of `TASKS.md`.
- The other rejections: 64 runs for `collection-error` with `junit`, 44 of them
  zha-device-handlers', and 20 for `unusable-input` with `junit` (FACT). Their
  full runs show mostly errors of the pull requests' own code: a `SyntaxError`
  or `IndentationError`, a `NameError` or `AttributeError`, an `ImportError` of
  a name that the head does not define, or a `ModuleNotFoundError` of a module
  that the pull request names, such as zha-device-handlers' `zha.zigbee.store`
  or chonkie's `chonkie.vision` (FACT, from the full runs' output); a few show
  none of these. That they are the pull requests' and not the replay's is an
  inference from those errors. Note 110 of `TASKS.md`.
- The environments not built, 28 (FACT): pydantic 17 at the head, 15 of them
  pydantic-core's Rust, which cargo failed to build, one `memray` and one
  `pyo3` that no version satisfied; electricitymaps-contrib 6 at M, 5 whose
  `required-version` asks for uv `>=0.9, <0.10`, which the build's uv 0.13.8
  does not meet, and one with no `uv.lock`; zha-device-handlers 2 at M with no
  `uv.lock`; and one at the head for each of rally, whose `esrally` did not
  build, chonkie, whose `uv.lock` uv could not parse, and pydantic-settings,
  for which uv could not download `pydantic-core==2.46.1`.
- Reruns: the failures of 6 red runs were not confirmed by a rerun, and 35
  failures were discarded as not reproduced (FACT, the report).
- The clones: each of the nine was left as it was, its own checkout, a clean
  work tree and no worktree but its own (FACT, 2026-11-27).

## Failed tests left out

70 failed tests were left out of a selection, in 15 runs (FACT, the records):
pydantic 64, in 11 runs, 7 of them missed; zha-device-handlers 3, in its 2
missed runs; mitmproxy 1, in its missed run; and electricitymaps-contrib 2, in
one caught run. The report lists each, by run, with its row and its run's paths
with no column and import-only. The user classifies them after the outcome, as
D-021 to D-023 did for the window (D-031): §13.2's share can be called marginal
from 29 classified failed tests left out if none has a file dependency (D-023),
and 70 are here.
