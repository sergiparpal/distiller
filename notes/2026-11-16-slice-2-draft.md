# Draft: Slice 2, replaying the pilots' red pull requests offline

A draft, in the format of `docs/SPEC.md`, of the slice of the bet that the user
wrote on 2026-11-17 (D-010), to move into the SPEC once the user has settled
it. First written on 2026-11-16 for urllib3 alone, from
`notes/2026-11-16-replay-slice-proposal.md`; rewritten on 2026-11-17 for both
pilots, from `notes/2026-11-16-bet-window-checks.md`. Nothing here is decided.
The bet, the non-goals and the "then" of every [core] example are the user's:
the non-goals below are proposals, and each [core] example carries a proposed
"then" for the user to keep, change or drop. Figures come from
`notes/2026-11-16-pilot-candidates.md`, `notes/2026-11-16-offline-replay.md` and
`notes/2026-11-16-bet-window-checks.md`; what was not checked carries [VERIFY].

## The slice

### Slice 2: Replaying the pilots' red pull requests offline
A harness, apart from the tool, replays the pull requests of two pilots whose CI
the Distiller cannot join, urllib3 and poetry, each in one job. For each pull
request of the bet's window, whose job failed in a CI run that started from
2025-12-01 to 2026-11-15, it rebuilds the environment of its commits from their
own lock files, records the coverage at the merge-base, runs the full suite at
the head of its latest such run, runs its failures again, and runs Slice 1's
`evaluate` on what it made, as the CI step did. The tool does not change: Slice
1's report over the replay's records gives the miss rate that Slice 1's pilot
could not.

- Supersedes: nothing of Slice 1, which keeps its tool, its records and its
  report; the harness's Deployment stands in for Slice 1's on these two pilots
  only.

Proposed non-goals, the user's:
- The harness changes nothing in `distiller`: no field in a record, no input, no
  rule.
- No pull request, window, run or floor pattern is chosen once a record exists
  (D-007): the window's pull requests are those of
  `notes/2026-11-17-window-red-runs.csv`, fixed before the first record.
- Two pilots and one job each: no Windows, macOS, pypy or other Python, and none
  of poetry's integration tests, which need the network and a GitHub token.
- No savings figure: only the pull requests whose job failed in the CI are
  replayed, as the bet says.
- It does not explain a red run of the CI that replays green: the record holds
  what the replay saw.
- No network in a suite run but the loopback: the network is for fetching and
  installing, before the runs.

Inputs for one replay:
- a pilot's configuration, a TOML file in this repository for each pilot, that
  names the repository, its base branch, the job, the Python, the commands that
  build an environment (for urllib3, `uv sync --frozen` with its nox session's
  arguments; for poetry, `poetry env use` and `poetry install --with
  github-actions`, with the environment in the work tree), the pytest options
  of the job's run with no network, the time limit per test, the package that
  the coverage measures and the floor configuration;
- the manifest: the window's CSV, `notes/2026-11-17-window-red-runs.csv`, one
  row per pull request with its project, number, run id, run start, head and
  the CI job's outcome; its two rows with no number get theirs, once, through
  `gh`, before the first record;
- the pilot's clone, a full clone in which each row's head is kept by a ref of
  its own, `refs/window/<run id>`, as `~/code/distiller-pilots/<project>` holds
  them since 2026-11-17;
- a work directory, for the worktrees, the environments, the inputs made for
  the tool and the logs;
- the record file, as in Slice 1, one for each pilot.

Terms:
- The window is the span of dates in which a run must have started to count:
  2025-12-01 to 2026-11-15.
- The run chosen for a pull request is its latest run in the window whose job
  failed, in any step, as the bet says; the CSV names it.
- The tested head is the commit that the chosen run tested. It is H for the
  tool (open question 1).
- The base commit is the last commit of the pilot's base branch before the
  chosen run started, standing in for the one that the run saw (open question
  7).
- M is the merge-base of the base commit and the tested head.
- The environment of a commit is what the pilot's configuration builds from
  that commit's own lock file: `uv.lock` for urllib3, `poetry.lock` for poetry.
- A failure is inherited when a test that failed at the tested head also failed
  at M, in the run that recorded the coverage.
- A pull request is not replayed when its head is not in the clone or one of
  its environments cannot be built: the log says which, no record is appended
  for it, and it counts toward the bet's 20% of environments.

#### Manifest
- Given a row of the window's CSV, when the manifest is read, then its tested
  head is the row's head, and the clone holds it at `refs/window/<run id>`.
- Given a row with no pull request number, when the manifest is read, then the
  replay does not start, and says that the number must be found first.
- Given a number that both pilots' rows hold, when the manifest is read, then
  the replay does not start, and names it: Slice 1's report counts pull requests
  by number alone (open question 8).
- Given a row whose head is not in the clone, when the manifest is read, then
  that pull request is listed as not replayed before any run starts.

#### Replaying a pull request
- [core] Given urllib3's #5375 at its tested head, b66457156bf7, when it is
  replayed, then (proposed) the full run's JUnit holds 5 failed tests, all in
  `test/test_response.py`, the rerun file holds those 5 run again, and one
  record is appended to urllib3's record file.
- Given poetry's #10980 at its tested head, 7b38c77a1ef2, when it is replayed,
  then the full run fails the two tests that the pull request adds, the rerun
  fails them again, and one record is appended to poetry's record file.
- Given a tested head whose lock file differs from its M's, when it is replayed,
  then each environment is built from its own commit's lock file, and the log
  names the SHA-256 of each.
- Given a test that waits for input, as poetry's #10956's did at its head of
  2026-06-16 when replayed on 2026-11-17, when the full run is replayed, then
  that test fails at the pilot's time limit, the full run ends, and the next
  pull request is replayed.
- Given a test that leaves a thread blocked, as urllib3's flaky HTTP/2 probe
  test did on 2026-11-16, when its run ends, then the pytest process ends with
  it.
- [core] Given a full run that ends in pytest's internal error, as poetry's
  #11226 did, when it is evaluated, then (proposed) the run is rejected with
  `unusable-input` and `junit`, as Slice 1 rejects such a JUnit file.
- Given a test that fails at the tested head and at M, when the pull request is
  replayed, then the log marks its failure as inherited.
- Given a replay stopped after some pull requests, when it is started again with
  the same manifest, then it starts at the first pull request that the log does
  not show as done.

#### Invariants
- Given the inputs that a replay kept, when they are evaluated again, then the
  two record files are byte-identical, as Slice 1's Invariants say. Two replays
  of one pull request are not: the tests' times differ.
- Given any suite run, when it runs, then it opens no network connection but the
  loopback.
- Given a pull request replayed, whatever its outcome, when the replay goes on,
  then the clone's checked-out commit and work tree are as they were: the
  commits are checked out in worktrees of the work directory.
- Given a record file that holds a replay's records, when the harness is started
  over it with a manifest whose SHA-256 differs from that replay's, then it
  replays nothing and says so.

#### Summary
- The report is Slice 1's, over both pilots' record files together, as the bet
  counts its 30 pull requests over the two projects.
- Given a replay done, when its summary is written, then it shows, apart from
  the report, for each pilot and for both: how many pull requests were replayed,
  how many were not and why, how many were red, and how many failures were
  inherited.

## Changes to Constraints

- Deployment, for Slice 2: the harness runs on the user's machine, where the
  pilots' clones are, with `git`, `uv` and the pilots' Python on the `PATH`;
  poetry runs through `uv tool run`. It reaches GitHub to fetch and PyPI to
  install, before the runs; the suite runs reach the loopback only. The agent's
  sandbox reaches neither `~/code/distiller-pilots` nor GitHub (open question
  9). The tool runs as in Slice 1: `python -P -m distiller evaluate` from a
  fixed commit of this repository, with coverage 7.16.2, which
  `requirements.txt` pins and which also records the coverage at M.
- Allowed dependencies, for the harness: the standard library, and `git`, `uv`
  and poetry, as programs on the `PATH`; `gh` only to find the two missing
  numbers. Nothing that `distiller` depends on changes.
- Agent safety: the harness runs the pilots' code at commits that strangers
  wrote, with no network but the loopback and a `HOME` in the work directory.
  Whether that is enough isolation, or the runs need a container or a CI runner,
  is open (open question 6).
- Performance, from the samples of 2026-11-17: a whole run of urllib3's suite
  took 50 to 118 s with no xdist, which its heads before 2026-10-15 lack, and
  poetry's 31 to 56 s with its own `-n logical` (FACT); the environments' build
  times were not measured [VERIFY]. With the run at M under test contexts and the
  rerun, some 3 to 6 minutes a pull request, and some 5 to 9 hours for the 90
  (INFERENCE).

## Technical sheet, draft

### Modules
In a package `replay`, apart from `distiller`, in `src/`:

| Module | Does |
|---|---|
| `__main__` | `raise SystemExit(cli.main())` |
| `cli` | argparse into the command `run` |
| `pilot` | reads a pilot's configuration, with `tomllib` |
| `manifest` | reads the window's CSV and checks its rows: numbers, heads in the clone, numbers that both pilots hold |
| `checkout` | adds and removes worktrees at a commit; unlike `distiller.git`, it writes to the clone's `.git` |
| `environment` | builds a commit's environment, as the pilot's configuration says |
| `suite` | runs pytest in a wrapper that writes the failed node ids and ends at once: the coverage at M, the full run and the rerun |
| `harness` | one pull request's steps, the log, the summary and starting again |

### Interfaces
```python
# pilot.py
def read_pilot(path: str) -> Pilot: ...

# manifest.py
def read_window(path: str, project: str) -> list[ManifestLine]: ...
def problems(lines: list[ManifestLine], clone: str) -> list[str]: ...  # empty when the replay can start

# checkout.py
def add_worktree(clone: str, commit: str, folder: str) -> None: ...
def remove_worktree(clone: str, folder: str) -> None: ...
def base_commit(clone: str, branch: str, started: str) -> str | None: ...  # the last commit before the run
def merge_base(clone: str, a: str, b: str) -> str | None: ...

# environment.py
def build(pilot: Pilot, worktree: str) -> StepResult: ...

# suite.py
def record_coverage(pilot: Pilot, worktree: str, coverage_file: str, junit_file: str) -> StepResult: ...
def full_run(pilot: Pilot, worktree: str, junit_file: str) -> StepResult: ...
def rerun(pilot: Pilot, worktree: str, failed: list[str], junit_file: str) -> StepResult: ...

# harness.py
def replay(pilot: Pilot, manifest: str, clone: str, work: str, records: str,
           only: list[int] | None) -> int: ...  # the exit code
```

### Data model
```python
@dataclass(frozen=True)
class Pilot:
    project: str
    repository: str
    base_branch: str
    job: str
    python: str
    environment: tuple[tuple[str, ...], ...]   # the commands that build it, in order
    pytest: tuple[str, ...]
    coverage_source: str
    seconds_per_test: int
    floor_config: str | None

@dataclass(frozen=True)
class ManifestLine:
    project: str
    pull_request: int | None   # None: to be found before the first record
    run: int
    run_started: str
    tested_head: str
    ci_job: str                # the job's outcome, as GitHub gave it on 2026-11-16

@dataclass(frozen=True)
class StepResult:
    exit_code: int | None      # None: stopped at its time limit
    seconds: float
    failed: tuple[str, ...]    # node ids, as the wrapper wrote them
```

### Command line
```
python -m replay run --pilot PATH --manifest PATH --clone DIR --work DIR
    --records PATH [--only N ...]
```

### How a replay goes
For each manifest line of the pilot, in order:

1. If the log shows it done, it is skipped.
2. The base commit is the last commit of the base branch before the run
   started, and M its merge-base with the tested head.
3. A worktree of M is added in the work directory, M's environment is built
   there, and the coverage at M is recorded with `--cov=<source>
   --cov-context=test` and `COVERAGE_CORE=ctrace`, its JUnit kept for the
   failures at M.
4. A worktree of the tested head is added, its environment built, and the full
   run writes its JUnit; the tests that failed run again into the rerun file.
5. `python -P -m distiller evaluate --pr N --head <tested head> --base <base
   commit> --coverage <file> --coverage-commit <M> --junit <file> [--rerun
   <file>] [--floor-config <file>] --records <file> --checkout <clone>` runs.
6. The log gets each step's command, exit code and time, the lock files'
   SHA-256, the failures at the head and at M, and those inherited.
7. Both worktrees are removed, whatever happened.

### Rules
1. The manifest is fixed: its SHA-256 goes into the log's first line, and a run
   with another manifest over the same record file replays nothing.
2. Every process has a time limit, and every test of a suite run the pilot's;
   for poetry, whose environments lack pytest-timeout, the replay adds it (open
   question 5).
3. A suite run takes the pilot's pytest options, reaches no network but the
   loopback, and has its `HOME` in the work directory and the environment's
   `bin` first on its `PATH`.
4. pytest runs in a wrapper that ends the process with `os._exit` once pytest
   returns, since a thread that a test left blocked kept one alive for 37
   minutes on 2026-11-16.
5. The coverage at M is recorded by coverage 7.16.2, under `ctrace`, with test
   contexts and no static context, as Slice 1's Deployment asks.
6. Every step's output is kept, with its colour codes taken out.

### Imports
- `distiller` imports nothing of `replay`, and `replay` nothing of `distiller`:
  it runs the tool as a process, as a CI step does.
- Only `checkout`, `environment` and `suite` import `subprocess`.

### Irreversible effects
| Effect | Module |
|---|---|
| Installing from PyPI and, for urllib3's hypercorn, from GitHub | `environment` |
| Running the code of commits that strangers wrote | `suite` |
| Appending to the record files | the tool, as in Slice 1 |
| Adding and removing worktrees in the clone's `.git` | `checkout` |
| Writing the work directory | `harness` |

### Checked and [VERIFY]
Checked on 2026-11-16 and 2026-11-17 (`notes/2026-11-16-bet-window-checks.md`):
all 90 heads of the window are in the pilots' clones, 53 fetched with
`pull/<n>/head` and 37 by their commit ids; the 21 environments of the two
samples, of heads from 2026-03-17 to 2026-10-12, were all built from their own
lock files, urllib3's with `uv sync --frozen` and poetry's with `poetry
install`; the wrapper with `os._exit` ended a run whose test left a thread
blocked; at a merge-base, the tests that had failed at a head ran with the
head's environment and `PYTHONPATH` set to the merge-base's `src/`, once
urllib3's generated `_version.py` was there; GitHub no longer gave the logs of
March's runs, nor the steps of jobs older than about 180 days, while it gave
the jobs' conclusions.

[VERIFY]:
- Whether the last commit of the base branch before a run started is the base
  commit that the run saw; the run's `pull_request` event would say, through
  `gh api repos/<repo>/actions/runs/<id>`, while GitHub keeps the run.
- How long the coverage run at M takes with test contexts, and for poetry under
  xdist, whose workers' data coverage must combine.
- Whether adding pytest-timeout to poetry's environments changes any test's
  outcome.

## Open questions
1. H: the tested head, or a merge of it into the base commit that the run saw,
   as the CI tested. For urllib3's #5278 both passed.
2. Which runs: settled by the bet of 2026-11-17, one per pull request, its
   latest run in the window whose job failed.
3. Where the harness lives: in this repository, as above, or in a repository of
   its own.
4. How many reruns: one, as Slice 1's pilot had, or more for tests as flaky as
   urllib3's `test_http2_probe_blocked_per_thread`, which the base branch held
   until early October 2026.
5. The time limit per test: 120 s held for urllib3; for poetry, pytest-timeout
   added to the replay's environments alone, or a run that hangs rejected at the
   process's limit.
6. Isolation: whether running strangers' commits with no network but the
   loopback is enough, or the runs need a container or a CI runner.
7. The base commit: the last commit of the base branch before the run started,
   or the one that the run's event names, looked up once through `gh` while
   GitHub keeps the runs.
8. One report or two: the bet counts the two pilots together, and Slice 1's
   report counts pull requests by number alone; in the window, urllib3's numbers
   run from 3593 to 5375 and poetry's from 9805 to 11226, so they do not collide,
   but the two rows with no number are still to be checked.
9. Where the replays run: on the user's machine, where the clones are, or with
   copies in the agent's scratchpad, as the samples were; the agent's sandbox
   reaches neither `~/code/distiller-pilots` nor GitHub.
