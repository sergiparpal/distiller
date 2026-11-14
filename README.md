# Distiller

Distiller measures what a test selector would have done on a project's pull requests, without ever deciding which tests run. It runs in CI after a pull request's full pytest run. From the per-test coverage recorded at a commit M of the base branch, the pull request's diff and the run's JUnit, it picks the tests that an all-affected, file-level selector would have chosen, judges whether that choice would have caught the run's failures, and appends one record. `distiller report` turns the records into a miss rate, with its bound, and the share of the suite's test time that the selection would have saved.

This is Slice 1 of a larger design, and `docs/SPEC.md` specifies it. It has no authority: the full suite runs either way.

## Status

The Bet behind Slice 1 was killed on 2026-11-14, at the end of its appetite (D-007). Its hypothesis was that, on sergiparpal/adaptive-policy-compilation, an all-affected, file-level selector would cut at least 25% of the full suite's test time across its pull requests. It cut 16.8%. The code stays here as what the Bet left, and nothing in it is being developed now.

## What was measured

In shadow on the pilot's pull requests, from 2026-10-31 to 2026-11-14:

- 97 runs of 53 pull requests count toward the Bet; D-006 leaves out the four opened for the tool itself. None of the records was rejected.
- Savings: 16.8% of the full suite's test time. It is an upper bound, since fixed per-run costs such as start-up and collection are not in the JUnit times. The floor matched in 44 of the 53 pull requests: the pilot's tests read its result records under `results*/`, which coverage cannot see, so a change to a record runs the whole suite (D-005).
- Cost: `evaluate` took 0.3 to 1.1 s per run, with at most 38 MB of memory. On a made-up run with 10,000 tests and 2,000 files it took 1.3 s and 53 MB, and the report over 1,000 records took 0.2 s.

## What is not proven

- The miss rate. Apart from a smoke test that failed on purpose, no pull request of the pilot had a failing test, so the report says 0 missed out of 0 pull requests with a red run, with no bound. Two other repositories looked at, semantic-diff-weaver and burgess, had no such run that the tool could use either: apart from a dependency bump, which the floor catches, and one failure that passed when run again, their pull requests passed their tests before merging. Nothing here shows how often a selection would let a real failure through.
- Savings anywhere else. There was one pilot, and its tests read its own data files; another project would give another figure.
- A selector with authority. Every figure is what the selector would have done; Slice 1 never ran fewer tests.

## What the Bet left

- Where the tests read files that coverage cannot see, the floor decides the figure. File tracing, which records the files each test reads and which the SPEC leaves out of Slice 1, could put in its place the tests that read each changed file. But the design decides whether to build it with the failed tests that a selection leaves out, and those need red runs.
- The miss rate needs a pilot whose pull requests fail before they merge. A next bet would start by choosing one, before seeing any figure from it.

## Running it

It is not packaged. It needs Python 3.12, the pinned requirements in `requirements.txt`, and GitHub Actions. The pilot's `.github/workflows/distiller.yml` and `.github/distiller/` are a working setup. One job records the coverage at M on every push to the base branch, with pytest-cov's `--cov-context=test` and `COVERAGE_CORE=ctrace`. The other runs the whole suite with `--junitxml` on every pull request, chooses M, and runs, with `PYTHONPATH=src`:

    python -m distiller evaluate --pr N --head REV --base REV --coverage PATH
        --coverage-commit REV --junit PATH [--rerun PATH] [--rootdir DIR]
        [--floor-config PATH] --records PATH [--checkout DIR]
    python -m distiller report RECORD_FILE [RECORD_FILE ...]

`docs/SPEC.md` says what each input must be.

## Documents

- `docs/SPEC.md`: the specification, with the Bet.
- `docs/DECISIONS.md`: the decisions, D-001 to D-007.
- `TASKS.md`: the tasks, and the notes from the pilot.

## License

MIT; see `LICENSE`.
