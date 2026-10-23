import pytest

from distiller import coverage_at_m, junit, selection

# Each test hands one of the four functions that give an evaluated record's
# figures its inputs, all as literals, and watches selection from outside: what
# that function returns. no_column and import_only_paths get the changed paths
# and the matrix, as build_matrix gives it; row_counts gets the rows, as
# build_matrix gives them, and the full run's results, as parse_junit gives
# them; durations gets the full run, as parse_junit gives it, and the
# selection, as select gives it.

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
CONSTANTS = "src/shop/constants.py"

# A file of the fixture that coverage did not measure.
INVOICE = "templates/invoice.html"

# The name that Selection 13 gives src/shop/tax.py, which M never saw.
TAXES = "src/shop/taxes.py"

# Edge 8 and 9 name no path: src/shop/discounts.py stands for a file under src/
# that M never saw, and src/shop/legacy.py for a file that coverage lists as
# measured with no line recorded, which build_matrix leaves out of every row
# and out of import_only.
DISCOUNTS = "src/shop/discounts.py"
LEGACY = "src/shop/legacy.py"

# The fixture's rows, as build_matrix gives them, test_render's being K1's.
FIXTURE_ROWS = {
    TEST_TOTAL: frozenset({PRICING, TAX, DB}),
    TEST_VAT: frozenset({TAX}),
    TEST_RENDER: frozenset({PRICING, REPORT}),
    TEST_CREATE: frozenset({ORDERS}),
}

# The fixture's matrix: its rows, and src/shop/constants.py, whose lines were
# all recorded outside any test.
FIXTURE_MATRIX = coverage_at_m.Matrix(
    rows=FIXTURE_ROWS, import_only=frozenset({CONSTANTS})
)

# Selection 7's test_rounding, which has no row, by its node id and its pair.
TEST_ROUNDING = "tests/test_tax.py::test_rounding"
ROUNDING_PAIR = ("tests.test_tax", "test_rounding")

# The fixture's matrix as build_matrix gives it when test_rounding's node id
# ran only files outside the repository: it keeps that node id's empty row.
WITH_EMPTY_ROW = coverage_at_m.Matrix(
    rows={**FIXTURE_ROWS, TEST_ROUNDING: frozenset[str]()},
    import_only=frozenset({CONSTANTS}),
)

# The SPEC's two node ids with one pair, and that pair.
V1_DOT_2 = "tests/v1.2/test_x.py::test_m"
V1_SLASH_2 = "tests/v1/2/test_x.py::test_m"
V1_2_PAIR = ("tests.v1.2.test_x", "test_m")

# test_vat's pair in the JUnit when it is renamed at H, and when it sets its
# own classname with record_xml_attribute, as in Edge 6.
RENAMED_PAIR = ("tests.test_tax", "test_vat_rate")
OVERRIDDEN_PAIR = ("billing.TaxSuite", "test_vat")

# A diff with no paths, and coverage with no test context.
NO_PATHS: list[str] = []
NO_ROWS: dict[str, frozenset[str]] = {}


# Full runs, as parse_junit gives them

# The results that tests can have in the full run's JUnit, with their times. A
# skipped test neither failed nor passed.
TOTAL_PASSED = junit.Result(failed=False, passed=True, time_ms=2000)
VAT_PASSED = junit.Result(failed=False, passed=True, time_ms=1000)
VAT_FAILED = junit.Result(failed=True, passed=False, time_ms=1000)
VAT_SKIPPED = junit.Result(failed=False, passed=False, time_ms=0)
RENDER_PASSED = junit.Result(failed=False, passed=True, time_ms=5000)
RENDER_FAILED = junit.Result(failed=True, passed=False, time_ms=5000)
CREATE_PASSED = junit.Result(failed=False, passed=True, time_ms=4000)
# test_create skipped by a pytest.skip in its body, once its 4.0 s had run: the
# JUnit times a skipped test too.
CREATE_SKIPPED = junit.Result(failed=False, passed=False, time_ms=4000)
# A test that the fixture does not have, test_rounding or test_m, passed.
PASSED = junit.Result(failed=False, passed=True, time_ms=300)


def junit_with(results: dict[tuple[str, str], junit.Result]) -> junit.JUnit:
    """A JUnit file as parse_junit gives it: these results, no collection error."""
    return junit.JUnit(results=results, has_collection_error=False)


# K1's full run, in which test_render failed. Its tests took 12.0 s in all.
K1_RESULTS: dict[tuple[str, str], junit.Result] = {
    TOTAL_PAIR: TOTAL_PASSED,
    VAT_PAIR: VAT_PASSED,
    RENDER_PAIR: RENDER_FAILED,
    CREATE_PAIR: CREATE_PASSED,
}
K1_FULL_RUN = junit_with(K1_RESULTS)

# Other full runs of the fixture's tests, named by what happened in them.
RUN_WITH_NO_FAILURE = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
# Verdict 1's.
RUN_VAT_FAILED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_FAILED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
RUN_VAT_SKIPPED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_SKIPPED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
RUN_CREATE_SKIPPED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_SKIPPED,
    }
)
# Selection 7's, which also has test_rounding.
RUN_WITH_ROUNDING = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        VAT_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
        ROUNDING_PAIR: PASSED,
    }
)
# Edge 6's: the JUnit names test_vat by the classname that it sets.
RUN_VAT_OVERRIDDEN = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        OVERRIDDEN_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
# Edge 7's: test_vat deleted at H, and renamed at H to test_vat_rate.
RUN_VAT_DELETED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
RUN_VAT_RENAMED = junit_with(
    {
        TOTAL_PAIR: TOTAL_PASSED,
        RENAMED_PAIR: VAT_PASSED,
        RENDER_PAIR: RENDER_PASSED,
        CREATE_PAIR: CREATE_PASSED,
    }
)
# K1's, with the test whose pair the SPEC's two node ids have.
RUN_WITH_V1_2 = junit_with({**K1_RESULTS, V1_2_PAIR: PASSED})
RUN_WITH_NO_TEST = junit_with({})


# Selections, as select gives them


def covers(path: str) -> selection.Reason:
    """`covers P`: the test's row has the changed path P."""
    return selection.Reason(rule="covers", path=path)


def floor(pattern: str, path: str) -> selection.Reason:
    """`floor X (P)`: the changed path P matches the floor pattern X."""
    return selection.Reason(rule="floor", path=path, pattern=pattern)


# `unmeasured`, which names no path.
UNMEASURED = selection.Reason(rule="unmeasured", path=None)

# The selections that select gives, as tests/test_select.py pins them, by the
# diff that gives each.

# templates/invoice.html, K1's diff and Selection 14's, selects no test.
NOTHING_SELECTED: selection.Selection = {}
# src/shop/tax.py, Selection 1's and Verdict 1's.
TAX_SELECTION: selection.Selection = {
    TOTAL_PAIR: frozenset({covers(TAX)}),
    VAT_PAIR: frozenset({covers(TAX)}),
}
# src/shop/pricing.py and src/shop/report.py, Selection 2's: test_render has a
# reason for each.
PRICING_AND_REPORT_SELECTION: selection.Selection = {
    TOTAL_PAIR: frozenset({covers(PRICING)}),
    RENDER_PAIR: frozenset({covers(PRICING), covers(REPORT)}),
}
# uv.lock, Selection 4's, selects every test through the floor.
UV_LOCK = floor("**/uv.lock", "uv.lock")
FLOOR_SELECTION: selection.Selection = {
    TOTAL_PAIR: frozenset({UV_LOCK}),
    VAT_PAIR: frozenset({UV_LOCK}),
    RENDER_PAIR: frozenset({UV_LOCK}),
    CREATE_PAIR: frozenset({UV_LOCK}),
}
# src/shop/report.py, Selection 7's, in a run that has test_rounding.
REPORT_AND_ROUNDING_SELECTION: selection.Selection = {
    RENDER_PAIR: frozenset({covers(REPORT)}),
    ROUNDING_PAIR: frozenset({UNMEASURED}),
}


# K1, with the values that its record line shows


def test_k1_templates_invoice_html_is_the_only_path_with_no_column() -> None:
    found = selection.no_column(["templates/invoice.html"], FIXTURE_MATRIX)

    assert found == ["templates/invoice.html"]


def test_k1_no_changed_path_is_import_only() -> None:
    found = selection.import_only_paths(["templates/invoice.html"], FIXTURE_MATRIX)

    assert found == []


def test_k1_four_tests_have_a_row_and_all_four_are_in_the_run() -> None:
    assert selection.row_counts(FIXTURE_ROWS, K1_RESULTS) == (4, 0)


def test_k1_no_test_is_selected_out_of_a_full_run_of_12000_ms() -> None:
    # A diff that modifies only templates/invoice.html selects no test.
    found = selection.durations(K1_FULL_RUN, NOTHING_SELECTED)

    assert found == (0, 12000)


# Selection 13, 14 and 15 and Edge 8 and 9

# The examples' changed paths, over the fixture's matrix, and the paths with no
# column that their records list. Selection 15 lists src/shop/constants.py as
# import-only, separately from these.
NO_COLUMN_EXAMPLES = [
    pytest.param(
        [TAX, TAXES],
        [TAXES],
        id="Selection 13, src/shop/tax.py renamed to src/shop/taxes.py",
    ),
    pytest.param([INVOICE], [INVOICE], id="Selection 14, templates/invoice.html"),
    pytest.param([CONSTANTS], [], id="Selection 15, src/shop/constants.py"),
    pytest.param([DISCOUNTS], [DISCOUNTS], id="Edge 8, a file that M never saw"),
    pytest.param([LEGACY], [LEGACY], id="Edge 9, a measured file with no line"),
]


@pytest.mark.parametrize(("changed", "expected"), NO_COLUMN_EXAMPLES)
def test_the_examples_list_their_paths_with_no_column(
    changed: list[str], expected: list[str]
) -> None:
    assert selection.no_column(changed, FIXTURE_MATRIX) == expected


# The same examples and the import-only paths that their records list. Only
# Selection 15 names one; the others leave out the fixture's only import-only
# file, src/shop/constants.py.
IMPORT_ONLY_EXAMPLES = [
    pytest.param(
        [TAX, TAXES],
        [],
        id="Selection 13, src/shop/tax.py renamed to src/shop/taxes.py",
    ),
    pytest.param([INVOICE], [], id="Selection 14, templates/invoice.html"),
    pytest.param([CONSTANTS], [CONSTANTS], id="Selection 15, src/shop/constants.py"),
    pytest.param([DISCOUNTS], [], id="Edge 8, a file that M never saw"),
    pytest.param([LEGACY], [], id="Edge 9, a measured file with no line"),
]


@pytest.mark.parametrize(("changed", "expected"), IMPORT_ONLY_EXAMPLES)
def test_the_examples_list_their_import_only_paths(
    changed: list[str], expected: list[str]
) -> None:
    assert selection.import_only_paths(changed, FIXTURE_MATRIX) == expected


# Columns, import-only paths and the paths with no column

# A diff with an import-only path, a column and a path with no column, in the
# order git lists them.
MIXED = [CONSTANTS, TAX, INVOICE]

# Changed paths, the matrix, and the paths with no column: a column is a file
# in at least one row, and a changed path that is neither a column nor
# import-only has no column, whatever floor pattern it matches.
NO_COLUMN_RULE = [
    pytest.param(
        MIXED,
        FIXTURE_MATRIX,
        [INVOICE],
        id="an import-only path, a column and a path with no column",
    ),
    pytest.param(
        MIXED,
        WITH_EMPTY_ROW,
        [INVOICE],
        id="the same over a matrix with an empty row, which makes no column",
    ),
    pytest.param(
        ["uv.lock"],
        FIXTURE_MATRIX,
        ["uv.lock"],
        id="uv.lock, which matches the floor and is in no row",
    ),
    pytest.param(NO_PATHS, FIXTURE_MATRIX, [], id="a diff with no paths"),
]


@pytest.mark.parametrize(("changed", "matrix", "expected"), NO_COLUMN_RULE)
def test_a_changed_path_in_no_row_that_is_not_import_only_has_no_column(
    changed: list[str], matrix: coverage_at_m.Matrix, expected: list[str]
) -> None:
    assert selection.no_column(changed, matrix) == expected


# Changed paths, the matrix, and the import-only paths: the changed paths that
# the matrix has as import-only, and no other.
IMPORT_ONLY_RULE = [
    pytest.param(
        MIXED,
        FIXTURE_MATRIX,
        [CONSTANTS],
        id="an import-only path, a column and a path with no column",
    ),
    pytest.param(
        MIXED,
        WITH_EMPTY_ROW,
        [CONSTANTS],
        id="the same over a matrix with an empty row",
    ),
    pytest.param(NO_PATHS, FIXTURE_MATRIX, [], id="a diff with no paths"),
]


@pytest.mark.parametrize(("changed", "matrix", "expected"), IMPORT_ONLY_RULE)
def test_only_the_changed_paths_that_the_matrix_has_as_import_only_are_listed(
    changed: list[str], matrix: coverage_at_m.Matrix, expected: list[str]
) -> None:
    assert selection.import_only_paths(changed, matrix) == expected


# Rule 8: both lists are sorted by code point, whatever the diff's order


def test_the_paths_with_no_column_are_sorted_by_code_point() -> None:
    # Four paths with no column, out of order. By code point, R comes before d.
    changed = [TAXES, "README.md", INVOICE, "docs/guide.md"]

    found = selection.no_column(changed, FIXTURE_MATRIX)

    assert found == [
        "README.md",
        "docs/guide.md",
        "src/shop/taxes.py",
        "templates/invoice.html",
    ]


def test_the_import_only_paths_are_sorted_by_code_point() -> None:
    # Three files whose lines were all recorded outside any test, changed out
    # of order. By code point, C comes before _, which comes before c.
    currency = "src/shop/Currency.py"
    version = "src/shop/_version.py"
    matrix = coverage_at_m.Matrix(
        rows=FIXTURE_ROWS, import_only=frozenset({CONSTANTS, currency, version})
    )

    found = selection.import_only_paths([CONSTANTS, currency, version], matrix)

    assert found == [
        "src/shop/Currency.py",
        "src/shop/_version.py",
        "src/shop/constants.py",
    ]


# Tests with a row, and how many of them are not in the run

# Full runs in which test_vat's node id, which keeps its row in the coverage at
# M, has a pair that is not in the run's JUnit.
NOT_IN_THE_RUN = [
    pytest.param(
        RUN_VAT_OVERRIDDEN,
        id="Edge 6, test_vat's classname set with record_xml_attribute",
    ),
    pytest.param(RUN_VAT_DELETED, id="Edge 7, test_vat deleted at H"),
    pytest.param(RUN_VAT_RENAMED, id="Edge 7, test_vat renamed at H"),
]


@pytest.mark.parametrize("full", NOT_IN_THE_RUN)
def test_edge_6_and_7_a_test_with_a_row_that_is_not_in_the_run_is_counted(
    full: junit.JUnit,
) -> None:
    assert selection.row_counts(FIXTURE_ROWS, full.results) == (4, 1)


# The rows, the full run, and the two counts. A node id with a row is in the
# run when its pair is in the run's JUnit, whatever the test's result there,
# and a test of the run with no row is not a test with a row.
IN_THE_RUN = [
    pytest.param(
        FIXTURE_ROWS, RUN_VAT_SKIPPED, (4, 0), id="test_vat skipped, so in the run"
    ),
    pytest.param(
        FIXTURE_ROWS,
        RUN_WITH_ROUNDING,
        (4, 0),
        id="Selection 7's test_rounding, in the run with no row",
    ),
    pytest.param(FIXTURE_ROWS, RUN_WITH_NO_TEST, (4, 4), id="a run with no test"),
    pytest.param(NO_ROWS, K1_FULL_RUN, (0, 0), id="coverage with no test context"),
]


@pytest.mark.parametrize(("rows", "full", "counts"), IN_THE_RUN)
def test_a_node_id_with_a_row_is_in_the_run_when_its_pair_is_in_the_junit(
    rows: dict[str, frozenset[str]], full: junit.JUnit, counts: tuple[int, int]
) -> None:
    assert selection.row_counts(rows, full.results) == counts


# The fixture's rows and the SPEC's two node ids with one pair, each with a
# row.
SHARED_ROWS = {
    **FIXTURE_ROWS,
    V1_DOT_2: frozenset({TAX}),
    V1_SLASH_2: frozenset({REPORT}),
}

# Full runs with their pair and without it, and the counts: the two node ids
# are two tests with a row, and both are in the run, or both not.
SHARED_PAIR = [
    pytest.param(RUN_WITH_V1_2, (6, 0), id="their pair in the run"),
    pytest.param(K1_FULL_RUN, (6, 2), id="their pair not in the run"),
]


@pytest.mark.parametrize(("full", "counts"), SHARED_PAIR)
def test_two_node_ids_with_one_pair_are_both_in_the_run_or_both_not(
    full: junit.JUnit, counts: tuple[int, int]
) -> None:
    assert selection.row_counts(SHARED_ROWS, full.results) == counts


# The fixture's rows and the SPEC's two node ids with one pair: the first one's
# row empty, as build_matrix keeps it when its lines all fell outside the
# repository, and the second one's not.
ONE_OF_TWO_EMPTY = {
    **FIXTURE_ROWS,
    V1_DOT_2: frozenset[str](),
    V1_SLASH_2: frozenset({TAX}),
}

# Rows with an empty row, the full run, and the counts. An empty row is no row:
# its node id counts in neither, whether or not its pair is in the run, and
# another node id with that pair and a row counts like any other.
EMPTY_ROWS = [
    pytest.param(
        WITH_EMPTY_ROW.rows,
        RUN_WITH_ROUNDING,
        (4, 0),
        id="test_rounding's, its pair in the run",
    ),
    pytest.param(
        WITH_EMPTY_ROW.rows,
        K1_FULL_RUN,
        (4, 0),
        id="test_rounding's, its pair not in the run",
    ),
    pytest.param(
        ONE_OF_TWO_EMPTY,
        RUN_WITH_V1_2,
        (5, 0),
        id="one of two node ids with one pair, that pair in the run",
    ),
    pytest.param(
        ONE_OF_TWO_EMPTY,
        K1_FULL_RUN,
        (5, 1),
        id="one of two node ids with one pair, that pair not in the run",
    ),
]


@pytest.mark.parametrize(("rows", "full", "counts"), EMPTY_ROWS)
def test_an_empty_row_is_no_row_whether_or_not_its_pair_is_in_the_run(
    rows: dict[str, frozenset[str]], full: junit.JUnit, counts: tuple[int, int]
) -> None:
    assert selection.row_counts(rows, full.results) == counts


# The selected and full-suite durations

# A full run, the selection that select gives for a diff, and the durations,
# selected_ms and then full_ms: selected_ms sums the times of the selected
# tests, each once, and full_ms those of every test in the full run, whatever
# its result.
DURATIONS = [
    pytest.param(
        RUN_VAT_FAILED,
        TAX_SELECTION,
        (3000, 12000),
        id="Verdict 1, test_total and test_vat selected, test_vat failed",
    ),
    pytest.param(
        RUN_WITH_NO_FAILURE,
        PRICING_AND_REPORT_SELECTION,
        (7000, 12000),
        id="Selection 2, test_render selected with two reasons",
    ),
    pytest.param(
        RUN_WITH_NO_FAILURE,
        FLOOR_SELECTION,
        (12000, 12000),
        id="Selection 4, every test selected through the floor",
    ),
    pytest.param(
        RUN_CREATE_SKIPPED,
        FLOOR_SELECTION,
        (12000, 12000),
        id="the same, with test_create skipped after its 4.0 s",
    ),
    pytest.param(
        RUN_WITH_ROUNDING,
        REPORT_AND_ROUNDING_SELECTION,
        (5300, 12300),
        id="Selection 7, test_render and the unmeasured test_rounding selected",
    ),
    pytest.param(RUN_WITH_NO_TEST, NOTHING_SELECTED, (0, 0), id="a run with no test"),
]


@pytest.mark.parametrize(("full", "selected", "expected"), DURATIONS)
def test_selected_ms_and_full_ms_sum_the_times_in_the_full_run(
    full: junit.JUnit, selected: selection.Selection, expected: tuple[int, int]
) -> None:
    assert selection.durations(full, selected) == expected
