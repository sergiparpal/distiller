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

## The finalists' configuration, and their suites run offline

The user cloned both on 2026-11-16, poetry at 18668c8d (2026-11-15) and urllib3
at d9f9b0ad (2026-11-14), and the agent read their configuration (FACT):

- poetry needs Python 3.11 or later. Its pytest options add `-n logical -ra`,
  so xdist, and its test group holds `pytest-randomly`, which runs the tests in
  another order each time. Its CI runs `poetry run pytest --integration -v`,
  with `POETRY_TEST_INTEGRATION_GIT_USERNAME` and
  `POETRY_TEST_INTEGRATION_GIT_PASSWORD` set to the actor and the job's token,
  and runs pytest only when a pull request changes the files that its "Detect
  changed files" job looks at. Without `--integration`, its `conftest.py` leaves
  out the tests marked `integration`. The tests marked `integration` or
  `network` are in two files, `tests/integration/test_utils_vcs_git.py`, marked
  as a whole, and `tests/masonry/builders/test_editable_builder.py`; the others
  mock HTTP with `responses`. Its environment is locked in `poetry.lock`.
- urllib3 needs Python 3.10 or later. Its nox session runs `pytest -n auto`
  with `--disable-socket --allow-unix-socket` and
  `--allow-hosts=localhost,127.0.0.1,::1,127.0.0.0,240.0.0.0`, so its CI runs
  its tests with no network but the loopback, and with `--cov=urllib3` under
  `COVERAGE_CORE=sysmon`, which a replay would not use, since it records M with
  `ctrace` as the SPEC asks. A test that needs the Internet carries
  `requires_network`, which skips it when there is no route; a test marked
  `integration` is skipped without `--integration`. Its environment is
  installed with `uv sync --frozen` from `uv.lock`.

The user built both environments with uv on Python 3.12: urllib3's with
`uv sync --frozen --group dev --extra socks --extra brotli --extra zstd
--extra h2`, and poetry's with `uv sync --group test`, resolved from its
`pyproject.toml` rather than from `poetry.lock`. The agent then ran each suite
once in its sandbox, which reaches no host but `pypi.org`, with a `HOME` of its
own and 16 threads (FACT):

- urllib3, with its nox session's pytest options but no coverage or memray:
  2695 passed, 348 skipped, 4 xfailed and none failed, in 28 s. The skips:
  126 that need TLSv1 and 126 TLSv1.1; 31 `requires_network`, since there was
  no route; 20 that need IPv6; 11 "Can't resolve localhost."; 10 `integration`;
  and fewer for other reasons.
- poetry, without `--integration`: 3362 passed, 34 skipped, all for Windows or
  macOS, 2 xfailed and none failed, in 36 s. A first run, with the
  environment's `python` not on `PATH`, had 11 failures: 9 raised
  `FileNotFoundError` for `python`, and 2 looked for Python interpreters. With
  the environment's `bin` first on `PATH`, as `poetry run` puts it, none failed.

No test of either failed, or logged anything, for want of the network. Which of
urllib3's skips its CI runs is not checked [VERIFY]; the 31 that need a route,
and those that need IPv6 or resolve `localhost`, likely run there (INFERENCE).

## urllib3's latest red pull requests, replayed

On 2026-11-16 the user ran one more script through `gh`: among the latest 300
pull request runs of urllib3's CI, those in which the job "Ubuntu 3.12" failed
in a step that runs the tests, one per pull request, the latest six. The user
then fetched them with `git fetch origin pull/<n>/head:refs/pr/<n>`, which also
brought every head that those runs had tested. A first fetch, by the heads'
commit ids, had brought nothing. `gh run view --job <id> --log-failed` gave an
empty log for each job, and the job logs from the API hold pytest's output with
colour codes, which the script did not take out, so the tests that failed in
the CI are known by their count, from pytest's summary line, not by their names.

The agent replayed each tested head in the clone, in the environment built at
d9f9b0ad, with the pytest options of urllib3's nox session and no coverage or
memray, in its sandbox, which reaches no host but `pypi.org` (FACT). The
`uv.lock` or `pyproject.toml` of four of the heads, #5357's and the three of
October, differ from the environment's commit, and they ran in it all the same.

| PR | Its change | CI, "Ubuntu 3.12" | Replayed |
|---|---|---|---|
| #5375 | bounded decoder flush | 5 failed | 5 failed, all in `test/test_response.py`, on zstd and deflate decoding |
| #5357 | empty `allowed_methods` | 1 failed | 1 failed: `test/test_retry.py::TestRetry::test_empty_allowed_methods` |
| #5295 | rejecting NaN timeouts | 1 failed | 2 failed: `test_http2_probe_blocked_per_thread`, with TLSv1_2 and TLSv1_3 |
| #5293 | a bump of pre-commit hooks | 1 failed | 1 failed: `test_http2_probe_blocked_per_thread`, with TLSv1_3 |
| #5296 | rejecting non-finite timeouts | 1 failed | stopped after 900 s with no result |
| #5278 | an HTTP/2 prototype | 57 failed, 1 error | 3044 passed, none failed |

Each replay that ended took 24 to 40 s. Three checks followed (FACT):

- #5296's head again, with `--timeout=120`: 2 failed, both
  `test_http2_probe_blocked_per_thread` with TLSv1_2, in `test_https.py` and in
  `contrib/test_pyopenssl.py`, in 37 s; no test reached the limit, so the hang
  did not happen again.
- #5278's head merged into d9f9b0ad, the last commit of `main` before its run,
  as the CI tests a merge: no conflict, and 3063 passed, none failed. Its head
  with `--memray --hide-memray-summary`, as its CI's log shows pytest run: 3044
  passed, none failed.
- `test_http2_probe_blocked_per_thread`, 10 runs at each commit: it failed in 1
  of 10 at #5293's head, 2 of 10 at #5295's, 3 of 10 at 796d200d, the last
  commit of `main` before #5293's run, on 2026-10-01, and 0 of 10 at d9f9b0ad.

So, of urllib3's latest six red pull requests (INFERENCE): two, #5375 and
#5357, failed from their own change, and replay so; three, #5293, #5295 and
#5296, failed on a test that was flaky on `main` at the time, which a rerun file
would mostly discard, and which, failing again, would count against the
selector, as the SPEC's open question on failures inherited from the base branch
says; and one, #5278, failed in the CI for a reason that its head, its merge
and memray do not show offline, so a replay records it green. What its CI has
that the replay lacks, coverage under `sysmon`, a newer Python 3.12 or IPv6, is
not checked [VERIFY]. If a third of urllib3's red pull requests count when
replayed, its 21 in 52 days give some 7, about 4 a month, so 30 take some seven
months of history: an estimate from six pull requests.

## poetry's latest red pull requests, replayed

The same, on 2026-11-16, for poetry's workflow "Tests" and its job "Ubuntu
(Python 3.12) / pytest", with the job's log read from the API and its colour
codes taken out, so that the tests that failed in the CI are known by name. The
script's first try stopped on an error that `gh run view --json jobs` gave for a
run; after that, it tried each such call three times, 5 s apart. The user
fetched five pull requests by `pull/<n>/head`, and one head, of a pull request
whose number the script did not find, by its commit id. The heads that #11081's
and #11057's runs had tested were not in their pull requests' later heads, and
came only when fetched by their ids.

The agent replayed each tested head in the environment built from 18668c8d's
`pyproject.toml`, without `--integration`, with the environment's `bin` first on
`PATH`, in its sandbox (FACT):

| PR | Its change | CI, "Ubuntu (Python 3.12) / pytest" | Replayed |
|---|---|---|---|
| no number found, branch `viktor/fix-config-int-validator-11148`, run of 2026-11-01 | the setting's name for invalid integer values | 2 failed: `tests/console/commands/test_config.py::test_cannot_set_invalid_integer_value`, two parameters | the same 2 failed |
| #11226, 2026-11-12 | keeping bracketed path segments | the job failed; its log names no failed test | a `RecursionError` in its own test, `tests/utils/test_dependency_specification.py::test_parse_path_requirement_keeps_brackets_before_extras`, stopped an xdist worker, and pytest ended with an internal error, exit 3 |
| #11081, 2026-10-17 | a missing URL in a repository's configuration | 1 failed: `tests/utils/test_authenticator.py::test_repository_config_supports_none_url` | not run: `ModuleNotFoundError: No module named 'tomlkit'`; its latest head, of 2026-11-15, passes |
| #11057, 2026-10-12 | invalid repository configurations | 1 failed: `tests/utils/test_helpers.py::test_extractall_sdist_no_symlink_path_traversal_via_directory_symlink` | not run, for `tomlkit`; its latest head, of 2026-11-14, passes |
| #11136, 2026-10-12 | accepting any matching hash | 1 failed: the same test | not run, for `tomlkit` |
| #11109, 2026-10-11 | clearing downloaded artifacts | 1 failed: the same test | not run, for `tomlkit` |

poetry's `pyproject.toml` lists `tomlkit` at the heads of October and not at
18668c8d, of 2026-11-15, so the environment of mid-November runs no head of
mid-October (FACT).

So, of poetry's latest six red pull requests (INFERENCE): three failed from their
own change, by the names of the tests that failed: the first, which replays
exactly; #11226, which replays as pytest's internal error, and a JUnit that holds
it is one that the Distiller rejects as `unusable-input`, so that run would not
be evaluated; and #11081, which could not be run. Three failed, within two days,
on one test that none of their changes touches, as urllib3's three did on a
flaky test of `main`: likely inherited, which was not checked, since the
environment of their date was not rebuilt [VERIFY]. Pass 2 found no failed run of
poetry's test workflow on its base branch; that workflow runs pytest only when a
push changes the files that its "Detect changed files" job looks at, which could
hide a red base branch [VERIFY].

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

Finalists (OPINION): urllib3/urllib3 and python-poetry/poetry, with neither
first yet. On their CI's figures alone poetry came first; their configuration
and the offline runs above put urllib3 first, since its CI already runs its
tests with no network and its lock is installed frozen, while poetry's CI also
runs tests that need the network and a GitHub token, which a replay cannot run,
and its tests change their order on every run. But only two of urllib3's latest
six red pull requests replay as red from their own change; of poetry's latest
six, three failed from their own change, of which one replays as red, one as
pytest's internal error, which the Distiller rejects, and one not at all without
the environment of its date. Both have red runs that a base branch, flaky or
red, seems to have passed on. urllib3 is the easier to replay: its environment
of mid-November ran heads six weeks older, while poetry's ran none four weeks
older. For either, a third to a half of the CI's red pull requests would count,
some 4 to 6 a month, so 30 take five to eight months of history (INFERENCE).

| | poetry | urllib3 |
|---|---|---|
| PRs red in a Linux job's tests, in 52 days | 26 | 21 |
| Base branch runs failed | 0% | 7% |
| A passing Linux test job | 0.9 min | 1.3 min |
| Suite run offline, 16 threads | 3362 passed, none failed, 36 s | 2695 passed, none failed, 28 s |
| Latest six red PRs, replayed | 1 red from its own change, 1 pytest internal error from its own change, 4 not run, for want of `tomlkit` | 2 red from their own change, 3 on a test flaky on `main` then, 1 green |
| For | its failures hit every Ubuntu Python alike, so they come from the diff (INFERENCE); a lock file for each commit's environment | its CI runs its tests with no network; `uv sync --frozen`; a small library with few dependencies |
| Against | its CI's integration tests need the network and a GitHub token, so a red run that failed only there cannot be replayed; `pytest-randomly` changes the order, and with it M's rows, unless turned off | some of its tests that need a route, IPv6 or `localhost` skip offline, which its CI likely runs; some tests start local servers, and may be flaky [VERIFY] |

With one Linux job replayed, about 30 pull requests with a red run, the 30 that
give Report 2's bound of 9.5% when none is missed, take three to four months of
either project's pull requests (INFERENCE, from the rates above). Replayed
offline, they come from history, with no wait.

To check before choosing [VERIFY]: whether, with the environment of each head's
date rebuilt, poetry's red runs of October fail again, and whether the test that
three of them failed on was red on their base branch then; how far back each
project's environments can be rebuilt, beyond the six weeks that urllib3's
replays reached; how many of poetry's red runs failed only in its integration
tests; and whether the red pull requests are spread over many authors, rather
than a burst from one contributor or a bot. Checked on 2026-11-16, above: their
tests need no network, but for poetry's integration tests; and of their latest
six red pull requests, two of urllib3's and one of poetry's replay as red from
their own change.
