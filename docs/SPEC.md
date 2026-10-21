# SPEC: Distiller
<!-- The Bet is mine: written before the interview, never edited by the agent.
The agent drafts the rest after interviewing me. The non-goals, the expected
values of [core] examples and the properties are mine.
Mark [core] the examples whose "then" cannot be undone: what gets stored and
in what form, a security decision, an action sent outside. When unsure, [core].
Properties: off. While off, write each invariant as one or two concrete
examples. -->

## Bet
- Hypothesis: on sergiparpal/adaptive-policy-compilation, an all-affected, file-level selector would cut at least 25% of the full suite's test time across its PRs.
- Appetite: 3 weeks, ends 2026-10-31
- Kill signal: at the end of the appetite, the savings measured on sergiparpal/adaptive-policy-compilation are below 25%, or Slice 1 does not run end to end in its CI.

## Problem
Teams whose pull-request CI is dominated by the test suite. As the suite grows, every PR waits for all of it and CI time becomes the bottleneck of the feedback loop: developers wait, and the platform or DevEx team that owns CI pays for the minutes. Today they run the full suite on every PR, keep hand-written per-directory rules, or buy a predictive service that ranks tests but cannot say why a given test did not run. None of these tells a team, from its own history, how often running fewer tests would have let a real failure through, and nobody hands a selector authority without that number.

The whole product is described in `docs/C6-destilador-revisada.md` (in Spanish); the § numbers in this spec refer to it.

## Non-goals
- It never deletes, skips or deselects tests for good: a selection holds for one commit and can be undone, and it is never minimization (§1, §9.1).
- Failure history never decides which tests are left out (§9.4).
- No columns for database schemas, environment variables or calls to other services (§6).
- It never calls a selection safe: it reports a measured miss rate with its bound (§11).
- In Slice 1 it never decides which tests run, and an evaluated run's verdict never changes the CI result: the full suite runs every time, and a missed run exits like a caught one.
- It classifies no failed test left out of a selection by cause: a person does it, from the report.
- Not in Slice 1, though not ruled out: the solver, shards and order (§5); sharded runs, with several JUnit files per run or coverage at M combined from several jobs; file tracing (§6), which §13.2 decides with this slice's figures; the static envelope (§14); any runner other than pytest.

## Constraints
- Stack: Python 3.12+, as a command-line tool run as a CI step; `git` is called as a local binary.
- Allowed dependencies: at run time, `coverage`, to read test contexts through its public API rather than the internal schema of `.coverage`, and `defusedxml`, because the JUnit XML is written by the code under review and is not trusted. `pytest` for the tool's own tests and, for development only, the harness's tools: `ruff`, `pyright`, `pip-audit`, `import-linter` and `pre-commit` with a secret scanner, none of which the tool imports. Anything else needs a change to this spec.
- Performance: in shadow the tool decides nothing and fails no check, but it runs in the pull request's test job, after the tests, so its time adds to that job's. Evaluating one run with 10,000 tests and 2,000 files takes under 60 s and under 1 GB of memory on a standard hosted CI runner; a report over 1,000 recorded runs takes under 10 s. Regime will set its own limit.
- Agent safety: not an agent and does not run inside one; no model reads its inputs or makes its decisions. The external-communication leg is cut anyway: Slice 1 opens no network connection. It reads local files, runs the local `git` and writes local output.
- If no leg can be cut: not applicable.
- Deployment: Slice 1 runs on one pilot repository, named in the Bet, on GitHub Actions. The pull request's full pytest run writes its JUnit in a single pytest invocation, without `--junit-prefix`. The tool's step runs after it whatever the tests' outcome (`if: always()`) and never fails the pull request's CI (`continue-on-error: true`): a rejection shows in the step's log and in the report, never as a failed check. The checkout has the whole history (`fetch-depth: 0`). H is the commit the full run tested, the checkout's HEAD: on the `pull_request` event, the merge commit in `github.sha`, not the pull request's head. Each CI job writes its own record file and the report reads them all, so no two jobs append to the same file. The coverage at M is recorded on the base branch by a separate job, at least once a day, with `--cov-context=test` and `COVERAGE_CORE=ctrace`, and each run is given the newest recorded M that is the merge-base or one of its ancestors. In the first week on the pilot, the records are checked by hand against the CI's list of pull request runs. The checkout is a full clone, not a partial one: in a partial clone, git can fetch missing objects from the remote, and Slice 1 opens no network connection. The base branch is given as `origin/<branch>`, since a pull request's checkout has it only as a remote-tracking branch. Slice 1 is not packaged: the step runs `python -P -m distiller` from a checkout of this repository at a fixed commit, with `PYTHONPATH` set to that checkout's `src` directory and the same version of `coverage` installed as in the job that records M. `-P` keeps the pilot's working directory out of `sys.path`, so that no file in the pilot can stand in for the tool's modules or its dependencies.

## Slices
<Add each slice's criteria just before starting it.>

### Slice 1: Shadow evaluation of an all-affected selector on full pytest runs
Run as a CI step after a pull request's full pytest run, the tool works out which tests an all-affected, file-level selector would have chosen and whether that choice would have caught the run's failures; over many recorded runs, it reports a miss rate and a savings figure. It has no authority: the full suite runs either way.

- Supersedes: none.

Inputs for one run:
- the pull request's number, which is required: the tool runs only on pull requests, not on pushes to the base branch;
- the run's head commit H, in a checkout with history;
- the base branch the pull request targets, as a branch name or as a commit; B is the commit it stands for. The merge-base is the merge-base of B and H, and the diff is `merge-base..H`, the pull request's own change. Neither is computed against M: whenever M is H or one of its ancestors, the merge-base of M and H is M itself, so the check below would reject nothing, not even coverage recorded at H, and the diff would take in the base branch's changes after M;
- the per-test coverage, recorded on the base branch at a commit M as a coverage.py data file with test contexts (pytest-cov `--cov-context=test`), and M itself. M must be the merge-base or one of its ancestors. The pytest run that records the coverage must use coverage's `ctrace` core (`COVERAGE_CORE=ctrace`): the `sysmon` core, coverage's default from Python 3.14, records each line only for the first test that runs it, and the data file does not say which core recorded it, so coverage in which no line was recorded for more than one test is rejected with a reason of its own, `no-shared-lines`, rather than as an unusable input. The rows recorded at M depend on the order of the tests and, under xdist, on how it shares them out among its workers, which changes from one identical run to the next (see the edge case on the session fixture);
- the full run's JUnit XML and, optionally, the JUnit XML of re-running only the tests that failed in it (the rerun file);
- pytest's rootdir, relative to the repository root, if it is not the repository root. Node ids are relative to it, and `own file` and `conftest` resolve paths through it;
- the floor configuration, if any: a text file whose path is given on the command line, with one pattern per line. Spaces and tabs at either end of a line are dropped, but no other whitespace; then a line left empty, or starting with `#`, is ignored, and what is left of any other line is its pattern. It is read as UTF-8: a byte order mark at its start is ignored, a line may end in `\n` or `\r\n`, and the `\r` is not part of its pattern. A file that is not valid UTF-8 cannot be read;
- the record file, whose path is given on the command line.

Terms:
- The changed paths are those that `git diff --name-only --no-renames --no-relative -z <merge-base> <H>` lists. With `--no-renames`, a renamed file is listed under both of its names, and with `-z`, no path is quoted; plain `git diff --name-only` lists only a renamed file's new name and quotes paths with non-ASCII or control characters, quotation marks or backslashes (checked with git 2.43). When H and the base branch have more than one best common ancestor, the merge-base is the one that `git merge-base` prints. That choice can change with the version of git, so evaluating the same inputs twice gives byte-identical results only with the same version of git.
- A test is a pytest test case, named by its node id (`tests/test_tax.py::test_vat`).
- A test context is a coverage context of the form `<node id>|setup`, `<node id>|run` or `<node id>|teardown`, read by splitting it at its last `|`, since a node id can contain one (`tests/test_tax.py::test_odd[a|b]|run`). Any other context, such as the empty one or a static one (`[run] context = ci`), is outside any test.
- A test's row is the set of repository files with at least one line recorded in one of its test contexts: during its setup, its call (`run`) or its teardown. A node id whose recorded lines all fall in files outside the repository has an empty row, and an empty row is no row: its test is unmeasured, and the node id is not among the tests with a row.
- A coverage file is a coverage data file only if coverage reads it without an error and it lists at least one measured file, so an empty file is not one, nor is an SQLite database of something else. A measured file in which no line was recorded is in no row and is not import-only.
- A file recorded in the coverage maps to the longest path among the files in M's tree that the recorded path equals or ends with right after a `/`, compared case-sensitively. A recorded file that maps to none is outside the repository and in no row. So `/runner/work/shop/src/shop/tax.py` maps to `src/shop/tax.py`.
- A column is a file in at least one row. A file whose lines were all recorded outside any test (at import, during collection) is import-only and in no row. A changed path that is neither a column nor import-only has no column.
- The JUnit XML names a test by a pair (`classname`, `name`) that pytest works out from its node id with a private function, `_pytest.junitxml.mangle_test_address`: it splits the node id at `::`, leaving the parameters, from the first `[` on, whole; `classname` is the node id's path, with each `/` turned into `.` and the final `.py` dropped, followed by any classes, all joined by `.`, and `name` is the function with its parameters. So the pair of `tests/test_tax.py::TestVat::test_rate[es-0.21]` is (`tests.test_tax.TestVat`, `test_rate[es-0.21]`).
- Each node id in the test contexts is turned into its pair by that rule and looked up in the JUnit, never the other way round: the rule loses information, and `tests/v1.2/test_x.py::test_m` and `tests/v1/2/test_x.py::test_m` have the same pair, (`tests.v1.2.test_x`, `test_m`). When two node ids have the same pair, the test with that pair counts as unmeasured. All the test cases of a JUnit file that share a pair are one test: failed if any of them has a `failure` or an `error`, with the sum of their times. That covers a `failure` in the call followed by an `error` in the teardown, repeated attempts of one test, and two node ids with the same pair, which the JUnit cannot tell apart. Every count and every list of the run's tests takes each pair once.
- An unmeasured test is a test in the run with no row: new, renamed, not measured, or whose pair is that of no node id in the test contexts, or of more than one.
- The floor is the default patterns `**/config/**`, `**/migrations/**`, `**/poetry.lock`, `**/uv.lock`, `**/Pipfile.lock`, `**/requirements*.txt`, `**/requirements/**`, `**/pyproject.toml`, `**/setup.py`, `**/setup.cfg`, `**/pytest.ini` and `**/tox.ini`, plus whatever patterns the floor configuration adds. A configuration adds patterns and never removes them (§9.3).
- Floor patterns have their own syntax, not Python's `fnmatch`, whose `*` crosses `/` and whose `**/uv.lock` does not match `uv.lock` at the root. A pattern is matched, case-sensitively and one `/`-separated segment at a time, against each changed path, relative to the repository root. A segment that is exactly `**` matches zero or more whole segments, or one or more when it ends the pattern. In any other segment, `*` matches any run of characters except `/`, an empty one included, and every other character matches itself, except `?`, `[` and `]`. A pattern with any of those three, or with a `**` inside a segment, as in `**.lock`, is not valid: whoever writes `data/?.csv` expects a wildcard, and taken literally it would match no real file. Nor is a pattern valid if a segment is empty, `.` or `..`, as in `/config/**`, `config/`, `a//b` or `./config/**`, or if it holds a NUL character, as every line of ASCII saved as UTF-16 without a byte order mark does: no changed path has such a segment or a NUL, so the pattern would silently match nothing. So `**/uv.lock` matches `uv.lock` and `services/billing/uv.lock`; `config/**` matches every file under the top-level `config/` but not a file named `config`; and `**/requirements*.txt` matches `requirements.txt` and `requirements-dev.txt` but not `requirements/dev.txt`, which is why the floor also has `**/requirements/**`.
- The selection is every test in the run that at least one rule picks, each with its reasons, written below as: `covers P` (its row has the changed path P), `floor X (P)` (the changed path P matches floor pattern X, which picks every test), `unmeasured`, `own file P` (P is the file in its node id, what comes before its first `::`) and `conftest P` (P is a `conftest.py` in the test's directory or any directory above it, up to pytest's rootdir). An unmeasured test has no node id, since a pair is never turned back into one, so `own file` and `conftest` never pick it; besides `unmeasured`, only a floor reason can. Every test carries one floor reason for each pattern and changed path that match: `config/pyproject.toml`, which matches `**/config/**` and `**/pyproject.toml`, gives every test two, and a pattern written twice, or a default one written again in the floor configuration, gives no reason twice. A renamed path counts under both of its names, a deleted one under its old name. This notation is for the examples, not an output format.
- A run is red when at least one test has a `failure` or an `error` that the rerun file does not discard; only a pass in the rerun file discards one, and the test is then marked not reproduced. A test passes in the rerun file only if none of its test cases there has a `failure`, an `error` or a `skipped`. A red run is caught when the selection holds at least one of its failed tests and missed otherwise. A run that is not red is green.
- A collection error is the test case that pytest writes in the JUnit for a file it could not collect: an empty `classname` and an `error` whose message is `collection failure` (checked with pytest 9.1.1). By default pytest then runs no test, so the JUnit holds only such errors. A run whose full-run JUnit holds a collection error is rejected with `collection-error`, with the input `junit`: evaluated, it would always count as caught, since the error has no row and is selected as unmeasured, and every test with a row would count as not in the run.
- A test case cannot be used if it lacks a `classname`, a `name` or a `time` attribute, or if its `time` is not one or more ASCII digits, optionally followed by a point and one or more ASCII digits, as pytest writes it (`0.123`). pytest's internal error is the test case it writes when it fails itself: `classname="pytest"`, `name="internal"` and an `error` whose message is `internal error` (checked with pytest 9.1.1). A JUnit file, the full run's or the rerun's, that has a test case that cannot be used, or that holds pytest's internal error, is rejected with `unusable-input` and its input. Evaluated, the internal error would count as an unmeasured failed test and make the run caught, as a collection error would.
- A record is one line that the tool appends to the record file named on its command line: a JSON object in ASCII, with no spaces between tokens and a newline at the end. In its strings, quotation marks, backslashes and the control characters that have one take JSON's short escapes (`\"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t`), and every other character outside printable ASCII (from space to `~`) is written as `\u` and four lowercase hex digits, as a surrogate pair beyond U+FFFF. Every record starts with these keys, in this order: `format`, the record format version, 1; `head`, H's full commit id, or H as given if it names no commit in the checkout; `junit_sha256`, the SHA-256 of the full run's JUnit file, or `null` if there is no such file or it cannot be read; `pr`, the pull request's number; and `verdict`, which is `green`, `caught`, `missed` or `rejected`. `head` and `junit_sha256` are the run's key. `pr` is not part of it: a rejected record already there with the same key, reason and input stops the append, whatever its `pr`. An evaluated run's record goes on with `merge_base` and `coverage_commit` (M), as full commit ids; `selected_ms` and `full_ms`, the selected and full-suite durations in whole milliseconds; `tests`, how many tests the run has; `unmeasured`, how many of them are unmeasured; `tests_with_row`, how many tests have a row; `tests_with_row_not_in_run`, how many of those are not in the run; `floor_matched` and `rerun_given`, as booleans; `not_reproduced`, the failures not reproduced, as pairs; `failed_left_out`, the failed tests left out of the selection, each an object with `pair`, `node_id` and `row`, in that order; `no_column`, the changed paths with no column; and `import_only`, the import-only ones. A node id with a row is in the run when its pair is in the run's JUnit, so two node ids with one pair are both in the run, or both not. A rejected run's record goes on with `reason`, one of `coverage-not-ancestor`, `missing-history`, `unsafe-xml`, `no-shared-lines`, `collection-error` and `unusable-input`, and `input`, one of `head`, `base`, `coverage`, `junit`, `rerun`, `floor` and `checkout`. A pair is a list of two strings, `classname` and `name`. Lists of pairs are sorted by `classname` and then `name`, `failed_left_out` by its pairs, and lists of paths by path, always by Unicode code point. A record holds nothing that changes between two evaluations of the same inputs, such as the time.
- A run is rejected for one of these reasons, each recorded with its input. `unusable-input`, with the input that cannot be used: `checkout` for a directory that is not a git checkout, `head` for an H that names no commit, `base` for a base branch that names no commit, or whose commit shares no history with H, so that they have no merge-base, `coverage` for a coverage file that is missing, cannot be read or is not a coverage data file, or for an M that names no commit, `junit` for a full-run JUnit file that is missing, cannot be read or is not well-formed XML, that has a test case that cannot be used, or that holds pytest's internal error, `rerun` for such a rerun file, and `floor` for a floor configuration that cannot be read or has an invalid pattern. `coverage-not-ancestor`, with `coverage`, when M is neither the merge-base nor one of its ancestors. `missing-history`, with `checkout`, when the checkout is shallow, as `git rev-parse --is-shallow-repository` reports: a shallow clone usually lacks M and the merge-base, so git cannot tell whether M is an ancestor. `unsafe-xml`, with `junit` or `rerun`, for a JUnit or rerun file that declares an entity, even one it never uses: no entity is ever resolved or expanded, so no file or URL that an entity names is ever read. `no-shared-lines`, with `coverage`, for coverage in which no line was recorded for more than one test. `collection-error`, with `junit`, for a full-run JUnit file that holds a collection error.
- An input file that exists but is not a regular file, such as a directory, or that the tool is not allowed to read, cannot be read, and counts like a missing one: `unusable-input`, with that input. The record file is not one of these inputs: if it exists but cannot be read, that is any other failure.
- When a run has more than one problem, the first in this order decides its record: the checkout (not a git checkout, then shallow); H; the base branch; the coverage (unusable, then `coverage-not-ancestor`, then `no-shared-lines`); the full run's JUnit (missing or cannot be read, then `unsafe-xml` or not well-formed, whichever the parser meets first, then a test case that cannot be used or pytest's internal error, then `collection-error`); the rerun file (missing or cannot be read, then `unsafe-xml` or not well-formed, whichever comes first, then a test case that cannot be used or pytest's internal error); the floor configuration.
- Warnings and error messages go to stderr. They name inputs by their path, and commits as given, and never quote what a file holds. A rejection's message names its input, or M when M is what failed: for `coverage-not-ancestor` and for an M that names no commit; the one for `no-shared-lines` also says that the coverage at M must be recorded with `--cov-context=test` and `COVERAGE_CORE=ctrace`, or that the suite's tests share no code. The message for an invalid floor pattern names the configuration file and the pattern's line number. The warning for a run that is already recorded says so and names its key as the record holds it. Any other failure, that is, one that is not a rejection, a line that is not a record, a record file that the report finds missing or cannot read or a usage error, prints one line that names only the class of the error, never its text or a traceback, and exits with 1: a library's error can quote what a file holds.
- Before evaluating a run, the tool reads the record file; if it does not exist, the tool treats it as empty and creates it when it appends. If the file holds a line that is not a record, the tool appends nothing, names the file and the line number in its error message, without quoting the line, and exits with 1. If an evaluated run's record has the run's key, nothing is appended, and the tool warns and exits with 0. Otherwise it evaluates the run, appends its record and exits with 0, whatever the verdict. If it rejects the run instead, it appends its record unless one with the same key, reason and input is already there, and exits with 3. A usage error exits with 2, and any other failure with 1.
- Apart from appending to the record file, the tool never writes to its inputs: it runs only git commands that read, and it leaves the coverage file, the JUnit files and the floor configuration byte for byte as they were, whatever the outcome.
- A line of a record file is a record only if it is byte for byte what the tool would write for a record with those keys and values: a record as defined above, of format 1, ending in a newline. Anything else is not a record, such as an empty line, a line that ends in a carriage return or lacks its newline, or a record of another format. That is checked on the line's shape: its keys and their order, the type and the allowed values of each field, and its bytes. Whether the fields agree with each other, as a `missed` record with an empty `failed_left_out` would not, is not checked.
- The miss rate counts pull requests and looks only at evaluated runs, never at rejected ones: n is the number of PRs with at least one red run, k the number of those with at least one missed run.
- Savings are 1 − Σ selected duration / Σ full-suite duration, summed over every evaluated run, green and red, but never over a rejected one, using the JUnit times.
- Each test case's JUnit time is rounded to the nearest whole millisecond, halves up, before any sum. `full_ms` is the sum over every test case of the full run's JUnit and `selected_ms` over those of the selected tests; neither uses a `testsuite` element's `time`.
- The floor rate counts pull requests, as §13.2 does, and looks only at evaluated runs, never at rejected ones: the share of evaluated PRs, those with at least one evaluated run, in which at least one run had a changed path that matched the floor. It measures how often the floor costs a run its savings. Unlike in §13.2, it does not decide whether to build file tracing: §9.3 keeps the floor when tracing is on, so tracing would not change it.
- The no-column rate counts pull requests: the share of evaluated PRs with at least one run in which a changed path had no column and no changed path matched the floor. Only in such runs could file tracing (§6) change the selection, so the rate is a ceiling on what tracing can change: it also counts paths that tracing would not turn into columns, such as new files or documentation. It is one of the two figures for §13.2. The other is the share of failed tests left out of a selection that are due to a file dependency, which a person classifies from the report, whether or not their run was caught.
- The report reads one or more record files. If one of them holds a line that is not a record, the report produces nothing, names the file and the line number in its error message, without quoting the line, and exits with 1, as the evaluation does. Every record file given to the report must exist and be readable: if one does not exist or cannot be read, the report writes nothing to stdout, names that file in its error message and exits with 1. Unlike the evaluation, it never takes a missing record file as empty, since a mistyped path would drop its runs without a warning. Every figure in it counts each key once, even when the key appears in several record files. If two evaluated runs' records have the same key but differ, the key is left out of every figure, and the report lists it as a conflict, with the record files it appears in: choosing one of the records would make the report depend on the order of the files. The report shows the rejected runs by reason and input, counting only the keys that no evaluated run's record has. The report covers one repository and is never given record files from several. A figure whose denominator is zero is never shown as a percentage: with no pull request with a red run, the miss rate is 0 out of 0, with no bound, and with no evaluated run, or a total full-suite time of zero, there is no savings figure. The report says that its figures belong to the all-affected selector, which picks every test that any rule picks over these rows; a selector that picks only some of them, such as a set cover over the same rows, misses at least as often. The report writes every pair, node id and path as a JSON string, the way the records hold it, so a control character in a test's name or in a path never reaches the terminal or a log unescaped.
- The report depends on neither the order of the record files nor that of their lines. Its lists are sorted first by the run's key, `head` and then `junit_sha256`, with `null` first, and within each run, tests by their pair and paths by path, a conflict's record files among them; the counts of rejected runs are sorted by reason and then input. Every comparison is by Unicode code point, as in records.

All examples use this fixture unless they say otherwise. The run belongs to pull request 7, and `<H>`, `<merge-base>` and `<M>` stand for its commit ids and `<sha>` for the SHA-256 of its JUnit file. Coverage measured `src/` only, M is an ancestor of the merge-base, pytest's rootdir is the repository root, and there is no floor configuration. The full suite takes 12.0 s:

| Test | JUnit time | Row |
|---|---|---|
| `tests/test_pricing.py::test_total` | 2.0 s | `src/shop/pricing.py`, `src/shop/tax.py`, `src/shop/db.py` (run by a session fixture set up during this test's setup) |
| `tests/test_tax.py::test_vat` | 1.0 s | `src/shop/tax.py` |
| `tests/test_report.py::test_render` | 5.0 s | `src/shop/report.py`, `src/shop/pricing.py` |
| `tests/api/test_orders.py::test_create` | 4.0 s | `src/shop/orders.py` |

`src/shop/constants.py` was recorded only outside any test. `templates/invoice.html`, `tests/conftest.py` and `tests/api/conftest.py` were not measured. Below, tests go by their function name. The record file is empty unless an example says otherwise. At least one line of `src/shop/tax.py` was recorded for both test_total and test_vat, so the coverage is not rejected as `no-shared-lines`.

#### Selection
- Given a diff that modifies `src/shop/tax.py`, when the run is evaluated, then the selection is test_total and test_vat, each with `covers src/shop/tax.py`, and test_render and test_create are left out.
- Given a diff that modifies `src/shop/pricing.py` and `src/shop/report.py`, when the run is evaluated, then the selection is test_total and test_render, and test_render has two reasons: `covers src/shop/pricing.py` and `covers src/shop/report.py`.
- Given a diff that modifies `src/shop/db.py`, when the run is evaluated, then the selection is test_total alone, with `covers src/shop/db.py`: what runs during a test's setup and teardown counts as that test's, like its body.
- Given a diff that modifies `uv.lock`, when the run is evaluated, then the selection is all four tests, each with `floor **/uv.lock (uv.lock)`.
- Given a floor configuration that adds `data/**` and a diff that modifies `data/rates.csv`, when the run is evaluated, then the selection is all four tests, each with `floor data/** (data/rates.csv)`.
- Given that same configuration and a diff that modifies `migrations/0002_vat.py`, when the run is evaluated, then the selection is all four tests: the configuration added a pattern and removed none.
- Given a run that also has `tests/test_tax.py::test_rounding`, which has no row, and a diff that modifies `src/shop/report.py`, when the run is evaluated, then the selection is test_render and test_rounding, the latter with `unmeasured`.
- Given a diff that modifies only `tests/test_report.py`, when the run is evaluated, then the selection is test_render, with `own file tests/test_report.py`, although coverage did not measure `tests/`.
- Given a diff that modifies only `tests/test_tax.py`, adding test_rounding, which has no row, when the run is evaluated, then the selection is test_vat, with `own file tests/test_tax.py`, and test_rounding, with only `unmeasured`: it has no node id, so `own file` cannot pick it.
- Given a diff that modifies `tests/api/conftest.py`, when the run is evaluated, then the selection is test_create, with `conftest tests/api/conftest.py`.
- Given a diff that modifies `tests/conftest.py`, when the run is evaluated, then the selection is all four tests, each with `conftest tests/conftest.py`; a `conftest.py` at pytest's rootdir would pick the whole suite.
- Given a diff that deletes `src/shop/report.py`, when the run is evaluated, then the selection is test_render, with `covers src/shop/report.py`.
- Given a diff that renames `src/shop/tax.py` to `src/shop/taxes.py`, when the run is evaluated, then the selection is test_total and test_vat, through the old path, and `src/shop/taxes.py` is listed as a path with no column.
- Given a diff that modifies only `templates/invoice.html`, when the run is evaluated, then the selection is empty and `templates/invoice.html` is listed as a path with no column.
- Given a diff that modifies only `src/shop/constants.py`, when the run is evaluated, then the selection is empty and `src/shop/constants.py` is listed as import-only, separately from the paths with no column.
- Given commits on the base branch after M, all before the merge-base, that modify `src/shop/report.py`, and a pull request whose own change modifies only `src/shop/tax.py`, when the run is evaluated, then the selection is test_total and test_vat: the diff starts at the merge-base of B and H, so the base branch's change to `src/shop/report.py` is not in it.

#### Verdict
- Given a diff that modifies `src/shop/tax.py` and a full run in which test_vat failed, when the run is evaluated, then it is caught.
- Given a diff that modifies only `templates/invoice.html` and a full run in which test_render failed, when the run is evaluated, then it is missed, and test_render is listed as failed and not selected.
- Given a diff that modifies `src/shop/tax.py` and a full run in which test_vat and test_render failed, when the run is evaluated, then it is caught, and test_render is still listed as failed and not selected.
- Given a full run with no `failure` and no `error`, when the run is evaluated, then it is green.
- Given a full run in which only test_render failed and a rerun file in which it passed, when the run is evaluated, then test_render is marked not reproduced and the run is green.

#### Report
- Given recorded runs r1 (green) and r2 (caught) of PR 1, r3 (missed) and r4 (caught) of PR 2, r5 (green) of PR 3 and r6 (caught) of PR 4, when the report is produced, then it shows 1 missed PR out of 3 PRs with a red run, a one-sided 95% Clopper–Pearson upper bound of 86.5%, and 4 red runs.
- Given 30 PRs with a red run and none missed, when the report is produced, then it shows 0 out of 30 and an upper bound of 9.5%.
- Given recorded runs that are all green, when the report is produced, then it shows the miss rate as 0 out of 0 PRs with a red run, with no bound.
- Given two recorded runs of the 12.0 s suite, one that selected 3.0 s and one where the floor selected all 12.0 s, when the report is produced, then it shows savings of 37.5% and says this is an upper bound, because fixed per-run costs such as start-up and collection are not in the JUnit times.
- Given recorded runs of 4 PRs, where all 3 runs of PR 1 matched the floor and the single runs of PRs 2, 3 and 4 did not, when the report is produced, then it shows a floor rate of 25%: 1 PR out of 4, not 3 runs out of 6.
- Given recorded runs of 4 PRs, where the run of PR 1 changed only `templates/invoice.html`, the run of PR 2 changed `templates/invoice.html` and `uv.lock`, and the runs of PRs 3 and 4 changed only `src/shop/tax.py`, when the report is produced, then it shows a no-column rate of 25%: 1 PR out of 4, since PR 2's path with no column came with a floor match.
- Given two recorded runs of four tests each, one of which had one unmeasured test, when the report is produced, then it shows 12.5% of tests treated as unmeasured.
- Given two recorded runs, each evaluated against coverage in which four tests have a row, where one of those four is not in the second run, when the report is produced, then it shows that 12.5% of the tests with a row were not in their run. That share is what gives away a broken matching; the unmeasured share cannot, because it also takes in new tests, skipped tests and tests that run no measured code.
- Given a recorded missed run whose diff modifies only `templates/invoice.html` and in which test_render failed, when the report is produced, then it lists test_render with the reason it was left out (its row, `src/shop/pricing.py` and `src/shop/report.py`, has none of the diff's paths, and no other rule picked it), next to the diff's paths with no column (`templates/invoice.html`) and the import-only ones (none).
- Given a recorded caught run in which test_render also failed without being selected, when the report is produced, then test_render is listed the same way: every failed test left out of a selection is, whether or not its run was caught.
- Given 5 recorded red runs, 2 of them without a rerun file, when the report is produced, then it says that the failures of 2 red runs were not confirmed by a rerun.
- Given recorded runs in which 3 failed tests passed in their rerun files, when the report is produced, then it says that 3 failures were discarded as not reproduced: order-dependent failures (§7) can hide in that count.
- Given a record file in which r1 of PR 1 was first rejected with `"reason":"unusable-input"` and `"input":"coverage"`, because its coverage file was missing, and then evaluated as caught, when the report is produced, then it shows no rejected run and 0 missed PRs out of 1 PR with a red run: a key that an evaluated run's record has is never counted as rejected.
- Given a record file with r1, which selected 3.0 s of the 12.0 s suite, and r2, where the floor selected all 12.0 s, and a second record file with the same record of r1, when the report is produced from both files, then it shows savings of 37.5%, not the 50% that counting r1 twice would give.
- Given a record file with r1 (caught) of PR 1 and r2 (missed) of PR 2, and a second record file where r2, with the same key, is caught, because it was evaluated against coverage from another commit, when the report is produced from both files, then it lists r2's key as a conflict, naming both files, and shows 0 missed PRs out of 1 PR with a red run: r2 counts in no figure.
- Given a recorded run in which a changed path with no column has a newline and an escape character in its name, when the report is produced, then both are written escaped, as `\n` and `\u001b`.
- Given two record files, one of which does not exist, when the report is produced, then it writes no report, its error message names the missing file, and it exits with code 1.

#### Invariants
- Given the same inputs, when the run is evaluated twice, each time with an empty record file, then the two record files end up byte-identical; given the same recorded runs, in any order of the record files and of the lines in them, when the report is produced twice, then both reports are byte-identical.
- Given two runs with the same coverage, diff, tests and floor configuration that differ only in which tests failed and how long tests took, when both are evaluated, then their selections and reasons are identical.
- Given a diff that modifies `src/shop/tax.py`, and then the same diff plus `src/shop/report.py`, when both are evaluated, then the selection grows from test_total and test_vat to test_total, test_vat and test_render, and loses no test.
- Given a diff that modifies `src/shop/tax.py` and a run that also has the unmeasured test_rounding, when the run is evaluated, then every selected test has at least one reason, and every path a reason names is in the diff.

#### Records, rejections and CI signal
- [core] Given a diff that modifies only `templates/invoice.html` and a full run of pull request 7 in which test_render failed, with no rerun file, when its evaluation is recorded, then exactly this line is appended to the record file, where `<H>`, `<merge-base>` and `<M>` stand for the fixture's commit ids and `<sha>` for the SHA-256 of its JUnit file:
  ```json
  {"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"missed","merge_base":"<merge-base>","coverage_commit":"<M>","selected_ms":0,"full_ms":12000,"tests":4,"unmeasured":0,"tests_with_row":4,"tests_with_row_not_in_run":0,"floor_matched":false,"rerun_given":false,"not_reproduced":[],"failed_left_out":[{"pair":["tests.test_report","test_render"],"node_id":"tests/test_report.py::test_render","row":["src/shop/pricing.py","src/shop/report.py"]}],"no_column":["templates/invoice.html"],"import_only":[]}
  ```
- [core] Given a full run in which test_render failed and a rerun file in which it passed, when the evaluation is recorded, then its record has `"verdict":"green"`, `"rerun_given":true`, `"not_reproduced":[["tests.test_report","test_render"]]` and `"failed_left_out":[]`.
- [core] Given a run whose evaluation is already recorded, when the same inputs are evaluated again, then the record file is left byte for byte as it was, the tool warns on stderr that the run is already recorded, naming its key, and it exits with code 0.
- [core] Given coverage recorded at a commit that is neither the merge-base nor one of its ancestors, such as the evaluated run's own coverage at H, when the run is evaluated, then nothing is evaluated, exactly this line is appended: `{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"coverage-not-ancestor","input":"coverage"}`, the error message names M, and the tool exits with code 3.
- [core] Given a shallow checkout, such as a clone made with `--depth 1`, when the run is evaluated, then nothing is evaluated, a record with `"reason":"missing-history"` and `"input":"checkout"` is appended, the error message names the checkout, and the tool exits with code 3.
- [core] Given a JUnit file that declares an external entity or nests entity expansions ("billion laughs"), when the run is evaluated, then no entity is resolved or expanded, so no file or URL that an entity names is ever read; nothing is evaluated, a record with `"reason":"unsafe-xml"` and `"input":"junit"`, or `"input":"rerun"` for the rerun file, is appended, the error message names the file and quotes nothing from it, and the tool exits with code 3.
- [core] Given a run with valid inputs, whether green, caught or missed, when its evaluation finishes as a CI step, then it exits with code 0 whatever the verdict: a missed run never turns the step red.
- [core] Given an input the evaluation cannot use, such as a missing coverage file or a JUnit file that is not well-formed XML, when the run is evaluated, then nothing is evaluated, a record with `"reason":"unusable-input"` and the input that failed is appended, the error message names that input, and the tool exits with code 3. The input is `"checkout"` for a directory that is not a git checkout, `"head"` for an H that names no commit, `"base"` for a base branch that names no commit or shares no history with H, `"coverage"` for a coverage file that is missing, cannot be read or is not a coverage data file, or for an M that names no commit, `"junit"` for a full-run JUnit file that is missing, cannot be read or is not well-formed XML, that has a test case that cannot be used, or that holds pytest's internal error, `"rerun"` for such a rerun file, and `"floor"` for a floor configuration that cannot be read or has an invalid pattern.
- [core] Given a full run whose JUnit holds only a collection error, for `tests/test_report.py`, when the run is evaluated, then nothing is evaluated, a record with `"reason":"collection-error"` and `"input":"junit"` is appended, the error message names the JUnit file, and the tool exits with code 3.
- [core] Given a run rejected because its coverage file was missing, when it is evaluated again with the same inputs, then the record file is left byte for byte as it was, the error message names the coverage file again, and the tool exits with code 3.
- [core] Given that same rejected run, when it is evaluated again with its coverage file, then it is evaluated, its record is appended after the rejected one, and the tool exits with code 0.
- [core] Given coverage in which no line was recorded for more than one test, as the `sysmon` core leaves it, when the run is evaluated, then nothing is evaluated, a record with `"reason":"no-shared-lines"` and `"input":"coverage"` is appended, the error message says that the coverage at M must be recorded with `--cov-context=test` and `COVERAGE_CORE=ctrace`, or that the suite's tests share no code, and the tool exits with code 3.
- [core] Given the missed run of the first [core] example and no file at the record file's path, when the run is evaluated, then the record file is created and holds that example's line and nothing else, the coverage file and the JUnit file are left byte for byte as they were, and the tool exits with code 0.
- [core] Given a coverage file that is empty, 0 bytes long, when the run is evaluated, then nothing is evaluated, a record with `"reason":"unusable-input"` and `"input":"coverage"` is appended, the error message names the coverage file, the coverage file is still 0 bytes long, and the tool exits with code 3.
- [core] Given a record file whose first line is a record and whose second line is not one and holds the text `canary`, when a run is evaluated, then nothing is appended, the record file is left byte for byte as it was, the error message names the record file and line 2, nothing the tool prints contains `canary`, and the tool exits with code 1.

#### Edge cases
- Edge case: test_vat also uses the session fixture whose setup runs `src/shop/db.py` during test_total's setup -> a session fixture's setup counts only in the row of the first test that requests it, and its teardown in the row of the session's last test, even if that test does not use it. A module fixture goes the same way, with its teardown in the row of the last test of its module, and so do `setUpClass` and `tearDownClass`, in the rows of the first and the last test of their class. Here the fixture's teardown runs no line of `src/shop/db.py`, so a diff that modifies only that file selects test_total and not test_vat; if it ran one, that diff would also select the session's last test.
- Edge case: test_create also runs `src/shop/report.py` in a subprocess -> a limitation: what a test runs in a subprocess is not in its row, since pytest-cov 7 no longer measures subprocesses. A diff that modifies only `src/shop/report.py` selects test_render and not test_create, and a run in which only test_create failed is missed.
- Edge case: pytest's rootdir is `backend/`, so a node id reads `tests/test_tax.py::test_vat` while the file is `backend/tests/test_tax.py` -> a diff that modifies `backend/tests/test_tax.py` selects test_vat with `own file`, and the conftest rule resolves paths the same way.
- Edge case: coverage recorded absolute paths under another checkout root (`/runner/work/shop/src/shop/tax.py`) -> matched to `src/shop/tax.py`; a recorded file outside the repository is not a column.
- Edge case: a changed path with spaces or non-ASCII characters (`src/shop/tarifa año.py`) -> matched to its column like any other path, and never listed as having no column because of how `git` quotes it.
- Edge case: test_vat overrides its `classname` with `record_xml_attribute` -> the JUnit names it by a pair that its node id does not turn into, so it is unmeasured: selected with `unmeasured`, counted in the unmeasured share, and counted among the tests with a row that are not in the run.
- Edge case: a test that has a row but is not in the run, because it was deleted or renamed at H -> not selected, and counted only among the tests with a row that are not in the run.
- Edge case: a changed file under `src/` that M never saw, because the PR added it or the base branch did after M -> listed as a path with no column; it picks no test.
- Edge case: a diff that modifies a file that the coverage lists as measured, but with no line recorded -> listed as a path with no column; it picks no test.
- Edge case: a changed path that is a column and also matches the floor (`src/shop/config/loader.py`) -> the whole suite; the tests that cover it carry `covers` as well as the floor reason.
- Edge case: a diff that modifies `services/billing/uv.lock` -> the whole suite: the default patterns match at any depth.
- Edge case: a diff that modifies `requirements/base.txt` -> the whole suite, through `**/requirements/**`.
- Edge case: a diff with no paths -> only the unmeasured tests are selected (none in the fixture).
- Edge case: a test with an `error` in setup or teardown and no `failure` -> it counts as failed, like a `failure`.
- Edge case: a run whose only non-passing results are skips -> green.
- Edge case: a failed test that is missing from the rerun file -> still failed: only a pass in the rerun file discards a failure.
- Edge case: a failed test that the rerun file shows as skipped -> still failed: a skip is not a pass.
- Edge case: a test in the rerun file that did not fail in the full run -> its result is ignored, but the file is still rejected if it has a test case that cannot be used or holds pytest's internal error.
- Edge case: a failure that only happens after certain other tests have run (order dependence, §7) -> it passes in the rerun file and is marked not reproduced, like a flaky one; Slice 1 cannot tell the two apart, and the report shows it only in its count of discarded failures.
- Edge case: a diff that renames `settings/app.yaml` to `config/app.yaml` -> the whole suite: the new name matches `**/config/**`.
- Edge case: a floor configuration with the pattern `**.lock` or `data/?.csv` -> not a valid pattern: an input the evaluation cannot use, as in the [core] example on unusable inputs.
- Edge case: a floor configuration saved with a byte order mark and `\r\n` line endings -> read like the same file without them: its patterns match as usual.
- Property (only while properties are on): for every <input>, <invariant that must hold>.

## Technical sheet
A module that produces the "then" of a [core] example is core. A module with an irreversible effect that no [core] example observes means a missing example.

Option A of `notes/2026-10-10-architecture-options.md`, with D-001 and D-002 of `docs/DECISIONS.md` applied: eleven modules in one package, `distiller`, and no layers.

### [core] examples
| # | Given, in short |
|---|---|
| K1 | a diff that modifies only `templates/invoice.html`; test_render failed; no rerun file |
| K2 | test_render failed in the full run and passed in the rerun file |
| K3 | a run whose evaluation is already recorded, evaluated again with the same inputs |
| K4 | coverage recorded at a commit that is neither the merge-base nor one of its ancestors |
| K5 | a shallow checkout |
| K6 | a JUnit file that declares an external entity or nests entity expansions |
| K7 | valid inputs, and a run that is green, caught or missed |
| K8 | an input the evaluation cannot use, such as a missing coverage file or a malformed JUnit file |
| K9 | a full-run JUnit that holds only a collection error |
| K10 | a run rejected for its missing coverage file, evaluated again with the same inputs |
| K11 | that run, evaluated again with its coverage file |
| K12 | coverage in which no line was recorded for more than one test |
| K13 | K1's missed run, with no file at the record file's path |
| K14 | a coverage file that is empty, 0 bytes long |
| K15 | a record file whose first line is a record and whose second, holding `canary`, is not |

### Modules
| Module | Does | Tier | [core] "then"s |
|---|---|---|---|
| `__main__` | `raise SystemExit(cli.main())`: the only place where a return value becomes the exit code the CI step sees, so one test runs `python -m distiller` | core | K3–K15 |
| `cli` | argparse (`allow_abbrev=False`) into `RunArgs`; runs `evaluate.run` or `report.run`; turns an unexpected exception into `messages.unexpected_failure` and 1. Nothing else | core | K1–K15 |
| `evaluate` | `RunArgs`, and the evaluate command as `run`: record file, key, evaluated check, problem order, record, append, message, exit code | core | K1–K15 |
| `selection` | pure, no I/O: `pair_of`, `match_tests`, `select`, `judge`, `no_column`, `import_only_paths`, `row_counts`, `durations` | core | K1, K2, K11, K13 |
| `messages` | `Rejected`, and one function per text written to stderr | core | K3–K6, K8–K10, K12, K14, K15 |
| `git` | the seven git queries | core | K1–K6, K8–K14 |
| `coverage_at_m` | reads the coverage at M as D-002 says; maps it to M's tree with the pure `build_matrix` | core | K1, K8, K10–K14 |
| `junit` | reads both JUnit files, `None` when missing or unreadable, and parses them, with the test-case rules and pytest's internal error | core | K1–K6, K8–K14 |
| `floor` | reads the floor configuration; the patterns and their matching | core | K1, K8, K11, K13 |
| `records` | encode, decode, read the record file, append | core | K1–K6, K8–K15 |
| `report` | the report command: dedupe, figures, bound, text, with the sentence that its figures belong to the all-affected selector | medium | none |

`git` and `junit` give the run's key, so they are in every row whose record or warning shows it. `report` is medium: records are kept, so a wrong figure is fixed by running a corrected report again.

### Interfaces
```python
# cli.py
def main(argv: list[str] | None = None) -> int: ...

# evaluate.py
def run(args: RunArgs) -> int: ...                       # prints its message; returns the exit code

# report.py
def run(paths: list[str]) -> int: ...                    # the report on stdout
def clopper_pearson_upper(k: int, n: int) -> float | None: ...  # None when n is 0

# messages.py
class Rejected(Exception):
    def __init__(self, reason: str, input_name: str, subject: str,
                 line_number: int | None = None) -> None: ...
def rejection(error: Rejected) -> str: ...
def already_recorded(head: str, junit_sha256: str | None) -> str: ...
def not_a_record(path: str, line_number: int) -> str: ...
def unreadable_record_file(path: str) -> str: ...        # the report's: it does not exist or cannot be read
def unexpected_failure(error_type: type[BaseException]) -> str: ...  # the class, never the instance

# selection.py
def pair_of(node_id: NodeId) -> Pair: ...
def match_tests(results: dict[Pair, Result], rows: dict[NodeId, frozenset[RepoPath]]) -> list[Test]: ...
def select(tests: list[Test], changed: list[RepoPath],
           hits: list[tuple[str, RepoPath]], rootdir: str) -> Selection: ...  # rootdir as RunArgs holds it, "" for the repository root
def judge(full: JUnit, rerun: JUnit | None, tests: list[Test], selection: Selection) -> Judgement: ...
def no_column(changed: list[RepoPath], matrix: Matrix) -> list[RepoPath]: ...         # sorted
def import_only_paths(changed: list[RepoPath], matrix: Matrix) -> list[RepoPath]: ...  # sorted
def row_counts(rows: dict[NodeId, frozenset[RepoPath]],
               results: dict[Pair, Result]) -> tuple[int, int]: ...  # tests_with_row, not in the run
def durations(full: JUnit, selection: Selection) -> tuple[int, int]: ...  # selected_ms, full_ms

# git.py: each runs `git -C checkout ...`
def is_checkout(checkout: str) -> bool: ...
def is_shallow(checkout: str) -> bool: ...
def resolve_commit(checkout: str, name: str) -> Commit | None: ...
def merge_base(checkout: str, a: Commit, b: Commit) -> Commit | None: ...  # None: no common history
def is_ancestor(checkout: str, ancestor: Commit, descendant: Commit) -> bool: ...
def changed_paths(checkout: str, old: Commit, new: Commit) -> list[RepoPath]: ...
def tree_files(checkout: str, commit: Commit) -> frozenset[RepoPath]: ...

# coverage_at_m.py
def read_coverage(path: str) -> RawCoverage: ...         # raises Rejected
def node_id_of(context: str) -> NodeId | None: ...       # None: not a test context
def build_matrix(raw: RawCoverage, tree: frozenset[RepoPath]) -> Matrix: ...

# junit.py
def read_junit(path: str) -> bytes | None: ...           # None: missing or cannot be read
def parse_junit(data: bytes, input_name: str, path: str) -> JUnit: ...  # raises Rejected

# floor.py
DEFAULT_PATTERNS: tuple[str, ...]
def read_floor(path: str | None) -> tuple[str, ...]: ... # the defaults, then the file's; raises Rejected
def matches(pattern: str, path: RepoPath) -> bool: ...
def floor_hits(patterns: tuple[str, ...], changed: list[RepoPath]) -> list[tuple[str, RepoPath]]: ...  # every (pattern, path) pair that matches

# records.py
class NotARecord(Exception):
    def __init__(self, path: str, line_number: int) -> None: ...
def encode(record: Record) -> bytes: ...
def decode(line: bytes) -> Record | None: ...            # None: not a record
def read_record_file(path: str) -> list[Record] | None: ...  # None: no file; raises NotARecord,
                                                             # or OSError if it exists but cannot be read
def has_evaluated(records: list[Record], key: RunKey) -> bool: ...
def has_rejected(records: list[Record], key: RunKey, reason: str, input_name: str) -> bool: ...
def append_record(path: str, record: Record) -> None: ...
```

A `Rejected`'s `subject` is the path or name, as given on the command line, that its message names; `line_number` is set only for an invalid floor pattern.

### Data model
Frozen dataclasses, the only decorator in the code: no metaclasses, registries, `getattr` dispatch or dynamic imports. Each type lives in the module that creates it, and there is no `model.py`. Python names say `input_name` where the record says `input`.

```python
# git.py
Commit = str                     # a full commit id
RepoPath = str                   # "/"-separated, from the repository root

# junit.py
Pair = tuple[str, str]           # (classname, name)
@dataclass(frozen=True)
class Result:                    # one pair in one JUnit file, its test cases merged
    failed: bool                 # a case has a failure or an error
    passed: bool                 # no case has a failure, an error or a skipped
    time_ms: int                 # the cases' times, each rounded half up, summed
@dataclass(frozen=True)
class JUnit:
    results: dict[Pair, Result]
    has_collection_error: bool

# coverage_at_m.py
NodeId = str                     # relative to pytest's rootdir
@dataclass(frozen=True)
class RawCoverage:               # as coverage's API gives it
    nodes_by_file: dict[str, frozenset[NodeId]]  # recorded path -> node ids with a line in it
    import_only_files: frozenset[str]            # recorded paths with lines, none in a test context
    has_shared_line: bool                        # a line recorded for two node ids or more
@dataclass(frozen=True)
class Matrix:                    # mapped to M's tree
    rows: dict[NodeId, frozenset[RepoPath]]      # every node id in a test context, empty rows too
    import_only: frozenset[RepoPath]

# selection.py
@dataclass(frozen=True)
class Test:                      # a test of the run, after matching
    pair: Pair
    node_id: NodeId | None       # None when unmeasured
    row: frozenset[RepoPath] | None  # None when unmeasured
@dataclass(frozen=True)
class Reason:
    rule: str                    # "covers", "floor", "unmeasured", "own file" or "conftest"
    path: RepoPath | None        # None only for "unmeasured"
    pattern: str | None = None   # only for "floor"
Selection = dict[Pair, frozenset[Reason]]        # selected tests only, never an empty set
@dataclass(frozen=True)
class Judgement:
    verdict: str                 # "green", "caught" or "missed"
    not_reproduced: frozenset[Pair]
    failed_left_out: tuple[Test, ...]            # all measured, so node_id and row are set

# records.py
@dataclass(frozen=True)
class RunKey:
    head: str                    # H's full commit id, or H as given
    junit_sha256: str | None
@dataclass(frozen=True)
class RejectedRecord:
    key: RunKey
    pr: int
    reason: str
    input_name: str
Record = EvaluatedRecord | RejectedRecord
```

`EvaluatedRecord` (`records.py`) has the record's fields in the SPEC's order, with `key: RunKey` in place of `head` and `junit_sha256`, and no `format`: `pr`, the durations and the counts are `int`, `verdict` is `str`, `merge_base` and `coverage_commit` are `Commit`, `floor_matched` and `rerun_given` `bool`, `not_reproduced` a `tuple[Pair, ...]`, `failed_left_out` a `tuple[Test, ...]`, and `no_column` and `import_only` `tuple[RepoPath, ...]`. `RunArgs` (`evaluate.py`) has one field per option: `pr: int`, `rerun` and `floor_config` `str | None`, `rootdir` `""` for the repository root, and the rest `str`. Each field holds its option as given, except `rootdir`, which is normalized by the rules under "Command line".

`Matrix.rows` keeps empty rows because a node id with an empty row still counts among the node ids of its pair; for everything else an empty row is no row.

### Command line
```
python -m distiller evaluate --pr N --head REV --base REV --coverage PATH
    --coverage-commit REV --junit PATH [--rerun PATH] [--rootdir DIR]
    [--floor-config PATH] --records PATH [--checkout DIR]
python -m distiller report RECORD_FILE [RECORD_FILE ...]
```

Each option is one of the inputs in the prose, `--coverage-commit` being M. On `pull_request`, `--head` is `$GITHUB_SHA` and `--base` is `origin/<branch>`. `--rootdir` defaults to the repository root and `--checkout` to `.`. Choosing M stays outside the tool.

Usage errors exit with 2 and append nothing: a missing or unknown option, never abbreviated, so `--rec` is not `--records`; a `--pr` that is not ASCII digits above 0; a `--rootdir` that is absolute or has a `..` segment. A path that does not exist is never a usage error: for `evaluate` it is a rejection, or an empty record file for `--records`, and for `report` an error that names it.

A `--rootdir` that is not a usage error is normalized by `cli`, which drops its empty and `.` segments: `.` and an empty value are the repository root, `""` in `RunArgs`, and `./backend` and `backend/` are `backend`.

| Exit | `evaluate` | `report` |
|---|---|---|
| 0 | evaluated, whatever the verdict, or already recorded | the report, on stdout |
| 1 | a line that is not a record, or any other failure | a record file that does not exist or cannot be read, a line that is not a record, or any other failure |
| 2 | a usage error | a usage error |
| 3 | rejected | never |

### How a run goes
1. `cli.main` parses the arguments and calls `evaluate.run`.
2. `run` reads the record file, `None` being an empty one (`NotARecord`: `messages.not_a_record`, exit 1), then reads the full run's JUnit bytes and resolves H, which give the key. If an evaluated record has the key: `messages.already_recorded`, exit 0, nothing appended.
3. It walks the problem order, one call per check, each returning a value or raising `Rejected`. For the coverage: M, then the file, read in full, then the ancestry, then the shared lines.
4. With no problem: the diff, M's tree, `build_matrix`, `match_tests`, `floor_hits`, `select` and `judge` give the record, which is appended; exit 0.
5. On `Rejected`: the rejected record is appended unless `has_rejected` finds it, and `messages.rejection` is printed; exit 3.
6. Any other exception reaches `cli.main`: `messages.unexpected_failure`, exit 1.

The report reads its record files in the order given, all of them before it writes anything to stdout, and the first problem stops it with exit 1: `messages.unreadable_record_file` when `read_record_file` gives `None` or raises `OSError`, and `messages.not_a_record` when it raises `NotARecord`.

### Rules
1. **Dependencies.** The standard library, `coverage` and `defusedxml`, each of the two imported by one module (Imports). git runs only through `subprocess.run` with an argument list, never a shell.
2. **Git names.** H, the base and M are each resolved once, with `git rev-parse --verify --quiet --end-of-options NAME^{commit}`; every other git command gets full commit ids only, so nothing from the command line reaches git as an option. Paths come from `-z` output, decoded with `os.fsdecode`. git's stdout and stderr are always captured, so nothing git prints reaches the tool's stderr. Only the commands under "Checked" run.
3. **Inputs are only read.** The coverage, JUnit, floor and record file paths are checked with `os.stat` to be regular files before they are opened: opening a FIFO blocks. The JUnit files and the floor configuration are opened for reading only. The coverage file is copied as D-002 says, with no SQLite header check, and `read()` runs on the copy before any query; a `coverage.CoverageException`, an `sqlite3.Error`, or a copy that lists no measured file, is `unusable-input`: coverage lets `sqlite3.OperationalError` through when the copy already holds a table named like one of its own, such as `meta`.
4. **Rows from the public API.** One `contexts_by_lineno(f)` per measured file; a line recorded for two node ids or more sets `has_shared_line`. The reader keeps nothing per line: of each file, only the node ids with a line in it, and of all files, only whether some line was recorded for two node ids or more. If reading the rows misses the time or memory limit, only `read_coverage` changes.
5. **JUnit.** Each file is read once into bytes; the full run's give `junit_sha256` and are parsed, and hashing parses nothing. `defusedxml.ElementTree.fromstring` runs at its defaults, with entities and external references forbidden and DTDs allowed: `EntitiesForbidden` and `ExternalReferenceForbidden` are `unsafe-xml`, `ParseError` is `unusable-input`. A `time` must fullmatch `[0-9]+(\.[0-9]+)?`, since `\d` and `Decimal` also take other scripts' digits, and goes through `Decimal(text).quantize(Decimal("0.001"), ROUND_HALF_UP)`, never through a float.
6. **Messages.** Every text on stderr comes from a function of `messages` (D-001), except argparse's usage error, which holds only the command line. `cli` catches any other `Exception`, prints `messages.unexpected_failure` and returns 1.
7. **Records.** `encode` builds a dict in the SPEC's key order and writes `json.dumps(obj, separators=(",", ":"))` and `\n`; the default `ensure_ascii` gives the SPEC's escapes. `decode` checks that the line is ASCII, parses it, checks its keys and their order, exact types (`type(x) is int`, so `true` is not `1`), allowed values, and lists sorted with no repeats, rebuilds the record and requires `encode(record) == line`. It checks no agreement between fields. `report` writes pairs, node ids and paths with the same `json.dumps`.
8. **Determinism.** Every list that reaches a record or the report is sorted where it is built, by code point, which is Python's `str` order. No set order, clock or environment value reaches an output. The append is one write of the whole line to a file opened for appending, created if missing.
9. **Floor configuration.** Its lines are split on `\n` only, and one `\r` at the end of a line is dropped: `str.splitlines()` also splits on `\r` alone, `\v`, `\f`, `\x1c` to `\x1e`, `\x85`, `\u2028` and `\u2029`. Then spaces and tabs are dropped from both ends with `strip(" \t")`: `str.strip()` also drops `\v`, `\f`, `\x1c` to `\x1f`, `\x85`, `\xa0` and other Unicode spaces.

### Imports
`lint-imports`, from import-linter, checks these once the harness is in place:
- only `coverage_at_m` imports `coverage`, only `junit` imports `defusedxml`, and only `git` imports `subprocess`;
- `messages` imports no other module of the package;
- only `__main__` imports `cli`, and only `cli` imports `evaluate` and `report`.

### Irreversible effects
| Effect | Module | Observed by |
|---|---|---|
| Appending a record line | `records`, as `evaluate` decides | K1, K2, K4–K6, K8, K9, K11–K14; nothing appended: K3, K10, K15 |
| Creating the record file | `records` | K13 |
| Writing to the coverage file | `coverage_at_m`, through coverage | K13, K14 |
| Writing to the JUnit file | `junit`, which opens it for reading only | K13 |
| Reading a file or URL that an XML entity names | `junit`, through defusedxml | K6 |
| Text on stderr, kept in the CI log | `messages`, printed by `evaluate`, `report` and `cli` | what it names: K3–K6, K8–K10, K12, K14, K15; that it quotes nothing: K6, K15. The unexpected-failure line: a test that makes a reader raise an error whose text holds a canary |
| The report's text, in a terminal or a log | `report` | no [core], since `report` is medium; its escaping, the Report example on a path with a newline and an escape character |
| A torn append, from a killed runner or a full disk | `records` | none; the line it leaves is not a record, which K15 covers |
| A network connection opened by git | `git` | none: the Deployment rules out a partial clone |
| The private copy, left in the temporary directory | `coverage_at_m` | none: only a killed process leaves it (D-002) |

### Checked and [VERIFY]
*read*: in the installed source of coverage 7.16.2, pytest 9.1.1 and defusedxml 0.7.1. *run*: executed on 2026-10-10, git with git 2.43.0 and coverage on Python 3.13.

- coverage 7.16.2. *read*: `CoverageData(basename=path)`, whose `read()` does nothing when the file is missing; `measured_files() -> set[str]`, which may list a file with no line; `measured_contexts() -> set[str]`; `contexts_by_lineno(filename) -> dict[int, list[str]]`, `{}` for an unknown file, built from arcs under branch coverage, both also used on pytest-cov data in the spike; `set_query_contexts()`, whose regexes are matched with `re.search`; `SCHEMA_VERSION = 7`, another version raising `DataError`; `set_context()` and `add_lines()` for test fixtures, with `write()` a no-op without a suffix. *run*: a file queried before `read()` loses its contexts for good; `read()` modifies an SQLite database without coverage's tables, and an empty file grows to 53,248 bytes; through a private copy the original is unchanged in all three cases, and the copy of an empty file, or of a foreign SQLite database, lists no measured file, unless that database already holds a table named like one of coverage's, such as `meta`, when `read()` raises `sqlite3.OperationalError` (run on 2026-10-19); a text file raises `DataError`, a subclass of `coverage.CoverageException`, which coverage exports at the top level; a data file recorded without contexts lists its files and only the empty context.
- pytest 9.1.1. *read*: `_pytest.junitxml.mangle_test_address(address: str) -> list[str]`; `classname` is `".".join(names[:-1])`, after `--junit-prefix`, and `name` is `bin_xml_escape(names[-1])`; a collection error is `<error message="collection failure">`, also seen in the spike; the fixtures `tmp_path`, `capsys`, `capfd` and `monkeypatch`. *run*: `pytest_internalerror` writes a test case with `classname="pytest"`, `name="internal"` and an `error` with the message `internal error`, whose text is the traceback; every test case's `time` is written as `f"{duration:.3f}"`.
- git 2.43. *run*: `rev-parse --is-inside-work-tree` prints `true`, and exits with 128 outside a repository; `rev-parse --is-shallow-repository` prints `false` in a full clone and `true` in one made with `--depth 1`; `rev-parse --verify --quiet --end-of-options NAME^{commit}` prints the full id, and exits with 1 for an unknown name, a tree or an option-like name such as `--all`; `merge-base A B` prints one commit, and with no common history exits with 1 and prints nothing; `merge-base --is-ancestor A B` exits with 0 when A is B or an ancestor of it, 1 when not, 128 for an unknown name; `diff --name-only --no-renames --no-relative -z A B` prints NUL-terminated paths from the root, also from a subdirectory with `diff.relative=true`, prints no colour codes with `color.ui=always` and leaves `.git/index` unchanged; `ls-tree -r --name-only -z --full-tree C` lists every path from the root, while without `--full-tree`, from a subdirectory, it lists only that subdirectory; in a clone made with `--filter=blob:none`, `diff --name-only`, `ls-tree -r --name-only --full-tree` and `merge-base` work with the remote unreachable, while with `--filter=tree:0` `diff` and `ls-tree` need it; a partial clone has `remote.<name>.promisor=true`; `git --no-lazy-fetch` is an unknown option. From *man gitrevisions*: a bare branch name resolves only through `refs/heads/`, `refs/remotes/<name>` and `refs/remotes/<name>/HEAD`.
- defusedxml 0.7.1. *read*: `defusedxml.ElementTree.fromstring(text, forbid_dtd=False, forbid_entities=True, forbid_external=True)`; an entity declaration raises `EntitiesForbidden`, an external reference `ExternalReferenceForbidden`, and malformed XML `xml.etree.ElementTree.ParseError`; the exceptions' `str()` holds the entity's name and system id. *run*: a malformed byte before an entity declaration raises `ParseError`; an entity declaration followed by a malformed body raises `EntitiesForbidden`; a DOCTYPE whose external subset does not exist parses, so the subset is not read.
- Standard library. *run*: `json.dumps` escapes as the SPEC says, with DEL as `\u007f`, lowercase hex and surrogate pairs; a Clopper–Pearson upper bound by bisection gives 86.5% for 1 of 3, 9.5% for 0 of 30, 63.2% for 0 of 3 and 9.8% for 0 of 29, and since `math.comb(n, i) * p**i` overflows from about n = 1,030, the report works with `math.lgamma`.

[VERIFY]:
- The time and memory of reading the rows, one `contexts_by_lineno()` per file, at 10,000 tests and 2,000 files. *run* on the pilot's M (1,456 tests, 198 measured files, a 638,976-byte file), on a laptop, not a CI runner: copying the file takes under 1 ms, and reading the rows about 55 ms and about 2 MB beyond the interpreter (`notes/2026-10-12-weight-of-m.md`). At 10,000 tests and 2,000 files, nobody has measured it. Batching with `set_query_contexts()` would bound memory but not time, and its speed is unknown.
- `mangle_test_address` is private: check its behaviour again on each pytest upgrade.
- Whether `coverage.exceptions` is documented as public; catching `coverage.CoverageException` sidesteps it.
- A repository owned by another user ("dubious ownership") makes every git command fail, which the tool would report as not a git checkout.
- defusedxml 0.7.1 on Python 3.13 and 3.14.
- Which coverage versions write schema 7: not needed while the Deployment installs the same `coverage` in both jobs.

## Open questions
- Failures inherited from the base branch. If the base branch was already red at the merge-base, the PR's run fails for reasons outside its diff and counts against the selector, and the rerun file reproduces them. Should a later slice read the base's results to set them apart? The same goes for a red run whose diff is empty: it is missed unless one of its failed tests is unmeasured.
- Matrix age. Slice 1 sets no limit on how far M lags behind the merge-base, while regime assumes a matrix at most 24 h old (§8). Should the report show the lag?
- Thresholds for §13.2. What "marginal" and "low" mean in numbers, and how many classified failed tests left out that takes. With the report's bound, showing that file dependencies are rare takes far more of them than showing that they are common: 0 out of 3 bounds the share below 63.2%, and bounding it below 10% takes 29 classified failed tests left out with no file dependency.
- `sysmon` under xdist. Each worker records a line once, so a line can be shared by as many tests as there are workers, and `no-shared-lines` may not fire although the rows are partial. An untested inference; one spike scenario (`COVERAGE_CORE=sysmon`, `-n 4`) settles it.
