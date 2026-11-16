# Replaying a project's pull requests offline

What it would take for the Distiller, as Slice 1 has it, to evaluate past pull
requests of a project whose CI it cannot join, such as python-poetry/poetry or
urllib3/urllib3 (`notes/2026-11-16-pilot-candidates.md`), and what that changes
against the SPEC's Deployment. Nothing here is decided, and nothing was run for
it: the next bet, its pilot and its slice are the user's.

Labels: **SPEC** = what `docs/SPEC.md` says; **INFERENCE**; **OPINION**;
**[VERIFY]** = not checked.

## What Slice 1 assumes

SPEC, Constraints and Deployment: the tool is a step of the pilot's own pull
request job on GitHub Actions, after the full pytest run, which writes its JUnit
in one invocation without `--junit-prefix`. H is the commit that run tested, on
`pull_request` the merge commit in `github.sha`. The coverage at M is recorded on
the base branch by a job of its own, at least once a day, with
`--cov-context=test`, `COVERAGE_CORE=ctrace` and no static context, and each run
is given the newest recorded M that is the merge-base or one of its ancestors.
The checkout is a full clone, and the base is given as `origin/<branch>`. The
step runs `python -P -m distiller` from a fixed commit of this repository, with
the same `coverage` as the job that records M, and each job writes its own
record file.

None of that is the pilot's to give when the pilot is someone else's project.

## What the tool needs, and where a replay gets it

The command line stays as it is (SPEC, Command line): `evaluate` takes the pull
request's number, H, the base, the coverage file, M, the JUnit file, the rerun
file, the rootdir, the floor configuration, the record file and the checkout,
all of them names and paths. A replay would be a harness that makes each of them
for a past pull request and then runs the tool unchanged (INFERENCE).

For each pull request:

1. **The checkout**: a full clone of the project, with every pull request's head
   fetched, as by `git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'`.
   GitHub keeps `refs/pull/<n>/head` for closed pull requests too [VERIFY].
2. **H**: Slice 1's H is the merge commit that the run tested, which GitHub
   moves as the base moves and drops once the pull request is closed [VERIFY].
   Two ways:
   - the pull request's head, which is always there: the diff from its
     merge-base with B is the pull request's own change, but its tests run
     without the base's later commits, so a failure that came only from the
     merge would not show (INFERENCE);
   - the merge commit rebuilt, merging the head into the base commit that the
     run saw: closer to the run, but a merge that conflicts, or that GitHub
     made otherwise, gives another tree [VERIFY]. Which base commit each run saw
     would come from its `pull_request` event [VERIFY].
3. **B**: the base commit that the run saw, given by its full id. The SPEC's
   `origin/<branch>` would name today's tip, not that run's.
4. **M**: the merge-base itself, or one older ancestor shared by several pull
   requests. With the merge-base, each pull request costs one more suite run and
   its rows are as fresh as they can be; with a shared M, fewer runs and older
   rows, which the SPEC's open question on matrix age leaves open. OPINION: the
   merge-base, since the candidates' Linux test jobs take about a minute.
5. **The coverage at M**: the project's suite at M, in M's environment, with
   `--cov-context=test`, `COVERAGE_CORE=ctrace` and no static context, under the
   version of `coverage` that the tool runs with. A project whose configuration
   sets a static context, or whose tests run under xdist, needs a look first
   [VERIFY].
6. **The full run's JUnit**: the suite at H, in H's environment, in one pytest
   invocation with `--junitxml` and no `--junit-prefix`, on one Linux CPython,
   such as the 3.12 that the candidates' search counted. The run that decides
   red or green is then the replay's, not the CI's: a failure that the CI saw
   may pass when replayed, and the record holds what the replay saw (INFERENCE).
7. **The rerun file**: the tests that failed in the replayed full run, run again
   at H, as the last pilot's workflow did.
8. **The environment of each commit**: rebuilt from what the commit holds,
   poetry's `poetry.lock` or urllib3's `uv.lock`, which its nox session installs
   with `uv sync --frozen`, with the Python that the project's CI job used. Installing reaches PyPI,
   though the tool itself opens no connection (SPEC, Agent safety). How far back
   that still works is what bounds the window [VERIFY].
9. **The floor configuration**: chosen before the first record, as D-005 chose
   the last pilot's, from the files that the project's tests read and coverage
   cannot see; until that is looked at, the default patterns alone.
10. **The record file**: one per replay, which the report reads with the others.

## Which pull requests

The miss rate counts only the pull requests with a red run, but the savings
count every evaluated run (SPEC). Replaying only the pull requests that the CI
saw red would bias the savings toward runs that failed (INFERENCE). Two ways:
replay every pull request of a window, or only the red ones and leave the
savings out of that replay's report. Either way the window would be chosen
before any record, by dates, as D-005's floor and D-006's exclusions were chosen
before the figures they bear on: D-007 asks for a pilot chosen before any figure
from it.

## Cost

Per pull request: one suite run at M, one at H, and a rerun of the tests that
failed. With a Linux test job of about a minute when it passes, 0.9 min for
poetry and 1.3 min for urllib3 on GitHub's runners, 30 red pull requests take
some 90 suite runs, about an hour and a half, besides building the environments;
every pull request of a three-month window, a few hundred runs (INFERENCE). They
would run on the user's machine or in a CI of the user's own. The SPEC's limit of
60 s per evaluation bears on the tool, not on the suite runs, and holds as it is.

## What changes against the SPEC

Each of these is the user's to decide, in the next bet's slice:

- Deployment: the step in the pilot's pull request job, after its full run,
  becomes a harness outside the pilot's CI.
- H: the merge commit in `github.sha` becomes the pull request's head, or a
  rebuilt merge (point 2).
- M: the newest recorded M that is the merge-base or one of its ancestors
  becomes an M that the replay records for the run, the merge-base or a shared
  ancestor (point 4).
- The base: given by a full commit id, not as `origin/<branch>` (point 3).
- The first week's check of the records by hand against the CI's list of runs
  becomes a check of the replay's red and green against the CI's.

The non-goal that Slice 1 never decides which tests run still holds: the replay
runs the full suite at every H. The tool's code needs no change for any of these
(INFERENCE): they are inputs that it takes on its command line.

## What replaying six of urllib3's red pull requests showed

On 2026-11-16 the agent replayed, with no network, the heads that the latest six
red runs of urllib3's job "Ubuntu 3.12" had tested
(`notes/2026-11-16-pilot-candidates.md`), with no tool: only the suite, to see
which red runs fail again. What it shows for the points above (FACT, unless
labelled):

- Point 1: fetching the heads by their commit ids brought nothing into the
  clone, while `git fetch origin pull/<n>/head:refs/pr/<n>` brought every head
  that the runs had tested, the older ones of pull requests pushed to again
  afterwards included.
- Point 2: for the one red run that did not replay, #5278, the pull request's
  head and its merge into the last commit of `main` before the run both passed,
  so no case yet shows the merge mattering.
- Point 6: a red run of the CI can replay green: #5278 failed in the CI with 57
  failed tests and 1 error, and passed replayed, at its head, at that merge and
  with `--memray`, as its CI runs pytest. The record then holds the replay's
  green, as point 6 says.
- Point 7: three of the six failed only on `test_http2_probe_blocked_per_thread`,
  which failed in 3 of 10 runs at the commit of `main` before the first of their
  runs, and in 0 of 10 at today's `main`: a flaky test of the base branch at the
  time. A rerun discards such a failure when the test passes the second time;
  when it fails again, the run is red for a reason outside its diff, and counts
  against the selector, as the SPEC's open question on inherited failures says.
- A limit per test belongs in the replay: one replay ran past 900 s with no
  result, and the same head, run again with `--timeout=120`, took 37 s with no
  test reaching the limit. A replay that hangs stalls every one after it.
- Point 8: four heads, up to six weeks older than the commit that the
  environment was built from, and whose `uv.lock` or `pyproject.toml` differ
  from its, ran in that environment; older ones were not tried.
- Cost: each replay of the suite took 24 to 40 s on 16 threads, by pytest's own
  count, as the estimate under Cost assumed.
- Reading the CI's results through `gh`: `gh run view --job <id> --log-failed`
  gave an empty log for every job asked for, and the job's log from the API,
  `gh api repos/<repo>/actions/jobs/<id>/logs`, holds pytest's output with its
  colour codes, which have to be taken out before its lines are read.
