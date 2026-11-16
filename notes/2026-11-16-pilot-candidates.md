# Pilot candidates for a next bet

A search, on 2026-11-15 and 2026-11-16, for a pilot whose pull requests fail
before they merge, which D-007 says a next bet starts by choosing, before it
sees any figure from it. Only CI outcomes were looked at, green or red, never a
figure of the Distiller. The scripts that read them lived in the agent's
scratchpad and are not kept; the `gh` commands they ran are below, so that each
pass can be run again. Nothing is decided here: the pilot and the bet are the
user's.

Labels: **FACT** = in the output of those commands, which the user ran on
2026-11-15 and 2026-11-16; **INFERENCE**; **OPINION**; **[VERIFY]** = not
checked.

## How

The agent's Bash cannot run `gh`: `.claude/settings.json` denies `Bash(gh *)`,
and the sandbox lets the network reach only `pypi.org`. So the agent wrote three
Python scripts that call `gh` and only read, and the user ran them from a
terminal: a few hundred API calls in all.

A pull request is taken as the head branch and the title that `gh run list`
gives its runs, so a fork's `main` under two titles counts twice, and two pull
requests with one branch and one title count once. A pull request is red when
one of its runs failed.

1. Every workflow. For each Python repository of the account, and for 30 Python
   projects that test with pytest on GitHub Actions: the latest 300 completed
   `pull_request` runs, `gh run list -R <repo> --event pull_request --limit 300
   --json databaseId,conclusion,status,headBranch,displayTitle,workflowName,createdAt,startedAt,updatedAt`;
   then, for the six with the most red pull requests per 30 days, the failed
   jobs and steps of three failed runs, `gh run view <id> -R <repo> --json jobs`.
2. The test workflow. For ten of them, the same with `--workflow <name>`; the
   latest 100 `push` runs of that workflow on the default branch, with
   `--event push --branch <branch>`, the branch from
   `gh repo view <repo> --json defaultBranchRef`; and the failed steps of the
   latest five failed runs.
3. One Linux CPython job. For four finalists: the pull requests in which a job
   whose name matches a pattern failed in a step whose name holds `test`,
   `pytest`, `nox` or `tox`, from at most 100 failed runs, latest first; and the
   median duration of such a job over 10 passing runs.

The window of a rate is what 300 runs cover, so a short one, such as pypa/
packaging's 2 days, gives a noisy rate. A run's minutes in passes 1 and 2 are
those of the whole workflow, its matrix included, not those of one job.

## The account's repositories

FACT: adaptive-policy-compilation, the pilot of the killed bet, had no red pull
request among 93; semantic-diff-weaver 3 among 136, in 21 days; burgess 1 among
71. The account's other Python repositories had none: two had 50 and 10 pull
requests with no failed run, and three, this one among them, no pull request
run. As note 80 of `TASKS.md` found, none of them gives red runs, so the pilot
is someone else's project, whose CI the Distiller cannot join: its pull requests
would be replayed offline (`notes/2026-11-16-offline-replay.md`).

## Pass 1: every workflow

FACT, by red pull requests per 30 days:

| Project | PRs | Red PRs | Days | Red / 30 days | Failing workflows, most failed runs first |
|---|---|---|---|---|---|
| pypa/packaging | 36 | 9 | 2 | 135.0 | Linting, Test, CodeQL |
| scrapy/scrapy | 72 | 45 | 15 | 90.0 | CI, codspeed, codspeed-walltime |
| psf/black | 31 | 11 | 5 | 66.0 | build and publish, lint and format, changelog |
| sphinx-doc/sphinx | 59 | 36 | 17 | 63.5 | CI, Lint source code, Synchronise translations |
| pypa/virtualenv | 29 | 12 | 6 | 60.0 | check, Changelog, CodeQL |
| pylint-dev/pylint | 38 | 10 | 5 | 60.0 | changelog, Tests, Checks |
| pytest-dev/pytest | 141 | 36 | 23 | 47.0 | test |
| tox-dev/tox | 37 | 10 | 7 | 42.9 | Changelog, check, CodeQL |
| urllib3/urllib3 | 29 | 12 | 9 | 40.0 | CI, lint, Check |
| pypa/pip | 69 | 27 | 23 | 35.2 | PR Checklist, CI |
| PyCQA/isort | 106 | 46 | 51 | 27.1 | CI |
| encode/starlette | 62 | 17 | 22 | 23.2 | Test Suite, a security analysis, CodSpeed |
| python-poetry/poetry | 132 | 35 | 52 | 20.2 | Tests |
| pallets/flask | 128 | 87 | 259 | 10.1 | Tests, pre-commit |
| pallets/click | 68 | 24 | 75 | 9.6 | pre-commit, Tests |

From 8.1 down to 0.9 red pull requests per 30 days: pypa/hatch, fastapi/typer,
celery/celery, pallets/jinja, jazzband/pip-tools, Textualize/textual,
marshmallow-code/marshmallow, pallets/werkzeug, python-attrs/attrs,
pytest-dev/pluggy, Textualize/rich, pre-commit/pre-commit, encode/httpx and
psf/requests. getsentry/sentry-python is missing: `gh` stopped with
`HTTP 404: Not Found` on one of its workflows. The names of virtualenv's and
tox's workflows start with an emoji, left out here.

The failed steps of the six reddest show that a red pull request is often no
failed test (FACT): packaging's runs failed in its lint session and, in one run,
in every job of its test matrix; black's in a pypy unit test, pre-commit hooks
and wheel builds; virtualenv's in news fragments, a graalpy test job and hooks;
pylint's in its changelog check and in creating a virtual environment; sphinx's
in "Test with pytest" in every job of its matrix; and scrapy's failed runs
listed no failed job.

## Pass 2: the test workflow

FACT, for the workflow that runs each project's tests:

| Project | Workflow | PRs | Red PRs | Days | Red / 30 days | Base branch runs failed |
|---|---|---|---|---|---|---|
| scrapy/scrapy | CI | 140 | 73 | 27 | 81.1 | 14% of 100 |
| sphinx-doc/sphinx | CI | 112 | 83 | 40 | 62.2 | 45% of 100 |
| pytest-dev/pytest | test | 141 | 36 | 23 | 47.0 | 5% of 100 |
| PyCQA/isort | CI | 112 | 51 | 54 | 28.3 | 0% of 100 |
| urllib3/urllib3 | CI | 109 | 41 | 52 | 23.7 | 7% of 99 |
| encode/starlette | Test Suite | 157 | 34 | 44 | 23.2 | 0% of 100 |
| python-poetry/poetry | Tests | 132 | 35 | 52 | 20.2 | 0% of 100 |
| pallets/flask | Tests | 120 | 93 | 338 | 8.3 | 49% of 39 |
| python-attrs/attrs | CI | 113 | 34 | 252 | 4.0 | 2% of 100 |
| pallets/jinja | Tests | 101 | 26 | 278 | 2.8 | no push run |

The steps that failed in the latest five failed runs (FACT): sphinx's, "Test
with pytest" in 19 or 20 jobs of each run, among them "Docutils HEAD" and
"Python 3.16"; pytest's, "Test with coverage" or "Test without coverage", mostly
in its xdist, pypy and Windows jobs; isort's, mostly "Lint"; urllib3's, "Run
tests" in most jobs of each run; starlette's, "Enforce coverage" and "Run
linting checks"; poetry's, `poetry run pytest --integration -v`, and `mypy` in
one run; flask's, "Development Versions" and typing; attrs's, its 100% coverage
gate, linters and mypy; jinja's, typing, and its tests in one run; scrapy's,
again no failed job.

## Pass 3: one Linux CPython job

FACT, the pull requests in which a Linux CPython job failed in a step that runs
the tests:

| Project | Jobs counted | PRs | Red PRs | Days | Red in a Linux job's tests | Per 30 days | Median of a passing job |
|---|---|---|---|---|---|---|---|
| pytest-dev/pytest | `build (ubuntu-py3...)` | 141 | 36 | 23 | 13 | 17.0 | 3.9 min |
| python-poetry/poetry | `Ubuntu (Python 3.x) / pytest` | 133 | 35 | 52 | 26 | 15.0 | 0.9 min |
| urllib3/urllib3 | `Ubuntu 3.x` | 109 | 41 | 52 | 21 | 12.1 | 1.3 min |
| scrapy/scrapy | any with `ubuntu` or `linux` | 140 | 73 | 27 | 9 | 10.0 | 3.8 min |

poetry's first try stopped on GitHub's `HTTP 502: Server Error`; run again
alone, it went through.

How the failures spread, in failed runs per job (FACT): poetry's Ubuntu pytest
jobs failed alike on every Python, 3.10 in 19 runs, 3.12 in 18, and 3.11, 3.14
and 3.15 in 17 each; urllib3's Ubuntu 3.15, 3.14t, 3.13, 3.12 and 3.14 in 25,
22, 21, 21 and 20; pytest's mostly in `ubuntu-py310-xdist`, 11, then in
`ubuntu-py312` and `ubuntu-py315`, 7 each; scrapy's in jobs on Python 3.15 or
with variant dependencies, 5 or 6 each. In one of pytest's failed runs only
`ubuntu-py310-xdist` failed. For both of scrapy's failed runs that were listed,
`gh` gave no job at all (INFERENCE: those runs failed before any job ran, so no
test failed in them).

## Where it leaves the choice

Discarded (OPINION, from the facts above):

- sphinx and flask: their base branch failed in 45% and 49% of its runs, so many
  of their pull requests' failures would not come from their diffs, and would
  count against the selector, as the SPEC's open question on failures inherited
  from the base branch says;
- isort, starlette and attrs: their test workflows failed mostly in lint, a
  coverage gate or mypy;
- jinja: under 3 red pull requests a month;
- scrapy: its few Linux test failures are in jobs on Python 3.15 or with variant
  dependencies, and none of its sampled failed runs had a failed job;
- pytest: its failures depend mostly on the environment, xdist, pypy or Windows,
  and one replayed job, such as `ubuntu-py312`, failed in 7 runs in 23 days.

Finalists (OPINION): python-poetry/poetry first, then urllib3/urllib3.

| | poetry | urllib3 |
|---|---|---|
| PRs red in a Linux job's tests, in 52 days | 26 | 21 |
| Base branch runs failed | 0% | 7% |
| A passing Linux test job | 0.9 min | 1.3 min |
| For | its failures hit every Ubuntu Python alike, so they come from the diff (INFERENCE); a lock file for each commit's environment | a small library with few dependencies |
| Against | its tests run with `--integration`, which may reach the network [VERIFY] | its tests start local servers, and some may be flaky [VERIFY] |

With one Linux job replayed, about 30 pull requests with a red run, the 30 that
give Report 2's bound of 9.5% when none is missed, take three to four months of
either project's pull requests (INFERENCE, from the rates above). Replayed
offline, they come from history, with no wait.

To check before choosing [VERIFY]: whether poetry's tests, and urllib3's, need
the network or anything beyond a Python environment; whether a failure seen in
CI fails again when replayed; how far back each project's environments can be
rebuilt; and whether the red pull requests are spread over many authors, rather
than a burst from one contributor or a bot.
