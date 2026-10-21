import pytest

from distiller import selection

# Each test hands select a run's tests, as match_tests gives them, the changed
# paths, the floor hits, as floor_hits gives them, and pytest's rootdir, all as
# literals, and watches selection from outside: what select returns.

# pytest's rootdir as select gets it, once cli has normalized it: "" for the
# repository root, as in the fixture, and backend for Edge 3's backend/.
ROOT = ""
BACKEND = "backend"

# The fixture's tests, by node id, relative to pytest's rootdir.
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

# Selection 7's and 9's test_rounding, which has no row: match_tests gives it
# with no node id and no row.
ROUNDING_PAIR = ("tests.test_tax", "test_rounding")
ROUNDING = selection.Test(pair=ROUNDING_PAIR, node_id=None, row=None)
WITH_ROUNDING = [*FIXTURE_TESTS, ROUNDING]

# A diff with no paths, and no floor hit.
NO_PATHS: list[str] = []
NO_HITS: list[tuple[str, str]] = []


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


def each_with(
    tests: list[selection.Test], *reasons: selection.Reason
) -> selection.Selection:
    """Each of tests selected, with those reasons and no other."""
    return {test.pair: frozenset(reasons) for test in tests}


def with_path_in_row(test: selection.Test, path: str) -> selection.Test:
    """test as match_tests would give it if its row also had path."""
    assert test.row is not None
    return selection.Test(pair=test.pair, node_id=test.node_id, row=test.row | {path})


# A diff over the fixture

# Diffs over the fixture's four tests, with pytest's rootdir at the repository
# root: the changed paths, the floor hits that floor_hits gives for them, and
# the selection.
FIXTURE_DIFFS = [
    pytest.param(
        [TAX],
        NO_HITS,
        {TOTAL_PAIR: frozenset({covers(TAX)}), VAT_PAIR: frozenset({covers(TAX)})},
        id="Selection 1, src/shop/tax.py",
    ),
    pytest.param(
        [PRICING, REPORT],
        NO_HITS,
        {
            TOTAL_PAIR: frozenset({covers(PRICING)}),
            RENDER_PAIR: frozenset({covers(PRICING), covers(REPORT)}),
        },
        id="Selection 2, two paths, both in test_render's row",
    ),
    pytest.param(
        [DB],
        NO_HITS,
        {TOTAL_PAIR: frozenset({covers(DB)})},
        id="Selection 3, a file run during test_total's setup",
    ),
    pytest.param(
        ["uv.lock"],
        [("**/uv.lock", "uv.lock")],
        each_with(FIXTURE_TESTS, floor("**/uv.lock", "uv.lock")),
        id="Selection 4, uv.lock",
    ),
    pytest.param(
        ["data/rates.csv"],
        [("data/**", "data/rates.csv")],
        each_with(FIXTURE_TESTS, floor("data/**", "data/rates.csv")),
        id="Selection 5, a pattern that the configuration adds",
    ),
    pytest.param(
        ["migrations/0002_vat.py"],
        [("**/migrations/**", "migrations/0002_vat.py")],
        each_with(FIXTURE_TESTS, floor("**/migrations/**", "migrations/0002_vat.py")),
        id="Selection 6, a default pattern, which the configuration keeps",
    ),
    pytest.param(
        ["tests/test_report.py"],
        NO_HITS,
        {RENDER_PAIR: frozenset({own_file("tests/test_report.py")})},
        id="Selection 8, a test file that coverage did not measure",
    ),
    pytest.param(
        ["tests/api/conftest.py"],
        NO_HITS,
        {CREATE_PAIR: frozenset({conftest("tests/api/conftest.py")})},
        id="Selection 10, tests/api/conftest.py",
    ),
    pytest.param(
        ["tests/conftest.py"],
        NO_HITS,
        each_with(FIXTURE_TESTS, conftest("tests/conftest.py")),
        id="Selection 11, tests/conftest.py",
    ),
    pytest.param(
        [REPORT],
        NO_HITS,
        {RENDER_PAIR: frozenset({covers(REPORT)})},
        id="Selection 12, a deleted file, under its old name",
    ),
    pytest.param(
        ["services/billing/uv.lock"],
        [("**/uv.lock", "services/billing/uv.lock")],
        each_with(FIXTURE_TESTS, floor("**/uv.lock", "services/billing/uv.lock")),
        id="Edge 11, services/billing/uv.lock",
    ),
    pytest.param(
        ["requirements/base.txt"],
        [("**/requirements/**", "requirements/base.txt")],
        each_with(FIXTURE_TESTS, floor("**/requirements/**", "requirements/base.txt")),
        id="Edge 12, requirements/base.txt",
    ),
    pytest.param(NO_PATHS, NO_HITS, {}, id="Edge 13, a diff with no paths"),
    pytest.param(
        ["config/app.yaml", "settings/app.yaml"],
        [("**/config/**", "config/app.yaml")],
        each_with(FIXTURE_TESTS, floor("**/config/**", "config/app.yaml")),
        id="Edge 20, settings/app.yaml renamed to config/app.yaml",
    ),
]


@pytest.mark.parametrize(("changed", "hits", "expected"), FIXTURE_DIFFS)
def test_a_diff_selects_every_test_that_a_rule_picks_with_all_its_reasons(
    changed: list[str], hits: list[tuple[str, str]], expected: selection.Selection
) -> None:
    assert selection.select(FIXTURE_TESTS, changed, hits, ROOT) == expected


# The selection in task 9's examples

# Edge 6's test_vat, which sets its own classname with record_xml_attribute:
# the JUnit names it by a pair that no node id turns into, so match_tests gives
# it as unmeasured.
OVERRIDDEN_PAIR = ("billing.TaxSuite", "test_vat")
OVERRIDDEN = selection.Test(pair=OVERRIDDEN_PAIR, node_id=None, row=None)

# Selection 13, 14 and 15 and Edge 6, 8 and 9, whose paths with no column and
# import-only paths are task 9's: the run's tests, the changed paths and the
# selection. Edge 8 and 9 name no path: src/shop/discounts.py stands for a file
# that M never saw, and src/shop/legacy.py for a measured file with no line.
TASK_9_EXAMPLES = [
    pytest.param(
        FIXTURE_TESTS,
        [TAX, "src/shop/taxes.py"],
        {TOTAL_PAIR: frozenset({covers(TAX)}), VAT_PAIR: frozenset({covers(TAX)})},
        id="Selection 13, src/shop/tax.py renamed, through its old name",
    ),
    pytest.param(
        FIXTURE_TESTS,
        ["templates/invoice.html"],
        {},
        id="Selection 14, templates/invoice.html, which has no column",
    ),
    pytest.param(
        FIXTURE_TESTS,
        ["src/shop/constants.py"],
        {},
        id="Selection 15, src/shop/constants.py, which is import-only",
    ),
    # Edge 6 names no diff: this one modifies src/shop/tax.py, which the row of
    # test_vat's node id has at M.
    pytest.param(
        [TOTAL, OVERRIDDEN, RENDER, CREATE],
        [TAX],
        {
            TOTAL_PAIR: frozenset({covers(TAX)}),
            OVERRIDDEN_PAIR: frozenset({UNMEASURED}),
        },
        id="Edge 6, test_vat with its classname set by record_xml_attribute",
    ),
    pytest.param(
        FIXTURE_TESTS,
        ["src/shop/discounts.py"],
        {},
        id="Edge 8, a file under src/ that M never saw",
    ),
    pytest.param(
        FIXTURE_TESTS,
        ["src/shop/legacy.py"],
        {},
        id="Edge 9, a measured file with no line recorded",
    ),
]


@pytest.mark.parametrize(("tests", "changed", "expected"), TASK_9_EXAMPLES)
def test_the_selection_in_task_9s_examples(
    tests: list[selection.Test], changed: list[str], expected: selection.Selection
) -> None:
    assert selection.select(tests, changed, NO_HITS, ROOT) == expected


# Unmeasured tests

# Diffs over the fixture's tests and test_rounding: the changed paths, the
# floor hits and the selection. Only unmeasured and a floor reason pick
# test_rounding: it has no row, for covers, and no node id, for own file and
# conftest.
UNMEASURED_DIFFS = [
    pytest.param(
        [REPORT],
        NO_HITS,
        {
            RENDER_PAIR: frozenset({covers(REPORT)}),
            ROUNDING_PAIR: frozenset({UNMEASURED}),
        },
        id="Selection 7, src/shop/report.py",
    ),
    pytest.param(
        ["tests/test_tax.py"],
        NO_HITS,
        {
            VAT_PAIR: frozenset({own_file("tests/test_tax.py")}),
            ROUNDING_PAIR: frozenset({UNMEASURED}),
        },
        id="Selection 9, tests/test_tax.py, which adds it",
    ),
    pytest.param(
        ["tests/conftest.py"],
        NO_HITS,
        {
            **each_with(FIXTURE_TESTS, conftest("tests/conftest.py")),
            ROUNDING_PAIR: frozenset({UNMEASURED}),
        },
        id="tests/conftest.py, in the directory of its file",
    ),
    pytest.param(
        ["uv.lock"],
        [("**/uv.lock", "uv.lock")],
        {
            **each_with(FIXTURE_TESTS, floor("**/uv.lock", "uv.lock")),
            ROUNDING_PAIR: frozenset({UNMEASURED, floor("**/uv.lock", "uv.lock")}),
        },
        id="uv.lock, whose floor hit picks it too",
    ),
    pytest.param(
        NO_PATHS,
        NO_HITS,
        {ROUNDING_PAIR: frozenset({UNMEASURED})},
        id="Edge 13, a diff with no paths, which selects only it",
    ),
]


@pytest.mark.parametrize(("changed", "hits", "expected"), UNMEASURED_DIFFS)
def test_an_unmeasured_test_is_picked_only_by_unmeasured_and_the_floor(
    changed: list[str], hits: list[tuple[str, str]], expected: selection.Selection
) -> None:
    assert selection.select(WITH_ROUNDING, changed, hits, ROOT) == expected


# Floor reasons

# Changed paths, the floor hits that floor_hits gives for them, and the floor
# reasons that every test carries: one for each hit, none twice.
FLOOR_REASONS = [
    pytest.param(
        ["config/pyproject.toml"],
        [
            ("**/config/**", "config/pyproject.toml"),
            ("**/pyproject.toml", "config/pyproject.toml"),
        ],
        [
            floor("**/config/**", "config/pyproject.toml"),
            floor("**/pyproject.toml", "config/pyproject.toml"),
        ],
        id="the SPEC's config/pyproject.toml, which two patterns match",
    ),
    pytest.param(
        ["config/app.yaml", "config/prod/db.yaml"],
        [("**/config/**", "config/app.yaml"), ("**/config/**", "config/prod/db.yaml")],
        [
            floor("**/config/**", "config/app.yaml"),
            floor("**/config/**", "config/prod/db.yaml"),
        ],
        id="one pattern that two paths match",
    ),
    pytest.param(
        ["data/rates.csv", "uv.lock"],
        [("**/uv.lock", "uv.lock"), ("data/**", "data/rates.csv")],
        [floor("**/uv.lock", "uv.lock"), floor("data/**", "data/rates.csv")],
        id="two patterns, each with its path",
    ),
    pytest.param(
        ["data/rates.csv"],
        [("data/**", "data/rates.csv"), ("data/**", "data/rates.csv")],
        [floor("data/**", "data/rates.csv")],
        id="a pattern that the configuration writes twice",
    ),
    pytest.param(
        ["uv.lock"],
        [("**/uv.lock", "uv.lock"), ("**/uv.lock", "uv.lock")],
        [floor("**/uv.lock", "uv.lock")],
        id="a default pattern that the configuration writes again",
    ),
]


@pytest.mark.parametrize(("changed", "hits", "reasons"), FLOOR_REASONS)
def test_every_test_cites_every_floor_hit_once(
    changed: list[str], hits: list[tuple[str, str]], reasons: list[selection.Reason]
) -> None:
    found = selection.select(FIXTURE_TESTS, changed, hits, ROOT)

    assert found == each_with(FIXTURE_TESTS, *reasons)


# Several rules

# Edge 10's changed path: a column, once a test's row has it, that matches the
# floor.
LOADER = "src/shop/config/loader.py"

# Every rule at once: a column, a test file, a conftest.py and a floor hit.
EVERY_RULE = [REPORT, "tests/conftest.py", "tests/test_report.py", "uv.lock"]
EVERY_RULE_HITS = [("**/uv.lock", "uv.lock")]


def test_edge_10_a_column_that_matches_the_floor_carries_both_reasons() -> None:
    # Edge 10 does not say which tests cover src/shop/config/loader.py: here
    # test_total and test_create do.
    tests = [
        with_path_in_row(TOTAL, LOADER),
        VAT,
        RENDER,
        with_path_in_row(CREATE, LOADER),
    ]

    found = selection.select(tests, [LOADER], [("**/config/**", LOADER)], ROOT)

    loader_floor = floor("**/config/**", LOADER)
    expected: selection.Selection = {
        TOTAL_PAIR: frozenset({covers(LOADER), loader_floor}),
        VAT_PAIR: frozenset({loader_floor}),
        RENDER_PAIR: frozenset({loader_floor}),
        CREATE_PAIR: frozenset({covers(LOADER), loader_floor}),
    }
    assert found == expected


def test_a_test_file_in_its_own_row_gives_covers_and_own_file() -> None:
    # Selection 8's diff, had coverage measured tests/ too: test_render's row
    # would have its own file.
    render = with_path_in_row(RENDER, "tests/test_report.py")

    found = selection.select(
        [TOTAL, VAT, render, CREATE], ["tests/test_report.py"], NO_HITS, ROOT
    )

    expected: selection.Selection = {
        RENDER_PAIR: frozenset(
            {covers("tests/test_report.py"), own_file("tests/test_report.py")}
        )
    }
    assert found == expected


def test_a_test_carries_a_reason_for_every_rule_that_picks_it() -> None:
    found = selection.select(WITH_ROUNDING, EVERY_RULE, EVERY_RULE_HITS, ROOT)

    uv_lock = floor("**/uv.lock", "uv.lock")
    in_tests = conftest("tests/conftest.py")
    expected: selection.Selection = {
        TOTAL_PAIR: frozenset({in_tests, uv_lock}),
        VAT_PAIR: frozenset({in_tests, uv_lock}),
        RENDER_PAIR: frozenset(
            {covers(REPORT), own_file("tests/test_report.py"), in_tests, uv_lock}
        ),
        CREATE_PAIR: frozenset({in_tests, uv_lock}),
        ROUNDING_PAIR: frozenset({UNMEASURED, uv_lock}),
    }
    assert found == expected


# Edge 1: a session fixture


def test_edge_1_test_vat_is_not_selected_although_it_uses_the_fixture() -> None:
    # The session fixture's setup ran src/shop/db.py during test_total's setup,
    # so only test_total's row has it, although test_vat also uses the fixture.
    found = selection.select(FIXTURE_TESTS, [DB], NO_HITS, ROOT)

    expected: selection.Selection = {TOTAL_PAIR: frozenset({covers(DB)})}
    assert found == expected


# The fixture's tests had the fixture's teardown run a line of src/shop/db.py:
# that line would count in the row of the session's last test, which the SPEC
# does not name, so each of the other three in turn. The tests and that pair.
SESSIONS_LAST_TEST = [
    pytest.param(
        [TOTAL, with_path_in_row(VAT, DB), RENDER, CREATE], VAT_PAIR, id="test_vat"
    ),
    pytest.param(
        [TOTAL, VAT, with_path_in_row(RENDER, DB), CREATE],
        RENDER_PAIR,
        id="test_render",
    ),
    pytest.param(
        [TOTAL, VAT, RENDER, with_path_in_row(CREATE, DB)],
        CREATE_PAIR,
        id="test_create",
    ),
]


@pytest.mark.parametrize(("tests", "last_pair"), SESSIONS_LAST_TEST)
def test_edge_1_a_teardown_that_ran_the_file_would_select_the_last_test_too(
    tests: list[selection.Test], last_pair: tuple[str, str]
) -> None:
    found = selection.select(tests, [DB], NO_HITS, ROOT)

    expected: selection.Selection = {
        TOTAL_PAIR: frozenset({covers(DB)}),
        last_pair: frozenset({covers(DB)}),
    }
    assert found == expected


# Own file and conftest

# Tests besides the fixture's, as match_tests gives them once measured.
IN_A_CLASS = selection.Test(
    pair=("tests.test_tax.TestVat", "test_rate"),
    node_id="tests/test_tax.py::TestVat::test_rate",
    row=frozenset({TAX}),
)
DOUBLE_COLON = selection.Test(
    pair=("tests.test_x", "test_m[a::b]"),
    node_id="tests/test_x.py::test_m[a::b]",
    row=frozenset({TAX}),
)
TEXT_DOCTEST = selection.Test(
    pair=("docs.tax.txt", "tax.txt"),
    node_id="docs/tax.txt::tax.txt",
    row=frozenset({TAX}),
)
IN_API_V2 = selection.Test(
    pair=("tests.api_v2.test_orders", "test_cancel"),
    node_id="tests/api_v2/test_orders.py::test_cancel",
    row=frozenset({ORDERS}),
)

# Diffs over the fixture's tests and one more: the run's tests, the changed
# paths and the selection. The file in a node id is what comes before its first
# ::, and a conftest.py picks the tests in its directory and the ones below it.
OWN_FILE_AND_CONFTEST = [
    pytest.param(
        [*FIXTURE_TESTS, IN_A_CLASS],
        ["tests/test_tax.py"],
        {
            VAT_PAIR: frozenset({own_file("tests/test_tax.py")}),
            IN_A_CLASS.pair: frozenset({own_file("tests/test_tax.py")}),
        },
        id="own file, with a class in the node id",
    ),
    pytest.param(
        [*FIXTURE_TESTS, DOUBLE_COLON],
        ["tests/test_x.py"],
        {DOUBLE_COLON.pair: frozenset({own_file("tests/test_x.py")})},
        id="own file, with a double colon in the parameters",
    ),
    pytest.param(
        [*FIXTURE_TESTS, TEXT_DOCTEST],
        ["docs/tax.txt"],
        {TEXT_DOCTEST.pair: frozenset({own_file("docs/tax.txt")})},
        id="own file, a text file's doctest",
    ),
    pytest.param(
        FIXTURE_TESTS,
        ["tests/my_conftest.py"],
        {},
        id="a file whose name only ends in conftest.py",
    ),
    pytest.param(
        [*FIXTURE_TESTS, IN_API_V2],
        ["tests/api/conftest.py"],
        {CREATE_PAIR: frozenset({conftest("tests/api/conftest.py")})},
        id="a conftest.py, and a directory whose name starts like its own",
    ),
]


@pytest.mark.parametrize(("tests", "changed", "expected"), OWN_FILE_AND_CONFTEST)
def test_own_file_and_conftest_go_by_the_file_in_the_node_id(
    tests: list[selection.Test], changed: list[str], expected: selection.Selection
) -> None:
    assert selection.select(tests, changed, NO_HITS, ROOT) == expected


# pytest's rootdir

# A test file at pytest's rootdir, and its test as match_tests gives it.
AT_ROOTDIR_PAIR = ("test_x", "test_m")
AT_ROOTDIR = selection.Test(
    pair=AT_ROOTDIR_PAIR, node_id="test_x.py::test_m", row=frozenset({TAX})
)
ROOTDIR_TESTS = [*FIXTURE_TESTS, AT_ROOTDIR]

# A rootdir two levels down.
SERVICES_BACKEND = "services/backend"

# Diffs over the fixture's tests and the test at the rootdir, whose node ids
# stay relative to the rootdir: the rootdir, the changed paths and the
# selection.
ROOTDIR_DIFFS = [
    pytest.param(
        ROOT,
        ["conftest.py"],
        each_with(ROOTDIR_TESTS, conftest("conftest.py")),
        id="Selection 11's conftest.py at the rootdir, the repository root",
    ),
    pytest.param(
        ROOT,
        ["tests/conftest.py"],
        each_with(FIXTURE_TESTS, conftest("tests/conftest.py")),
        id="tests/conftest.py, which is below the test at the rootdir",
    ),
    pytest.param(
        ROOT,
        ["test_x.py"],
        {AT_ROOTDIR_PAIR: frozenset({own_file("test_x.py")})},
        id="the own file of the test at the rootdir",
    ),
    pytest.param(
        BACKEND,
        ["backend/tests/test_tax.py"],
        {VAT_PAIR: frozenset({own_file("backend/tests/test_tax.py")})},
        id="Edge 3, test_vat's own file",
    ),
    pytest.param(
        BACKEND,
        ["tests/test_tax.py"],
        {},
        id="backend/, tests/test_tax.py, another file outside the rootdir",
    ),
    pytest.param(
        BACKEND,
        ["backend/test_x.py"],
        {AT_ROOTDIR_PAIR: frozenset({own_file("backend/test_x.py")})},
        id="backend/, the own file of the test at the rootdir",
    ),
    pytest.param(
        BACKEND,
        ["backend/tests/api/conftest.py"],
        {CREATE_PAIR: frozenset({conftest("backend/tests/api/conftest.py")})},
        id="Edge 3, the conftest.py of test_create's directory",
    ),
    pytest.param(
        BACKEND,
        ["backend/tests/conftest.py"],
        each_with(FIXTURE_TESTS, conftest("backend/tests/conftest.py")),
        id="Edge 3, backend/tests/conftest.py",
    ),
    pytest.param(
        BACKEND,
        ["backend/conftest.py"],
        each_with(ROOTDIR_TESTS, conftest("backend/conftest.py")),
        id="backend/, the conftest.py at the rootdir, which picks every test",
    ),
    pytest.param(
        BACKEND,
        ["conftest.py"],
        {},
        id="backend/, a conftest.py above the rootdir",
    ),
    pytest.param(
        BACKEND,
        ["tests/conftest.py"],
        {},
        id="backend/, tests/conftest.py, outside the rootdir",
    ),
    pytest.param(
        SERVICES_BACKEND,
        ["services/backend/tests/test_tax.py"],
        {VAT_PAIR: frozenset({own_file("services/backend/tests/test_tax.py")})},
        id="services/backend/, test_vat's own file",
    ),
    pytest.param(
        SERVICES_BACKEND,
        ["services/backend/conftest.py"],
        each_with(ROOTDIR_TESTS, conftest("services/backend/conftest.py")),
        id="services/backend/, the conftest.py at the rootdir",
    ),
    pytest.param(
        SERVICES_BACKEND,
        ["services/conftest.py"],
        {},
        id="services/backend/, a conftest.py between the root and the rootdir",
    ),
]


@pytest.mark.parametrize(("rootdir", "changed", "expected"), ROOTDIR_DIFFS)
def test_own_file_and_conftest_resolve_node_ids_through_pytests_rootdir(
    rootdir: str, changed: list[str], expected: selection.Selection
) -> None:
    assert selection.select(ROOTDIR_TESTS, changed, NO_HITS, rootdir) == expected


# Diffs that pytest's rootdir leaves as they are, since rows and floor hits hold
# paths from the repository root: the changed paths, the floor hits and the
# selection.
ROOTDIR_FREE_DIFFS = [
    pytest.param(
        [TAX],
        NO_HITS,
        {TOTAL_PAIR: frozenset({covers(TAX)}), VAT_PAIR: frozenset({covers(TAX)})},
        id="covers, Selection 1's diff",
    ),
    pytest.param(
        ["uv.lock"],
        [("**/uv.lock", "uv.lock")],
        each_with(FIXTURE_TESTS, floor("**/uv.lock", "uv.lock")),
        id="the floor, Selection 4's diff",
    ),
]


@pytest.mark.parametrize(("changed", "hits", "expected"), ROOTDIR_FREE_DIFFS)
def test_pytests_rootdir_changes_neither_covers_nor_the_floor(
    changed: list[str], hits: list[tuple[str, str]], expected: selection.Selection
) -> None:
    assert selection.select(FIXTURE_TESTS, changed, hits, BACKEND) == expected


# A run with no tests


def test_a_run_with_no_tests_selects_none_even_through_the_floor() -> None:
    found = selection.select([], ["uv.lock"], [("**/uv.lock", "uv.lock")], ROOT)

    assert found == {}


# Invariants


def test_invariant_2_the_order_of_the_tests_does_not_change_the_selection() -> None:
    # A test reaches select as its pair, node id and row: which tests failed
    # and how long they took never do. Two runs that differ only in those give
    # select the same tests, perhaps in another order, since the SPEC fixes no
    # order for match_tests's list.
    in_one_order = selection.select(WITH_ROUNDING, EVERY_RULE, EVERY_RULE_HITS, ROOT)
    in_another = selection.select(
        list(reversed(WITH_ROUNDING)), EVERY_RULE, EVERY_RULE_HITS, ROOT
    )

    assert in_one_order == in_another


def test_invariant_3_a_diff_that_grows_loses_no_test() -> None:
    smaller = selection.select(FIXTURE_TESTS, [TAX], NO_HITS, ROOT)
    larger = selection.select(FIXTURE_TESTS, [TAX, REPORT], NO_HITS, ROOT)

    assert set(smaller) == {TOTAL_PAIR, VAT_PAIR}
    assert set(larger) == {TOTAL_PAIR, VAT_PAIR, RENDER_PAIR}


# Diffs over the fixture's tests and test_rounding: the changed paths, the floor
# hits and the tests selected.
INVARIANT_4 = [
    pytest.param(
        [TAX],
        NO_HITS,
        {TOTAL_PAIR, VAT_PAIR, ROUNDING_PAIR},
        id="the SPEC's example, src/shop/tax.py",
    ),
    pytest.param(
        EVERY_RULE,
        EVERY_RULE_HITS,
        {TOTAL_PAIR, VAT_PAIR, RENDER_PAIR, CREATE_PAIR, ROUNDING_PAIR},
        id="every rule at once",
    ),
]


@pytest.mark.parametrize(("changed", "hits", "selected"), INVARIANT_4)
def test_invariant_4_each_selected_test_has_a_reason_and_names_only_the_diffs_paths(
    changed: list[str], hits: list[tuple[str, str]], selected: set[tuple[str, str]]
) -> None:
    found = selection.select(WITH_ROUNDING, changed, hits, ROOT)

    assert set(found) == selected
    for reasons in found.values():
        assert len(reasons) >= 1
        for reason in reasons:
            assert reason.path is None or reason.path in changed
