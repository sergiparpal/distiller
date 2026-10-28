import contextlib
import os
import re
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

import coverage
import pytest

from distiller import evaluate

# Each test lays out one run's inputs in tmp_path, its working directory, with
# one input that cannot be used, evaluates the run against a git repository
# that the module builds once, and watches the evaluation from outside: what it
# returns, what it prints, what the record file holds after, and what the
# inputs hold after. The tests call evaluate.run, so that an exception it
# raises reaches the test: cli would turn it into exit 1 with nothing appended.
# Only the tests of the exit code that the CI step sees run python -m
# distiller. The repository, the coverage at M and K1's JUnit file are those of
# tests/test_evaluate.py, so that K1's line and its commit ids hold here too;
# the history adds a branch that shares no history with H.
#
# Where the SPEC leaves the rejections open, these tests follow the answers
# given in task 14's tests phase, 2026-10-28: a run whose checkout is not a git
# checkout, or does not exist, has H as given in its key, since H names no
# commit there; a --checkout that does not exist, or that is a file, is
# unusable-input with checkout; such a run expects checkout although its H, its
# base and M cannot be resolved either, as K8 says; a rejection prints nothing
# on stdout; HEAD@{99}, for which git exits with 128 rather than 1, names no
# commit; an input left as it was keeps its kind, permissions, size,
# modification time and, if it is a regular file that can be read, its bytes;
# and a message is checked only for what it names and for what it must not
# quote. The record file is empty, 0 bytes long, unless a test says otherwise.

# The real git, found before any test changes PATH, and the tool's source.
GIT = shutil.which("git") or "git"
SRC = Path(__file__).resolve().parent.parent / "src"

# How long an evaluation may run before fails_if_it_blocks stops it, and how
# long python -m distiller may run.
BLOCKING_SECONDS = 10
PROCESS_SECONDS = 60

# Every commit is made by this author at this time, so that the module builds
# the same commit ids each time it runs.
AUTHOR = "Distiller Tests"
EMAIL = "tests@distiller.invalid"
COMMIT_DATE = "2026-10-10T12:00:00+00:00"

# The fixture's commits, as tests/test_evaluate.py writes them: <H>, pull
# request 7's head, the merge-base of B and H, and M. And <sha>, the SHA-256 of
# K1's JUnit file.
HEAD = "f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f"
MERGE_BASE = "65269ed7f8ecfbb07005af16444ae310a68d5863"
M = "6a174f7d9ac42221c89969c7aa68d12de15942f0"
K1_SHA256 = "402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec"

# The inputs as the command line gives them, from the working directory: H as
# its branch, the base as a remote-tracking branch and M as its first 12
# digits. A message names each one exactly so, ./ included.
HEAD_AS_GIVEN = "pr-7"
BASE = "origin/main"
M_AS_GIVEN = M[:12]
COVERAGE = "./ci/m.coverage"
JUNIT = "./ci/junit.xml"
RERUN = "./ci/rerun.xml"
FLOOR_CONFIG = "./ci/floor.txt"
RECORDS = "./ci/records.jsonl"

# The input files, which no evaluation may change.
INPUT_FILES = (COVERAGE, JUNIT, RERUN, FLOOR_CONFIG)

# A text that files of the runs hold where a message that quoted them would
# show it.
CANARY = "canary"

# The fixture's tests, by node id.
TEST_TOTAL = "tests/test_pricing.py::test_total"
TEST_VAT = "tests/test_tax.py::test_vat"
TEST_RENDER = "tests/test_report.py::test_render"
TEST_CREATE = "tests/api/test_orders.py::test_create"

# The fixture's files, by their paths from the repository root.
PRICING = "src/shop/pricing.py"
TAX = "src/shop/tax.py"
DB = "src/shop/db.py"
REPORT = "src/shop/report.py"
ORDERS = "src/shop/orders.py"
CONSTANTS = "src/shop/constants.py"
INVOICE = "templates/invoice.html"


# The repository

# M's tree, as tests/test_evaluate.py writes it.
FILES_AT_M = {
    "README.md": "A shop.\n",
    "uv.lock": "version = 1\n",
    PRICING: "TOTAL = 0\n",
    TAX: "RATE = 21\n",
    DB: "URL = 'sqlite://'\n",
    REPORT: "TITLE = 'Sales'\n",
    ORDERS: "CHANNELS = ['web']\n",
    CONSTANTS: "CURRENCY = 'EUR'\n",
    INVOICE: "<p>Invoice</p>\n",
    "tests/conftest.py": "",
    "tests/api/conftest.py": "",
    "tests/test_pricing.py": "TOTAL = 2\n",
    "tests/test_tax.py": "VAT = 21\n",
    "tests/test_report.py": "RENDER = True\n",
    "tests/api/test_orders.py": "CREATE = True\n",
}


@dataclass(frozen=True)
class Commits:
    """The commits of the history that K1's line holds."""

    m: str
    merge_base: str
    head: str  # pr-7's head, H


FIXTURE_COMMITS = Commits(m=M, merge_base=MERGE_BASE, head=HEAD)


@dataclass(frozen=True)
class Builder:
    """Builds the history in checkout, running git with environment."""

    checkout: Path
    environment: dict[str, str]

    def git(self, *arguments: str) -> str:
        result = subprocess.run(  # noqa: S603
            [GIT, "-C", str(self.checkout), *arguments],
            capture_output=True,
            check=False,
            env=self.environment,
        )
        assert result.returncode == 0, os.fsdecode(result.stderr)
        return os.fsdecode(result.stdout)

    def commit(self, message: str, files: dict[str, str]) -> str:
        """Write files and commit every change; return the commit's full id."""
        for name, text in files.items():
            path = self.checkout / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "--all")
        self.git("commit", "--quiet", "--message", message)
        return self.git("rev-parse", "HEAD").strip()


def git_settings(home: Path, ceiling: Path) -> dict[str, str]:
    """The variables that keep git to a repository's own configuration, with
    the tests' identity and time.

    git reads no configuration of the user's or the system's, and looks for no
    repository in ceiling or above it. Stop runs these tests with neither the
    user's home directory nor the network, so they rely on neither.
    """
    return {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CEILING_DIRECTORIES": str(ceiling),
        "GIT_AUTHOR_NAME": AUTHOR,
        "GIT_AUTHOR_EMAIL": EMAIL,
        "GIT_AUTHOR_DATE": COMMIT_DATE,
        "GIT_COMMITTER_NAME": AUTHOR,
        "GIT_COMMITTER_EMAIL": EMAIL,
        "GIT_COMMITTER_DATE": COMMIT_DATE,
    }


def environment_for_git(home: Path, ceiling: Path) -> dict[str, str]:
    """This process's environment for the git that builds the history.

    None of the caller's GIT_ variables, which can point git at another
    repository or add configuration of their own, and git_settings.
    """
    environment = {
        name: value for name, value in os.environ.items() if not name.startswith("GIT_")
    }
    environment.update(git_settings(home, ceiling))
    return environment


def build_history(directory: Path) -> Commits:
    """Build the fixture's repository in directory/checkout.

    As in tests/test_evaluate.py, main has M, then R, which modifies
    src/shop/report.py, then MB, the merge-base, which modifies README.md, then
    B, which modifies src/shop/orders.py and which origin/main names; and pr-7
    forks at MB with one commit, H, which modifies templates/invoice.html. The
    branch unrelated has one commit, which shares no history with H.
    """
    home = directory / "home"
    home.mkdir()
    checkout = directory / "checkout"
    checkout.mkdir()
    builder = Builder(checkout, environment_for_git(home, directory))
    builder.git("init", "--quiet", "--initial-branch=main")
    m = builder.commit("Open the shop", FILES_AT_M)
    builder.commit("Rework the report", {REPORT: "TITLE = 'Sales by month'\n"})
    merge_base = builder.commit("Describe the shop", {"README.md": "A small shop.\n"})
    builder.git("switch", "--quiet", "--create", "pr-7", merge_base)
    head = builder.commit(
        "Restyle the invoice", {INVOICE: "<p>Invoice, restyled</p>\n"}
    )
    builder.git("switch", "--quiet", "--orphan", "unrelated")
    builder.commit("Start over", {"NOTES.md": "Elsewhere.\n"})
    builder.git("switch", "--quiet", "main")
    base = builder.commit(
        "Take orders by phone", {ORDERS: "CHANNELS = ['web', 'tel']\n"}
    )
    builder.git("update-ref", "refs/remotes/origin/main", base)
    return Commits(m=m, merge_base=merge_base, head=head)


# The coverage at M

# The checkout where the coverage at M was recorded: coverage records each file
# by its absolute path under it, as it does by default.
RUNNER_ROOT = "/runner/work/shop/"

# The fixture's coverage at M, as tests/test_evaluate.py writes it: line 3 of
# src/shop/tax.py ran for test_total and for test_vat, so the coverage is not
# rejected as no-shared-lines.
COVERAGE_LINES = {
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


def write_coverage_at_m(path: Path) -> None:
    """Write the fixture's coverage at M through coverage's public API."""
    data = coverage.CoverageData(basename=path)
    for context, lines_by_file in COVERAGE_LINES.items():
        data.set_context(context)
        data.add_lines(
            {RUNNER_ROOT + name: numbers for name, numbers in lines_by_file.items()}
        )
    data.write()
    data.close()


@dataclass(frozen=True)
class Shop:
    """The fixture's repository and the bytes of its coverage at M."""

    checkout: Path
    coverage_data: bytes


@pytest.fixture(scope="module")
def shop(tmp_path_factory: pytest.TempPathFactory) -> Shop:
    """The fixture, built once for the module.

    The tool only reads the repository, and each test gets its own copy of
    the coverage file.
    """
    directory = tmp_path_factory.mktemp("shop")
    commits = build_history(directory)
    assert commits == FIXTURE_COMMITS, f"git built other commit ids: {commits}"
    coverage_file = directory / "m.coverage"
    write_coverage_at_m(coverage_file)
    return Shop(
        checkout=directory / "checkout", coverage_data=coverage_file.read_bytes()
    )


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the tool's git as the history was built, from tmp_path."""
    for name in list(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    home = tmp_path / "home"
    home.mkdir()
    for name, value in git_settings(home, tmp_path).items():
        monkeypatch.setenv(name, value)
    monkeypatch.chdir(tmp_path)


# The JUnit files

XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'

# A failure, with the message pytest writes in it.
FAILURE = '<failure message="assert 2 == 3">assert 2 == 3</failure>'

# The testsuite's times, as tests/test_evaluate.py writes them.
SUITE_TIME = "12.871"
RERUN_SUITE_TIME = "5.214"


def case(classname: str, name: str, time: str, *children: str) -> str:
    """A testcase element with these attributes and children."""
    attributes = f'classname="{classname}" name="{name}" time="{time}"'
    return f"<testcase {attributes}>{''.join(children)}</testcase>"


def junit_file(suite_time: str, *testcases: str) -> bytes:
    """A JUnit file as pytest writes it, around these test cases."""
    failures = sum("<failure" in testcase for testcase in testcases)
    errors = sum("<error" in testcase for testcase in testcases)
    suite = (
        f'<testsuite name="pytest" errors="{errors}" failures="{failures}" '
        f'skipped="0" tests="{len(testcases)}" time="{suite_time}" '
        'timestamp="2026-10-10T12:00:00.000000+00:00" hostname="runner">'
    )
    cases = "".join(testcases)
    text = f'<testsuites name="pytest tests">{suite}{cases}</testsuite></testsuites>'
    return (XML_DECLARATION + text).encode()


# The fixture's tests as pytest writes them, with their JUnit times.
TOTAL_PASSED = case("tests.test_pricing", "test_total", "2.000")
VAT_PASSED = case("tests.test_tax", "test_vat", "1.000")
RENDER_PASSED = case("tests.test_report", "test_render", "5.000")
RENDER_FAILED = case("tests.test_report", "test_render", "5.000", FAILURE)
CREATE_PASSED = case("tests.api.test_orders", "test_create", "4.000")

# K1's full run, in which test_render failed, and K2's rerun file, in which it
# passed.
K1_JUNIT = junit_file(
    SUITE_TIME, TOTAL_PASSED, VAT_PASSED, RENDER_FAILED, CREATE_PASSED
)
K2_RERUN = junit_file(RERUN_SUITE_TIME, RENDER_PASSED)

# Test cases that cannot be used: one with no time, named after the canary;
# test_render's with no time; test_vat's with no time, with captured output
# that holds the canary; and pytest's internal error, whose text is the canary.
NO_TIME_CANARY = '<testcase classname="tests.test_canary" name="test_canary" />'
RENDER_NO_TIME = '<testcase classname="tests.test_report" name="test_render" />'
VAT_NO_TIME = (
    '<testcase classname="tests.test_tax" name="test_vat">'
    "<system-out>canary</system-out></testcase>"
)
INTERNAL_ERROR = case(
    "pytest", "internal", "0.000", '<error message="internal error">canary</error>'
)

# A file that is not well-formed XML: its root element is never closed.
MALFORMED_XML = (XML_DECLARATION + '<testsuites name="canary">').encode()

# Full runs that cannot be used: K1's with a test case that has no time, and
# one in which pytest failed itself after two tests.
NO_TIME_JUNIT = junit_file(
    SUITE_TIME,
    TOTAL_PASSED,
    VAT_PASSED,
    RENDER_FAILED,
    CREATE_PASSED,
    NO_TIME_CANARY,
)
INTERNAL_ERROR_JUNIT = junit_file(SUITE_TIME, TOTAL_PASSED, VAT_PASSED, INTERNAL_ERROR)

# Rerun files that cannot be used, next to K1's full run, in which only
# test_render failed: test_render's test case with no time; test_render passed,
# then pytest's internal error; and, for Edge 18, test_render passed and
# test_vat, which did not fail in the full run, has no time.
RENDER_NO_TIME_RERUN = junit_file(RERUN_SUITE_TIME, RENDER_NO_TIME)
INTERNAL_ERROR_RERUN = junit_file(RERUN_SUITE_TIME, RENDER_PASSED, INTERNAL_ERROR)
EDGE_18_RERUN = junit_file(RERUN_SUITE_TIME, RENDER_PASSED, VAT_NO_TIME)


# The other inputs

# A coverage file that is text, not a coverage data file.
COVERAGE_TEXT = b"canary: not a coverage data file\n"

# A floor configuration that can be used, and three that cannot: one that is
# not valid UTF-8, Edge 21's **.lock at line 3, and an invalid pattern, which ?
# makes invalid, at line 2.
VALID_FLOOR = b"data/**\n"
NOT_UTF_8_FLOOR = b"canary/\xff.csv\n"
EDGE_21_FLOOR = b"# Paths that no test covers\ndata/**\n**.lock\n"
CANARY_PATTERN_FLOOR = b"data/**\ncanary/?.csv\n"


# What a test can put at an input's path once the inputs are laid out.


def nothing(path: Path) -> None:
    path.unlink()


def a_directory(path: Path) -> None:
    path.unlink(missing_ok=True)
    path.mkdir()


def a_fifo(path: Path) -> None:
    # Opening it for reading would wait until something opens it for writing.
    path.unlink()
    os.mkfifo(path)


def a_file_it_may_not_read(path: Path) -> None:
    path.chmod(0)
    if os.access(path, os.R_OK):
        pytest.skip("this user reads a file whatever its mode, as root does")


def a_file(path: Path) -> None:
    path.write_text("Not a checkout.\n", encoding="utf-8")


def an_sqlite_database_of_something_else(path: Path) -> None:
    # None of its tables is named like one of coverage's.
    path.unlink()
    with contextlib.closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, total TEXT)")
        connection.execute("INSERT INTO orders (total) VALUES ('12.00')")
        connection.commit()


# The runs


@dataclass(frozen=True)
class Run:
    """A run's inputs, as they differ from K1's run.

    replaced names a path, from the working directory, and what is put there
    once the inputs are laid out.
    """

    pr: int = 7
    head: str = HEAD_AS_GIVEN
    base: str = BASE
    coverage_commit: str = M_AS_GIVEN
    checkout: str | None = None  # None: the fixture's checkout
    coverage: bytes | None = None  # None: the fixture's coverage at M
    junit: bytes = K1_JUNIT
    rerun: bytes | None = None  # None: no --rerun
    floor: bytes | None = None  # None: no --floor-config
    replaced: tuple[str, Callable[[Path], None]] | None = None


# K1's run: a diff that modifies only templates/invoice.html, a full run of
# pull request 7 in which test_render failed, and no rerun file.
K1_RUN = Run()

# K8's and K10's run: K1's with no coverage file, in pull request 7 and in
# pull request 12.
MISSING_COVERAGE_RUN = Run(replaced=(COVERAGE, nothing))
MISSING_COVERAGE_FOR_PR_12 = Run(pr=12, replaced=(COVERAGE, nothing))

# K1's run with no full-run JUnit file, and with an H that names no commit.
MISSING_JUNIT_RUN = Run(replaced=(JUNIT, nothing))
NO_SUCH_HEAD_RUN = Run(head="no-such-head")


def record_file(directory: Path) -> Path:
    """The record file that RECORDS names, from directory."""
    return directory / RECORDS


def lay_out(
    run: Run, shop: Shop, directory: Path, records_before: bytes | None
) -> None:
    """Write run's inputs where the command line names them, from directory,
    and a record file that holds records_before, or none if it is None."""
    (directory / "ci").mkdir()
    coverage_data = shop.coverage_data if run.coverage is None else run.coverage
    (directory / COVERAGE).write_bytes(coverage_data)
    (directory / JUNIT).write_bytes(run.junit)
    if run.rerun is not None:
        (directory / RERUN).write_bytes(run.rerun)
    if run.floor is not None:
        (directory / FLOOR_CONFIG).write_bytes(run.floor)
    if records_before is not None:
        record_file(directory).write_bytes(records_before)
    if run.replaced is not None:
        path, make = run.replaced
        make(directory / path)


def run_args(run: Run, shop: Shop) -> evaluate.RunArgs:
    """run's inputs as cli gives them to evaluate.run."""
    return evaluate.RunArgs(
        pr=run.pr,
        head=run.head,
        base=run.base,
        coverage=COVERAGE,
        coverage_commit=run.coverage_commit,
        junit=JUNIT,
        rerun=RERUN if run.rerun is not None else None,
        rootdir="",
        floor_config=FLOOR_CONFIG if run.floor is not None else None,
        records=RECORDS,
        checkout=run.checkout if run.checkout is not None else str(shop.checkout),
    )


class BlockedError(BaseException):
    """A call was still running when the alarm went off.

    A BaseException, so that no `except Exception` in the code under test
    catches it.
    """


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


def evaluate_run(run: Run, shop: Shop) -> int:
    """What evaluate.run returns for run's inputs, laid out in the working
    directory; stopped if it blocks."""
    with fails_if_it_blocks():
        return evaluate.run(run_args(run, shop))


def evaluated(
    run: Run, records_before: bytes | None, shop: Shop, directory: Path
) -> int:
    """Evaluate run from directory with a record file that holds records_before,
    or with no record file if it is None; return what evaluate.run returns."""
    lay_out(run, shop, directory, records_before)
    return evaluate_run(run, shop)


# An input file's kind and permissions, size, modification time and, if it is
# a regular file that the tests can read, bytes: a FIFO is never opened.
FileState = tuple[int, int, int, bytes | None]


def state_of_inputs(directory: Path) -> dict[str, FileState]:
    """The state of each input file at its path from directory, if any."""
    states: dict[str, FileState] = {}
    for name in INPUT_FILES:
        path = directory / name
        if not path.exists():
            continue
        status = path.stat()
        data = None
        if stat.S_ISREG(status.st_mode) and os.access(path, os.R_OK):
            data = path.read_bytes()
        states[name] = (status.st_mode, status.st_size, status.st_mtime_ns, data)
    return states


def make_inputs_old(directory: Path) -> None:
    """Give each input file there is an old time, which any write would replace."""
    for name in INPUT_FILES:
        path = directory / name
        if path.exists():
            os.utime(path, ns=(0, 0))


def numbers_in(text: str) -> list[int]:
    """Every run of ASCII digits in text, as a number."""
    return [int(digits) for digits in re.findall(r"[0-9]+", text)]


# The lines

# The rejected runs' lines, as the prose on records defines them: each is pull
# request 7's, rejected with unusable-input, and holds HEAD for <H> and
# K1_SHA256 for <sha>, unless its comment says otherwise.

# K8, checkout: in a directory that is not a git checkout, H names no commit,
# so the key holds it as given.
CHECKOUT_LINE = (
    b'{"format":1,"head":"pr-7",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"checkout"}\n'
)

# K8, head: an H that names no commit, which the key holds as given.
NO_SUCH_HEAD_LINE = (
    b'{"format":1,"head":"no-such-head",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"head"}\n'
)
REFLOG_HEAD_LINE = (
    b'{"format":1,"head":"HEAD@{99}",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"head"}\n'
)
OPTION_HEAD_LINE = (
    b'{"format":1,"head":"--all",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"head"}\n'
)

# K8, base.
BASE_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"base"}\n'
)

# K8, K10 and K14, coverage: the coverage file, or M.
COVERAGE_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"coverage"}\n'
)

# The same rejection in pull request 12.
COVERAGE_LINE_FOR_PR_12 = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":12,"verdict":"rejected","reason":"unusable-input","input":"coverage"}\n'
)

# K8, junit: a full-run JUnit file that is missing or cannot be read, so the
# key has no SHA-256.
NO_JUNIT_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":null,'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"junit"}\n'
)

# K8, junit: full-run JUnit files that can be read but not used, each with the
# SHA-256 of its own bytes: MALFORMED_XML, NO_TIME_JUNIT and
# INTERNAL_ERROR_JUNIT.
MALFORMED_JUNIT_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"682086aca122973c79b9eeb086fe8f28af739e62522f50b7d102877a9e74e47f",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"junit"}\n'
)
NO_TIME_JUNIT_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"d61171e4d5a3bbeadd79f923c377f41c0d61cd58d52b6307114f9bb08dcf533b",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"junit"}\n'
)
INTERNAL_ERROR_JUNIT_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"7ef21137b2a37a7f2f4e5e71dd6a54d6616ad3de1a7d1c02d10e907fdbac8589",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"junit"}\n'
)

# K8, rerun: the key holds the full run's SHA-256, whatever the rerun file
# holds.
RERUN_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"rerun"}\n'
)

# K8, floor.
FLOOR_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"floor"}\n'
)

# Lines that a test writes in the record file before the run.

# K1's line, as tests/test_evaluate.py writes it: K1's run evaluated.
K1_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"missed",'
    b'"merge_base":"65269ed7f8ecfbb07005af16444ae310a68d5863",'
    b'"coverage_commit":"6a174f7d9ac42221c89969c7aa68d12de15942f0",'
    b'"selected_ms":0,"full_ms":12000,'
    b'"tests":4,"unmeasured":0,"tests_with_row":4,"tests_with_row_not_in_run":0,'
    b'"floor_matched":false,"rerun_given":false,'
    b'"not_reproduced":[],'
    b'"failed_left_out":[{"pair":["tests.test_report","test_render"],'
    b'"node_id":"tests/test_report.py::test_render",'
    b'"row":["src/shop/pricing.py","src/shop/report.py"]}],'
    b'"no_column":["templates/invoice.html"],'
    b'"import_only":[]}\n'
)

# K4's line, as tests/test_evaluate.py writes it: the run rejected for another
# reason, with the coverage as its input.
K4_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"coverage-not-ancestor",'
    b'"input":"coverage"}\n'
)

# Another run's rejected record, as tests/test_evaluate.py writes it, in pull
# request 12.
OTHER_RUNS_LINE = (
    b'{"format":1,"head":"0a9b8c7d6e5f40312a3b4c5d6e7f8091a2b3c4d5",'
    b'"junit_sha256":'
    b'"f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d2c3b4a5968778695a4b3c2d1e0f",'
    b'"pr":12,"verdict":"rejected","reason":"unusable-input","input":"coverage"}\n'
)

# COVERAGE_LINE's rejection under the run's head and no SHA-256, as a run with
# no JUnit file and no coverage file would have recorded it.
NO_SHA256_COVERAGE_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":null,'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"coverage"}\n'
)


# K8: the runs with an input that cannot be used


@dataclass(frozen=True)
class Rejection:
    """A run with one input that cannot be used, the line its rejection
    appends, and what its message names: the input's path, or a name as given.

    holds_canary is set when a file of the run holds CANARY, and line_number
    when the message names an invalid floor pattern's line.
    """

    name: str
    run: Run
    line: bytes
    named: str
    holds_canary: bool = False
    line_number: int | None = None


REJECTIONS = [
    Rejection(
        "checkout, a directory that is not a git checkout",
        Run(checkout="./elsewhere", replaced=("./elsewhere", a_directory)),
        CHECKOUT_LINE,
        "./elsewhere",
    ),
    Rejection(
        "checkout, a path that does not exist",
        Run(checkout="./no-such-checkout"),
        CHECKOUT_LINE,
        "./no-such-checkout",
    ),
    Rejection(
        "checkout, a file",
        Run(checkout="./checkout.txt", replaced=("./checkout.txt", a_file)),
        CHECKOUT_LINE,
        "./checkout.txt",
    ),
    Rejection(
        "head, a name of no commit", NO_SUCH_HEAD_RUN, NO_SUCH_HEAD_LINE, "no-such-head"
    ),
    Rejection(
        "head, beyond the reflog, for which git exits with 128",
        Run(head="HEAD@{99}"),
        REFLOG_HEAD_LINE,
        "HEAD@{99}",
    ),
    Rejection(
        "head, an option-like name", Run(head="--all"), OPTION_HEAD_LINE, "--all"
    ),
    Rejection(
        "base, a name of no commit",
        Run(base="origin/no-such-branch"),
        BASE_LINE,
        "origin/no-such-branch",
    ),
    Rejection(
        "base, no common history with H",
        Run(base="unrelated"),
        BASE_LINE,
        "unrelated",
    ),
    Rejection(
        "K10 coverage, a missing file", MISSING_COVERAGE_RUN, COVERAGE_LINE, COVERAGE
    ),
    Rejection(
        "coverage, a directory",
        Run(replaced=(COVERAGE, a_directory)),
        COVERAGE_LINE,
        COVERAGE,
    ),
    Rejection(
        "coverage, a FIFO", Run(replaced=(COVERAGE, a_fifo)), COVERAGE_LINE, COVERAGE
    ),
    Rejection(
        "coverage, a file it may not read",
        Run(replaced=(COVERAGE, a_file_it_may_not_read)),
        COVERAGE_LINE,
        COVERAGE,
    ),
    Rejection("K14 coverage, empty", Run(coverage=b""), COVERAGE_LINE, COVERAGE),
    Rejection(
        "coverage, text",
        Run(coverage=COVERAGE_TEXT),
        COVERAGE_LINE,
        COVERAGE,
        holds_canary=True,
    ),
    Rejection(
        "coverage, an SQLite database of something else",
        Run(replaced=(COVERAGE, an_sqlite_database_of_something_else)),
        COVERAGE_LINE,
        COVERAGE,
    ),
    Rejection(
        "coverage, an M that names no commit",
        Run(coverage_commit="no-such-commit"),
        COVERAGE_LINE,
        "no-such-commit",
    ),
    Rejection("junit, a missing file", MISSING_JUNIT_RUN, NO_JUNIT_LINE, JUNIT),
    Rejection(
        "junit, a directory", Run(replaced=(JUNIT, a_directory)), NO_JUNIT_LINE, JUNIT
    ),
    Rejection("junit, a FIFO", Run(replaced=(JUNIT, a_fifo)), NO_JUNIT_LINE, JUNIT),
    Rejection(
        "junit, a file it may not read",
        Run(replaced=(JUNIT, a_file_it_may_not_read)),
        NO_JUNIT_LINE,
        JUNIT,
    ),
    Rejection(
        "junit, not well-formed",
        Run(junit=MALFORMED_XML),
        MALFORMED_JUNIT_LINE,
        JUNIT,
        holds_canary=True,
    ),
    Rejection(
        "junit, a test case with no time",
        Run(junit=NO_TIME_JUNIT),
        NO_TIME_JUNIT_LINE,
        JUNIT,
        holds_canary=True,
    ),
    Rejection(
        "junit, pytest's internal error",
        Run(junit=INTERNAL_ERROR_JUNIT),
        INTERNAL_ERROR_JUNIT_LINE,
        JUNIT,
        holds_canary=True,
    ),
    Rejection(
        "rerun, a missing file",
        Run(rerun=K2_RERUN, replaced=(RERUN, nothing)),
        RERUN_LINE,
        RERUN,
    ),
    Rejection(
        "rerun, a directory",
        Run(rerun=K2_RERUN, replaced=(RERUN, a_directory)),
        RERUN_LINE,
        RERUN,
    ),
    Rejection(
        "rerun, a FIFO",
        Run(rerun=K2_RERUN, replaced=(RERUN, a_fifo)),
        RERUN_LINE,
        RERUN,
    ),
    Rejection(
        "rerun, a file it may not read",
        Run(rerun=K2_RERUN, replaced=(RERUN, a_file_it_may_not_read)),
        RERUN_LINE,
        RERUN,
    ),
    Rejection(
        "rerun, not well-formed",
        Run(rerun=MALFORMED_XML),
        RERUN_LINE,
        RERUN,
        holds_canary=True,
    ),
    Rejection(
        "rerun, the failed test_render with no time",
        Run(rerun=RENDER_NO_TIME_RERUN),
        RERUN_LINE,
        RERUN,
    ),
    Rejection(
        "Edge 18, rerun, pytest's internal error after test_render passed",
        Run(rerun=INTERNAL_ERROR_RERUN),
        RERUN_LINE,
        RERUN,
        holds_canary=True,
    ),
    Rejection(
        "Edge 18, rerun, test_vat with no time, which did not fail in the full run",
        Run(rerun=EDGE_18_RERUN),
        RERUN_LINE,
        RERUN,
        holds_canary=True,
    ),
    Rejection(
        "floor, a missing file",
        Run(floor=VALID_FLOOR, replaced=(FLOOR_CONFIG, nothing)),
        FLOOR_LINE,
        FLOOR_CONFIG,
    ),
    Rejection(
        "floor, a directory",
        Run(floor=VALID_FLOOR, replaced=(FLOOR_CONFIG, a_directory)),
        FLOOR_LINE,
        FLOOR_CONFIG,
    ),
    Rejection(
        "floor, a FIFO",
        Run(floor=VALID_FLOOR, replaced=(FLOOR_CONFIG, a_fifo)),
        FLOOR_LINE,
        FLOOR_CONFIG,
    ),
    Rejection(
        "floor, a file it may not read",
        Run(floor=VALID_FLOOR, replaced=(FLOOR_CONFIG, a_file_it_may_not_read)),
        FLOOR_LINE,
        FLOOR_CONFIG,
    ),
    Rejection(
        "floor, not valid UTF-8",
        Run(floor=NOT_UTF_8_FLOOR),
        FLOOR_LINE,
        FLOOR_CONFIG,
        holds_canary=True,
    ),
    Rejection(
        "Edge 21, floor, the pattern **.lock at line 3",
        Run(floor=EDGE_21_FLOOR),
        FLOOR_LINE,
        FLOOR_CONFIG,
        line_number=3,
    ),
    Rejection(
        "floor, an invalid pattern at line 2",
        Run(floor=CANARY_PATTERN_FLOOR),
        FLOOR_LINE,
        FLOOR_CONFIG,
        holds_canary=True,
        line_number=2,
    ),
]

# The same runs, with what each test of the table needs.
RUNS = [pytest.param(rejection.run, id=rejection.name) for rejection in REJECTIONS]
RUNS_AND_LINES = [
    pytest.param(rejection.run, rejection.line, id=rejection.name)
    for rejection in REJECTIONS
]
RUNS_AND_NAMES = [
    pytest.param(rejection.run, rejection.named, id=rejection.name)
    for rejection in REJECTIONS
]
RUNS_THAT_HOLD_THE_CANARY = [
    pytest.param(rejection.run, id=rejection.name)
    for rejection in REJECTIONS
    if rejection.holds_canary
]
RUNS_AND_LINE_NUMBERS = [
    pytest.param(rejection.run, rejection.line_number, id=rejection.name)
    for rejection in REJECTIONS
    if rejection.line_number is not None
]


@pytest.mark.parametrize(("run", "line"), RUNS_AND_LINES)
def test_k8_the_rejection_appends_exactly_its_line(
    run: Run, line: bytes, shop: Shop, tmp_path: Path
) -> None:
    evaluated(run, b"", shop, tmp_path)

    assert record_file(tmp_path).read_bytes() == line


@pytest.mark.parametrize("run", RUNS)
def test_k8_a_rejected_run_exits_with_3(run: Run, shop: Shop, tmp_path: Path) -> None:
    assert evaluated(run, b"", shop, tmp_path) == 3


@pytest.mark.parametrize(("run", "named"), RUNS_AND_NAMES)
def test_k8_the_error_names_the_input_that_failed_as_given(
    run: Run,
    named: str,
    shop: Shop,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    capfd.readouterr()  # drop what was written before the evaluation

    evaluated(run, b"", shop, tmp_path)

    assert named in capfd.readouterr().err


@pytest.mark.parametrize("run", RUNS)
def test_a_rejection_prints_nothing_on_stdout(
    run: Run, shop: Shop, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    # Warnings and error messages go to stderr.
    capfd.readouterr()

    evaluated(run, b"", shop, tmp_path)

    assert capfd.readouterr().out == ""


@pytest.mark.parametrize("run", RUNS)
def test_the_inputs_are_left_as_they_were(run: Run, shop: Shop, tmp_path: Path) -> None:
    # Byte for byte, whatever the outcome. A directory or a FIFO keeps its
    # time too: creating a file in it, or writing to it, would change it.
    lay_out(run, shop, tmp_path, b"")
    make_inputs_old(tmp_path)
    before = state_of_inputs(tmp_path)

    evaluate_run(run, shop)

    assert state_of_inputs(tmp_path) == before


@pytest.mark.parametrize("run", RUNS_THAT_HOLD_THE_CANARY)
def test_nothing_the_tool_prints_quotes_what_a_file_holds(
    run: Run, shop: Shop, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()

    evaluated(run, b"", shop, tmp_path)

    output = capfd.readouterr()
    assert CANARY not in output.out + output.err


@pytest.mark.parametrize(("run", "line_number"), RUNS_AND_LINE_NUMBERS)
def test_an_invalid_floor_pattern_is_named_by_its_line_number(
    run: Run,
    line_number: int,
    shop: Shop,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    capfd.readouterr()

    evaluated(run, b"", shop, tmp_path)

    assert line_number in numbers_in(capfd.readouterr().err)


# K10 and K11: a rejected record is appended once


# A record file that already holds the run's rejection, with the same key,
# reason and input: whatever its pr, nothing is appended.
ALREADY_REJECTED = [
    pytest.param(
        MISSING_COVERAGE_RUN,
        COVERAGE_LINE,
        id="K10, the run rejected again for its missing coverage file",
    ),
    pytest.param(
        MISSING_COVERAGE_FOR_PR_12,
        COVERAGE_LINE,
        id="the same rejection recorded for pull request 7",
    ),
    pytest.param(
        MISSING_JUNIT_RUN,
        NO_JUNIT_LINE,
        id="a missing JUnit file, so a key with no SHA-256",
    ),
    pytest.param(
        NO_SUCH_HEAD_RUN,
        NO_SUCH_HEAD_LINE,
        id="an H that names no commit, which the key holds as given",
    ),
]


@pytest.mark.parametrize(("run", "recorded"), ALREADY_REJECTED)
def test_k10_a_rejection_already_recorded_leaves_the_record_file_as_it_was(
    run: Run, recorded: bytes, shop: Shop, tmp_path: Path
) -> None:
    lay_out(run, shop, tmp_path, recorded)
    os.utime(record_file(tmp_path), ns=(0, 0))  # an old time, which a write replaces

    evaluate_run(run, shop)

    assert record_file(tmp_path).read_bytes() == recorded
    assert record_file(tmp_path).stat().st_mtime_ns == 0


def test_k10_the_run_rejected_again_exits_with_3(shop: Shop, tmp_path: Path) -> None:
    assert evaluated(MISSING_COVERAGE_RUN, COVERAGE_LINE, shop, tmp_path) == 3


def test_k10_the_error_names_the_coverage_file_again(
    shop: Shop, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()

    evaluated(MISSING_COVERAGE_RUN, COVERAGE_LINE, shop, tmp_path)

    assert COVERAGE in capfd.readouterr().err


def test_k11_with_its_coverage_file_the_run_is_evaluated_after_its_rejection(
    shop: Shop, tmp_path: Path
) -> None:
    # K11 names no diff or failed test: the run is K1's, which K10 rejected.
    evaluated(K1_RUN, COVERAGE_LINE, shop, tmp_path)

    assert record_file(tmp_path).read_bytes() == COVERAGE_LINE + K1_LINE


def test_k11_the_run_evaluated_with_its_coverage_file_exits_with_0(
    shop: Shop, tmp_path: Path
) -> None:
    assert evaluated(K1_RUN, COVERAGE_LINE, shop, tmp_path) == 0


# A record file that holds a rejection with another key, reason or input: the
# run's rejected record goes after it.
APPENDED_AFTER = [
    pytest.param(
        MISSING_COVERAGE_RUN,
        K4_LINE,
        COVERAGE_LINE,
        id="the run rejected for another reason, with the same input",
    ),
    pytest.param(
        MISSING_COVERAGE_RUN,
        FLOOR_LINE,
        COVERAGE_LINE,
        id="the run rejected for the same reason, with another input",
    ),
    pytest.param(
        MISSING_COVERAGE_FOR_PR_12,
        OTHER_RUNS_LINE,
        COVERAGE_LINE_FOR_PR_12,
        id="another run rejected, and the run in pull request 12",
    ),
    pytest.param(
        MISSING_COVERAGE_RUN,
        NO_SHA256_COVERAGE_LINE,
        COVERAGE_LINE,
        id="the same rejection under a key with no SHA-256",
    ),
]


@pytest.mark.parametrize(("run", "recorded", "line"), APPENDED_AFTER)
def test_a_rejection_with_another_key_reason_or_input_is_appended_after_it(
    run: Run, recorded: bytes, line: bytes, shop: Shop, tmp_path: Path
) -> None:
    evaluated(run, recorded, shop, tmp_path)

    assert record_file(tmp_path).read_bytes() == recorded + line


def test_with_no_record_file_the_rejection_creates_one_that_holds_only_its_line(
    shop: Shop, tmp_path: Path
) -> None:
    evaluated(MISSING_COVERAGE_RUN, None, shop, tmp_path)

    assert record_file(tmp_path).read_bytes() == COVERAGE_LINE


# A run already evaluated: How a run goes, step 2, looks the key up before any
# check, so K1's run, evaluated before, is not rejected for its missing
# coverage file now.


def test_a_run_already_evaluated_is_not_rejected_and_the_record_file_is_left_as_it_was(
    shop: Shop, tmp_path: Path
) -> None:
    lay_out(MISSING_COVERAGE_RUN, shop, tmp_path, K1_LINE)
    os.utime(record_file(tmp_path), ns=(0, 0))

    evaluate_run(MISSING_COVERAGE_RUN, shop)

    assert record_file(tmp_path).read_bytes() == K1_LINE
    assert record_file(tmp_path).stat().st_mtime_ns == 0


def test_a_run_already_evaluated_exits_with_0_whatever_its_inputs(
    shop: Shop, tmp_path: Path
) -> None:
    assert evaluated(MISSING_COVERAGE_RUN, K1_LINE, shop, tmp_path) == 0


# The exit code that the CI step sees: K8's run, with no coverage file, through
# python -m distiller, as tests/test_main.py runs it.


def python_m_distiller(
    shop: Shop, directory: Path
) -> subprocess.CompletedProcess[bytes]:
    """Evaluate K8's run from directory as the CI step does."""
    lay_out(MISSING_COVERAGE_RUN, shop, directory, b"")
    command = [
        sys.executable,
        "-P",
        "-m",
        "distiller",
        "evaluate",
        "--pr",
        "7",
        "--head",
        HEAD_AS_GIVEN,
        "--base",
        BASE,
        "--coverage",
        COVERAGE,
        "--coverage-commit",
        M_AS_GIVEN,
        "--junit",
        JUNIT,
        "--records",
        RECORDS,
        "--checkout",
        str(shop.checkout),
    ]
    return subprocess.run(  # noqa: S603
        command,
        cwd=directory,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        capture_output=True,
        check=False,
        timeout=PROCESS_SECONDS,
    )


def test_k8_python_m_distiller_exits_with_3(shop: Shop, tmp_path: Path) -> None:
    assert python_m_distiller(shop, tmp_path).returncode == 3


def test_k8_python_m_distiller_appends_exactly_the_rejected_line(
    shop: Shop, tmp_path: Path
) -> None:
    python_m_distiller(shop, tmp_path)

    assert record_file(tmp_path).read_bytes() == COVERAGE_LINE


def test_k8_python_m_distiller_names_the_coverage_file(
    shop: Shop, tmp_path: Path
) -> None:
    assert COVERAGE.encode() in python_m_distiller(shop, tmp_path).stderr
