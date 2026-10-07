# SPEC: Distiller
<!-- The Bet is mine: written before the interview, never edited by the agent.
The agent drafts the rest after interviewing me. The non-goals, the expected
values of [core] examples and the properties are mine.
Mark [core] the examples whose "then" cannot be undone: what gets stored and
in what form, a security decision, an action sent outside. When unsure, [core].
Properties: off. While off, write each invariant as one or two concrete
examples. -->

## Bet
- Hypothesis: <falsifiable sentence from the idea protocol>
- Appetite: <N weeks>, ends <YYYY-MM-DD>
- Kill signal: <observable result that ends the project>

## Problem
Teams whose pull-request CI is dominated by the test suite. As the suite grows, every PR waits for all of it and CI time becomes the bottleneck of the feedback loop: developers wait, and the platform or DevEx team that owns CI pays for the minutes. Today they run the full suite on every PR, keep hand-written per-directory rules, or buy a predictive service that ranks tests but cannot say why a given test did not run. None of these tells a team, from its own history, how often running fewer tests would have let a real failure through, and nobody hands a selector authority without that number.

The whole product is described in `docs/C6-destilador-revisada.md` (in Spanish); the § numbers in this spec refer to it.

## Non-goals
- <What it will not do, even if it is easy.>

## Constraints
- Stack: Python 3.12+, as a command-line tool run as a CI step; `git` is called as a local binary.
- Allowed dependencies: at run time, `coverage`, to read test contexts through its public API rather than the internal schema of `.coverage`, and `defusedxml`, because the JUnit XML is written by the code under review and is not trusted. `pytest` for the tool's own tests. Anything else needs a change to this spec.
- Performance: in shadow the tool is off the critical path. Evaluating one run with 10,000 tests and 2,000 files takes under 60 s and under 1 GB of memory on a standard hosted CI runner; a report over 1,000 recorded runs takes under 10 s. Regime will set its own limit.
- Agent safety: not an agent and does not run inside one; no model reads its inputs or makes its decisions. The external-communication leg is cut anyway: Slice 1 opens no network connection. It reads local files, runs the local `git` and writes local output.
- If no leg can be cut: not applicable.

## Slices
<Add each slice's criteria just before starting it.>

### Slice 1: Shadow evaluation of an all-affected selector on full pytest runs
Run as a CI step after a pull request's full pytest run, the tool works out which tests an all-affected, file-level selector would have chosen and whether that choice would have caught the run's failures; over many recorded runs, it reports a miss rate and a savings figure. It has no authority: the full suite runs either way.

- Supersedes: none.

Inputs for one run:
- the run's head commit H, in a checkout with history;
- the base branch the pull request targets, as a branch name or as a commit; B is the commit it stands for. The merge-base is the merge-base of B and H, and the diff is `merge-base..H`, the pull request's own change. Neither is computed against M: whenever M is H or one of its ancestors, the merge-base of M and H is M itself, so the check below would reject nothing, not even coverage recorded at H, and the diff would take in the base branch's changes after M;
- the per-test coverage, recorded on the base branch at a commit M as a coverage.py data file with test contexts (pytest-cov `--cov-context=test`), and M itself. M must be the merge-base or one of its ancestors. The pytest run that records the coverage must use coverage's `ctrace` core (`COVERAGE_CORE=ctrace`): the `sysmon` core, coverage's default from Python 3.14, records each line only for the first test that runs it, and the data file does not say which core recorded it, so coverage in which no line was recorded for more than one test is an input the evaluation cannot use. The rows recorded at M depend on the order of the tests and, under xdist, on how it shares them out among its workers, which changes from one identical run to the next (see the edge case on the session fixture);
- the full run's JUnit XML and, optionally, the JUnit XML of re-running only the tests that failed in it (the rerun file);
- the repository's floor configuration, if it has one.

Terms:
- A test is a pytest test case, named by its node id (`tests/test_tax.py::test_vat`).
- A test context is a coverage context of the form `<node id>|setup`, `<node id>|run` or `<node id>|teardown`, read by splitting it at its last `|`, since a node id can contain one (`tests/test_tax.py::test_odd[a|b]|run`). Any other context, such as the empty one or a static one (`[run] context = ci`), is outside any test.
- A test's row is the set of repository files with at least one line recorded in one of its test contexts: during its setup, its call (`run`) or its teardown.
- A column is a file in at least one row. A file whose lines were all recorded outside any test (at import, during collection) is import-only and in no row. A changed path that is neither a column nor import-only has no column.
- The JUnit XML names a test by a pair (`classname`, `name`) that pytest works out from its node id with a private function, `_pytest.junitxml.mangle_test_address`: it splits the node id at `::`, leaving the parameters, from the first `[` on, whole; `classname` is the node id's path, with each `/` turned into `.` and the final `.py` dropped, followed by any classes, all joined by `.`, and `name` is the function with its parameters. So the pair of `tests/test_tax.py::TestVat::test_rate[es-0.21]` is (`tests.test_tax.TestVat`, `test_rate[es-0.21]`).
- Each node id in the test contexts is turned into its pair by that rule and looked up in the JUnit, never the other way round: the rule loses information, and `tests/v1.2/test_x.py::test_m` and `tests/v1/2/test_x.py::test_m` have the same pair, (`tests.v1.2.test_x`, `test_m`). When two node ids have the same pair, the tests with that pair count as unmeasured. A pair that one test leaves twice, a `failure` in its call and an `error` in its teardown, is one failed test, whose time is the sum of both.
- An unmeasured test is a test in the run with no row: new, renamed, not measured, or whose pair is that of no node id in the test contexts, or of more than one.
- The floor is the default patterns `**/config/**`, `**/migrations/**`, `**/poetry.lock`, `**/uv.lock`, `**/Pipfile.lock`, `**/requirements*.txt`, `**/requirements/**`, `**/pyproject.toml`, `**/setup.py`, `**/setup.cfg`, `**/pytest.ini` and `**/tox.ini`, plus whatever patterns the repository's configuration adds. A configuration adds patterns and never removes them (§9.3).
- Floor patterns have their own syntax, not Python's `fnmatch`, whose `*` crosses `/` and whose `**/uv.lock` does not match `uv.lock` at the root. A pattern is matched, case-sensitively and one `/`-separated segment at a time, against each changed path, relative to the repository root. A segment that is exactly `**` matches zero or more whole segments, or one or more when it ends the pattern. In any other segment, `*` matches any run of characters except `/`, and every other character matches itself, except `?`, `[` and `]`. A pattern with any of those three, or with a `**` inside a segment, as in `**.lock`, is not valid: whoever writes `data/?.csv` expects a wildcard, and taken literally it would match no real file. So `**/uv.lock` matches `uv.lock` and `services/billing/uv.lock`; `config/**` matches every file under the top-level `config/` but not a file named `config`; and `**/requirements*.txt` matches `requirements-dev.txt` but not `requirements/dev.txt`, which is why the floor also has `**/requirements/**`.
- The selection is every test in the run that at least one rule picks, each with its reasons, written below as: `covers P` (its row has the changed path P), `floor X (P)` (the changed path P matches floor pattern X, which picks every test), `unmeasured`, `own file P` (P is the file in its node id) and `conftest P` (P is a `conftest.py` in the test's directory or any directory above it, up to pytest's rootdir). An unmeasured test has no node id, since a pair is never turned back into one, so `own file` and `conftest` never pick it; besides `unmeasured`, only a floor reason can. A renamed path counts under both of its names, a deleted one under its old name. This notation is for the examples, not an output format.
- A run is red when at least one test has a `failure` or an `error` that the rerun file does not discard; only a pass in the rerun file discards one, and the test is then marked not reproduced. A red run is caught when the selection holds at least one of its failed tests and missed otherwise. A run that is not red is green.
- The miss rate counts pull requests: n is the number of PRs with at least one red run, k the number of those with at least one missed run.
- Savings are 1 − Σ selected duration / Σ full-suite duration, summed over every recorded run, green and red, using the JUnit times.
- The floor rate counts pull requests, as §13.2 does: the share of evaluated PRs, those with at least one recorded run, in which at least one run had a changed path that matched the floor. It is one of the two figures with which §13.2 decides whether to build file tracing.

All examples use this fixture unless they say otherwise. Coverage measured `src/` only, M is an ancestor of the merge-base, pytest's rootdir is the repository root, and there is no floor configuration. The full suite takes 12.0 s:

| Test | JUnit time | Row |
|---|---|---|
| `tests/test_pricing.py::test_total` | 2.0 s | `src/shop/pricing.py`, `src/shop/tax.py`, `src/shop/db.py` (run by a session fixture set up during this test's setup) |
| `tests/test_tax.py::test_vat` | 1.0 s | `src/shop/tax.py` |
| `tests/test_report.py::test_render` | 5.0 s | `src/shop/report.py`, `src/shop/pricing.py` |
| `tests/api/test_orders.py::test_create` | 4.0 s | `src/shop/orders.py` |

`src/shop/constants.py` was recorded only outside any test. `templates/invoice.html`, `tests/conftest.py` and `tests/api/conftest.py` were not measured. Below, tests go by their function name.

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
- Given two recorded runs of the 12.0 s suite, one that selected 3.0 s and one where the floor selected all 12.0 s, when the report is produced, then it shows savings of 37.5% and says this is an upper bound, because fixed per-run costs such as start-up and collection are not in the JUnit times.
- Given recorded runs of 4 PRs, where all 3 runs of PR 1 matched the floor and the single runs of PRs 2, 3 and 4 did not, when the report is produced, then it shows a floor rate of 25%: 1 PR out of 4, not 3 runs out of 6.
- Given two recorded runs of four tests each, one of which had one unmeasured test, when the report is produced, then it shows 12.5% of tests treated as unmeasured.
- Given two recorded runs, each evaluated against coverage in which four tests have a row, where one of those four is not in the second run, when the report is produced, then it shows that 12.5% of the tests with a row were not in their run. That share is what gives away a broken matching; the unmeasured share cannot, because it also takes in new tests, skipped tests and tests that run no measured code.
- Given a recorded missed run whose diff modifies only `templates/invoice.html` and in which test_render failed, when the report is produced, then it lists test_render with the reason it was left out (its row, `src/shop/report.py` and `src/shop/pricing.py`, has none of the diff's paths, and no other rule picked it), next to the diff's paths with no column (`templates/invoice.html`) and the import-only ones (none).
- Given a recorded caught run in which test_render also failed without being selected, when the report is produced, then test_render is listed the same way: every failed test left out of a selection is, whether or not its run was caught.
- Given 5 recorded red runs, 2 of them without a rerun file, when the report is produced, then it says that the failures of 2 red runs were not confirmed by a rerun.
- Given recorded runs in which 3 failed tests passed in their rerun files, when the report is produced, then it says that 3 failures were discarded as not reproduced: order-dependent failures (§7) can hide in that count.

#### Invariants
- Given the same inputs, when the run is evaluated twice, then the selection, its reasons and the verdict come out byte-identical; given the same recorded runs, when the report is produced twice, then both reports are byte-identical.
- Given two runs with the same coverage, diff, tests and floor configuration that differ only in which tests failed and how long tests took, when both are evaluated, then their selections and reasons are identical.
- Given a diff that modifies `src/shop/tax.py`, and then the same diff plus `src/shop/report.py`, when both are evaluated, then the selection grows from test_total and test_vat to test_total, test_vat and test_render, and loses no test.
- Given a diff that modifies `src/shop/tax.py` and a run that also has the unmeasured test_rounding, when the run is evaluated, then every selected test has at least one reason, and every path a reason names is in the diff.

#### Records, rejections and CI signal
- [core] Given a run evaluated as in the examples above, when its evaluation is recorded, then <TO FILL>.
- [core] Given a full run in which test_render failed and a rerun file in which it passed, when the evaluation is recorded, then <TO FILL>.
- [core] Given a run whose evaluation is already recorded, when the same inputs are evaluated again, then <TO FILL>.
- [core] Given coverage recorded at a commit that is neither the merge-base nor one of its ancestors, such as the evaluated run's own coverage at H, when the run is evaluated, then <TO FILL>.
- [core] Given a checkout without the history to prove that M is the merge-base or one of its ancestors, such as a shallow clone, when the run is evaluated, then <TO FILL>.
- [core] Given a JUnit file that declares an external entity or nests entity expansions ("billion laughs"), when the run is evaluated, then <TO FILL>.
- [core] Given a run with valid inputs, whether green, caught or missed, when its evaluation finishes as a CI step, then <TO FILL>.
- [core] Given an input the evaluation cannot use, such as a missing coverage file or a JUnit file that is not well-formed XML, when the run is evaluated, then <TO FILL>.

#### Edge cases
- Edge case: test_vat also uses the session fixture whose setup runs `src/shop/db.py` during test_total's setup -> a session fixture's setup counts only in the row of the first test that requests it, and its teardown in the row of the session's last test, even if that test does not use it. A module fixture goes the same way, with its teardown in the row of the last test of its module, and so do `setUpClass` and `tearDownClass`, in the rows of the first and the last test of their class. Here the fixture's teardown runs no line of `src/shop/db.py`, so a diff that modifies only that file selects test_total and not test_vat; if it ran one, that diff would also select the session's last test.
- Edge case: test_create also runs `src/shop/report.py` in a subprocess -> a limitation: what a test runs in a subprocess is not in its row, since pytest-cov 7 no longer measures subprocesses. A diff that modifies only `src/shop/report.py` selects test_render and not test_create, and a run in which only test_create failed is missed.
- Edge case: pytest's rootdir is `backend/`, so a node id reads `tests/test_tax.py::test_vat` while the file is `backend/tests/test_tax.py` -> a diff that modifies `backend/tests/test_tax.py` selects test_vat with `own file`, and the conftest rule resolves paths the same way.
- Edge case: coverage recorded absolute paths under another checkout root (`/runner/work/shop/src/shop/tax.py`) -> matched to `src/shop/tax.py`; a recorded file outside the repository is not a column.
- Edge case: a changed path with spaces or non-ASCII characters (`src/shop/tarifa año.py`) -> matched to its column like any other path, and never listed as having no column because of how `git` quotes it.
- Edge case: test_vat overrides its `classname` with `record_xml_attribute` -> the JUnit names it by a pair that its node id does not turn into, so it is unmeasured: selected with `unmeasured`, counted in the unmeasured share, and counted among the tests with a row that are not in the run.
- Edge case: a test that has a row but is not in the run, because it was deleted or renamed at H -> not selected, and counted only among the tests with a row that are not in the run.
- Edge case: a changed file under `src/` that M never saw, because the PR added it or the base branch did after M -> listed as a path with no column; it picks no test.
- Edge case: a changed path that is a column and also matches the floor (`src/shop/config/loader.py`) -> the whole suite; the tests that cover it carry `covers` as well as the floor reason.
- Edge case: a diff that modifies `services/billing/uv.lock` -> the whole suite: the default patterns match at any depth.
- Edge case: a diff that modifies `requirements/base.txt` -> the whole suite, through `**/requirements/**`.
- Edge case: a diff with no paths -> only the unmeasured tests are selected (none in the fixture).
- Edge case: a test with an `error` in setup or teardown and no `failure` -> it counts as failed, like a `failure`.
- Edge case: a run whose only non-passing results are skips -> green.
- Edge case: a failed test that is missing from the rerun file -> still failed: only a pass in the rerun file discards a failure.
- Edge case: a test in the rerun file that did not fail in the full run -> ignored.
- Edge case: a failure that only happens after certain other tests have run (order dependence, §7) -> it passes in the rerun file and is marked not reproduced, like a flaky one; Slice 1 cannot tell the two apart, and the report shows it only in its count of discarded failures.
- Edge case: a diff that renames `settings/app.yaml` to `config/app.yaml` -> the whole suite: the new name matches `**/config/**`.
- Edge case: a floor configuration with the pattern `**.lock` or `data/?.csv` -> not a valid pattern: an input the evaluation cannot use, as in the [core] example on unusable inputs.
- Edge case: coverage in which no line was recorded for more than one test, as the `sysmon` core leaves it -> an input the evaluation cannot use, as in the [core] example on unusable inputs.
- Property (only while properties are on): for every <input>, <invariant that must hold>.

## Technical sheet
<Modules with their risk tier, interfaces, data model. Written in phase 2.
A module that produces the "then" of a [core] example is core. A module with
an irreversible effect that no [core] example observes means a missing example.>

## Open questions
- Collection errors. A collection error is a result of the evaluated run: if it counted as an unmeasured test, the selection would no longer be blind to results. Decide how to treat it according to how pytest will run once the tool decides which tests run.
- Which PR a run belongs to. None of the inputs says so, and both the miss rate and the floor rate count PRs. How each run gets its PR is open, and so is what happens to runs that belong to none, such as pushes to the base branch.
- Failures inherited from the base branch. If the base branch was already red at the merge-base, the PR's run fails for reasons outside its diff and counts against the selector, and the rerun file reproduces them. Should a later slice read the base's results to set them apart?
- Matrix age. Slice 1 sets no limit on how far M lags behind the merge-base, while regime assumes a matrix at most 24 h old (§8). Should the report show the lag?
- Sharded runs: one run split across several JUnit files, and what a test id that appears twice means.
