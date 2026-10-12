# Spike: Weight of M

Throwaway spike on the open question "Weight of M" in `docs/SPEC.md`: how long
the coverage run at M takes on the pilot, how big its file is, how long the
private copy of D-002 takes, and whether reading it through the public API, as
Rule 4 of the technical sheet says, fits the Performance constraint. The code
lived on the branch `spike/weight-of-m` (commit 076775a), deleted afterwards;
the reader is reproduced at the end. `docs/SPEC.md` was not touched.

Labels: **FACT** = I ran it and saw it; **DOC** = official documentation, with
a link; **INFERENCE**; **OPINION**.

## Setup

- Pilot: `sergiparpal/adaptive-policy-compilation`, base branch `main`, tip
  `38470b36eeee228a13000dcad03a90db66e1a5f8`, used as M. FACT.
- Machine: this laptop, WSL2 on Linux 6.6, AMD Ryzen AI 7 350 (16 threads),
  15 GB RAM. **Not a CI runner.** FACT.
- Tools, in a venv outside the pilot (the pilot has no pytest, and its venv
  and `requirements.lock.txt` were not touched): CPython 3.12.3, pytest 9.1.1,
  pytest-cov 7.1.0, coverage 7.16.2 with its C tracer present
  (`coverage/tracer.cpython-312-x86_64-linux-gnu.so`). FACT.
- Nothing written in the pilot's tree: `PYTHONDONTWRITEBYTECODE=1`,
  `-p no:cacheprovider`, `COVERAGE_FILE` and `--junitxml` pointing outside.
  Before and after, `git status --porcelain --ignored` and a listing of every
  file with size and mtime were identical, HEAD unchanged, tree clean. FACT.

## Finding before the figures: the pilot's CI does not run pytest

- The pilot's workflow (`.github/workflows/`, job `suite`) runs
  `python -m unittest discover` on Python 3.10 and 3.12, with nothing
  installed, no coverage options and no JUnit file. FACT (read the file).
- So "the coverage options of its CI" do not exist. I used `--cov=.` (the
  whole repository, tests included), `--cov-context=test`,
  `--cov-report=` (no report) and `COVERAGE_CORE=ctrace`. FACT.
- The Deployment assumes the pull request's full run is a single pytest
  invocation that writes a JUnit file. On the pilot that is not true today:
  either the pilot's CI changes to pytest, or the Deployment does. OPINION:
  this matters more for Slice 1 than any figure below.
- Under pytest the suite collects and passes the same tests as under unittest:
  1,456 test cases (unittest: `Ran 1456 tests`, `skipped=2`; pytest:
  `1454 passed, 2 skipped, 9214 subtests passed`; 1,456 `<testcase>` in each
  JUnit). FACT.

## Step 1: the suite at M, twice

Wall time and peak RSS from `/usr/bin/time -v`, one run each. FACT.

| Run | Wall time | pytest's own time | Peak RSS | Tests |
|---|---|---|---|---|
| plain | 84.29 s | 82.99 s | 332,600 kB | 1,456 |
| `--cov=. --cov-context=test`, `COVERAGE_CORE=ctrace` | 219.95 s | 214.30 s | 342,660 kB | 1,456 |

- Coverage with contexts made the run 2.6 times as long here (one run each, so
  no spread is known). FACT for the two figures, the ratio is arithmetic.
- This is the M job, a separate job, not the pull request's: the 60 s limit
  does not apply to it. But the pilot's workflow has `timeout-minutes: 10` and
  a comment saying the suite takes ~45 s in CI; locally, unittest alone took
  80.7 s. FACT (the comment is the pilot's own claim, not measured by me).
  INFERENCE: at 2.6x, a CI M job would take around 2 min, under 10 min, but
  the ratio was not measured on a runner.

The data file (FACT, through coverage's public API, via the reader below):

| | |
|---|---|
| Size | 638,976 bytes |
| Measured files | 198 (all in the repository; 65 under `tests/`; 2 with no line) |
| Contexts | 1,503: 1,455 `…|run`, 45 `…|setup`, 2 `…|teardown`, 1 empty |
| Node ids with at least one line | 1,455 (of 1,456 test cases) |
| Lines with at least one context | 23,216 |
| (line, context) pairs from `contexts_by_lineno` | 66,895 |
| Most contexts on one line | 126 |
| Line shared by two node ids or more | yes, so not `no-shared-lines` |
| Arcs | no (line coverage) |

The 9,214 subtests add no contexts of their own: contexts are per test, not
per subtest. FACT (no context beyond the 1,456 tests' phases). Which test case
has no line I did not check: unknown.

## Step 2: reading it as the technical sheet says

Script `read_m.py` (end of this note): `shutil.copyfile` into a
`tempfile.TemporaryDirectory`, `CoverageData(basename=copy)`, `read()` before
any query, `measured_files()`, `measured_contexts()`, then one
`contexts_by_lineno(f)` per measured file, splitting each context at its last
`|`. Three runs, each a fresh process. Peak memory is `ru_maxrss` of the
process, interpreter included. FACT.

| Run | Copy | `read()` | listing | rows | read total | RSS at start | Peak RSS |
|---|---|---|---|---|---|---|---|
| 1 | 0.4 ms | 0.5 ms | 0.6 ms | 55.2 ms | 56.3 ms | 23,912 kB | 25,960 kB |
| 2 | 0.3 ms | 0.5 ms | 0.6 ms | 51.7 ms | 52.8 ms | 23,916 kB | 25,964 kB |
| 3 | 0.3 ms | 0.5 ms | 0.6 ms | 51.2 ms | 52.2 ms | 24,040 kB | 25,960 kB |

- The original file's SHA-256 was the same before and after the three runs.
  FACT.
- Almost all of the time is in `contexts_by_lineno`. FACT.
- The script keeps only the set of node ids, not the rows. The tool will keep
  the rows (the Matrix), so its memory will be higher than this; by how much
  was not measured. FACT about the script; the rest is INFERENCE.
- The copy ran from and to a disk the page cache already held; a cold copy on
  a runner was not measured. FACT about the setup.

## Step 3: against the Constraints

The limit: "Evaluating one run with 10,000 tests and 2,000 files takes under
60 s and under 1 GB of memory on a standard hosted CI runner." A standard
GitHub-hosted Linux runner has 4 CPUs, 16 GB RAM for public repositories and
2 CPUs, 8 GB for private ones. DOC:
<https://docs.github.com/en/actions/reference/runners/github-hosted-runners>.
The pilot is public. FACT (`gh repo view`).

All figures here are from this laptop, not from a runner.

- At the pilot's size (1,456 tests, 198 files): copy plus read is about
  0.06 s and 2 MB above the interpreter, three orders of magnitude under the
  limits. FACT for this machine. INFERENCE: a runner several times slower
  still fits.
- No measured figure comes near the limit.
- Extrapolation to 10,000 tests and 2,000 files, all INFERENCE, assuming time
  and the number of pairs grow linearly with tests (x6.9) or with tests times
  files (x69), which bracket it without having been checked:
  - pairs: about 460,000 to 4.6 million;
  - rows time: about 0.4 s to 4 s; far under 60 s even on a runner 5x slower;
  - file size, and so the copy: about 4.4 MB to 44 MB; the copy should stay
    under a second;
  - **memory is the figure that could approach the limit.** If the Matrix
    keeps one Python `str` per (line, context) as `contexts_by_lineno`
    returns them (a fresh string per pair, roughly 100 to 150 bytes with the
    list slot), 4.6 million pairs would take about 0.5 to 0.7 GB, before the
    rest of the run. Interning node ids, or keeping integer ids per test and
    per file, would cut that by an order of magnitude. OPINION: decide it in
    `build_matrix`, not by changing the public-API rule.

## What we learned

- At the pilot's real size, Weight of M is not a problem: neither the copy of
  D-002 nor the public API comes near the limit. FACT on this machine.
- The cost of per-test coverage falls on the M job (2.6x the suite here), not
  on the pull request's job. FACT for the ratio here.
- The pilot's CI runs unittest, not pytest, and writes no JUnit, which the
  Deployment requires. FACT.
- coverage's docs say the `sysmon` core "does not yet support plugins, dynamic
  contexts, or some concurrency libraries" and that `ctrace` "was the default
  until Python 3.13" — DOC:
  <https://coverage.readthedocs.io/en/7.16.2/config.html> (`[run] core`).
  The SPEC's wording ("records each line only for the first test") comes from
  the 2026-10-07 spike; the docs agree it should not be used, and say it more
  broadly. pytest-cov's context names are `<test id>|setup|run|teardown`,
  matching what the file holds. DOC:
  <https://pytest-cov.readthedocs.io/en/latest/contexts.html>.
- Neither coverage's contexts page nor pytest-cov's mentions overhead or size
  of contexts. DOC (checked:
  <https://coverage.readthedocs.io/en/7.16.2/contexts.html> and the pytest-cov
  page above).

## Still unknown

- Every figure on a real GitHub-hosted runner: the M job's time, the copy from
  a cold disk, the read.
- The tool's own memory once it keeps the rows; the 0.5 to 0.7 GB above is an
  estimate, not a measurement. A synthetic data file with 10,000 test contexts
  and 2,000 files, written with `set_context()`/`add_lines()` and read by the
  real `read_coverage`/`build_matrix`, would turn it into a FACT.
- How the number of pairs actually grows with tests and files; the x6.9 to x69
  range is a bracket, not a model.
- The spread of the M job's time: one run of each.
- Whether `set_query_contexts()` batching is needed at all; at the pilot's
  size it is not.
- Which pilot test case has no recorded line, and why.
- Whether the pilot moves its CI to pytest, which Slice 1 needs.

## Reproducing

```sh
uv venv -p 3.12 venv
uv pip install -p venv/bin/python pytest==9.1.1 pytest-cov coverage==7.16.2   # pytest-cov resolved to 7.1.0
cd <pilot>   # at 38470b3
PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -v venv/bin/python -m pytest \
  -p no:cacheprovider -q --junitxml=$OUT/plain.junit.xml
PYTHONDONTWRITEBYTECODE=1 COVERAGE_FILE=$OUT/coverage.db COVERAGE_CORE=ctrace \
  /usr/bin/time -v venv/bin/python -m pytest -p no:cacheprovider -q \
  --junitxml=$OUT/cov.junit.xml --cov=. --cov-context=test --cov-report=
venv/bin/python read_m.py $OUT/coverage.db   # three times
```

`read_m.py`, the core of it:

```python
with tempfile.TemporaryDirectory() as tmp:
    copy = os.path.join(tmp, "coverage")
    shutil.copyfile(path, copy)                      # timed: copy
    data = coverage.CoverageData(basename=copy)
    data.read()                                      # before any query
    files = sorted(data.measured_files())
    contexts = data.measured_contexts()
    for f in files:                                  # timed: rows
        for ctxs in data.contexts_by_lineno(f).values():
            ids = {c.rsplit("|", 1)[0] for c in ctxs if "|" in c}
            ...                                      # node ids, has_shared_line
# peak memory: resource.getrusage(RUSAGE_SELF).ru_maxrss
```
