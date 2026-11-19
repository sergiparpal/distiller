# The window replayed, 2026-11-19

Task 9 of Slice 2: the 90 pull requests of `notes/2026-11-17-window-red-runs.csv`,
48 of urllib3's and 42 of poetry's, replayed by the harness `replay` into each
pilot's record file, and Slice 1's report over both, which gives the Bet's
bound. The records are copied here, `2026-11-19-window-records-urllib3.jsonl`
and `2026-11-19-window-records-poetry.jsonl`, and the report over those copies is
`2026-11-19-window-report.txt`.

## How it ran

- The harness: this repository at 2301238, whose `src/` e32c73d left as it
  was, started as `PYTHONPATH=src .venv/bin/python -P -m replay run ...`. The
  agent replayed K16 and poetry's #11226; the user replayed the rest from a
  terminal, urllib3's window and then poetry's.
- The tool: a clone of this repository at 6763be8, `~/code/distiller-tool`, with
  the `.venv` that `make install` builds, and coverage 7.16.2.
- The pilots: `pilots/urllib3.toml` and `pilots/poetry.toml`, with no floor
  configuration (D-015) and three of poetry's tests deselected (D-016); the
  plugins at pytest-cov 7.1.0 and pytest-timeout 2.4.0 (7223cf1); and builds that
  get neither the harness's `PYTHONPATH` nor its `VIRTUAL_ENV` (note 95).
- The work directory: `~/code/distiller-replay/`, with the logs `urllib3.log` and
  `poetry.log`, each pull request's kept inputs and the summary, outside the
  repository. Its `discarded/` holds the logs and the record of poetry's two
  earlier replays of #11226, which notes 95 and 96 set aside.
- The time: urllib3's window took 1.73 h of steps and poetry's 1.46 h; a pull
  request took a median of 129 s in urllib3 and 108 s in poetry, at most 262 s
  and 490 s, and the coverage at M a median of 68 s and 55 s.

## The summary

```
poetry: replayed 42, not replayed 0, red 27, inherited failures 0
urllib3: replayed 46, not replayed 2, red 25, inherited failures 5
urllib3: not replayed, environment at M not built: 2
both: replayed 88, not replayed 2, red 52, inherited failures 5
both: not replayed, environment at M not built: 2
```

The records: urllib3, 22 caught, 3 missed, 17 green and 4 rejected; poetry, 27
caught, none missed, 13 green and 2 rejected.

## The report

Its first line: "Miss rate: 3 missed PRs out of 52 PRs with a red run (52 red
runs), with a one-sided 95% Clopper-Pearson upper bound of 14.2%."

Against the Bet, as measured: the bound, 14.2%, is below 15%, over 52 pull
requests with a red run, at least the 30 it asks; and the harness could not
build the environment of 2 of the 90, 2.2%, below the 20% of its Kill signal.
The Bet's outcome is the user's to write.

Its line on savings, 39.2%, does not apply: Slice 2 gives no savings figure,
since only the pull requests whose job failed were replayed (Non-goals).

The bound moves fast with the count of misses, each computed by
`clopper_pearson_upper`:

| Missed | Red | Bound |
|---|---|---|
| 0 | 49 | 5.9% |
| 2 | 51 | 11.8% |
| 3 | 52 | 14.2% |
| 4 | 52 | 16.7% |

## The three missed pull requests

urllib3's #5156, #5173 and #5279. In each, the only failed test that the
selection left out is `test_http2_probe_blocked_per_thread`, under TLS 1.2 or
1.3, in `test/with_dummyserver/test_https.py` or `test/contrib/test_pyopenssl.py`:
it failed in the full run and again in the rerun, and the pull request's diff
touches none of its row's paths. urllib3 fixed that test's lock leak on
2026-10-04 (a164d79c, #5254) and its threads on 2026-10-07 (25edc55a, #5290)
(`2026-11-16-bet-window-checks.md`). It is the only test that failed at any of
urllib3's Ms, at 21 of them, and the inherited failure of #3786, #5049, #5097
and #5103, where it failed at the head too.

On 2026-11-19 the user classified the three, as the Non-goals give a person to
do: failures of a flaky test that urllib3 fixed in October 2026, not of the pull
requests' changes. The records stand as replayed, and the bound above counts
them (D-017). Whether that test fails twice is a matter of chance, so another
replay of the window could count two misses or four.

## Failed tests left out of caught runs

Each of these runs was caught by other failed tests that its selection held:
urllib3's #5050 and #4962, four tests of client certificates,
`test_load_invalid_cert_file` and `test_load_keyfile_with_invalid_password` in
`test/contrib/test_pyopenssl.py` and `test/with_dummyserver/test_socketlevel.py`;
and #5097, three parametrizations of
`test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors`. Not
classified.

## Rejected and not replayed

- Rejected, 6, each for its own head: poetry's #11226, K17, pytest's internal
  error once a test of the pull request crashed a worker; urllib3's #3729, #3761
  and #4947, collection errors; urllib3's #4946, a `SyntaxError` in
  `src/urllib3/_collections.py`, which stopped pytest with exit code 4; and
  poetry's #10719, an `ImportError` of `PEELED_TAG_SUFFIX` from the dulwich that
  its own `poetry.lock` pins, exit code 4 too.
- Not replayed, 2: urllib3's #3766 and #3770, whose M, ce16b219 of 2020-11-07,
  holds a `setup.py` and no `pyproject.toml`, so `uv sync` cannot build it.

## What the window checked

- pytest-cov 7.1.0 recorded the coverage at M with urllib3's pytest 8.4.2,
  9.0.3, 9.1.1 and 9.2.0, and poetry's 9.0.2, 9.0.3, 9.1.1 and 9.2.0: no run was
  rejected for its coverage, which answers that [VERIFY] of the SPEC.
- The rerun discarded 117 failures as not reproduced.
- The inherited failures, 5, are all urllib3's probe test, the only test that
  failed at any of urllib3's Ms; poetry's coverage runs at M, with its three
  tests deselected, had no failure.
