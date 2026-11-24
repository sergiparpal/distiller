# New pilots looked for, 2026-11-21

Option B of `2026-11-20-next-bet-options.md`, which the user chose on
2026-11-21: pilots whose figures nobody has seen, for a next bet that the user
writes. This note holds the first steps of the plan that the user approved that
day (note 103 of `TASKS.md`): the candidates, D-024's criteria applied to them
from CI outcomes alone, the CSVs of those that pass and their clones. The
Distiller ran on none of them, and none of their suites ran. Nothing is decided
here: the pilots, the window and the bet are the user's.

Labels: **FACT** = in the output of the scripts below, run on 2026-11-21;
**INFERENCE**; **OPINION**; **[VERIFY]** = not checked.

## How

The rules are D-024's, written before any candidate's CI was read. Since D-013
the agent's shell runs `gh`, with the read-only token of `GH_TOKEN`, so the
scripts ran from it, and this time they are kept, in `pilot-search/`, beside
their outputs:

- `github.py`: the calls, through `gh api`, every one a GET or a GraphQL query,
  tried again on GitHub's passing errors, and paused when the rate limit runs
  low. A listing of runs filtered by event or date gives at most 1,000 runs, so
  `list_runs` splits its span of dates in two until each part gives fewer.
- `candidates.py`: D-024's search, split by stars so that each search gives
  every repository it counts, and, for each repository with a lock file and for
  each of the 28 of 2026-11-16, the files that the criteria look for at the
  root of its default branch. It writes `candidates.json`.
- `funnel.py`: D-024's criteria, cheapest first, for each candidate that passes
  the files: at least 20 failed pull request runs; its job; at most how many
  pull requests had a failed run of the job's workflow; the job's median
  duration; the base branch; the red pull requests, each with its latest run
  whose job failed; their authors; and the steps they failed in. It stops a
  candidate at the first criterion that it fails, keeps each result in a cache
  outside the repository, and writes `funnel.json` and, for each candidate that
  passes, `<project>-red-runs.csv`, in the columns of
  `2026-11-17-window-red-runs.csv`, and `<project>-pull-request-runs.json`,
  every pull request run of the job's workflow, for option C.
- `fetch_heads.py`: a passing candidate's clone, with each red pull request's
  head kept by a ref `refs/window/<run id>`.

No output holds a user name, a branch name or a title: an author is a number
within its project, and a repository's name is kept, since it names the
project. Where a run gives no pull request, as GitHub's runs from forks do, its
pull request is the one whose head has the run's owner and branch and that was
open when the run was created, read from the project's pull requests. GitHub's
`commits/<sha>/pulls`, tried on six heads of urllib3's window, gave the number
of one only: for a commit that is not on the default branch, it lists only open
pull requests (FACT).

## What GitHub still gives

On 2026-11-21, urllib3's runs of 2025-12-03 and 2025-12-05 in the window's
manifest, 19903409392 and 19955298005, answered HTTP 404, while its run of
2026-01-17 and poetry's of 2026-01-01 were still there; poetry's oldest pull
request run still listed was of 2025-12-11 (FACT). So GitHub keeps a run some
345 to 350 days, and drops about a day of the oldest each day (INFERENCE). The
window's replay needs none of those runs, but a new pilot's counts lose them a
day at a time, and with them the heads that only a run named.

## The funnel checked on urllib3 and poetry

Before the candidates, `funnel.py` ran on the window's two pilots, which are no
candidates, to check it against the manifest, `2026-11-17-window-red-runs.csv`
(FACT, 2026-11-21, 393 calls for urllib3 and 230 for poetry):

| | urllib3 | poetry |
|---|---|---|
| Job that D-024's rule picks | "Ubuntu 3.12", workflow "CI" | "Ubuntu (Python 3.12) / pytest", workflow "Tests" |
| Red pull requests | 47 | 42 |
| Of those with steps, failed in a test step | 24 of 24 | 19 of 20 |
| Authors, most by one | 41, 3 | 34, 3 |
| Base branch: push runs in which the job failed | 0 | 0 |
| Median of a successful job | 1.29 min | 1.09 min |

Both pass D-024's criteria, and the rule picks the job that each pilot's
configuration names. Against the manifest:

- urllib3: of its 48 rows, the runs of 2025-12-03 and 2025-12-05, #3720's and
  #3729's, are gone from GitHub. The count adds #3758, whose job "Ubuntu 3.12"
  failed in run 21097199737, of 2026-01-17: the manifest lacks it. And the
  manifest's row for run 25715213323, of 2026-05-12, names #5047, a pull request
  opened ten days after the run, from another account's branch of the same
  name; the run is #5007's, whose head has the run's owner and branch and which
  was open then. Both are note 104 of `TASKS.md`. #5021's run, 25940853270,
  came from a fork deleted since, which leaves the run with no owner; the funnel
  then looks for its pull request among those from deleted forks, by the run's
  branch, and finds #5021, as it found #5007, #3758 and #3759 for their runs.
- poetry: of its 42 rows, #11226's run, 43162239778, answers HTTP 404 since
  GitHub hides that pull request; #11151, hidden too, comes with no number; and
  #10751's run came from a deleted fork, which this check ran before the funnel
  looked among deleted forks. The count adds #11240, of after the window. No
  pull request of poetry's window is missing.

So the funnel's counts agree with the manifest's, but for the runs that GitHub
has dropped or hides, and where the manifest is wrong.

## The candidates

`candidates.py` ran on 2026-11-21 in 1,177 calls (FACT, `pilot-search/candidates.json`).
D-024's query gave 4,345 repositories, in eight ranges of stars, from 1,000 to
1,249 up to 50,000 and more, each of which the search gives whole. urllib3 and
poetry were among them, and are out. Of the 28 of 2026-11-16, 26 were among the
4,345, two of them under a new name, encode/starlette as `Kludex/starlette` and
jazzband/pip-tools as `pypa/pip-tools`, and two came from the list alone, jinja
and packaging. The first `candidates.json` held the two renamed projects twice,
once under each name that led to them; on 2026-11-22 `merge_renamed` made each
one entry, with no new call, and the funnel had read starlette once, the second
time from its cache. Of the 4,345 left:

| | Repositories |
|---|---|
| With `uv.lock` at the root of the default branch | 984 |
| With `poetry.lock` | 129 |
| With both | 9 |
| With either, so 1,104, but naming no pytest | 142 |
| Passing the files: a lock file, pytest named, not archived | 962 |

Of the 28 of 2026-11-16, 15 pass the files: attrs, click, flask, isort, jinja,
marshmallow, pluggy, pytest, rich, sentry-python, sphinx, starlette (now
`Kludex/starlette`), textual, typer and werkzeug.

## The funnel

`funnel.py` ran from 2026-11-21 at 16:38 UTC to 2026-11-22 at 20:14 UTC, first
in four processes, each a fourth of the candidates, then one process for each
candidate that an error had stopped, in at least 78,000 calls, at GitHub's 5,000 an
hour (FACT, from its logs). The last two, Chia-Network/chia-blockchain and
datamodel-code-generator, whose runs hold hundreds of jobs each, took most of
2026-11-22. Each candidate stops at the first criterion it fails, cheapest first
(FACT, `pilot-search/funnel.json`, 962 results):

| Stopped at | Candidates |
|---|---|
| no Linux CPython 3.12 job with a test step | 413 |
| fewer than 20 failed pull request runs | 226 |
| fewer than 20 red pull requests | 97 |
| fewer than 20 pull requests with a failed run of the job's workflow | 78 |
| the job's median duration above 5 minutes | 76 |
| one author has more than a third of the red pull requests | 20 |
| fewer than 5 authors | 9 |
| fewer than 80% of the red pull requests failed in a test step | 9 |
| no push run of the job's workflow on the default branch | 8 |
| the job failed in 10% or more of the base branch's push runs | 5 |
| the job ran in no push run of the default branch | 2 |
| no successful pull request run of the job | 1 |
| passed | 18 |

Near misses: browser-use and opentelemetry-python-contrib had 19 red pull
requests each, and prefect's job a median of 5.23 minutes. Of the last two,
datamodel-code-generator had 26 red pull requests by 3 authors, one with 19,
and chia-blockchain 391, too few of which failed in a test step (FACT).

On the way, the funnel met five things that its first version did not take,
each fixed before the candidates it stopped were read again, none of them a
change to D-024's rules (FACT): an HTTP/2 `stream error` and a refused
connection, now tried again as GitHub's passing errors are; a `gh` call that
hung, now stopped after 300 s and tried again; runs with hundreds of jobs, whose
page of 100 jobs GitHub answered with HTTP 502 five times running, now read in
pages of 20; a pull request of a run with no base repository; and a run whose
head repository has no owner, from a fork or an account deleted since.

## Those that pass

FACT, by red pull requests. "Base" is the base branch's push runs in which the
job failed, of those in which it ran, where the count stops once fewer than 10%
can have failed (`count_base_failures`).

| Repository | Job | Red PRs | Oldest red run | Authors, most by one | By bots | Failed in a test step | Base | Median, min | PR numbers |
|---|---|---|---|---|---|---|---|---|---|
| modelcontextprotocol/python-sdk | checks / test (3.12, locked, ubuntu-latest) | 295 | 2026-01-16 | 196, 13 | 4 | 146 of 160 | 0 of 2 | 1.52 | 1591 to 3890 |
| pydantic/pydantic | Test ubuntu-latest / 3.12 | 163 | 2025-12-27 | 95, 32 | 15 | 81 of 93 | 0 of 33 | 3.16 | 10834 to 14290 |
| zigpy/zha-device-handlers | shared-ci / Run tests Python 3.12 | 147 | 2025-12-18 | 98, 11 | 0 | 69 of 69 | 0 of 1 | 0.80 | 3986 to 5760 |
| The-PR-Agent/pr-agent | Unit tests (Python 3.12) | 135 | 2026-09-16 | 42, 32 | 10 | 135 of 135 | 0 of 3 | 4.42 | 3129 to 5088 |
| PennyLaneAI/pennylane | tests / data-tests (3.12) / data-tests (3.12) | 83 | 2026-06-30 | 19, 15 | 0 | 52 of 61 | 0 of 3 | 2.20 | 9684 to 10573 |
| ManimCommunity/manim | test (ubuntu-22.04, 3.12) | 73 | 2026-01-12 | 40, 12 | 0 | 44 of 45 | 0 of 1 | 4.44 | 3112 to 5139 |
| EvoScientist/EvoScientist | pytest (ubuntu-latest, 3.12) | 53 | 2026-06-09 | 19, 14 | 1 | 51 of 51 | 1 of 11 | 2.48 | 271 to 872 |
| NVIDIA-NeMo/DataDesigner | Test (Python 3.12 on macos-latest) | 42 | 2025-12-16 | 9, 12 | 0 | 7 of 7 | 0 of 1 | 0.05 | 118 to 1100 |
| feyninc/chonkie | test (3.12) | 40 | 2025-12-22 | 8, 12 | 12 | 15 of 15 | 4 of 41 | 2.39 | 242 to 657 |
| pallets/click | 3.12 | 36 | 2026-01-01 | 27, 4 | 0 | 13 of 13 | 0 of 1 | 0.33 | 2864 to 3873 |
| wemake-services/wemake-python-styleguide | build (3.12) | 36 | 2025-12-19 | 18, 7 | 8 | 15 of 15 | 0 of 1 | 2.57 | 3577 to 3882 |
| electricitymaps/electricitymaps-contrib | Python / Tests (3.12) | 26 | 2026-01-12 | 9, 8 | 1 | 8 of 8 | 0 of 1 | 1.99 | 8515 to 8897 |
| soxoj/maigret | build (3.12) | 25 | 2026-03-22 | 12, 7 | 4 | 3 of 3 | 0 of 1 | 2.58 | 2205 to 3467 |
| elastic/rally | unit Ubuntu 3.12 | 25 | 2025-12-15 | 10, 8 | 2 | 5 of 5 | 0 of 4 | 0.83 | 1868 to 2181 |
| gdsfactory/gdsfactory | test_code (3.12, ubuntu-latest) | 25 | 2026-07-20 | 11, 7 | 0 | 17 of 18 | 1 of 11 | 1.57 | 4515 to 4939 |
| PrimeIntellect-ai/verifiers | Unit (3.12) | 25 | 2026-10-19 | 7, 7 | 0 | 24 of 25 | 1 of 20 | 1.30 | 2568 to 3212 |
| mitmproxy/mitmproxy | test (ubuntu-latest, 3.12) | 24 | 2025-12-17 | 18, 4 | 4 | 12 of 14 | 0 of 8 | 0.88 | 7985 to 8598 |
| pydantic/pydantic-settings | test py3.12 on ubuntu-latest | 20 | 2025-12-22 | 18, 3 | 3 | 10 of 10 | 0 of 1 | 0.76 | 729 to 1147 |

Where the oldest red run is recent, as pr-agent's of September, verifiers' of
October or gdsfactory's of July, the job likely took its name then, and its
runs under an older name are not counted, as D-024's Consequences say
(INFERENCE).

The first of D-024's checks of a finalist is whether its job builds its
environment from the lock file. Read in each workflow, and in what it calls, at
the head of its default branch on 2026-11-22 (FACT), two do not:

- DataDesigner: the rule picked `Test (Python 3.12 on macos-latest)`, a job on
  `ubuntu-latest` whose one step, `Check all tests passed`, checks that the
  workflow's test jobs passed, those on macOS among them. It builds no
  environment, as its median of 3 seconds shows, and its red runs include the
  macOS jobs' failures. It matches the rule's words, labels, name and a step
  holding "test", but not what the rule is for, and this check is where it
  stops.
- PennyLane: its unit tests install with `uv pip install --upgrade` from its
  dependency groups and a built wheel, not from `uv.lock`.

The other 16 build from their lock file: with `uv sync`, as python-sdk
(`--frozen`), manim and rally (`--locked`), pr-agent (`--frozen`), pydantic,
pydantic-settings, verifiers, gdsfactory, electricitymaps-contrib, EvoScientist
and zha-device-handlers (whose shared workflow falls back to its requirements
files when `uv sync` fails); with `uv run`, as chonkie; with tox's
`uv-venv-lock-runner`, as click and mitmproxy; or with `poetry install`, as
maigret and wemake-python-styleguide. A sync without `--frozen` or `--locked`
uses the lock file as it is unless `pyproject.toml` no longer matches it.

All 18 are cloned in `~/code/distiller-pilots/<project>`, 3.0 GB in all, with each
red pull request's head kept by `refs/window/<run id>`: all of them but two of
python-sdk's 295, runs 21068951903 and 21069462837, whose heads GitHub no
longer gives by commit or by `pull/<n>/head` (FACT). At those heads, the lock
file is there for every red pull request but two of zha-device-handlers' 147
(FACT), so that no finalist comes near the Bet's 20% of environments not built
for want of one.

## Pull request numbers that two pilots share

Of the 190 pairs among the 18 and the window's two pilots, 25 share at least one
pull request number among their red pull requests: manim and pr-agent 10,
python-sdk and wemake-python-styleguide 8, manim and zha-device-handlers 8,
pr-agent with zha-device-handlers and with python-sdk 7 each, click and
python-sdk 7, and so on down to one (FACT). Slice 1's report counts pull
requests by number alone, and the harness refuses a manifest in which two pilots
hold one number (D-011). So the next bet either takes pilots that share no
number, or comes with a slice in which the report counts a pull request by its
project and its number; the user's choice, when the bet is written.

## What comes next

- D-024's other checks of each of the 16 finalists that build from their lock
  file, and of Chia and datamodel-code-generator if they pass: a pilot
  configuration for each, like `pilots/urllib3.toml`, written from its job, and
  then `pilot-search/feasibility.py`, which builds its environments at its
  oldest and newest red heads, runs its suite twice at three base commits to
  find the tests that fail with no change, and replays a sample of ten red pull
  requests with its own suite alone. At some 50 minutes a finalist, some 14
  hours for 16 (INFERENCE, from the window's replay, where a pull request took a
  median of two minutes).
- A note from which the user writes the bet: the expected number of pull
  requests with a red run, from each sample's share, the table of bounds, and
  the hours of steps.
- Note 102 checked again, before the bet is written and by 2026-12-09.

## The finalists checked, with no run of the Distiller

On 2026-11-22 `pilot-search/feasibility.py` ran D-024's checks of each of the
16 finalists that build from their lock file (FACT, its outputs
`pilot-search/<project>-feasibility.json`): its environments built at the heads
of its oldest and newest red pull requests; its suite run twice at the base
commits of its oldest, middle and newest red pull requests, whose failures D-024
deselects; and a sample of ten red pull requests, spread evenly by date, each
built and run at its head with those tests deselected, then rerun on the tests
that failed. It runs the harness's own `checkout`, `environment` and `suite`, so
that each build and each run is the replay's, and never the Distiller. Each
finalist has a pilot configuration, `pilot-search/pilots/<project>.toml`,
written from its job: the job's install, with `--frozen` for uv; the job's
pytest options, less those that only print or measure, and less `-n` where
pytest-xdist is not in the lock of every red head; a path that the job gives
pytest, as `-o testpaths=...`, so that a rerun runs only the tests that failed;
120 s a test; and pytest-timeout added wherever a red head's lock lacks it.

The first pass, at 14:08 UTC, found two things that the configurations had to
take, and all 16 ran again (FACT):

- uv prefers a Python that it installed itself, and the user's machine had uv's
  CPython 3.12.13 in `~/.local/share/uv/python`: an environment built with it
  has its `.venv/bin/python` in the home, which the suite's sandbox hides, so
  every suite run ended at once, `bwrap: execvp ... No such file or directory`,
  exit 1 and no failed test (note 105). Every uv command now names
  `/usr/bin/python3.12`, and runs as uv 0.13.8, through `uv tool run --from
  uv==0.13.8`, since the user's uv, 0.11.23, is older than some of the locks'
  `required-version`.
- verifiers' pyproject turns on uv's preview features, with which uv 0.13.8
  keeps the project's environment in its cache under the home and makes `.venv`
  a link to it: its sync takes `--no-preview`.

What the second pass gave, by finalist (FACT): of the 15 builds, the two
environments, the three base commits and the ten heads of the sample, how many
did not build; the tests deselected; and of the sample, the pull requests whose
head failed in the full run and again in the rerun, red as a replay would count
them if the tool caught or missed them.

| Finalist | Not built, of 15 | Deselected | Red, of 10 | CSV rows | Expected red PRs (INFERENCE) |
|---|---|---|---|---|---|
| zha-device-handlers | 0 | 0 | 9 | 147 | 132 |
| pydantic | 4 | 1 | 5 | 163 | 82 |
| EvoScientist | 0 | 2 | 7 | 53 | 37 |
| click | 0 | 0 | 9 | 36 | 32 |
| python-sdk | 0 | 1 | 1 | 295 | 30 |
| rally | 2 | 0 | 8 | 25 | 20 |
| maigret | 1 | 9 | 7 | 25 | 18 |
| chonkie | 0 | 134 | 4 | 40 | 16 |
| mitmproxy | 0 | 3 | 6 | 24 | 14 |
| pydantic-settings | 0 | 0 | 7 | 20 | 14 |
| gdsfactory | 1 | 6 | 5 | 25 | 12 |
| electricitymaps-contrib | 7 | 9 | 4 | 26 | 10 |
| verifiers | 0 | 1 | 2 | 25 | 5 |
| wemake-python-styleguide | 0 | 12 | 1 | 36 | 4 |
| manim | 0 | 0 | 0 | 73 | 0 |
| pr-agent | 15 | 0 | 0 | 135 | 0 |

The expected count is the sample's share times the CSV's rows, from ten pull
requests each, so it can be far off either way (INFERENCE).

What stands out (FACT, from each step's output, but where marked):

- pr-agent builds nowhere with the harness as it is: its pyproject's
  `required-version` asks for uv `==0.12.10` at its older heads and `>=0.13.8`
  at its newer ones, so no one uv builds them all, and the harness installs its
  plugins with the user's own uv from the worktree, where the same check
  refuses it.
- electricitymaps-contrib did not build 7 of 15: `required-version` asks for uv
  `>=0.9, <0.10` at older heads and `>=0.13.4` at newer ones, which the plugin
  install's uv 0.11.23 fails, and its oldest base commit has no `uv.lock`.
- pydantic did not build 4 of 15: `required-version >=0.13.0` at the plugin
  install, and at one older head pydantic-core's Rust did not compile with Rust
  1.100. Of its sample's runs, one ended with exit 139, a test of deep
  recursion that crashed the interpreter, and two with exit 4, a
  `SyntaxError` and an `IndentationError` in the pull requests' own code.
- manim's suite does not run in the sandbox: its `tests/conftest.py` asks for an
  OpenGL context as pytest starts, which its CI gets from a virtual display, and
  with none pytest stops with an internal error, exit 3, before any test. That
  is D-024's check that the suite runs inside bubblewrap, and manim fails it.
- python-sdk: nine of its sample's heads passed every test. Its job's test step
  also runs `coverage report` and `strict-no-cover`, so its red runs likely come
  from coverage, not from a test (INFERENCE).
- wemake-python-styleguide: its job's `make test` runs its lint and type check
  before pytest, which likely makes most of its red runs (INFERENCE).
- verifiers: eight of its sample's heads passed every test. Its job runs `uv
  sync` with no `--frozen`, under a pyproject whose `exclude-newer` is "7 days",
  so its CI may have installed newer packages than its lock holds, and failed
  on them (INFERENCE) [VERIFY].
- chonkie: 134 tests failed at its base commits with no change, most of them its
  tokenizers' and chunkers', likely for want of the network to fetch a model
  (INFERENCE); D-024's rule deselects them all.
- mitmproxy: two pull requests of its sample left both `[tool.pytest]` and
  `[tool.pytest.ini_options]` in their pyproject, which pytest 9 refuses, exit 4:
  the pull requests' own change, as in the CI.

## What it leaves for the bet

The bound that a number of pull requests with a red run allows, with k missed
among n, by `clopper_pearson_upper` (FACT, computed on 2026-11-22):

| n | k = 0 | k = 3 | k = 5 | k = 10 | k = 20 |
|---|---|---|---|---|---|
| 100 | 3.0% | 7.6% | 10.2% | 16.4% | 27.7% |
| 200 | 1.5% | 3.8% | 5.2% | 8.3% | 14.2% |
| 300 | 1.0% | 2.6% | 3.5% | 5.6% | 9.5% |
| 400 | 0.7% | 1.9% | 2.6% | 4.2% | 7.2% |

The finalists whose suites ran give some 420 pull requests with a red run
between them, by the samples' shares, against the window's 52 (INFERENCE, from
ten pull requests each). Replayed as the window was, a pull request costs about
two and a half of its suite's runs, one recording the coverage at M, one full
run and a rerun of what failed: at the step 3 runs' pace, some 23 hours of
steps for all of them, 13 of which are EvoScientist's, whose suite took eight
minutes a run with no `-n` (INFERENCE). Those that pull requests of the window
took two minutes each, 3.2 hours in all.

Facts that bear on which finalists a bet could take, all the user's to weigh:

- The Bet's Kill signal counts environments not built against 20% of the pull
  requests replayed. At step 3, pr-agent built none, electricitymaps-contrib 8
  of 15 and pydantic 11 of 15; every other finalist built at least 13 of 15.
- manim's suite does not run inside the sandbox, and pr-agent's environments
  need the uv that each commit asks for: either would take a change to the
  harness, a display inside the sandbox or a uv chosen for each commit, which
  is a slice of its own.
- Pull request numbers that two pilots share, above, limit which finalists one
  report can hold together while it counts pull requests by number alone.
- Every pilot configuration here is a draft from each job, for these checks:
  a bet's pilots would be fixed again before their first record, with the tests
  that D-024's rule deselected.
