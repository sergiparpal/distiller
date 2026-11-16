# Draft: Slice 2, replaying a pilot's pull requests offline

A draft, in the format of `docs/SPEC.md`, of a second slice, from
`notes/2026-11-16-replay-slice-proposal.md`, to move into the SPEC once the user
has written the new bet. Nothing here is decided. The bet, the non-goals and the
"then" of every [core] example are the user's: the non-goals below are
proposals, and each [core] example carries a proposed "then" for the user to
keep, change or drop. Figures from the replays of 2026-11-16 come from
`notes/2026-11-16-pilot-candidates.md` and `notes/2026-11-16-offline-replay.md`;
what was not checked carries [VERIFY].

## The slice

### Slice 2: Replaying a pilot's pull requests offline
A harness, apart from the tool, replays the pull requests of a pilot whose CI
the Distiller cannot join. For each pull request of a manifest fixed before the
first record, it rebuilds the environment of its commits, records the coverage
at the merge-base, runs the full suite at the head that the CI tested, runs its
failures again, and runs Slice 1's `evaluate` on what it made, as the CI step
did. The tool does not change: Slice 1's report over the replay's records gives
the miss rate that Slice 1's pilot could not.

- Supersedes: nothing of Slice 1, which keeps its tool, its records and its
  report; the harness's Deployment stands in for Slice 1's on this pilot only.

Proposed non-goals, the user's:
- The harness changes nothing in `distiller`: no field in a record, no input, no
  rule.
- No pull request, window, run or floor pattern is chosen once a record exists
  (D-007).
- One pilot and one job: no Windows, macOS, pypy or integration session.
- It does not explain a red run of the CI that replays green: the record holds
  what the replay saw, and the log the CI's summary.
- No network in a suite run but the loopback: the network is for fetching and
  installing, before the runs.

Inputs for one replay:
- the pilot's configuration, a TOML file in this repository that names the
  repository, the job, the Python version, the arguments of `uv sync`, the
  pytest options of the job's run with no network, the package that the
  coverage measures, the time limit per test and the floor configuration;
- the manifest, a JSON Lines file that `python -m replay manifest` writes once
  from the CI's runs and that is committed before the first record: one line
  per pull request, with its number, the run chosen for it, the head that run
  tested, the base commit that run saw, and, read from the run's log with its
  colour codes taken out, the summary line and the tests that failed in the job;
- the pilot's clone, a full clone into which the manifest's heads are fetched;
- a work directory, for the environments, the inputs made for the tool and the
  logs;
- the record file, as in Slice 1.

Terms:
- The window is the span of dates in which a run must have started to be in the
  manifest.
- The run chosen for a pull request is its first red run of the job in the
  window, if it has one, and else its last run there (open question 2).
- The tested head is the commit on the pull request's branch that the chosen run
  tested. It is H for the tool (open question 1).
- M is the merge-base of the base commit that the chosen run saw and the tested
  head.
- The environment of a commit is what `uv sync --frozen`, with the pilot's
  arguments, builds from that commit's own lock file.
- A failure is inherited when a test that failed at the tested head also failed
  at M, in the run that recorded the coverage.
- A pull request is not replayed when its head cannot be fetched or one of its
  environments cannot be built: the log says which, and no record is appended
  for it.

#### Manifest
- Given a pull request with three runs of the job in the window, the second of
  them red, when the manifest is written, then its line names the second run and
  the head that it tested.
- Given a pull request whose runs of the job in the window were all green, when
  the manifest is written, then its line names its last run in the window.
- Given a pull request whose only red run started before the window, and whose
  runs in it were green, when the manifest is written, then its line names its
  last run in the window, as a green pull request's.
- Given a run whose log GitHub no longer serves, when the manifest is written,
  then its line holds no CI summary and no failed test, and says that the log
  was gone.

#### Replaying a pull request
- [core] Given urllib3's #5375 at its tested head, b66457156bf7, when it is
  replayed, then (proposed) the full run's JUnit holds 5 failed tests, all in
  `test/test_response.py`, the rerun file holds those 5 run again, and one
  record is appended to the record file.
- Given a tested head whose `uv.lock` differs from its M's, when it is replayed,
  then each environment is built from its own commit's `uv.lock`, and the log
  names the SHA-256 of each.
- Given a test that hangs at the tested head, when the full run is replayed,
  then that test fails at the pilot's time limit, the full run ends, and the next
  pull request is replayed.
- [core] Given a full run that ends in pytest's internal error, as poetry's
  #11226 did, when it is evaluated, then (proposed) the run is rejected with
  `unusable-input` and `junit`, as Slice 1 rejects such a JUnit file.
- Given a test that fails at the tested head and at M, when the pull request is
  replayed, then the log marks its failure as inherited.
- Given a tested head that cannot be fetched, when its pull request comes up,
  then it is not replayed, the log says why, no record is appended for it, and
  the next pull request is replayed.
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
  then the clone is back on the branch it was on, with no change in its work
  tree.
- Given a record file that holds a replay's records, when the harness is started
  over it with a manifest whose SHA-256 differs from that replay's, then it
  replays nothing and says so.

#### Summary
- The report is Slice 1's, over the replay's record file.
- Given a replay done, when its summary is written, then it shows, apart from
  the report, how many pull requests were replayed, how many were not and why,
  and how many failures were inherited.

## Changes to Constraints

- Deployment, for Slice 2: the harness runs on the user's machine or in a CI of
  the user's own, with `git` and `uv` on the `PATH` and the pilot's Python. It
  reaches GitHub to fetch and PyPI to install, before the runs; the suite runs
  reach the loopback only. The tool runs as in Slice 1: `python -P -m distiller
  evaluate` from a fixed commit of this repository, with coverage 7.16.2, which
  `requirements.txt` pins and which also records the coverage at M.
- Allowed dependencies, for the harness: the standard library, and `git`, `uv`
  and, for the manifest only, `gh`, as programs on the `PATH`. Nothing that
  `distiller` depends on changes.
- Agent safety: the harness runs the pilot's code at commits that strangers
  wrote, with no network but the loopback and a `HOME` in the work directory.
  Whether that is enough isolation, or the runs need a container or a CI runner,
  is open (open question 6).
- Performance: a full run of urllib3's suite took 24 to 40 s on 16 threads on
  2026-11-16; a pull request, with its two environments, the run at M with test
  contexts and the rerun, two to three minutes (INFERENCE).

## Technical sheet, draft

### Modules
In a package `replay`, apart from `distiller`, in `src/`:

| Module | Does |
|---|---|
| `__main__` | `raise SystemExit(cli.main())` |
| `cli` | argparse into the commands `manifest` and `run` |
| `pilot` | reads the pilot's configuration, with `tomllib` |
| `manifest` | writes the manifest from the CI's runs, through `gh`; reads it and checks its lines |
| `checkout` | fetches heads, checks commits out and puts the clone back; unlike `distiller.git`, it writes to the clone |
| `environment` | builds a commit's environment with `uv sync --frozen` |
| `suite` | runs pytest: the coverage at M, the full run and the rerun; reads a JUnit file's failed tests |
| `harness` | one pull request's steps, the log, the summary and starting again |

### Interfaces
```python
# pilot.py
def read_pilot(path: str) -> Pilot: ...

# manifest.py
def write_manifest(pilot: Pilot, since: date, until: date, out: TextIO) -> None: ...  # through gh
def read_manifest(path: str) -> list[ManifestLine]: ...

# checkout.py
def missing_heads(clone: str, lines: list[ManifestLine]) -> list[int]: ...  # pull requests whose head is not there
def check_out(clone: str, commit: str) -> None: ...
def merge_base(clone: str, a: str, b: str) -> str | None: ...
def put_back(clone: str, branch: str) -> None: ...

# environment.py
def build(pilot: Pilot, clone: str, commit: str, target: str) -> StepResult: ...

# suite.py
def record_coverage(pilot: Pilot, clone: str, environment: str, coverage_file: str, junit_file: str) -> StepResult: ...
def full_run(pilot: Pilot, clone: str, environment: str, junit_file: str) -> StepResult: ...
def rerun(pilot: Pilot, clone: str, environment: str, failed: list[str], junit_file: str) -> StepResult: ...
def failed_in(junit_file: str) -> list[str]: ...

# harness.py
def replay(pilot: Pilot, manifest: str, clone: str, work: str, records: str,
           only: list[int] | None) -> int: ...  # the exit code
```

### Data model
```python
@dataclass(frozen=True)
class Pilot:
    repository: str
    job: str
    python: str
    uv_sync: tuple[str, ...]
    pytest: tuple[str, ...]
    coverage_source: str
    seconds_per_test: int
    floor_config: str | None

@dataclass(frozen=True)
class ManifestLine:
    pull_request: int
    run: int
    tested_head: str
    base_commit: str
    ci_summary: str | None   # None: the log was gone
    ci_failed: tuple[str, ...]

@dataclass(frozen=True)
class StepResult:
    exit_code: int | None    # None: stopped at its time limit
    seconds: float
    failed: tuple[str, ...]
```

### Command line
```
python -m replay manifest --pilot PATH --since DATE --until DATE > MANIFEST
python -m replay run --pilot PATH --manifest PATH --clone DIR --work DIR
    --records PATH [--only N ...]
```

### How a replay goes
For each manifest line, in order:

1. If the log shows it done, it is skipped.
2. M is the merge-base of the base commit and the tested head; a head that is not
   in the clone makes the pull request not replayed.
3. M's environment is built, M is checked out, and the coverage at M is recorded
   with `--cov=<source> --cov-context=test` and `COVERAGE_CORE=ctrace`, its JUnit
   kept for the failures at M.
4. The tested head's environment is built, the head is checked out, and the full
   run writes its JUnit; the tests that failed run again into the rerun file.
5. `python -P -m distiller evaluate --pr N --head <tested head> --base <base
   commit> --coverage <file> --coverage-commit <M> --junit <file> [--rerun
   <file>] [--floor-config <file>] --records <file> --checkout <clone>` runs.
6. The log gets each step's command, exit code and time, the locks' SHA-256, the
   failures at the head and at M, and those inherited.
7. The clone is put back on its branch, whatever happened.

### Rules
1. The manifest is fixed: its SHA-256 goes into the log's first line, and a run
   with another manifest over the same record file replays nothing.
2. Every process has a time limit, and every test of a suite run the pilot's.
3. A suite run takes the pilot's pytest options, reaches no network but the
   loopback, and has its `HOME` in the work directory.
4. The coverage at M is recorded by coverage 7.16.2, under `ctrace`, with test
   contexts and no static context, as Slice 1's Deployment asks.
5. Every step's output is kept, with its colour codes taken out.

### Imports
- `distiller` imports nothing of `replay`, and `replay` nothing of `distiller`:
  it runs the tool as a process, as a CI step does.
- Only `manifest`, `checkout`, `environment` and `suite` import `subprocess`.

### Irreversible effects
| Effect | Module |
|---|---|
| Fetching from GitHub, installing from PyPI | `checkout`, `environment` |
| Running the code of commits that strangers wrote | `suite` |
| Appending to the record file | the tool, as in Slice 1 |
| Changing the clone's checked-out commit | `checkout`, put back after each pull request |
| Writing the work directory | `harness` |

### Checked and [VERIFY]
Checked on 2026-11-16 (the two notes): `git fetch origin
pull/<n>/head:refs/pr/<n>` brings a pull request's head, and fetching by commit
id brought tested heads that later pushes no longer held; an environment that
`uv sync --frozen` built at urllib3's commit of 2026-11-14 ran heads up to six
weeks older, while poetry's environment broke within four weeks, on `tomlkit`;
urllib3's suite with its nox session's options ran with no network in 24 to 40
s; `gh run view --job <id> --log-failed` gave empty logs, and the API's job log
holds colour codes.

[VERIFY]:
- Where a run's base commit comes from: the `pull_request` event's, through
  `gh api repos/<repo>/actions/runs/<id>`.
- How long GitHub keeps a run's log: if 90 days, the manifest's CI summary is
  gone for most of an eight-month window, while a run's conclusion stays.
- Whether `uv sync --frozen` still builds an environment eight months back.
- How long the coverage run at M takes with test contexts under xdist.

## Open questions
1. H: the tested head, or a merge of it into the base commit that the run saw,
   as the CI tested. For urllib3's #5278 both passed.
2. Which runs: one per pull request, as the terms above have it, or every run of
   the job in the window, which costs about three times more: urllib3's CI ran
   300 times for 109 pull requests in 52 days.
3. Where the harness lives: in this repository, as above, or in a repository of
   its own.
4. How many reruns: one, as Slice 1's pilot had, or more for tests as flaky as
   urllib3's `test_http2_probe_blocked_per_thread`.
5. The time limit per test: 120 s held for urllib3.
6. Isolation: whether running strangers' commits with no network but the
   loopback is enough, or the runs need a container or a CI runner.
