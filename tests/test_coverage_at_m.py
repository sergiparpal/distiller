import contextlib
import os
import signal
import sqlite3
from collections.abc import Callable, Generator
from pathlib import Path
from types import FrameType

import coverage
import pytest

from distiller import coverage_at_m, messages

# Each test writes its own coverage file in tmp_path through coverage's public
# API, or hands build_matrix coverage as read_coverage gives it, and watches
# coverage_at_m from outside: what node_id_of, read_coverage and build_matrix
# return or raise, and what the coverage file holds after.

# How long a call may run before fails_if_it_blocks stops it.
BLOCKING_SECONDS = 5

# The coverage file's path as a command line could give it, from the working
# directory, which the coverage_file fixture sets to tmp_path. A rejection
# names it exactly, ./ included.
COVERAGE = "./ci/m.coverage"

# What read_coverage raises for a coverage file it cannot use: its reason,
# input, subject and line number.
UNUSABLE = ("unusable-input", "coverage", COVERAGE, None)

# The fixture's tests, by node id.
TEST_TOTAL = "tests/test_pricing.py::test_total"
TEST_VAT = "tests/test_tax.py::test_vat"
TEST_RENDER = "tests/test_report.py::test_render"
TEST_CREATE = "tests/api/test_orders.py::test_create"

# The fixture's measured files, by their paths from the repository root.
PRICING = "src/shop/pricing.py"
TAX = "src/shop/tax.py"
DB = "src/shop/db.py"
REPORT = "src/shop/report.py"
ORDERS = "src/shop/orders.py"
CONSTANTS = "src/shop/constants.py"

# M's tree: every file that the fixture names.
FIXTURE_TREE = frozenset(
    {
        PRICING,
        TAX,
        DB,
        REPORT,
        ORDERS,
        CONSTANTS,
        "templates/invoice.html",
        "tests/conftest.py",
        "tests/api/conftest.py",
        "tests/test_pricing.py",
        "tests/test_tax.py",
        "tests/test_report.py",
        "tests/api/test_orders.py",
    }
)

# The checkout where the coverage at M was recorded: by default, coverage
# records each file by its absolute path under it (Edge 4).
RUNNER_ROOT = "/runner/work/shop/"

# A file outside the repository, which coverage measures if it is told to.
OUTSIDE = "/usr/lib/python3.12/json/__init__.py"

# A file that never ran: coverage lists each file under its source that never
# ran as measured, with no line.
NEVER_RAN = "src/shop/__init__.py"

# A node id whose path holds a newline, as a directory's name can. The newline
# is written by its code point.
NEWLINE_NODE_ID = "tests/new" + chr(10) + "line/test_x.py::test_m"

# The lines recorded in each context, by file.
LinesByContext = dict[str, dict[str, list[int]]]

# The fixture's coverage at M as pytest-cov records it with --cov-context=test,
# each file by its path from the repository root. What ran at import is in the
# empty context; the session fixture runs src/shop/db.py during test_total's
# setup; and line 3 of src/shop/tax.py ran for test_total and for test_vat.
FIXTURE_LINES: LinesByContext = {
    "": {
        PRICING: [1, 2, 6],
        TAX: [1, 2],
        DB: [1, 4],
        REPORT: [1, 2],
        ORDERS: [1, 2],
        CONSTANTS: [1, 2],
    },
    f"{TEST_TOTAL}|setup": {DB: [2, 3]},
    f"{TEST_TOTAL}|run": {PRICING: [3, 4], TAX: [3]},
    f"{TEST_VAT}|run": {TAX: [3, 4]},
    f"{TEST_RENDER}|run": {REPORT: [3, 4], PRICING: [7]},
    f"{TEST_CREATE}|run": {ORDERS: [3]},
}

# The same coverage as the sysmon core leaves it: line 3 of src/shop/tax.py is
# recorded only for test_total, the first test that ran it.
SYSMON_LINES: LinesByContext = {**FIXTURE_LINES, f"{TEST_VAT}|run": {TAX: [4]}}

# What read_coverage gives for the fixture's coverage recorded under
# RUNNER_ROOT: each file's node ids, and the file recorded only at import.
FIXTURE_NODES_BY_FILE = {
    RUNNER_ROOT + PRICING: frozenset({TEST_TOTAL, TEST_RENDER}),
    RUNNER_ROOT + TAX: frozenset({TEST_TOTAL, TEST_VAT}),
    RUNNER_ROOT + DB: frozenset({TEST_TOTAL}),
    RUNNER_ROOT + REPORT: frozenset({TEST_RENDER}),
    RUNNER_ROOT + ORDERS: frozenset({TEST_CREATE}),
}
FIXTURE_IMPORT_ONLY_FILES = frozenset({RUNNER_ROOT + CONSTANTS})

# The fixture's table, test_render's row being K1's, and its import-only file.
FIXTURE_MATRIX = coverage_at_m.Matrix(
    rows={
        TEST_TOTAL: frozenset({PRICING, TAX, DB}),
        TEST_VAT: frozenset({TAX}),
        TEST_RENDER: frozenset({PRICING, REPORT}),
        TEST_CREATE: frozenset({ORDERS}),
    },
    import_only=frozenset({CONSTANTS}),
)

# How coverage records what ran: lines, or arcs under branch coverage, from
# which contexts_by_lineno works out the lines.
MEASUREMENTS = [
    pytest.param("lines", id="lines"),
    pytest.param("arcs", id="arcs, under branch coverage"),
]

# How coverage records each file: by its absolute path, as it does by default,
# or by its path from the checkout, as it does with relative_files.
ROOTS = [
    pytest.param(RUNNER_ROOT, id="absolute paths"),
    pytest.param("", id="relative paths"),
]

# Contexts outside any test: the one at import, a static one, and one that
# only looks like a test context.
OTHER_CONTEXTS = [
    pytest.param("", id="the empty context"),
    pytest.param("ci", id="a static context"),
    pytest.param(f"{TEST_TOTAL}|call", id="a phase other than setup, run, teardown"),
]

# Coverage in which a line was recorded for two node ids or more.
SHARED_LINES = [
    pytest.param(
        {f"{TEST_TOTAL}|run": {TAX: [3]}, f"{TEST_VAT}|run": {TAX: [3]}},
        id="two tests' calls",
    ),
    pytest.param(
        {f"{TEST_TOTAL}|setup": {DB: [2]}, f"{TEST_VAT}|teardown": {DB: [2]}},
        id="one test's setup and another's teardown",
    ),
    pytest.param(
        {
            "tests/test_tax.py::test_rate[es-0.21]|run": {TAX: [3]},
            "tests/test_tax.py::test_rate[fr-0.20]|run": {TAX: [3]},
        },
        id="two parameters of one test",
    ),
]

# Coverage in which no line was recorded for more than one node id.
UNSHARED_LINES = [
    pytest.param(
        {
            f"{TEST_VAT}|setup": {TAX: [3]},
            f"{TEST_VAT}|run": {TAX: [3]},
            f"{TEST_VAT}|teardown": {TAX: [3]},
        },
        id="one test's setup, call and teardown",
    ),
    pytest.param(
        {"": {TAX: [3]}, f"{TEST_VAT}|run": {TAX: [3]}},
        id="import and one test",
    ),
    pytest.param(
        {"": {TAX: [3]}, "ci": {TAX: [3]}},
        id="two contexts outside any test",
    ),
    pytest.param(
        {f"{TEST_TOTAL}|run": {TAX: [3]}, f"{TEST_VAT}|run": {TAX: [4]}},
        id="two tests on different lines",
    ),
    pytest.param(
        {f"{TEST_TOTAL}|run": {TAX: [3]}, f"{TEST_VAT}|run": {PRICING: [3]}},
        id="two tests on the same line number of different files",
    ),
    pytest.param(
        {f"{TEST_TOTAL}|call": {TAX: [3]}, f"{TEST_VAT}|run": {TAX: [3]}},
        id="one test and a context that only looks like one",
    ),
]


class BlockedError(BaseException):
    """A call was still running when the alarm went off.

    A BaseException, so that no `except Exception` in the code under test
    catches it.
    """


def recorded_under(root: str, lines: LinesByContext) -> LinesByContext:
    """The same lines, with each file recorded as root followed by its path."""
    return {
        context: {root + path: numbers for path, numbers in lines_by_file.items()}
        for context, lines_by_file in lines.items()
    }


def write_coverage(
    path: Path,
    lines: LinesByContext,
    *,
    measurement: str = "lines",
    files_with_no_line: tuple[str, ...] = (),
) -> None:
    """Write a coverage data file that holds these lines, through coverage's API.

    With measurement "arcs", each line is recorded as an arc that enters it.
    The files with no line are listed as measured all the same.
    """
    data = coverage.CoverageData(basename=path)
    for context, lines_by_file in lines.items():
        data.set_context(context)
        if measurement == "arcs":
            data.add_arcs(
                {
                    recorded: [(-1, number) for number in numbers]
                    for recorded, numbers in lines_by_file.items()
                }
            )
        else:
            data.add_lines(lines_by_file)
    if files_with_no_line:
        data.touch_files(files_with_no_line)
    data.write()
    data.close()


def write_fixture_coverage(path: Path) -> None:
    write_coverage(path, recorded_under(RUNNER_ROOT, FIXTURE_LINES))


def write_empty_file(path: Path) -> None:
    path.write_bytes(b"")


def write_text_file(path: Path) -> None:
    path.write_text("not a coverage data file\n", encoding="utf-8")


def write_database(path: Path, *statements: str) -> None:
    """Write an SQLite database of something else, made by these statements."""
    with contextlib.closing(sqlite3.connect(path)) as connection:
        for statement in statements:
            connection.execute(statement)
        connection.commit()


def write_foreign_database(path: Path) -> None:
    # None of its tables is named like one of coverage's.
    write_database(
        path,
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, total TEXT)",
        "INSERT INTO orders (total) VALUES ('12.00')",
    )


def write_foreign_database_with_a_meta_table(path: Path) -> None:
    # Its table meta is named like one of coverage's.
    write_database(
        path,
        "CREATE TABLE meta (key TEXT, value TEXT)",
        "INSERT INTO meta (key, value) VALUES ('owner', 'billing')",
    )


def write_coverage_with_no_measured_file(path: Path) -> None:
    # coverage's tables, with nothing measured in them.
    write_coverage(path, {"": {}})


def write_cut_short_coverage(path: Path) -> None:
    # The fixture's coverage file, of which only the first half was written.
    write_fixture_coverage(path)
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])


# Files that are not coverage data files, each written by its function.
NOT_COVERAGE_DATA = [
    pytest.param(write_text_file, id="text"),
    pytest.param(write_foreign_database, id="an SQLite database of something else"),
    pytest.param(
        write_foreign_database_with_a_meta_table,
        id="an SQLite database with a table named like one of coverage's",
    ),
    pytest.param(
        write_coverage_with_no_measured_file,
        id="coverage's tables with no measured file",
    ),
    pytest.param(write_cut_short_coverage, id="a coverage file cut short"),
]


def files_with_node_ids(raw: coverage_at_m.RawCoverage) -> dict[str, frozenset[str]]:
    """raw.nodes_by_file, without the files that no node id has a line in.

    The data model does not say whether nodes_by_file lists those files, with
    no node id, so the tests take either.
    """
    return {path: node_ids for path, node_ids in raw.nodes_by_file.items() if node_ids}


def raw_coverage(
    nodes_by_file: dict[str, frozenset[str]], import_only_files: frozenset[str]
) -> coverage_at_m.RawCoverage:
    """Coverage as read_coverage gives it, with a shared line.

    evaluate builds no matrix from coverage with no shared line: it rejects it.
    """
    return coverage_at_m.RawCoverage(
        nodes_by_file=nodes_by_file,
        import_only_files=import_only_files,
        has_shared_line=True,
    )


def rejection(path: str) -> tuple[str, str, str, int | None]:
    """The reason, input, subject and line number of what read_coverage raises."""
    with pytest.raises(messages.Rejected) as caught:
        coverage_at_m.read_coverage(path)
    error = caught.value
    return error.reason, error.input_name, error.subject, error.line_number


@contextlib.contextmanager
def fails_if_it_blocks() -> Generator[None]:
    """Stop with BlockedError a call that blocks, so that the test fails.

    Opening a FIFO for reading waits until something opens it for writing,
    which nothing does here: without the alarm, the test would hang.
    """

    def interrupt(_signal_number: int, _frame: FrameType | None) -> None:
        raise BlockedError

    previous = signal.signal(signal.SIGALRM, interrupt)
    signal.alarm(BLOCKING_SECONDS)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


@pytest.fixture
def coverage_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The file that COVERAGE names, with tmp_path as the working directory.

    Nothing is there yet: each test puts there what it needs.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ci").mkdir()
    return tmp_path / "ci" / "m.coverage"


# Test contexts


@pytest.mark.parametrize(
    ("context", "node_id"),
    [
        pytest.param(f"{TEST_VAT}|setup", TEST_VAT, id="setup"),
        pytest.param(f"{TEST_VAT}|run", TEST_VAT, id="run, the call"),
        pytest.param(f"{TEST_VAT}|teardown", TEST_VAT, id="teardown"),
        pytest.param(
            "tests/test_tax.py::TestVat::test_rate[es-0.21]|run",
            "tests/test_tax.py::TestVat::test_rate[es-0.21]",
            id="a class and parameters",
        ),
        pytest.param(
            "tests/test_tax.py::test_odd[a|b]|run",
            "tests/test_tax.py::test_odd[a|b]",
            id="a node id with a |, the SPEC's example",
        ),
        pytest.param(
            "tests/test_tax.py::test_odd[a|run]|teardown",
            "tests/test_tax.py::test_odd[a|run]",
            id="a node id that holds |run",
        ),
        pytest.param(
            NEWLINE_NODE_ID + "|run", NEWLINE_NODE_ID, id="a node id with a newline"
        ),
    ],
)
def test_a_test_context_is_split_at_its_last_bar_into_its_node_id(
    context: str, node_id: str
) -> None:
    assert coverage_at_m.node_id_of(context) == node_id


@pytest.mark.parametrize(
    "context",
    [
        *OTHER_CONTEXTS,
        pytest.param(TEST_VAT, id="a node id with no phase"),
        pytest.param("tests/test_tax.py::test_odd[a|run]", id="|run inside a node id"),
        pytest.param("run", id="a phase with no bar"),
    ],
)
def test_any_other_context_is_outside_any_test(context: str) -> None:
    assert coverage_at_m.node_id_of(context) is None


# Reading the coverage file


@pytest.mark.parametrize("measurement", MEASUREMENTS)
def test_reading_the_fixtures_coverage_gives_each_files_node_ids(
    measurement: str, coverage_file: Path
) -> None:
    lines = recorded_under(RUNNER_ROOT, FIXTURE_LINES)
    write_coverage(coverage_file, lines, measurement=measurement)

    raw = coverage_at_m.read_coverage(COVERAGE)

    assert files_with_node_ids(raw) == FIXTURE_NODES_BY_FILE
    assert raw.import_only_files == FIXTURE_IMPORT_ONLY_FILES
    assert raw.has_shared_line is True


@pytest.mark.parametrize(
    ("context", "node_id"),
    [
        pytest.param(f"{TEST_TOTAL}|setup", TEST_TOTAL, id="setup"),
        pytest.param(f"{TEST_TOTAL}|run", TEST_TOTAL, id="run, the call"),
        pytest.param(f"{TEST_TOTAL}|teardown", TEST_TOTAL, id="teardown"),
        pytest.param(
            "tests/test_tax.py::test_odd[a|b]|run",
            "tests/test_tax.py::test_odd[a|b]",
            id="a node id with a |",
        ),
    ],
)
def test_a_line_recorded_in_a_test_context_counts_for_its_node_id(
    context: str, node_id: str, coverage_file: Path
) -> None:
    write_coverage(coverage_file, {context: {RUNNER_ROOT + DB: [2]}})

    raw = coverage_at_m.read_coverage(COVERAGE)

    assert files_with_node_ids(raw) == {RUNNER_ROOT + DB: frozenset({node_id})}
    assert raw.import_only_files == frozenset[str]()


@pytest.mark.parametrize("context", OTHER_CONTEXTS)
def test_a_context_outside_any_test_adds_no_node_id(
    context: str, coverage_file: Path
) -> None:
    lines = {context: {TAX: [1, 3]}, f"{TEST_VAT}|run": {TAX: [3, 4]}}
    write_coverage(coverage_file, recorded_under(RUNNER_ROOT, lines))

    raw = coverage_at_m.read_coverage(COVERAGE)

    assert files_with_node_ids(raw) == {RUNNER_ROOT + TAX: frozenset({TEST_VAT})}
    assert raw.import_only_files == frozenset[str]()


@pytest.mark.parametrize("context", OTHER_CONTEXTS)
def test_a_file_whose_lines_were_all_recorded_outside_any_test_is_import_only(
    context: str, coverage_file: Path
) -> None:
    lines = {context: {CONSTANTS: [1, 2]}, f"{TEST_VAT}|run": {TAX: [3]}}
    write_coverage(coverage_file, recorded_under(RUNNER_ROOT, lines))

    raw = coverage_at_m.read_coverage(COVERAGE)

    assert files_with_node_ids(raw) == {RUNNER_ROOT + TAX: frozenset({TEST_VAT})}
    assert raw.import_only_files == frozenset({RUNNER_ROOT + CONSTANTS})


def test_coverage_recorded_without_test_contexts_has_only_import_only_files(
    coverage_file: Path,
) -> None:
    # Without --cov-context=test, coverage records every line in the empty
    # context. Reading it rejects nothing: no-shared-lines comes later, after
    # the ancestry (How a run goes, step 3).
    lines = {"": {TAX: [1, 2, 3], PRICING: [1, 2]}}
    write_coverage(coverage_file, recorded_under(RUNNER_ROOT, lines))

    raw = coverage_at_m.read_coverage(COVERAGE)

    assert files_with_node_ids(raw) == {}
    assert raw.import_only_files == frozenset(
        {RUNNER_ROOT + TAX, RUNNER_ROOT + PRICING}
    )
    assert raw.has_shared_line is False


def test_a_file_that_lists_measured_files_with_no_line_is_a_coverage_data_file(
    coverage_file: Path,
) -> None:
    write_coverage(
        coverage_file, {"": {}}, files_with_no_line=(RUNNER_ROOT + NEVER_RAN,)
    )

    raw = coverage_at_m.read_coverage(COVERAGE)

    assert files_with_node_ids(raw) == {}
    assert raw.import_only_files == frozenset[str]()
    assert raw.has_shared_line is False


def test_a_coverage_file_that_may_only_be_read_is_read(coverage_file: Path) -> None:
    # D-002: what coverage writes goes to the reader's private copy.
    write_fixture_coverage(coverage_file)
    coverage_file.chmod(0o444)

    raw = coverage_at_m.read_coverage(COVERAGE)

    assert files_with_node_ids(raw) == FIXTURE_NODES_BY_FILE
    assert raw.import_only_files == FIXTURE_IMPORT_ONLY_FILES
    assert raw.has_shared_line is True


# Shared lines


@pytest.mark.parametrize("lines", SHARED_LINES)
def test_a_line_recorded_for_two_node_ids_or_more_is_shared(
    lines: LinesByContext, coverage_file: Path
) -> None:
    write_coverage(coverage_file, recorded_under(RUNNER_ROOT, lines))

    assert coverage_at_m.read_coverage(COVERAGE).has_shared_line is True


@pytest.mark.parametrize("lines", UNSHARED_LINES)
def test_no_line_is_shared_if_each_was_recorded_for_one_node_id_at_most(
    lines: LinesByContext, coverage_file: Path
) -> None:
    write_coverage(coverage_file, recorded_under(RUNNER_ROOT, lines))

    assert coverage_at_m.read_coverage(COVERAGE).has_shared_line is False


def test_coverage_with_no_shared_line_is_read_and_not_rejected(
    coverage_file: Path,
) -> None:
    # The fixture's coverage as the sysmon core leaves it. no-shared-lines
    # comes later, after the ancestry (How a run goes, step 3).
    write_coverage(coverage_file, recorded_under(RUNNER_ROOT, SYSMON_LINES))

    raw = coverage_at_m.read_coverage(COVERAGE)

    assert files_with_node_ids(raw) == FIXTURE_NODES_BY_FILE
    assert raw.import_only_files == FIXTURE_IMPORT_ONLY_FILES
    assert raw.has_shared_line is False


# Coverage files that cannot be used


@pytest.mark.usefixtures("coverage_file")
def test_k8_a_missing_coverage_file_cannot_be_used() -> None:
    # Nothing is at the path that COVERAGE names.
    assert rejection(COVERAGE) == UNUSABLE


@pytest.mark.parametrize(
    "mode", [pytest.param(0o644, id="writable"), pytest.param(0o444, id="read-only")]
)
def test_k14_an_empty_coverage_file_cannot_be_used_and_stays_0_bytes_long(
    mode: int, coverage_file: Path
) -> None:
    coverage_file.write_bytes(b"")
    coverage_file.chmod(mode)

    assert rejection(COVERAGE) == UNUSABLE
    assert coverage_file.stat().st_size == 0


@pytest.mark.parametrize("write", NOT_COVERAGE_DATA)
def test_k8_a_file_that_is_not_a_coverage_data_file_cannot_be_used(
    write: Callable[[Path], None], coverage_file: Path
) -> None:
    write(coverage_file)

    assert rejection(COVERAGE) == UNUSABLE


def test_k8_a_directory_cannot_be_read(coverage_file: Path) -> None:
    coverage_file.mkdir()

    assert rejection(COVERAGE) == UNUSABLE


def test_k8_a_coverage_file_the_tool_is_not_allowed_to_read_cannot_be_read(
    coverage_file: Path,
) -> None:
    write_fixture_coverage(coverage_file)
    coverage_file.chmod(0)
    if os.access(coverage_file, os.R_OK):
        pytest.skip("this user reads a file whatever its mode, as root does")

    assert rejection(COVERAGE) == UNUSABLE


def test_k8_a_fifo_cannot_be_read_and_reading_it_does_not_block(
    coverage_file: Path,
) -> None:
    os.mkfifo(coverage_file)

    with fails_if_it_blocks():
        found = rejection(COVERAGE)

    assert found == UNUSABLE


# The coverage file, byte for byte


@pytest.mark.parametrize(
    "write",
    [
        pytest.param(write_fixture_coverage, id="K13, the fixture's coverage"),
        pytest.param(write_empty_file, id="K14, empty"),
        *NOT_COVERAGE_DATA,
    ],
)
def test_reading_leaves_the_coverage_file_byte_for_byte_as_it_was(
    write: Callable[[Path], None], coverage_file: Path
) -> None:
    write(coverage_file)
    data = coverage_file.read_bytes()
    os.utime(coverage_file, ns=(0, 0))  # an old time, which any write would replace

    with contextlib.suppress(messages.Rejected):
        coverage_at_m.read_coverage(COVERAGE)

    assert coverage_file.read_bytes() == data
    assert coverage_file.stat().st_mtime_ns == 0


# The matrix


def test_k1_the_fixtures_coverage_maps_to_the_fixtures_rows() -> None:
    raw = raw_coverage(FIXTURE_NODES_BY_FILE, FIXTURE_IMPORT_ONLY_FILES)

    matrix = coverage_at_m.build_matrix(raw, FIXTURE_TREE)

    assert matrix.rows["tests/test_report.py::test_render"] == frozenset(
        {"src/shop/pricing.py", "src/shop/report.py"}
    )
    assert matrix == FIXTURE_MATRIX


@pytest.mark.parametrize(
    ("recorded", "tree", "row"),
    [
        pytest.param(TAX, FIXTURE_TREE, frozenset({TAX}), id="equal to a tree path"),
        pytest.param(
            "/runner/work/shop/src/shop/tax.py",
            FIXTURE_TREE,
            frozenset({"src/shop/tax.py"}),
            id="under another checkout root (Edge 4)",
        ),
        pytest.param(
            "/runner/work/shop/src/shop/tax.py",
            frozenset({"tax.py", "shop/tax.py", "src/shop/tax.py"}),
            frozenset({"src/shop/tax.py"}),
            id="the longest of the tree paths it ends with",
        ),
        pytest.param(
            "/runner/work/shop/tax.py",
            frozenset({"hop/tax.py", "tax.py"}),
            frozenset({"tax.py"}),
            id="ends with a tree path only right after a /",
        ),
        pytest.param(
            "/runner/work/shop/src/shop/vat_tax.py",
            frozenset({"tax.py"}),
            frozenset[str](),
            id="ends with a tree path, but not right after a /",
        ),
        pytest.param(
            "/runner/work/shop/src/shop/Tax.py",
            FIXTURE_TREE,
            frozenset[str](),
            id="compared case-sensitively",
        ),
        pytest.param(
            "/runner/work/shop/src/shop/tarifa año.py",
            FIXTURE_TREE | {"src/shop/tarifa año.py"},
            frozenset({"src/shop/tarifa año.py"}),
            id="a space and a letter that is not ASCII",
        ),
        pytest.param(
            OUTSIDE, FIXTURE_TREE, frozenset[str](), id="outside the repository"
        ),
    ],
)
def test_a_recorded_file_maps_to_the_longest_tree_path_it_ends_with_after_a_slash(
    recorded: str, tree: frozenset[str], row: frozenset[str]
) -> None:
    raw = raw_coverage({recorded: frozenset({TEST_VAT})}, frozenset())

    matrix = coverage_at_m.build_matrix(raw, tree)

    assert matrix.rows == {TEST_VAT: row}
    assert matrix.import_only == frozenset[str]()


def test_a_file_outside_the_repository_is_in_no_row() -> None:
    nodes_by_file = {
        RUNNER_ROOT + TAX: frozenset({TEST_VAT}),
        OUTSIDE: frozenset({TEST_VAT}),
    }

    matrix = coverage_at_m.build_matrix(
        raw_coverage(nodes_by_file, frozenset()), FIXTURE_TREE
    )

    assert matrix.rows == {TEST_VAT: frozenset({TAX})}


def test_a_node_id_with_lines_only_outside_the_repository_keeps_an_empty_row() -> None:
    # Matrix.rows keeps empty rows: such a node id still counts among the node
    # ids of its pair.
    nodes_by_file = {
        RUNNER_ROOT + TAX: frozenset({TEST_VAT}),
        OUTSIDE: frozenset({TEST_VAT, TEST_CREATE}),
    }

    matrix = coverage_at_m.build_matrix(
        raw_coverage(nodes_by_file, frozenset()), FIXTURE_TREE
    )

    assert matrix.rows == {TEST_VAT: frozenset({TAX}), TEST_CREATE: frozenset[str]()}


def test_an_import_only_file_maps_to_its_tree_path() -> None:
    raw = raw_coverage(
        {RUNNER_ROOT + TAX: frozenset({TEST_VAT})},
        frozenset({RUNNER_ROOT + CONSTANTS}),
    )

    matrix = coverage_at_m.build_matrix(raw, FIXTURE_TREE)

    assert matrix == coverage_at_m.Matrix(
        rows={TEST_VAT: frozenset({TAX})}, import_only=frozenset({CONSTANTS})
    )


def test_an_import_only_file_outside_the_repository_is_not_import_only() -> None:
    raw = raw_coverage({RUNNER_ROOT + TAX: frozenset({TEST_VAT})}, frozenset({OUTSIDE}))

    matrix = coverage_at_m.build_matrix(raw, FIXTURE_TREE)

    assert matrix.import_only == frozenset[str]()


def test_a_recorded_file_with_no_node_id_is_in_no_row_and_not_import_only() -> None:
    # A measured file in which no line was recorded, if nodes_by_file lists it.
    nodes_by_file: dict[str, frozenset[str]] = {
        RUNNER_ROOT + NEVER_RAN: frozenset(),
        RUNNER_ROOT + TAX: frozenset({TEST_VAT}),
    }

    matrix = coverage_at_m.build_matrix(
        raw_coverage(nodes_by_file, frozenset()), FIXTURE_TREE | {NEVER_RAN}
    )

    assert matrix == coverage_at_m.Matrix(
        rows={TEST_VAT: frozenset({TAX})}, import_only=frozenset()
    )


@pytest.mark.parametrize(
    ("in_a_row", "import_only"),
    [
        pytest.param(RUNNER_ROOT + TAX, TAX, id="the absolute path in a row"),
        pytest.param(TAX, RUNNER_ROOT + TAX, id="the relative path in a row"),
    ],
)
def test_a_repository_file_in_a_row_is_not_import_only_through_another_path(
    in_a_row: str, import_only: str
) -> None:
    # Two recorded paths map to src/shop/tax.py. Not all of its lines were
    # recorded outside any test, so the repository file is not import-only.
    raw = raw_coverage({in_a_row: frozenset({TEST_VAT})}, frozenset({import_only}))

    matrix = coverage_at_m.build_matrix(raw, FIXTURE_TREE)

    assert matrix == coverage_at_m.Matrix(
        rows={TEST_VAT: frozenset({TAX})}, import_only=frozenset()
    )


# From the coverage file to the matrix


@pytest.mark.parametrize("measurement", MEASUREMENTS)
@pytest.mark.parametrize("root", ROOTS)
def test_k1_the_row_of_test_render_is_pricing_and_report(
    root: str, measurement: str, coverage_file: Path
) -> None:
    lines = recorded_under(root, FIXTURE_LINES)
    write_coverage(coverage_file, lines, measurement=measurement)

    raw = coverage_at_m.read_coverage(COVERAGE)
    matrix = coverage_at_m.build_matrix(raw, FIXTURE_TREE)

    # The node id and the row of K1's failed test left out.
    assert matrix.rows["tests/test_report.py::test_render"] == frozenset(
        {"src/shop/pricing.py", "src/shop/report.py"}
    )
    assert matrix == FIXTURE_MATRIX


def test_a_measured_file_with_no_line_is_in_no_row_and_not_import_only(
    coverage_file: Path,
) -> None:
    lines = recorded_under(RUNNER_ROOT, FIXTURE_LINES)
    write_coverage(coverage_file, lines, files_with_no_line=(RUNNER_ROOT + NEVER_RAN,))

    raw = coverage_at_m.read_coverage(COVERAGE)
    matrix = coverage_at_m.build_matrix(raw, FIXTURE_TREE | {NEVER_RAN})

    assert matrix == FIXTURE_MATRIX


def test_a_test_that_ran_only_files_outside_the_repository_keeps_an_empty_row(
    coverage_file: Path,
) -> None:
    lines = recorded_under(RUNNER_ROOT, FIXTURE_LINES)
    lines["tests/test_tax.py::test_rounding|run"] = {OUTSIDE: [5]}
    write_coverage(coverage_file, lines)

    raw = coverage_at_m.read_coverage(COVERAGE)
    matrix = coverage_at_m.build_matrix(raw, FIXTURE_TREE)

    assert matrix.rows == {
        **FIXTURE_MATRIX.rows,
        "tests/test_tax.py::test_rounding": frozenset[str](),
    }
    assert matrix.import_only == FIXTURE_MATRIX.import_only
