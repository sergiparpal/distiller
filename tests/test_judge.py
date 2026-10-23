import pytest

from distiller import junit, selection

# Each test hands judge a run's full JUnit and its rerun file, as parse_junit
# gives them, the run's tests, as match_tests gives them, and the selection, as
# select gives it, all as literals, and watches judge from outside: what it
# returns.

# The fixture's tests, by node id.
TEST_TOTAL = "tests/test_pricing.py::test_total"
TEST_VAT = "tests/test_tax.py::test_vat"
TEST_RENDER = "tests/test_report.py::test_render"
TEST_CREATE = "tests/api/test_orders.py::test_create"

# Their pairs, as pytest writes them in the JUnit.
TOTAL_PAIR = ("tests.test_pricing", "test_total")
VAT_PAIR = ("tests.test_tax", "test_vat")
RENDER_PAIR = ("tests.test_report", "test_render")
CREATE_PAIR = ("tests.api.test_orders", "test_create")

# The fixture's measured files, by their paths from the repository root.
PRICING = "src/shop/pricing.py"
TAX = "src/shop/tax.py"
DB = "src/shop/db.py"
REPORT = "src/shop/report.py"
ORDERS = "src/shop/orders.py"

# The fixture's tests as match_tests gives them, each with its node id and row.
TOTAL = selection.Test(
    pair=TOTAL_PAIR, node_id=TEST_TOTAL, row=frozenset({PRICING, TAX, DB})
)
VAT = selection.Test(pair=VAT_PAIR, node_id=TEST_VAT, row=frozenset({TAX}))
RENDER = selection.Test(
    pair=RENDER_PAIR, node_id=TEST_RENDER, row=frozenset({REPORT, PRICING})
)
CREATE = selection.Test(pair=CREATE_PAIR, node_id=TEST_CREATE, row=frozenset({ORDERS}))
FIXTURE_TESTS = [TOTAL, VAT, RENDER, CREATE]

# test_render's entry in K1's failed_left_out, as its record line writes it.
K1_TEST_RENDER = selection.Test(
    pair=("tests.test_report", "test_render"),
    node_id="tests/test_report.py::test_render",
    row=frozenset({"src/shop/pricing.py", "src/shop/report.py"}),
)

# Selection 7's test_rounding, which has no row: match_tests gives it with no
# node id and no row, and select picks it, with unmeasured, in every run that
# has it.
ROUNDING_PAIR = ("tests.test_tax", "test_rounding")
ROUNDING = selection.Test(pair=ROUNDING_PAIR, node_id=None, row=None)
WITH_ROUNDING = [*FIXTURE_TESTS, ROUNDING]

# The results that these tests can have in a JUnit file, with their times. A
# skipped test neither failed nor passed.
TOTAL_PASSED = junit.Result(failed=False, passed=True, time_ms=2000)
TOTAL_FAILED = junit.Result(failed=True, passed=False, time_ms=2000)
TOTAL_SKIPPED = junit.Result(failed=False, passed=False, time_ms=0)
VAT_PASSED = junit.Result(failed=False, passed=True, time_ms=1000)
VAT_FAILED = junit.Result(failed=True, passed=False, time_ms=1000)
VAT_SKIPPED = junit.Result(failed=False, passed=False, time_ms=0)
RENDER_PASSED = junit.Result(failed=False, passed=True, time_ms=5000)
RENDER_FAILED = junit.Result(failed=True, passed=False, time_ms=5000)
RENDER_SKIPPED = junit.Result(failed=False, passed=False, time_ms=0)
CREATE_PASSED = junit.Result(failed=False, passed=True, time_ms=4000)
CREATE_FAILED = junit.Result(failed=True, passed=False, time_ms=4000)
CREATE_SKIPPED = junit.Result(failed=False, passed=False, time_ms=0)
ROUNDING_PASSED = junit.Result(failed=False, passed=True, time_ms=300)
ROUNDING_FAILED = junit.Result(failed=True, passed=False, time_ms=300)


def junit_with(results: dict[tuple[str, str], junit.Result]) -> junit.JUnit:
    """A JUnit file as parse_junit gives it: these results, no collection error."""
    return junit.JUnit(results=results, has_collection_error=False)


# Full runs of the fixture's tests, named by the tests that failed in them.
RUN_WITH_NO_FAILURE = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
RUN_VAT_FAILED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_FAILED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
# K1's full run, which is also K2's.
RUN_RENDER_FAILED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_FAILED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
RUN_VAT_AND_RENDER_FAILED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_FAILED,
        RENDER_PAIR: RENDER_FAILED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
RUN_CREATE_FAILED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_FAILED,
    }
)

# A full run of the fixture's tests and test_rounding, in which only
# test_rounding failed.
RUN_ROUNDING_FAILED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
        ROUNDING_PAIR: ROUNDING_FAILED,
    }
)

# Rerun files that hold only test_render, by its result there.
RERUN_RENDER_PASSED = junit_with({RENDER_PAIR: RENDER_PASSED})
RERUN_RENDER_FAILED = junit_with({RENDER_PAIR: RENDER_FAILED})
RERUN_RENDER_SKIPPED = junit_with({RENDER_PAIR: RENDER_SKIPPED})

# A rerun file with no test case, so test_render is missing from it.
RERUN_WITH_NO_TEST = junit_with({})

# A rerun file in which pytest could not collect tests/test_report.py, so
# test_render did not run. It holds the collection error's test case, failed,
# under the pair that pytest writes for it; the SPEC does not say whether
# parse_junit lists it, and either way test_render is missing.
RERUN_NOT_COLLECTED = junit.JUnit(
    results={
        ("", "tests.test_report"): junit.Result(failed=True, passed=False, time_ms=0)
    },
    has_collection_error=True,
)


# The reasons, in the SPEC's notation


def covers(path: str) -> selection.Reason:
    """`covers P`: the test's row has the changed path P."""
    return selection.Reason(rule="covers", path=path)


def floor(pattern: str, path: str) -> selection.Reason:
    """`floor X (P)`: the changed path P matches the floor pattern X."""
    return selection.Reason(rule="floor", path=path, pattern=pattern)


def own_file(path: str) -> selection.Reason:
    """`own file P`: P is the file in the test's node id."""
    return selection.Reason(rule="own file", path=path)


def conftest(path: str) -> selection.Reason:
    """`conftest P`: P is a conftest.py in the test's directory or above it."""
    return selection.Reason(rule="conftest", path=path)


# `unmeasured`, which names no path.
UNMEASURED = selection.Reason(rule="unmeasured", path=None)

# The selections that select gives, as tests/test_select.py pins them, by the
# diff that gives each.

# templates/invoice.html, K1's diff and Selection 14's, selects no test.
NOTHING_SELECTED: selection.Selection = {}
# src/shop/tax.py, Selection 1's.
TAX_SELECTION: selection.Selection = {
    TOTAL_PAIR: frozenset({covers(TAX)}),
    VAT_PAIR: frozenset({covers(TAX)}),
}
# src/shop/report.py, Selection 12's and Edge 2's.
REPORT_SELECTION: selection.Selection = {RENDER_PAIR: frozenset({covers(REPORT)})}
# uv.lock, Selection 4's, selects every test through the floor.
UV_LOCK = floor("**/uv.lock", "uv.lock")
FLOOR_SELECTION: selection.Selection = {
    TOTAL_PAIR: frozenset({UV_LOCK}),
    VAT_PAIR: frozenset({UV_LOCK}),
    RENDER_PAIR: frozenset({UV_LOCK}),
    CREATE_PAIR: frozenset({UV_LOCK}),
}
# tests/test_report.py, Selection 8's.
OWN_FILE_SELECTION: selection.Selection = {
    RENDER_PAIR: frozenset({own_file("tests/test_report.py")})
}
# tests/api/conftest.py, Selection 10's.
CONFTEST_SELECTION: selection.Selection = {
    CREATE_PAIR: frozenset({conftest("tests/api/conftest.py")})
}
# A diff with no paths, Edge 13's, in a run that has test_rounding: it alone.
ROUNDING_SELECTION: selection.Selection = {ROUNDING_PAIR: frozenset({UNMEASURED})}


# Judgements that several tests expect

# A run with no failure that the rerun file leaves.
GREEN = selection.Judgement(
    verdict="green", not_reproduced=frozenset(), failed_left_out=()
)
# A failed test selected, no failure discarded and no failed test left out.
CAUGHT = selection.Judgement(
    verdict="caught", not_reproduced=frozenset(), failed_left_out=()
)
# K1's: test_render failed and was left out, and no rerun file discarded it.
RENDER_MISSED = selection.Judgement(
    verdict="missed", not_reproduced=frozenset(), failed_left_out=(RENDER,)
)
# Verdict 5's: test_render failed and then passed in the rerun file.
RENDER_NOT_REPRODUCED = selection.Judgement(
    verdict="green", not_reproduced=frozenset({RENDER_PAIR}), failed_left_out=()
)


# The Verdict examples

# The full run, the rerun file, the selection that the diff gives, and the
# judgement. Verdict 4 and 5 name no diff, so each is tried with two
# selections, and gives the same judgement with both.
VERDICT_EXAMPLES = [
    pytest.param(
        RUN_VAT_FAILED,
        None,
        TAX_SELECTION,
        CAUGHT,
        id="Verdict 1, test_vat failed and src/shop/tax.py selects it",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        None,
        NOTHING_SELECTED,
        RENDER_MISSED,
        id="Verdict 2, test_render failed and templates/invoice.html selects none",
    ),
    pytest.param(
        RUN_VAT_AND_RENDER_FAILED,
        None,
        TAX_SELECTION,
        selection.Judgement(
            verdict="caught", not_reproduced=frozenset(), failed_left_out=(RENDER,)
        ),
        id="Verdict 3, test_vat and test_render failed, only test_vat selected",
    ),
    pytest.param(
        RUN_WITH_NO_FAILURE,
        None,
        NOTHING_SELECTED,
        GREEN,
        id="Verdict 4, no failure, with no test selected",
    ),
    pytest.param(
        RUN_WITH_NO_FAILURE,
        None,
        FLOOR_SELECTION,
        GREEN,
        id="Verdict 4, no failure, with every test selected through the floor",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        RERUN_RENDER_PASSED,
        NOTHING_SELECTED,
        RENDER_NOT_REPRODUCED,
        id="Verdict 5, test_render passed in the rerun file, with none selected",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        RERUN_RENDER_PASSED,
        REPORT_SELECTION,
        RENDER_NOT_REPRODUCED,
        id="Verdict 5, test_render passed in the rerun file, with it selected",
    ),
]


@pytest.mark.parametrize(("full", "rerun", "selected", "expected"), VERDICT_EXAMPLES)
def test_a_run_is_caught_missed_or_green_as_the_verdict_examples_say(
    full: junit.JUnit,
    rerun: junit.JUnit | None,
    selected: selection.Selection,
    expected: selection.Judgement,
) -> None:
    assert selection.judge(full, rerun, FIXTURE_TESTS, selected) == expected


# K1 and K2, with the values that their record lines show


def test_k1_a_missed_run_lists_test_render_as_failed_and_left_out() -> None:
    # A diff that modifies only templates/invoice.html selects no test, and
    # test_render failed in a full run with no rerun file.
    found = selection.judge(RUN_RENDER_FAILED, None, FIXTURE_TESTS, NOTHING_SELECTED)

    expected = selection.Judgement(
        verdict="missed",
        not_reproduced=frozenset(),
        failed_left_out=(K1_TEST_RENDER,),
    )
    assert found == expected


# K2 names no diff: the selections that templates/invoice.html and
# src/shop/report.py give, which leave test_render out and select it.
K2_SELECTIONS = [
    pytest.param(NOTHING_SELECTED, id="test_render left out"),
    pytest.param(REPORT_SELECTION, id="test_render selected"),
]


@pytest.mark.parametrize("selected", K2_SELECTIONS)
def test_k2_a_failure_that_passes_in_the_rerun_file_is_not_reproduced(
    selected: selection.Selection,
) -> None:
    # test_render failed in the full run and passed in the rerun file.
    found = selection.judge(
        RUN_RENDER_FAILED, RERUN_RENDER_PASSED, FIXTURE_TESTS, selected
    )

    expected = selection.Judgement(
        verdict="green",
        not_reproduced=frozenset({("tests.test_report", "test_render")}),
        failed_left_out=(),
    )
    assert found == expected


# Only a pass discards a failure

# Rerun files of K1's full run, in which test_render failed and no test is
# selected, and the judgement: only a rerun file in which test_render passed
# discards its failure.
RERUNS_OF_TEST_RENDER = [
    pytest.param(None, RENDER_MISSED, id="no rerun file, as in K1"),
    pytest.param(RERUN_RENDER_PASSED, RENDER_NOT_REPRODUCED, id="passed, as in K2"),
    pytest.param(RERUN_RENDER_FAILED, RENDER_MISSED, id="failed again"),
    pytest.param(RERUN_RENDER_SKIPPED, RENDER_MISSED, id="Edge 17, skipped"),
    pytest.param(RERUN_WITH_NO_TEST, RENDER_MISSED, id="Edge 16, missing"),
    pytest.param(
        RERUN_NOT_COLLECTED,
        RENDER_MISSED,
        id="Edge 16, missing because tests/test_report.py was not collected",
    ),
]


@pytest.mark.parametrize(("rerun", "expected"), RERUNS_OF_TEST_RENDER)
def test_only_a_pass_in_the_rerun_file_discards_a_failure(
    rerun: junit.JUnit | None, expected: selection.Judgement
) -> None:
    found = selection.judge(RUN_RENDER_FAILED, rerun, FIXTURE_TESTS, NOTHING_SELECTED)

    assert found == expected


# Rerun files of Verdict 3's full run, in which test_vat and test_render failed
# and src/shop/tax.py selects test_vat alone, and the judgement. A failure that
# the rerun file discards is no longer a failed test: it does not make the run
# caught, and it is not left out.
DISCARDED_FAILURES = [
    pytest.param(
        junit_with({VAT_PAIR: VAT_PASSED, RENDER_PAIR: RENDER_FAILED}),
        selection.Judgement(
            verdict="missed",
            not_reproduced=frozenset({VAT_PAIR}),
            failed_left_out=(RENDER,),
        ),
        id="test_vat passed and test_render failed again: missed",
    ),
    pytest.param(
        junit_with({VAT_PAIR: VAT_FAILED, RENDER_PAIR: RENDER_PASSED}),
        selection.Judgement(
            verdict="caught",
            not_reproduced=frozenset({RENDER_PAIR}),
            failed_left_out=(),
        ),
        id="test_render passed and test_vat failed again: caught, none left out",
    ),
    pytest.param(
        junit_with({VAT_PAIR: VAT_PASSED, RENDER_PAIR: RENDER_PASSED}),
        selection.Judgement(
            verdict="green",
            not_reproduced=frozenset({VAT_PAIR, RENDER_PAIR}),
            failed_left_out=(),
        ),
        id="both passed: green",
    ),
]


@pytest.mark.parametrize(("rerun", "expected"), DISCARDED_FAILURES)
def test_a_failure_that_the_rerun_file_discards_is_no_longer_a_failed_test(
    rerun: junit.JUnit, expected: selection.Judgement
) -> None:
    found = selection.judge(
        RUN_VAT_AND_RENDER_FAILED, rerun, FIXTURE_TESTS, TAX_SELECTION
    )

    assert found == expected


# Edge 18: a test that did not fail in the full run

# A full run, a rerun file in which a test that did not fail in the full run
# failed or passed, and the judgement, with no test selected: that test's
# result in the rerun file is ignored.
DID_NOT_FAIL_IN_THE_FULL_RUN = [
    pytest.param(
        RUN_WITH_NO_FAILURE,
        junit_with({VAT_PAIR: VAT_FAILED}),
        GREEN,
        id="a run with no failure, and test_vat failed in the rerun file",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        junit_with({RENDER_PAIR: RENDER_PASSED, VAT_PAIR: VAT_FAILED}),
        RENDER_NOT_REPRODUCED,
        id="test_vat, which passed in the full run, failed",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        junit_with({RENDER_PAIR: RENDER_PASSED, VAT_PAIR: VAT_PASSED}),
        RENDER_NOT_REPRODUCED,
        id="test_vat, which passed in the full run, passed and is not marked",
    ),
    pytest.param(
        junit_with(
            {
                TOTAL_PAIR: TOTAL_PASSED,
                VAT_PAIR: VAT_SKIPPED,
                RENDER_PAIR: RENDER_FAILED,
                CREATE_PAIR: CREATE_PASSED,
            }
        ),
        junit_with({RENDER_PAIR: RENDER_PASSED, VAT_PAIR: VAT_FAILED}),
        RENDER_NOT_REPRODUCED,
        id="test_vat, which was skipped in the full run, failed",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        junit_with({RENDER_PAIR: RENDER_PASSED, ROUNDING_PAIR: ROUNDING_FAILED}),
        RENDER_NOT_REPRODUCED,
        id="test_rounding, which is not in the full run, failed",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        junit_with({RENDER_PAIR: RENDER_PASSED, ROUNDING_PAIR: ROUNDING_PASSED}),
        RENDER_NOT_REPRODUCED,
        id="test_rounding, which is not in the full run, passed and is not marked",
    ),
]


@pytest.mark.parametrize(("full", "rerun", "expected"), DID_NOT_FAIL_IN_THE_FULL_RUN)
def test_edge_18_a_test_that_did_not_fail_in_the_full_run_is_ignored_in_the_rerun(
    full: junit.JUnit, rerun: junit.JUnit, expected: selection.Judgement
) -> None:
    found = selection.judge(full, rerun, FIXTURE_TESTS, NOTHING_SELECTED)

    assert found == expected


# Edge 19: an order-dependent failure


def test_edge_19_an_order_dependent_failure_is_not_reproduced() -> None:
    # Verdict 1's run, had test_vat failed only because test_total ran before
    # it: a rerun of the failed test alone passes, as a flaky test's would,
    # so its failure is not reproduced and the run is green, not caught.
    rerun = junit_with({VAT_PAIR: VAT_PASSED})

    found = selection.judge(RUN_VAT_FAILED, rerun, FIXTURE_TESTS, TAX_SELECTION)

    expected = selection.Judgement(
        verdict="green", not_reproduced=frozenset({VAT_PAIR}), failed_left_out=()
    )
    assert found == expected


# Edge 15: skips

# Full runs whose only results that are not passes are skips.
ONLY_SKIPS = [
    pytest.param(
        junit_with(
            {
                TOTAL_PAIR: TOTAL_PASSED,
                VAT_PAIR: VAT_SKIPPED,
                RENDER_PAIR: RENDER_PASSED,
                CREATE_PAIR: CREATE_SKIPPED,
            }
        ),
        id="test_vat and test_create skipped",
    ),
    pytest.param(
        junit_with(
            {
                TOTAL_PAIR: TOTAL_SKIPPED,
                VAT_PAIR: VAT_SKIPPED,
                RENDER_PAIR: RENDER_SKIPPED,
                CREATE_PAIR: CREATE_SKIPPED,
            }
        ),
        id="every test skipped",
    ),
]


@pytest.mark.parametrize("full", ONLY_SKIPS)
def test_edge_15_a_run_whose_only_non_passing_results_are_skips_is_green(
    full: junit.JUnit,
) -> None:
    assert selection.judge(full, None, FIXTURE_TESTS, NOTHING_SELECTED) == GREEN


# Edge 2: a subprocess


def test_edge_2_only_test_create_failed_so_the_run_is_missed() -> None:
    # test_create also runs src/shop/report.py in a subprocess, which is not in
    # its row, so a diff that modifies only that file selects test_render.
    found = selection.judge(RUN_CREATE_FAILED, None, FIXTURE_TESTS, REPORT_SELECTION)

    expected = selection.Judgement(
        verdict="missed", not_reproduced=frozenset(), failed_left_out=(CREATE,)
    )
    assert found == expected


# Any rule

# A full run in which one test failed, the run's tests, and a selection that
# holds that test through one rule alone: the run is caught whatever the rule.
SELECTED_THROUGH_EACH_RULE = [
    pytest.param(
        RUN_RENDER_FAILED,
        FIXTURE_TESTS,
        REPORT_SELECTION,
        id="covers, src/shop/report.py selects test_render",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        FIXTURE_TESTS,
        FLOOR_SELECTION,
        id="floor, uv.lock selects every test",
    ),
    pytest.param(
        RUN_RENDER_FAILED,
        FIXTURE_TESTS,
        OWN_FILE_SELECTION,
        id="own file, tests/test_report.py selects test_render",
    ),
    pytest.param(
        RUN_CREATE_FAILED,
        FIXTURE_TESTS,
        CONFTEST_SELECTION,
        id="conftest, tests/api/conftest.py selects test_create",
    ),
    pytest.param(
        RUN_ROUNDING_FAILED,
        WITH_ROUNDING,
        ROUNDING_SELECTION,
        id="unmeasured, a diff with no paths selects test_rounding",
    ),
]


@pytest.mark.parametrize(("full", "tests", "selected"), SELECTED_THROUGH_EACH_RULE)
def test_a_run_whose_failed_test_is_selected_is_caught_whatever_the_rule(
    full: junit.JUnit, tests: list[selection.Test], selected: selection.Selection
) -> None:
    assert selection.judge(full, None, tests, selected) == CAUGHT


# A diff with no paths

# Full runs of the fixture's tests and test_rounding, and the judgement, when a
# diff with no paths selects only the unmeasured test_rounding: a red run is
# missed unless one of its failed tests is unmeasured.
WITH_NO_PATHS = [
    pytest.param(
        junit_with(
            {
                TOTAL_PAIR: TOTAL_PASSED,
                VAT_PAIR: VAT_PASSED,
                RENDER_PAIR: RENDER_FAILED,
                CREATE_PAIR: CREATE_PASSED,
                ROUNDING_PAIR: ROUNDING_PASSED,
            }
        ),
        RENDER_MISSED,
        id="test_render failed: missed",
    ),
    pytest.param(
        junit_with(
            {
                TOTAL_PAIR: TOTAL_PASSED,
                VAT_PAIR: VAT_PASSED,
                RENDER_PAIR: RENDER_FAILED,
                CREATE_PAIR: CREATE_PASSED,
                ROUNDING_PAIR: ROUNDING_FAILED,
            }
        ),
        selection.Judgement(
            verdict="caught", not_reproduced=frozenset(), failed_left_out=(RENDER,)
        ),
        id="test_render and test_rounding failed: caught",
    ),
]


@pytest.mark.parametrize(("full", "expected"), WITH_NO_PATHS)
def test_a_diff_with_no_paths_misses_a_red_run_unless_a_failed_test_is_unmeasured(
    full: junit.JUnit, expected: selection.Judgement
) -> None:
    found = selection.judge(full, None, WITH_ROUNDING, ROUNDING_SELECTION)

    assert found == expected


# The order of failed_left_out

# Two cases of a parametrized test_render, whose ids differ only in case, as
# match_tests gives them. By code point, P comes before h.
RENDER_PDF = selection.Test(
    pair=("tests.test_report", "test_render[PDF]"),
    node_id="tests/test_report.py::test_render[PDF]",
    row=frozenset({REPORT, PRICING}),
)
RENDER_HTML = selection.Test(
    pair=("tests.test_report", "test_render[html]"),
    node_id="tests/test_report.py::test_render[html]",
    row=frozenset({REPORT, PRICING}),
)

# Missed runs with several failed tests and no test selected: the run's tests
# and its full run, both in one order, and failed_left_out, which is sorted by
# pair, by code point, whatever that order.
SEVERAL_LEFT_OUT = [
    pytest.param(
        FIXTURE_TESTS,
        junit_with(
            {
                TOTAL_PAIR: TOTAL_FAILED,
                VAT_PAIR: VAT_PASSED,
                RENDER_PAIR: RENDER_FAILED,
                CREATE_PAIR: CREATE_FAILED,
            }
        ),
        (CREATE, TOTAL, RENDER),
        id="test_total, test_render and test_create, in the fixture's order",
    ),
    pytest.param(
        [CREATE, RENDER, VAT, TOTAL],
        junit_with(
            {
                CREATE_PAIR: CREATE_FAILED,
                RENDER_PAIR: RENDER_FAILED,
                VAT_PAIR: VAT_PASSED,
                TOTAL_PAIR: TOTAL_FAILED,
            }
        ),
        (CREATE, TOTAL, RENDER),
        id="the same, the other way round",
    ),
    pytest.param(
        [RENDER_HTML, RENDER_PDF],
        junit_with({RENDER_HTML.pair: RENDER_FAILED, RENDER_PDF.pair: RENDER_FAILED}),
        (RENDER_PDF, RENDER_HTML),
        id="the html and PDF cases of test_render, whose ids differ in case",
    ),
]


@pytest.mark.parametrize(("tests", "full", "left_out"), SEVERAL_LEFT_OUT)
def test_failed_left_out_is_sorted_by_pair_whatever_the_order_of_the_tests(
    tests: list[selection.Test],
    full: junit.JUnit,
    left_out: tuple[selection.Test, ...],
) -> None:
    # Rule 8: a list that reaches a record is sorted where it is built, by code
    # point, and a record sorts failed_left_out by its pairs.
    found = selection.judge(full, None, tests, NOTHING_SELECTED)

    expected = selection.Judgement(
        verdict="missed", not_reproduced=frozenset(), failed_left_out=left_out
    )
    assert found == expected


# A run with no tests


def test_a_run_with_no_tests_is_green() -> None:
    assert selection.judge(junit_with({}), None, [], {}) == GREEN
