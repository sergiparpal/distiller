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

- Over the bet's window, 39 of urllib3's pull requests had "Ubuntu 3.12" fail
  in the CI, 25 of them seen to fail in a step that runs the tests and 13 in
  runs whose steps GitHub no longer gives; poetry's job failed in 31 (FACT).
  Where the steps show, 25 of 26 and 21 of 21 failed in the tests, so nearly
  all of the others likely did too (INFERENCE). The first counts had found 25
  and 21, since they looked for a failed test step, which GitHub drops after
  about 180 days (FACT, corrected on 2026-11-17).
- So the CI saw more than the bet's 30 in urllib3's window alone. But the bet
  counts the replay's red runs, which a pass in the rerun discards, and of the
  six pull requests replayed so far, two stayed red from their own change: at
  that share, some 13 for urllib3 alone, and some 30 for both finalists over
  all that GitHub lists (INFERENCE, from six). A sample of eleven more,
  replayed on 2026-11-17, kept five red, each from its own change: 7 of 17 in
  all, about 41%, which gives some 16 for urllib3's window alone, too few for
  a bound below 15% even with no miss (INFERENCE).
- A sample of ten of poetry's kept five red, each from its own change, and one
  gave no result: 6 of 12 with the two of before, 50%. Both finalists together
  would give some 31 red in the replay over the bet's window, and some 41 over
  all that GitHub lists, from November 2025 (INFERENCE).
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

These first counts could see a red run only while GitHub gave its job's steps,
for runs younger than about 180 days: see "GitHub drops a job's steps after
about 180 days", and the counts again below. A script read through `gh`, month
by month, every pull request run of the
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
| poetry, "Ubuntu (Python 3.12) / pytest", 2025-10-01 to 2026-03-15 | 297 | 90 | 45 | 27 | 0 |

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
- Before the window, these counts found no pull request red in the job, in
  urllib3 or in poetry, from November 2025, the first month in which GitHub
  lists any of their runs, to 2026-03-15; nor any from 2026-03-16 to the end of
  April (FACT). Both are blind spots, not zeros: see the next section.

## GitHub drops a job's steps after about 180 days

Neither count found a red run older than 2026-05-23 in urllib3 or 2026-05-24 in
poetry, though both projects had failed runs before then, so on 2026-11-16 a
script read the latest five failed runs of April and of October 2026 in each
(FACT):

| Failed runs read | Jobs given with no steps | Steps of the counted job | Counted job failed |
|---|---|---|---|
| urllib3, April | 31 of 31, in each run | 0 | 2 of 5 |
| urllib3, October | 0 to 3 of 31 | 15 | 1 of 5, in "Run tests" |
| poetry, April | all, in each run | 0 | 3 of 4; one run had no such job |
| poetry, October | 0 to 3 of 50 to 59 | 10 | 0 of 5 |

So GitHub still gives an old run's jobs and their conclusions, but not their
steps, and a count that looks for a failed test step sees no red run in them
(FACT). In the counts below, the latest failed job given with no steps ran on
2026-05-19 in urllib3 and 2026-05-17 in poetry, and the earliest given with its
steps on 2026-05-23 and 2026-05-24, 180 days before 2026-11-16 being 2026-05-20
(FACT); one later job came with no steps, on 2026-07-16, of a pull request that
failed in its tests in September. Which rule GitHub follows is not checked
[VERIFY].

## The counts again, by the job's outcome

On 2026-11-16 the script counted again, from 2025-11-01 to 2026-11-15, the pull
requests whose job failed in any step, and sorted them: red in tests, when a
run's job failed in a step that runs the tests; step unknown, when not so but a
run's failed job came with no steps; and failed elsewhere, the rest. It kept,
in a JSON file of the scratchpad, every failed run it opened, with its job's
outcome and failed steps as GitHub gave them that day (FACT). No call failed
for good.

| Project, days | Job failed | Red in tests | Step unknown | Failed elsewhere |
|---|---|---|---|---|
| urllib3, the bet's window, 2026-03-16 to 2026-11-15 | 39 | 25 | 13 | 1 |
| urllib3, all that GitHub lists, 2025-11-01 to 2026-11-15 | 48 | 25 | 22 | 1 |
| poetry, the bet's window | 31 | 21 | 10 | 0 |
| poetry, all that GitHub lists | 42 | 21 | 21 | 0 |

By month, the pull requests whose job failed (one with failed runs in two
months counts in each):

| | 2025-11 | 12 | 2026-01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11, to the 15th |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| urllib3 | 0 | 2 | 3 | 3 | 6 | 2 | 11 | 2 | 3 | 3 | 5 | 9 | 3 |
| poetry | 0 | 0 | 2 | 8 | 3 | 6 | 7 | 3 | 1 | 0 | 2 | 11 | 2 |

Of the pull requests whose failed job came with its steps, 25 of 26 in urllib3
and 21 of 21 in poetry failed in a step that runs the tests (FACT), so nearly
every pull request of unknown step likely did too (INFERENCE: those are older
runs, which may have failed otherwise).

## A sample of urllib3's red pull requests, replayed

On 2026-11-17, to measure how many of the CI's red pull requests a replay keeps
red, the agent chose eleven of urllib3's by a rule fixed before any replay: of
the window's pull requests whose job failed in the tests or in a run of unknown
step, 32 once the six replayed on 2026-11-16 are left out, ordered by the day
of their latest such run, one in every three from the first, each at the head
of that run. The user fetched the heads, 9 with `pull/<number>/head` and 2 by
their commit ids, and built each environment with the command of urllib3's nox
session all through the window, `uv sync --frozen --python 3.12 --group dev`
with the extras socks, brotli, zstd and h2: all 11 were built (FACT).

The agent replayed each head with no network: the whole suite once, with the
pytest options of urllib3's nox session but no coverage or memray and 120 s per
test, then once more the tests that failed, as a rerun file would. A pull
request is red when a test failed in both, as a red run is in the SPEC. pytest
ran inside a wrapper that wrote the node id of each failed test, as a pytest
plugin heard of it, and ended the process with `os._exit` as soon as pytest
returned, so that a thread left blocked could not keep it alive. No run hung,
and each whole run took 50 to 118 s, with no xdist, which none of these heads'
locks holds (FACT).

| PR | The CI's run | Whole run, node ids failed | Failed again | Replay |
|---|---|---|---|---|
| #3796 | 2026-03-17, step unknown | 1 | 1 | red |
| #4962 | 2026-04-13, step unknown | 9, one the probe test | 8 | red |
| #4996 | 2026-05-09, step unknown | 2, one the probe test | 1 | red |
| #5009 | 2026-05-12, step unknown | 14 | 14 | red |
| #5034 | 2026-05-19, step unknown | 1, the probe test | 0 | green |
| #5091 | 2026-06-24, red in tests | 0 | | green |
| #5103 | 2026-07-06, red in tests | 6 | 6 | red |
| #5173 | 2026-08-17, red in tests | 0 | | green |
| #5228 | 2026-09-07, red in tests | 1, the probe test | 0 | green |
| #5279 | 2026-10-01, red in tests | 0 | | green |
| #5291 | 2026-10-01, red in tests | 0 | | green |

Then, at the merge-base of each red pull request with `main`, the agent ran the
tests that had failed twice, with the head's environment and `PYTHONPATH` set
to the merge-base's `src/` (FACT). For #3796, #4962, #4996 and #5009 every one
of them passed there, so they failed from the pull request's change. For #5103
they failed there too; its change includes `uv.lock`, so the head's
environment holds the dependencies it brings, and those, not the code at its
merge-base, likely make them fail [VERIFY: with the merge-base's own
environment]. The titles fit the failing tests: socket options, the SSL context
of a proxy, header names, header types and pyOpenSSL's API (INFERENCE). A
first try of that check ran no test, since git does not
hold `src/urllib3/_version.py`, which installing writes: without it, urllib3
cannot be imported from a bare checkout (FACT).

What the sample says (INFERENCE unless labelled):

- With the six of 2026-11-16, two red from their own change, three failed only
  on the probe test, which a rerun would mostly discard, and one green, the
  replay kept 7 of 17 red, about 41%; 17 pull requests leave that share wide.
- Of the five of unknown step, from March to May, four replayed red; of the
  six seen red in the tests, from June to October, one (FACT). The CI's red
  runs of the later months may hold more failures inherited from `main`, such
  as those of 2026-10-01, or flaky ones [VERIFY].
- At 41%, the replay would keep some 16 of the 39 of urllib3's window: too few
  for a bound below 15%, which takes at least 19 pull requests with no miss,
  and too few for the bet's 30. Some 29 of both finalists' windows and some 37
  of both over all that GitHub lists, if poetry's share were the same, which is
  not measured.
- For the harness (OPINION): pytest inside such a wrapper, and a check at a
  merge-base needs that merge-base's generated files or its own environment.

## A sample of poetry's red pull requests, replayed

On 2026-11-17 the user asked for the same sample of poetry's. The rule was the
same, without the two pull requests whose replay of 2026-11-16 gave a result,
#11226 and the one of head 4240f5cb: ten of 29 (FACT). The user built each
environment as poetry's CI does, from the head's own `poetry.lock`, with the
latest poetry from PyPI run through `uv tool run`: `poetry env use
/usr/bin/python3.12`, then `poetry install --with github-actions`. All 10 were
built, with pytest-xdist and pytest-randomly but without pytest-timeout; the
heads came, 5 with `pull/<number>/head`, 4 by their commit ids, and 1 was in
the clone already (FACT).

The agent replayed them as urllib3's, with poetry's own pytest options from its
`pyproject.toml` (`-n logical -ra`, and pytest-randomly's order), without
`--integration`, and with no limit per test, since the environments have no
pytest-timeout (FACT):

| PR | The CI's run | Whole run, node ids failed | Failed again | Replay |
|---|---|---|---|---|
| #10742 | 2026-04-03, step unknown | 3 | 1 | red |
| #9805 | 2026-04-16, step unknown | 2 | 1 | red |
| #10881 | 2026-05-03, step unknown | 4 | 3 | red |
| #10908 | 2026-05-17, step unknown | 1 | 1 | red |
| #10956 | 2026-06-16, red in tests | 1, after 1679 s | the rerun reached the limit of 2400 s | no result |
| #10980 | 2026-07-29, red in tests | 2 | 2 | red |
| #11115 | 2026-10-08, red in tests | 0 | | green |
| #11132 | 2026-10-09, red in tests | 0 | | green |
| #11135 | 2026-10-10, red in tests | 0 | | green |
| #11057 | 2026-10-12, red in tests | 0 | | green |

At the merge-base, with the head's environment, the tests that had failed twice
passed for #10742, #9805, #10881 and #10908, and #10980's two are tests that the
pull request adds, which its merge-base does not hold (FACT). So each of the
five failed from its own change. #10956 changes the prompts of `poetry init`,
and the test that took 28 minutes gives that command scripted answers: it
likely waited for an answer that never came, a red run from its own change that
a limit per test would have ended [VERIFY].

What it says (INFERENCE unless labelled):

- With the two of 2026-11-16, one red from its own change and one ended in
  pytest's internal error, the replay kept 6 of 12 red, 50%.
- As in urllib3, those of unknown step, from April and May, replayed red, 4 of
  4, and those of October green, 4 of 4 (FACT). In the CI, #11057 had failed on
  the test of `extractall` on which #11136 and #11109 failed within two days
  (`notes/2026-11-16-pilot-candidates.md`), and it passes replayed in its own
  environment: likely a failure of that time's `main`, not of its change.
- Both finalists together, at 41% and 50%: some 31 pull requests red in the
  replay over the bet's window, and some 41 over all that GitHub lists, where
  the months that replay red more often are older. A bound below 15% takes at
  least 19 pull requests with no miss, 30 with one, or 40 with two.
- For the harness (OPINION): poetry needs a limit per test, such as
  pytest-timeout added for the replay alone, or else its runs that hang are
  rejected.

## How far back GitHub lists runs

By its own `total_count`, GitHub has no pull request run of urllib3's CI in any
month from 2025-03 to 2025-10, and two in 2025-11; none of poetry's test
workflow in 2025-10, and 14 in 2025-11 (FACT). GitHub's changelog of
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

Written on 2026-11-16, from the first counts, and corrected on 2026-11-17: the
options below assumed that neither finalist's job gave 30 red pull requests in
the CI over the window, which held only for the runs whose steps GitHub still
gives. Whether to change the bet is the user's. The options that the agent saw
(OPINION):

1. Both finalists, each in its own job: 46 pull requests red in the CI by the
   first counts, 70 over the window and 90 over all that GitHub lists by the
   job's outcome, and a harness that also builds poetry's environments, one per
   head, without its integration tests.
2. A lower bar: fewer pull requests, or a bound above 15%, as the table above
   shows.
3. Faults put into the lines that each pull request changes, to see whether the
   selector picks the tests that catch them: hundreds of cases, but of injected
   faults, which is another hypothesis.

The agent recommended the first, after a count of poetry from late 2025 to
2026-03-15, which would give the two projects' total over all that GitHub lists.
The user accepted it on 2026-11-16, and that count found no red pull request
(FACT), but all its months are older than 180 days.

With the counts by the job's outcome, the CI saw 39 pull requests fail in
urllib3's window alone. What decides the bet's minimum is how many of them the
replay keeps red: a failure that passes in the rerun does not count (SPEC), and
of the six replayed so far, two stayed red from their own change, three failed
only on the flaky probe test, which a rerun would mostly discard, and one
passed. At a third, the replay would keep some 13 of urllib3's window, some 23
of both finalists' windows, and some 30 of both over all that GitHub lists
(INFERENCE, from six pull requests of October and November). On 2026-11-17 the
user asked for a sample of about ten of urllib3's, over the whole window, to
measure that share before the bet is rewritten. It kept 7 of 17 red in all, so
some 16 of urllib3's window, and with both finalists some 29 over their windows
and some 37 over all that GitHub lists, if poetry's share were the same
(INFERENCE; see "A sample of urllib3's red pull requests, replayed"). The same
day the user asked for the same sample of poetry's, to measure its share. It
kept 6 of 12 red, 50%, so both finalists would give some 31 over the bet's
window, at the edge of its 30, and some 41 over all that GitHub lists, enough
for a bound below 15% with up to two misses (INFERENCE; see "A sample of
poetry's red pull requests, replayed"). Which pilots, which window and which
minimum the bet takes is the user's to write.

The user wrote it on 2026-11-17: both finalists, over the pull requests whose
job failed in a CI run that started from 2025-12-01 to 2026-11-15 (D-010).

## The window's red pull requests, kept

On 2026-11-17 the agent wrote `notes/2026-11-17-window-red-runs.csv` from the
window counts of 2026-11-16, with the bet's rule: the pull requests whose job
failed in a CI run that started from 2025-12-01 to 2026-11-15, in any step,
each with its latest such run, whose head the replay takes. It has one row per
pull request, 90 in all, 48 of urllib3's and 42 of poetry's, from 2025-12-03 to
2026-11-14, and no user or branch name: the project, the pull request's number,
the run's id and start, the head that the run tested, the job's outcome as
GitHub gave it on 2026-11-16, and its failed steps (FACT).

| Job's outcome in the latest such run | urllib3 | poetry |
|---|---|---|
| failed in a test step | 25 | 20 |
| failed, steps no longer given | 22 | 21 |
| failed in another step | 1 | 1 |

Two rows are worth knowing (FACT). urllib3's in another step has no number,
since the count looked numbers up only for the pull requests red in tests or of
unknown step; its run id gives it. Its job failed in "Set up job" on
2026-05-26, as in two more of its runs that minute, and its later runs did not
fail. poetry's in another step is #10956, whose run of 2026-06-17 failed with no
step given as failed, the day after a run red in its tests, so its row has the
later run's head; its sample's replay, at the earlier head, waited for an answer
that never came, so its job may have hung until a time limit [VERIFY]. One more
row, poetry's of 2026-11-01, has no number, since the count did not find it;
its run id gives it.
