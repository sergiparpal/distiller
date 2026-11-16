# Checks of the bet's window, before its slice is built

Checks made on 2026-11-16, after the user wrote the new bet (14816bb), of two of
its kill signals before anything is built for it: whether the window holds 30
pull requests with a red run, and whether the environments of its oldest pull
requests can be rebuilt. They read only CI outcomes and ran only the pilot's own
suite, never the Distiller, so no figure of the tool was seen (D-007). The
scripts and the clones lived in the session's scratchpad, outside the
repository; this note says what they did, so that they can be written again.

Labels: **FACT** = seen on 2026-11-16; **INFERENCE**; **OPINION**;
**[VERIFY]** = not checked.

## In short

- Over the bet's window, the CI saw 25 of urllib3's pull requests red in the
  tests of "Ubuntu 3.12", before any replay, and 30 are what the bet asks for;
  poetry's job saw 21; and the year before the window adds none to urllib3's,
  in the months that GitHub still lists (FACT). So neither finalist alone gives
  the bet's 30 pull requests with a red run of one job (INFERENCE: a replay
  could pass the CI's count only by turning red pull requests that the CI saw
  green).
- The environment of the window's first day builds and runs urllib3's suite
  with no network: 1912 passed and 2 failed, both on the flaky HTTP/2 probe
  test, which then kept the process from exiting (FACT).

## GitHub still lists March's runs, not their logs

A listing that the user ran gave the CI workflow's pull request runs created
from 2026-03-16 to 2026-03-31: 21 runs, each with its conclusion and its head,
as the count below found too. The job logs asked for answered HTTP 410 (FACT).
So a manifest of the window can name each red run's head, but the CI's summary
line and failed tests, which `notes/2026-11-16-replay-slice-proposal.md` puts
in it, are gone for the window's older runs [VERIFY: how long GitHub keeps
logs]. The replays do not need them.

## The environment of the window's first day

At 6dc3f7d5 (2026-03-15), the last commit of urllib3's `main` before the
window, the user built the environment with `uv sync --frozen --python 3.12
--group dev --extra socks --extra brotli --extra zstd --extra h2`, and uv
installed 59 packages (FACT). One of them, `hypercorn`, comes from a git
repository on GitHub, `https://github.com/urllib3/hypercorn` at its branch
`urllib3-changes`, not from PyPI, so building an environment needs GitHub as
well as PyPI (FACT, in that commit's `uv.lock`).

The agent then ran that commit's suite with no network, with the options of its
nox session but without coverage or memray (FACT):

    PYTHONWARNINGS=always::FutureWarning timeout 2400 .venv/bin/python -m pytest \
      -q -rfE --tb=line --timeout=120 --durations=5 --strict-config \
      --strict-markers --disable-socket --allow-unix-socket \
      --allow-hosts=localhost,127.0.0.1,::1,127.0.0.0,240.0.0.0 test/

- It gave `2 failed, 1912 passed, 335 skipped, 4 xfailed, 247 warnings in
  182.85s`, one test at a time: March's lock has no pytest-xdist, which
  urllib3's CI started to use on 2026-10-15 (a37bc93b, "Run tests in parallel
  (#5263)") (FACT).
- Both failures are `test_http2_probe_blocked_per_thread`, in
  `test/contrib/test_pyopenssl.py`, the flaky test on which alone three of
  urllib3's latest six red runs failed (`notes/2026-11-16-pilot-candidates.md`).
  Under TLS 1.2, its assertion that two threads differ failed; under TLS 1.3, it
  reached the limit of 120 s, with a thread blocked on a lock at line 37 of
  `src/urllib3/http2/probe.py` (FACT).
- urllib3 fixed that lock's leak on 2026-10-04 (a164d79c, #5254) and the test's
  threads on 2026-10-07 (25edc55a, #5290), and the test exists since 2024-08-06
  (9316764e) (FACT). So from the window's first day to early October, the base
  branch holds that test, and a replay of that time may fail on it for a reason
  outside the pull request's change (INFERENCE).
- pytest printed its summary after about three minutes, but the process did
  not exit: `timeout` stopped it at 2400 s, with exit code 124 (FACT). The
  blocked thread is the likely cause, since at exit Python waits for the thread
  pool's threads (INFERENCE).
- A first run, with `-p no:cacheprovider` as well, ended in pytest's internal
  error after 756 tests had passed: the `limit_memory` mark of pytest-memray
  1.8.0, in March's lock, reads pytest's cache, which that option removes. The
  same option gave no such error in November's environment, which has
  pytest-memray 1.11.0 (FACT).

What it means for the harness (OPINION):

1. A time limit on each pytest process, besides the one on each test, and a way
   to keep the JUnit of a process that had to be stopped [VERIFY: that pytest
   writes it before it waits for the threads].
2. Each run takes the project's own pytest options at that commit, and turns no
   plugin off.
3. The SPEC's open question on failures inherited from the base branch weighs
   more than it seemed: for most of the window, a run may be red from that test
   alone, and it counts against the selector when it fails again on the rerun.

## Pull requests red in one job

A script read through `gh`, month by month, every pull request run of the
project's test workflow, opened the jobs of every failed run, and counted a pull
request as red when one of its runs had the job fail in a step that runs the
tests, the criterion of the search's third pass. It told pull requests apart by
their head's repository and branch. It listed the runs with
`repos/<repository>/actions/workflows/<file>/runs?event=pull_request&created=<first day>..<last day>`
and the jobs with `repos/<repository>/actions/runs/<id>/jobs?filter=latest`,
page by page, trying each call up to three times (FACT). A run's outcome is its
latest attempt's, so a red run that passed when run again counts as passed. No
call failed for good, and in every month with failed runs, the runs opened had
a job of that name (FACT).

| Project, job, window | Runs | PRs | Failed runs | PRs failed | PRs red |
|---|---|---|---|---|---|
| urllib3, "Ubuntu 3.12", 2026-03-16 to 2026-11-15 | 967 | 352 | 317 | 166 | 25 |
| poetry, "Ubuntu (Python 3.12) / pytest", 2026-03-16 to 2026-11-15 | 929 | 352 | 153 | 101 | 21 |
| urllib3, "Ubuntu 3.12", 2025-03-16 to 2026-03-15 | 173 | 58 | 64 | 19 | 0 |

urllib3's 352 pull requests and poetry's are different ones, from 198 and 174
repositories. By month, the pull requests red; one red in two months counts in
each, so the months add up to more than the window:

| | Mar 16-31 | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov 1-15 |
|---|---|---|---|---|---|---|---|---|---|
| urllib3 | 0 | 0 | 2 | 2 | 2 | 3 | 5 | 9 | 3 |
| poetry | 0 | 0 | 3 | 3 | 1 | 0 | 2 | 11 | 2 |

urllib3's 25: #3786 and #5050 in May; #5091 and #5093 in June; #5097 and #5103
in July; #5156, #5168 and #5173 in August; #4947, #5210, #5212, #5228 and #5237
in September; #5242, #5278, #5279, #5290, #5291, #5292, #5293, #5295 and #5296
in October; #5278, #5357 and #5375 in November. poetry's 21: #10849, #10911 and
#10924 in May; #10956, #10961 and #10964 in June; #10980 in July; #11010 and
#11051 in September; #10877, #10911, #11057, #11081, #11092, #11109, #11115,
#11131, #11132, #11135 and #11136 in October; #11226 and one whose number was
not found in November.

What the counts say:

- urllib3's 25 are the CI's, and some will not replay as red from their own
  change. Of those replayed so far, #5278 replayed green, and #5293, #5295 and
  #5296 failed only on the flaky probe test (FACT). Eight of October's nine ran
  on 2026-10-01 and 2026-10-02, among them two of dependabot's updates (#5292,
  #5293), one whose title says it documents (#5291) and the probe test's own fix
  (#5290): more likely failures of the base branch than of their changes. Some
  15 to 17 may replay as red from their own change (INFERENCE).
- poetry's 21 are a ceiling: the job's one test step runs the integration tests
  too, `poetry run pytest --integration -v`, which a replay with no network
  cannot run (FACT, in its `.github/workflows/.tests-matrix.yaml`).
- In the year before the window, no urllib3 pull request was red in the job,
  from November 2025, the first month in which GitHub lists any run, to
  2026-03-15 (FACT; see the next section).
- Both projects have the most in October, and neither has any from 2026-03-16
  to the end of April (FACT).

## How far back GitHub lists runs

By its own `total_count`, GitHub has no pull request run of urllib3's CI in any
month from 2025-03 to 2025-10, and two in 2025-11 (FACT). GitHub's changelog of
2026-08-27 ("Actions retention will cover checks, workflow runs, and statuses")
says that runs "were retained for 400+ days", and that from 2026-10-01 the runs
of public repositories would be kept 90 days at most; that post is marked
"Retired", and the runs of March 2026 are still listed on 2026-11-16 (FACT).
Which rule holds now is not checked [VERIFY]. So a window cannot start much
before late 2025, and if the runs were cut to 90 days, most of this window's
would go (INFERENCE). The count's output, in the scratchpad, holds each red
run's id, head, date and pull request.

## What so few pull requests allow

The one-sided 95% Clopper-Pearson upper bound of the miss rate, for n pull
requests with a red run, k of which had every failed test left out (computed on
2026-11-16):

| n | k = 0 | k = 1 | k = 2 |
|---|---|---|---|
| 15 | 18.1% | 27.9% | 36.3% |
| 20 | 13.9% | 21.6% | 28.3% |
| 25 | 11.3% | 17.6% | 23.1% |
| 30 | 9.5% | 14.9% | 19.5% |

A bound below 15% takes at least 19 pull requests with no miss, 30 with one, or
40 with two.

## What it leaves open

The bet asks for at least 30 pull requests with a red run, which neither
finalist's job gives over the window (INFERENCE, from the counts above).
Whether to change the bet is the user's. The options that the agent saw
(OPINION):

1. Both finalists, each in its own job: 46 pull requests red in the CI, some 25
   to 35 after the replays (INFERENCE), and a harness that also builds poetry's
   environments, one per head, without its integration tests.
2. A lower bar: fewer pull requests, or a bound above 15%, as the table above
   shows.
3. Faults put into the lines that each pull request changes, to see whether the
   selector picks the tests that catch them: hundreds of cases, but of injected
   faults, which is another hypothesis.

The agent recommended the first, after a count of poetry from late 2025 to
2026-03-15, which would give the two projects' total over all that GitHub lists.
