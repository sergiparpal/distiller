import pytest

from distiller import junit, selection

# Each test hands pair_of a node id, or match_tests a run's results and the
# rows of the coverage at M, as literals, and watches selection from outside:
# what pair_of and match_tests return.

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

# The fixture's rows, as build_matrix gives them.
FIXTURE_ROWS = {
    TEST_TOTAL: frozenset({PRICING, TAX, DB}),
    TEST_VAT: frozenset({TAX}),
    TEST_RENDER: frozenset({REPORT, PRICING}),
    TEST_CREATE: frozenset({ORDERS}),
}

# The fixture's results in K1's full run, with their JUnit times: test_render
# failed.
TOTAL_PASSED = junit.Result(failed=False, passed=True, time_ms=2000)
VAT_PASSED = junit.Result(failed=False, passed=True, time_ms=1000)
RENDER_FAILED = junit.Result(failed=True, passed=False, time_ms=5000)
CREATE_PASSED = junit.Result(failed=False, passed=True, time_ms=4000)
K1_RESULTS: dict[tuple[str, str], junit.Result] = {
    TOTAL_PAIR: TOTAL_PASSED,
    VAT_PAIR: VAT_PASSED,
    RENDER_PAIR: RENDER_FAILED,
    CREATE_PAIR: CREATE_PASSED,
}

# The result of a test that the fixture does not have, which plays no part in
# matching.
PASSED = junit.Result(failed=False, passed=True, time_ms=300)

# test_render's entry in K1's failed_left_out, as its record line writes it.
K1_TEST_RENDER = selection.Test(
    pair=("tests.test_report", "test_render"),
    node_id="tests/test_report.py::test_render",
    row=frozenset({"src/shop/pricing.py", "src/shop/report.py"}),
)

# The fixture's other tests after matching, each with its node id and row.
MATCHED_TOTAL = selection.Test(
    pair=TOTAL_PAIR, node_id=TEST_TOTAL, row=frozenset({PRICING, TAX, DB})
)
MATCHED_VAT = selection.Test(pair=VAT_PAIR, node_id=TEST_VAT, row=frozenset({TAX}))
MATCHED_CREATE = selection.Test(
    pair=CREATE_PAIR, node_id=TEST_CREATE, row=frozenset({ORDERS})
)
FIXTURE_TESTS = [MATCHED_TOTAL, MATCHED_VAT, K1_TEST_RENDER, MATCHED_CREATE]

# The SPEC's two node ids with one pair, and that pair.
V1_DOT_2 = "tests/v1.2/test_x.py::test_m"
V1_SLASH_2 = "tests/v1/2/test_x.py::test_m"
V1_2_PAIR = ("tests.v1.2.test_x", "test_m")

# Selection 9's test_rounding, which has no row, by its pair and its node id.
ROUNDING_PAIR = ("tests.test_tax", "test_rounding")
TEST_ROUNDING = "tests/test_tax.py::test_rounding"

# test_vat's pair in the JUnit when it is renamed at H, and when it sets its
# own classname with record_xml_attribute, as in Edge 6.
RENAMED_PAIR = ("tests.test_tax", "test_vat_rate")
OVERRIDDEN_PAIR = ("billing.TaxSuite", "test_vat")

# A run with no test, coverage with no test context, and no test after matching.
NO_RESULTS: dict[tuple[str, str], junit.Result] = {}
NO_ROWS: dict[str, frozenset[str]] = {}
NO_TESTS: list[selection.Test] = []


def unmeasured(pair: tuple[str, str]) -> selection.Test:
    """A test of the run with no row, and so with no node id."""
    return selection.Test(pair=pair, node_id=None, row=None)


def in_pair_order(tests: list[selection.Test]) -> list[selection.Test]:
    """The tests sorted by pair: the SPEC fixes no order for match_tests."""
    return sorted(tests, key=lambda test: test.pair)


# The pair rule

# A node id and the pair that pytest works out from it for the JUnit.
PAIRS = [
    pytest.param(
        "tests/test_tax.py::TestVat::test_rate[es-0.21]",
        ("tests.test_tax.TestVat", "test_rate[es-0.21]"),
        id="the SPEC's example, a class and parameters",
    ),
    pytest.param(
        "tests/test_report.py::test_render",
        ("tests.test_report", "test_render"),
        id="K1's test_render",
    ),
    pytest.param(TEST_TOTAL, TOTAL_PAIR, id="the fixture's test_total"),
    pytest.param(TEST_VAT, VAT_PAIR, id="the fixture's test_vat"),
    pytest.param(TEST_CREATE, CREATE_PAIR, id="the fixture's test_create, deeper"),
    pytest.param(
        V1_DOT_2, V1_2_PAIR, id="the SPEC's tests/v1.2/test_x.py, a dot in a directory"
    ),
    pytest.param(
        V1_SLASH_2,
        V1_2_PAIR,
        id="the SPEC's tests/v1/2/test_x.py, which has the same pair",
    ),
    pytest.param(
        "tests/test_tax.py::TestVat::test_rate",
        ("tests.test_tax.TestVat", "test_rate"),
        id="a class",
    ),
    pytest.param(
        "tests/test_tax/TestVat.py::test_rate",
        ("tests.test_tax.TestVat", "test_rate"),
        id="a module named like that class, which has the same pair",
    ),
    pytest.param(
        "tests/test_tax.py::TestVat::TestEs::test_rate",
        ("tests.test_tax.TestVat.TestEs", "test_rate"),
        id="a class inside a class",
    ),
    pytest.param(
        "test_x.py::test_m", ("test_x", "test_m"), id="a file at pytest's rootdir"
    ),
    pytest.param(
        "tests/test_x.py::test_m[a::b]",
        ("tests.test_x", "test_m[a::b]"),
        id="parameters with a double colon",
    ),
    pytest.param(
        "tests/test_x.py::test_m[data/a.py]",
        ("tests.test_x", "test_m[data/a.py]"),
        id="parameters with a / and a .py",
    ),
    pytest.param(
        "tests/test_x.py::test_m[a::b[0]]",
        ("tests.test_x", "test_m[a::b[0]]"),
        id="parameters with a double colon before a second bracket",
    ),
    pytest.param(
        "tests/test_tax.py::test_odd[a|b]",
        ("tests.test_tax", "test_odd[a|b]"),
        id="parameters with a |, as in the SPEC's test context",
    ),
    pytest.param(
        "tests/v.py/test_x.py::test_m",
        ("tests.v.py.test_x", "test_m"),
        id="a .py that does not end the path",
    ),
    pytest.param(
        "docs/tax.txt::tax.txt",
        ("docs.tax.txt", "tax.txt"),
        id="a path that does not end in .py, a text file's doctest",
    ),
    pytest.param(
        "src/shop/tax.py::shop.tax.vat",
        ("src.shop.tax", "shop.tax.vat"),
        id="a name with dots, a module's doctest",
    ),
    pytest.param(
        "tests/tarifa año/test_x.py::test_m",
        ("tests.tarifa año.test_x", "test_m"),
        id="a space and a letter that is not ASCII",
    ),
]


@pytest.mark.parametrize(("node_id", "pair"), PAIRS)
def test_pair_of_turns_a_node_id_into_the_pair_pytest_writes_in_the_junit(
    node_id: str, pair: tuple[str, str]
) -> None:
    assert selection.pair_of(node_id) == pair


# Matching, with K1's values


def test_k1_test_render_is_matched_to_its_node_id_and_row() -> None:
    tests = selection.match_tests(K1_RESULTS, FIXTURE_ROWS)

    assert K1_TEST_RENDER in tests


def test_k1_each_of_the_fixtures_tests_is_matched_to_its_row() -> None:
    # As K1's record says, 4 tests and none of them unmeasured.
    tests = selection.match_tests(K1_RESULTS, FIXTURE_ROWS)

    assert in_pair_order(tests) == in_pair_order(FIXTURE_TESTS)


# One direction, from node id to pair

# Node ids with the pair of a test in the run. Turned back into a node id, a
# pair could give only one of each two that have it.
THROUGH_THE_PAIR = [
    pytest.param(V1_DOT_2, V1_2_PAIR, id="the SPEC's tests/v1.2/test_x.py"),
    pytest.param(V1_SLASH_2, V1_2_PAIR, id="the SPEC's tests/v1/2/test_x.py"),
    pytest.param(
        "tests/test_tax.py::TestVat::test_rate[es-0.21]",
        ("tests.test_tax.TestVat", "test_rate[es-0.21]"),
        id="the SPEC's example, a class",
    ),
    pytest.param(
        "tests/test_tax/TestVat.py::test_rate[es-0.21]",
        ("tests.test_tax.TestVat", "test_rate[es-0.21]"),
        id="a module named like that class",
    ),
]


@pytest.mark.parametrize(("node_id", "pair"), THROUGH_THE_PAIR)
def test_a_node_id_is_matched_to_the_test_of_the_run_with_its_pair(
    node_id: str, pair: tuple[str, str]
) -> None:
    results = {**K1_RESULTS, pair: PASSED}
    rows = {**FIXTURE_ROWS, node_id: frozenset({TAX})}

    tests = selection.match_tests(results, rows)

    matched = selection.Test(pair=pair, node_id=node_id, row=frozenset({TAX}))
    assert in_pair_order(tests) == in_pair_order([*FIXTURE_TESTS, matched])


# Runs whose JUnit lacks the pairs of node ids in the test contexts: the run's
# results and the tests that match_tests gives.
NOT_IN_THE_RUN = [
    pytest.param(
        {
            TOTAL_PAIR: TOTAL_PASSED,
            RENDER_PAIR: RENDER_FAILED,
            CREATE_PAIR: CREATE_PASSED,
        },
        [MATCHED_TOTAL, K1_TEST_RENDER, MATCHED_CREATE],
        id="test_vat, deleted at H",
    ),
    pytest.param(NO_RESULTS, NO_TESTS, id="every test, in a run with none"),
]


@pytest.mark.parametrize(("results", "expected"), NOT_IN_THE_RUN)
def test_a_node_id_whose_pair_is_not_in_the_run_gives_no_test(
    results: dict[tuple[str, str], junit.Result], expected: list[selection.Test]
) -> None:
    tests = selection.match_tests(results, FIXTURE_ROWS)

    assert in_pair_order(tests) == in_pair_order(expected)


# Unmeasured tests

# Tests in the run whose pair no node id in the test contexts has: the run's
# results, the rows of the coverage at M and the tests that match_tests gives.
NO_NODE_ID = [
    pytest.param(
        {**K1_RESULTS, ROUNDING_PAIR: PASSED},
        FIXTURE_ROWS,
        [*FIXTURE_TESTS, unmeasured(ROUNDING_PAIR)],
        id="a new test, Selection 9's test_rounding",
    ),
    pytest.param(
        {
            TOTAL_PAIR: TOTAL_PASSED,
            RENAMED_PAIR: VAT_PASSED,
            RENDER_PAIR: RENDER_FAILED,
            CREATE_PAIR: CREATE_PASSED,
        },
        FIXTURE_ROWS,
        [MATCHED_TOTAL, unmeasured(RENAMED_PAIR), K1_TEST_RENDER, MATCHED_CREATE],
        id="test_vat renamed at H, its old node id still in the coverage",
    ),
    pytest.param(
        {
            TOTAL_PAIR: TOTAL_PASSED,
            OVERRIDDEN_PAIR: VAT_PASSED,
            RENDER_PAIR: RENDER_FAILED,
            CREATE_PAIR: CREATE_PASSED,
        },
        FIXTURE_ROWS,
        [MATCHED_TOTAL, unmeasured(OVERRIDDEN_PAIR), K1_TEST_RENDER, MATCHED_CREATE],
        id="test_vat's classname set with record_xml_attribute, as in Edge 6",
    ),
    pytest.param(
        K1_RESULTS,
        NO_ROWS,
        [
            unmeasured(TOTAL_PAIR),
            unmeasured(VAT_PAIR),
            unmeasured(RENDER_PAIR),
            unmeasured(CREATE_PAIR),
        ],
        id="coverage with no test context",
    ),
]


@pytest.mark.parametrize(("results", "rows", "expected"), NO_NODE_ID)
def test_a_test_whose_pair_no_node_id_has_is_unmeasured(
    results: dict[tuple[str, str], junit.Result],
    rows: dict[str, frozenset[str]],
    expected: list[selection.Test],
) -> None:
    tests = selection.match_tests(results, rows)

    assert in_pair_order(tests) == in_pair_order(expected)


def test_a_test_whose_only_node_id_has_an_empty_row_is_unmeasured() -> None:
    # test_rounding ran only files outside the repository, so its node id has
    # an empty row, and an empty row is no row.
    results = {**K1_RESULTS, ROUNDING_PAIR: PASSED}
    rows = {**FIXTURE_ROWS, TEST_ROUNDING: frozenset[str]()}

    tests = selection.match_tests(results, rows)

    expected = [*FIXTURE_TESTS, unmeasured(ROUNDING_PAIR)]
    assert in_pair_order(tests) == in_pair_order(expected)


# Node ids that have one pair, each with its row, and that pair.
SHARED_PAIRS = [
    pytest.param(
        {V1_DOT_2: frozenset({TAX}), V1_SLASH_2: frozenset({REPORT})},
        V1_2_PAIR,
        id="the SPEC's tests/v1.2/test_x.py and tests/v1/2/test_x.py",
    ),
    pytest.param(
        {
            "tests/test_tax.py::TestVat::test_rate": frozenset({TAX}),
            "tests/test_tax/TestVat.py::test_rate": frozenset({REPORT}),
        },
        ("tests.test_tax.TestVat", "test_rate"),
        id="a class and a module named like it",
    ),
    pytest.param(
        {V1_DOT_2: frozenset({TAX}), V1_SLASH_2: frozenset({TAX})},
        V1_2_PAIR,
        id="two node ids with the same row",
    ),
    pytest.param(
        {
            V1_DOT_2: frozenset({TAX}),
            V1_SLASH_2: frozenset({REPORT}),
            "tests.v1/2/test_x.py::test_m": frozenset({PRICING}),
        },
        V1_2_PAIR,
        id="three node ids",
    ),
]


@pytest.mark.parametrize(("shared_rows", "pair"), SHARED_PAIRS)
def test_two_node_ids_with_one_pair_make_its_test_unmeasured(
    shared_rows: dict[str, frozenset[str]], pair: tuple[str, str]
) -> None:
    results = {**K1_RESULTS, pair: PASSED}
    rows = {**FIXTURE_ROWS, **shared_rows}

    tests = selection.match_tests(results, rows)

    assert in_pair_order(tests) == in_pair_order([*FIXTURE_TESTS, unmeasured(pair)])


# The SPEC's two node ids with one pair, with one of their rows empty or both.
EMPTY_ROWS = [
    pytest.param(
        {V1_DOT_2: frozenset[str](), V1_SLASH_2: frozenset({TAX})},
        id="the first node id's row empty",
    ),
    pytest.param(
        {V1_DOT_2: frozenset({TAX}), V1_SLASH_2: frozenset[str]()},
        id="the second node id's row empty",
    ),
    pytest.param(
        {V1_DOT_2: frozenset[str](), V1_SLASH_2: frozenset[str]()},
        id="both rows empty",
    ),
]


@pytest.mark.parametrize("shared_rows", EMPTY_ROWS)
def test_a_node_id_with_an_empty_row_still_counts_among_its_pairs_node_ids(
    shared_rows: dict[str, frozenset[str]],
) -> None:
    # Matrix.rows keeps empty rows for this, so that the other node id's row
    # is not taken as the test's.
    results = {**K1_RESULTS, V1_2_PAIR: PASSED}
    rows = {**FIXTURE_ROWS, **shared_rows}

    tests = selection.match_tests(results, rows)

    expected = [*FIXTURE_TESTS, unmeasured(V1_2_PAIR)]
    assert in_pair_order(tests) == in_pair_order(expected)


# What a test's result changes

# Results that test_render can have in the full run.
RENDER_RESULTS = [
    pytest.param(RENDER_FAILED, id="failed, as in K1"),
    pytest.param(junit.Result(failed=False, passed=True, time_ms=5000), id="passed"),
    pytest.param(junit.Result(failed=False, passed=False, time_ms=0), id="skipped"),
]


@pytest.mark.parametrize("result", RENDER_RESULTS)
def test_a_tests_result_does_not_change_how_it_is_matched(
    result: junit.Result,
) -> None:
    results = {**K1_RESULTS, RENDER_PAIR: result}

    tests = selection.match_tests(results, FIXTURE_ROWS)

    assert in_pair_order(tests) == in_pair_order(FIXTURE_TESTS)
