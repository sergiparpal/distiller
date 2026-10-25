import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import coverage
import pytest

from distiller import cli, evaluate

# Each test lays out one run's inputs in tmp_path, its working directory,
# evaluates the run against a git repository that the module builds once, and
# watches the evaluation from outside: what it returns, what it prints, what
# the record file holds after, and what the coverage and JUnit files hold
# after. The tests call evaluate.run, so that an exception it raises reaches
# the test: cli would turn it into exit 1, which some of these tests expect.
# Only the test of a failure that cli reports goes through cli.main.
#
# Where the SPEC leaves the evaluation open, these tests follow the answers
# given in task 13's tests phase, 2026-10-25: an evaluated run prints nothing;
# K1's record file is empty, 0 bytes long, while K13 has none; K3's record
# file holds K1's line, written by the test, which K1 shows is what the
# evaluation writes; a record file that exists but cannot be read is any other
# failure, whatever class of OSError it names; Invariant 1 evaluates twice in
# this process, in two working directories with the same relative paths; an
# evaluated record goes after the lines already in the file; Edge 6 and 7 use
# a pull request that modifies tests/test_tax.py, and K2 K1's diff; and the
# head and M are given as a branch name and an abbreviated commit id, so that
# the record shows them resolved.

# The real git, found before any test changes PATH.
GIT = shutil.which("git") or "git"

# Every commit is made by this author at this time, so that the module builds
# the same commit ids each time it runs.
AUTHOR = "Distiller Tests"
EMAIL = "tests@distiller.invalid"
COMMIT_DATE = "2026-10-10T12:00:00+00:00"

# The fixture's commits that K1's line holds: <H>, pull request 7's head, the
# merge-base of B and H, and M. And <sha>, the SHA-256 of K1's JUnit file.
HEAD = "f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f"
MERGE_BASE = "65269ed7f8ecfbb07005af16444ae310a68d5863"
M = "6a174f7d9ac42221c89969c7aa68d12de15942f0"
K1_SHA256 = "402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec"

# The inputs as the command line gives them, from the working directory. The
# base is a remote-tracking branch, as in a pull request's checkout; H is
# given as its branch and M as its first 12 digits, so that the record shows
# them resolved to full commit ids.
BASE = "origin/main"
M_AS_GIVEN = M[:12]
COVERAGE = "./ci/m.coverage"
JUNIT = "./ci/junit.xml"
RERUN = "./ci/rerun.xml"
RECORDS = "./ci/records.jsonl"

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

# M's tree: every file that the fixture names, and a README.md and a uv.lock.
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

# Each pull request's branch, with the message and the files of its only
# commit, made on the merge-base.
PULL_REQUESTS = {
    "pr-7": ("Restyle the invoice", {INVOICE: "<p>Invoice, restyled</p>\n"}),
    "pr-12": ("Lower the rate", {TAX: "RATE = 10\n"}),
    "pr-31": (
        "Bill in dollars",
        {"uv.lock": "version = 2\n", CONSTANTS: "CURRENCY = 'USD'\n"},
    ),
    "pr-44": ("Rename the VAT test", {"tests/test_tax.py": "VAT_RATE = 21\n"}),
}


@dataclass(frozen=True)
class Commits:
    """The commits of the history that K1's line holds."""

    m: str
    merge_base: str
    head: str  # pr-7's head, H in K1


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

    main has M, then R, which modifies src/shop/report.py, then MB, the
    merge-base, which modifies README.md, then B, which modifies
    src/shop/orders.py and which origin/main names. Each pull request's branch
    forks at MB with one commit: those of PULL_REQUESTS, and pr-58, which
    deletes src/shop/report.py.
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
    heads: dict[str, str] = {}
    for branch, (message, files) in PULL_REQUESTS.items():
        builder.git("switch", "--quiet", "--create", branch, merge_base)
        heads[branch] = builder.commit(message, files)
    builder.git("switch", "--quiet", "--create", "pr-58", merge_base)
    (checkout / REPORT).unlink()
    builder.commit("Drop the sales report", {})  # its only change, the deletion
    builder.git("switch", "--quiet", "main")
    base = builder.commit(
        "Take orders by phone", {ORDERS: "CHANNELS = ['web', 'tel']\n"}
    )
    builder.git("update-ref", "refs/remotes/origin/main", base)
    return Commits(m=m, merge_base=merge_base, head=heads["pr-7"])


# The coverage at M

# The checkout where the coverage at M was recorded: coverage records each file
# by its absolute path under it, as it does by default.
RUNNER_ROOT = "/runner/work/shop/"

# The fixture's coverage at M as pytest-cov records it with --cov-context=test,
# as tests/test_coverage_at_m.py writes it. What ran at import is in the empty
# context; the session fixture runs src/shop/db.py during test_total's setup;
# and line 3 of src/shop/tax.py ran for test_total and for test_vat, so the
# coverage is not rejected as no-shared-lines. src/shop/constants.py ran only
# at import, so it is import-only.
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

# Children of a test case, with the messages pytest writes in them.
FAILURE = '<failure message="assert 2 == 3">assert 2 == 3</failure>'
TEARDOWN_ERROR = (
    '<error message="failed on teardown with &quot;OSError&quot;">x</error>'
)

# The testsuite's time, which pytest takes from the whole session, collection
# included: not the 12.0 s that the fixture's test cases take, so that full_ms
# cannot come from it (note 42). A rerun file's session is shorter.
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
TOTAL_FAILED = case("tests.test_pricing", "test_total", "2.000", FAILURE)
VAT_PASSED = case("tests.test_tax", "test_vat", "1.000")
VAT_FAILED = case("tests.test_tax", "test_vat", "1.000", FAILURE)
RENDER_PASSED = case("tests.test_report", "test_render", "5.000")
RENDER_FAILED = case("tests.test_report", "test_render", "5.000", FAILURE)
CREATE_PASSED = case("tests.api.test_orders", "test_create", "4.000")
CREATE_FAILED = case("tests.api.test_orders", "test_create", "4.000", FAILURE)

# K1's full run, which is also K2's: test_render failed.
K1_JUNIT = junit_file(
    SUITE_TIME, TOTAL_PASSED, VAT_PASSED, RENDER_FAILED, CREATE_PASSED
)

# K2's rerun file, which reran test_render alone: it passed.
K2_RERUN = junit_file(RERUN_SUITE_TIME, RENDER_PASSED)

# Full runs named by what happened in them.
NO_FAILURE_JUNIT = junit_file(
    SUITE_TIME, TOTAL_PASSED, VAT_PASSED, RENDER_PASSED, CREATE_PASSED
)
VAT_FAILED_JUNIT = junit_file(
    SUITE_TIME, TOTAL_PASSED, VAT_FAILED, RENDER_PASSED, CREATE_PASSED
)
THREE_FAILED_JUNIT = junit_file(
    SUITE_TIME, TOTAL_FAILED, VAT_PASSED, RENDER_FAILED, CREATE_FAILED
)

# K1's full run as Edge 6 and 7 change it. In Edge 6, test_vat sets its own
# classname with record_xml_attribute; in Edge 7, H deleted test_vat, or
# renamed it to test_vat_rate.
EDGE_6_VAT = case("billing.TaxSuite", "test_vat", "1.000")
EDGE_6_JUNIT = junit_file(
    SUITE_TIME, TOTAL_PASSED, EDGE_6_VAT, RENDER_FAILED, CREATE_PASSED
)
EDGE_7_DELETED_JUNIT = junit_file(
    SUITE_TIME, TOTAL_PASSED, RENDER_FAILED, CREATE_PASSED
)
EDGE_7_RENAMED_JUNIT = junit_file(
    SUITE_TIME,
    TOTAL_PASSED,
    case("tests.test_tax", "test_vat_rate", "1.000"),
    RENDER_FAILED,
    CREATE_PASSED,
)

# A full run in which two tests have two test cases each: Edge 6's test_vat,
# run twice, which failed and then passed, and test_render, which failed in
# its call and then had an error in its teardown. Six test cases of four
# tests, which take 12.0 s.
REPEATED_JUNIT = junit_file(
    SUITE_TIME,
    TOTAL_PASSED,
    case("billing.TaxSuite", "test_vat", "0.400", FAILURE),
    case("billing.TaxSuite", "test_vat", "0.600"),
    case("tests.test_report", "test_render", "4.900", FAILURE),
    case("tests.test_report", "test_render", "0.100", TEARDOWN_ERROR),
    CREATE_PASSED,
)


# The runs

# K1's line, as the SPEC gives it, with HEAD for <H>, MERGE_BASE for
# <merge-base>, M for <M> and K1_SHA256 for <sha>.
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

# K4's line for the fixture's run, as the SPEC gives it: K15's record file
# starts with it.
K4_LINE = (
    b'{"format":1,"head":"f5dc5ccbd62964df83d34c5dd3cb9b598fc3e51f",'
    b'"junit_sha256":'
    b'"402eb2fb1acba1cf0816f586edb02a4fec58e729489904a6ec18a8b13600a2ec",'
    b'"pr":7,"verdict":"rejected","reason":"coverage-not-ancestor",'
    b'"input":"coverage"}\n'
)

# K15: a record file whose first line is a record and whose second line is
# not one and holds the text canary.
CANARY = "canary"
K15_RECORD_FILE = K4_LINE + CANARY.encode("ascii") + b"\n"

# Another run's rejected record, with tests/test_messages.py's other key.
OTHER_RUNS_LINE = (
    b'{"format":1,"head":"0a9b8c7d6e5f40312a3b4c5d6e7f8091a2b3c4d5",'
    b'"junit_sha256":'
    b'"f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d2c3b4a5968778695a4b3c2d1e0f",'
    b'"pr":12,"verdict":"rejected","reason":"unusable-input","input":"coverage"}\n'
)


@dataclass(frozen=True)
class Run:
    """What changes from one run to the next: its pull request, its head as
    given, its full run's JUnit file and its rerun file, if any."""

    pr: int
    head: str
    junit: bytes
    rerun: bytes | None = None


# K1's run: a diff that modifies only templates/invoice.html, a full run of
# pull request 7 in which test_render failed, and no rerun file.
K1_RUN = Run(pr=7, head="pr-7", junit=K1_JUNIT)
# K2's run: K1's, with a rerun file in which test_render passed.
K2_RUN = Run(pr=7, head="pr-7", junit=K1_JUNIT, rerun=K2_RERUN)
# Verdict 4's: K1's diff and a full run with no failure.
GREEN_RUN = Run(pr=7, head="pr-7", junit=NO_FAILURE_JUNIT)
# Verdict 1's, in pull request 12: a diff that modifies only src/shop/tax.py
# and a full run in which test_vat failed. It is also Selection 16's run.
CAUGHT_RUN = Run(pr=12, head="pr-12", junit=VAT_FAILED_JUNIT)
# Selection 4's and 15's at once, in pull request 31: a diff that modifies
# uv.lock and src/shop/constants.py, and a full run with no failure.
FLOOR_RUN = Run(pr=31, head="pr-31", junit=NO_FAILURE_JUNIT)
# Selection 12's, in pull request 58: a diff that deletes src/shop/report.py,
# and K1's full run, in which test_render failed.
DELETED_REPORT_RUN = Run(pr=58, head="pr-58", junit=K1_JUNIT)
# Edge 6's and 7's, in pull request 44, which modifies tests/test_tax.py.
EDGE_6_RUN = Run(pr=44, head="pr-44", junit=EDGE_6_JUNIT)
EDGE_7_DELETED_RUN = Run(pr=44, head="pr-44", junit=EDGE_7_DELETED_JUNIT)
EDGE_7_RENAMED_RUN = Run(pr=44, head="pr-44", junit=EDGE_7_RENAMED_JUNIT)
# K1's diff with the full run whose tests have several test cases, without
# and with K2's rerun file.
REPEATED_RUN = Run(pr=7, head="pr-7", junit=REPEATED_JUNIT)
REPEATED_WITH_RERUN = Run(pr=7, head="pr-7", junit=REPEATED_JUNIT, rerun=K2_RERUN)
# K1's diff with a full run in which test_total, test_render and test_create
# failed: every list of its record has an entry or more, and test_total's row
# three paths.
INVARIANT_RUN = Run(pr=7, head="pr-7", junit=THREE_FAILED_JUNIT)


def record_file(directory: Path) -> Path:
    """The record file that RECORDS names, from directory."""
    return directory / "ci" / "records.jsonl"


def lay_out(run: Run, shop: Shop, directory: Path) -> None:
    """Write run's JUnit files and the coverage at M where the inputs name
    them, from directory."""
    ci = directory / "ci"
    ci.mkdir()
    (ci / "junit.xml").write_bytes(run.junit)
    if run.rerun is not None:
        (ci / "rerun.xml").write_bytes(run.rerun)
    (ci / "m.coverage").write_bytes(shop.coverage_data)


def run_args(run: Run, shop: Shop) -> evaluate.RunArgs:
    """run's inputs as cli gives them to evaluate.run."""
    rerun = RERUN if run.rerun is not None else None
    return evaluate.RunArgs(
        pr=run.pr,
        head=run.head,
        base=BASE,
        coverage=COVERAGE,
        coverage_commit=M_AS_GIVEN,
        junit=JUNIT,
        rerun=rerun,
        rootdir="",
        floor_config=None,
        records=RECORDS,
        checkout=str(shop.checkout),
    )


def evaluated(
    run: Run, records_before: bytes | None, shop: Shop, directory: Path
) -> int:
    """Evaluate run from directory with a record file that holds records_before,
    or with no record file if it is None; return what evaluate.run returns."""
    lay_out(run, shop, directory)
    if records_before is not None:
        record_file(directory).write_bytes(records_before)
    return evaluate.run(run_args(run, shop))


def only_record(directory: Path) -> dict[str, object]:
    """The record file's only line, as JSON."""
    return json.loads(record_file(directory).read_bytes())


def numbers_in(text: str) -> list[int]:
    """Every run of ASCII digits in text, as a number."""
    return [int(digits) for digits in re.findall(r"[0-9]+", text)]


# K1 and K13: the missed run and its record


def test_k1_a_missed_run_appends_exactly_its_line(shop: Shop, tmp_path: Path) -> None:
    evaluated(K1_RUN, b"", shop, tmp_path)

    assert record_file(tmp_path).read_bytes() == K1_LINE


def test_k13_with_no_record_file_one_is_created_that_holds_only_k1s_line(
    shop: Shop, tmp_path: Path
) -> None:
    evaluated(K1_RUN, None, shop, tmp_path)

    assert record_file(tmp_path).read_bytes() == K1_LINE


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("m.coverage", id="the coverage file"),
        pytest.param("junit.xml", id="the JUnit file"),
    ],
)
def test_k13_the_coverage_file_and_the_junit_file_are_left_byte_for_byte_as_they_were(
    name: str, shop: Shop, tmp_path: Path
) -> None:
    lay_out(K1_RUN, shop, tmp_path)
    path = tmp_path / "ci" / name
    data = path.read_bytes()
    os.utime(path, ns=(0, 0))  # an old time, which any write would replace

    evaluate.run(run_args(K1_RUN, shop))

    assert path.read_bytes() == data
    assert path.stat().st_mtime_ns == 0


def test_an_evaluated_runs_record_goes_after_the_lines_already_there(
    shop: Shop, tmp_path: Path
) -> None:
    evaluated(K1_RUN, OTHER_RUNS_LINE, shop, tmp_path)

    assert record_file(tmp_path).read_bytes() == OTHER_RUNS_LINE + K1_LINE


# K2: a failure not reproduced


def test_k2_a_failure_that_passes_in_the_rerun_file_is_not_reproduced(
    shop: Shop, tmp_path: Path
) -> None:
    evaluated(K2_RUN, b"", shop, tmp_path)

    record = only_record(tmp_path)
    found = {
        key: record[key]
        for key in ("verdict", "rerun_given", "not_reproduced", "failed_left_out")
    }
    assert found == {
        "verdict": "green",
        "rerun_given": True,
        "not_reproduced": [["tests.test_report", "test_render"]],
        "failed_left_out": [],
    }


# K3: a run already recorded


def test_k3_a_run_already_recorded_leaves_the_record_file_byte_for_byte_as_it_was(
    shop: Shop, tmp_path: Path
) -> None:
    lay_out(K1_RUN, shop, tmp_path)
    record_file(tmp_path).write_bytes(K1_LINE)
    os.utime(record_file(tmp_path), ns=(0, 0))

    evaluate.run(run_args(K1_RUN, shop))

    assert record_file(tmp_path).read_bytes() == K1_LINE
    assert record_file(tmp_path).stat().st_mtime_ns == 0


def test_k3_the_warning_names_the_runs_key_as_the_record_holds_it(
    shop: Shop, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    # H is given as pr-7, its branch: the record holds its full commit id.
    capfd.readouterr()  # drop what was written before the evaluation

    evaluated(K1_RUN, K1_LINE, shop, tmp_path)

    output = capfd.readouterr()
    assert output.out == ""
    assert HEAD in output.err
    assert K1_SHA256 in output.err


# K7 and the exit codes


@pytest.mark.parametrize(
    ("run", "records_before"),
    [
        pytest.param(K1_RUN, b"", id="K7, a missed run"),
        pytest.param(K1_RUN, None, id="K13, a missed run with no record file"),
        pytest.param(GREEN_RUN, b"", id="K7, a green run"),
        pytest.param(CAUGHT_RUN, b"", id="K7, a caught run"),
        pytest.param(K1_RUN, K1_LINE, id="K3, a run already recorded"),
    ],
)
def test_k7_an_evaluated_run_or_one_already_recorded_exits_with_0(
    run: Run, records_before: bytes | None, shop: Shop, tmp_path: Path
) -> None:
    assert evaluated(run, records_before, shop, tmp_path) == 0


# K15: a line that is not a record


def test_k15_a_record_file_with_a_line_that_is_not_a_record_exits_with_1(
    shop: Shop, tmp_path: Path
) -> None:
    assert evaluated(K1_RUN, K15_RECORD_FILE, shop, tmp_path) == 1


def test_k15_nothing_is_appended_and_the_record_file_is_left_as_it_was(
    shop: Shop, tmp_path: Path
) -> None:
    lay_out(K1_RUN, shop, tmp_path)
    record_file(tmp_path).write_bytes(K15_RECORD_FILE)
    os.utime(record_file(tmp_path), ns=(0, 0))

    evaluate.run(run_args(K1_RUN, shop))

    assert record_file(tmp_path).read_bytes() == K15_RECORD_FILE
    assert record_file(tmp_path).stat().st_mtime_ns == 0


def test_k15_the_error_names_the_record_file_and_line_2(
    shop: Shop, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()

    evaluated(K1_RUN, K15_RECORD_FILE, shop, tmp_path)

    output = capfd.readouterr()
    assert output.out == ""
    assert RECORDS in output.err
    assert 2 in numbers_in(output.err)


def test_k15_nothing_the_tool_prints_holds_canary(
    shop: Shop, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()

    evaluated(K1_RUN, K15_RECORD_FILE, shop, tmp_path)

    output = capfd.readouterr()
    assert CANARY not in output.out + output.err


def test_the_record_file_is_read_before_any_input(
    shop: Shop, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    # K15's record file, and neither a coverage file nor a JUnit file where the
    # inputs name them: the record file's line 2 is the error, not an input
    # that cannot be used (How a run goes, step 2).
    (tmp_path / "ci").mkdir()
    record_file(tmp_path).write_bytes(K15_RECORD_FILE)
    capfd.readouterr()

    evaluate.run(run_args(K1_RUN, shop))

    output = capfd.readouterr()
    assert RECORDS in output.err
    assert 2 in numbers_in(output.err)


# What an evaluated run prints


def test_an_evaluated_run_prints_nothing(
    shop: Shop, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    # Warnings and error messages go to stderr, and an evaluated run has
    # neither.
    capfd.readouterr()

    evaluated(K1_RUN, b"", shop, tmp_path)

    assert capfd.readouterr() == ("", "")


# The diff


def test_selection_16_the_diff_starts_at_the_merge_base_of_b_and_h(
    shop: Shop, tmp_path: Path
) -> None:
    # Pull request 12's own change modifies only src/shop/tax.py. On main, R
    # modified src/shop/report.py after M and before the merge-base, and B
    # modified src/shop/orders.py after it. The selection is test_total and
    # test_vat, which take 2,000 ms and 1,000 ms: no other set of the
    # fixture's tests takes 3,000 ms. A diff from M would add test_render's
    # 5,000 ms, and one against B test_create's 4,000 ms.
    evaluated(CAUGHT_RUN, b"", shop, tmp_path)

    assert only_record(tmp_path)["selected_ms"] == 3000


def test_selection_12_a_deleted_file_selects_through_ms_tree(
    shop: Shop, tmp_path: Path
) -> None:
    # Pull request 58 deletes src/shop/report.py, which M's tree has and H's
    # does not. Mapped to M's tree, test_render's row has it, so test_render is
    # selected, with its 5,000 ms. Mapped to H's tree, its row would be
    # src/shop/pricing.py alone, and no test would be selected.
    evaluated(DELETED_REPORT_RUN, b"", shop, tmp_path)

    assert only_record(tmp_path)["selected_ms"] == 5000


# The record's fields

# A run, and a field of its record with the value that the SPEC gives it. K1's
# line shows every field; these show the fields whose values in K1 another
# rule could also give: a verdict, a pull request, a floor match and an
# import-only path that K1 does not have, a path with no column next to an
# import-only one, and the SHA-256 of the full run's JUnit file when there is
# a rerun file too.
RECORD_FIELDS = [
    pytest.param(GREEN_RUN, {"verdict": "green"}, id="Verdict 4, green"),
    pytest.param(CAUGHT_RUN, {"verdict": "caught"}, id="Verdict 1, caught"),
    pytest.param(CAUGHT_RUN, {"pr": 12}, id="the pull request given"),
    pytest.param(
        K2_RUN,
        {"junit_sha256": K1_SHA256},
        id="the full run's SHA-256, not the rerun file's",
    ),
    pytest.param(FLOOR_RUN, {"floor_matched": True}, id="uv.lock matches the floor"),
    pytest.param(
        FLOOR_RUN,
        {"import_only": ["src/shop/constants.py"]},
        id="Selection 15, src/shop/constants.py is import-only",
    ),
    pytest.param(
        FLOOR_RUN,
        {"no_column": ["uv.lock"]},
        id="uv.lock has no column, and the import-only path is not listed with it",
    ),
]


@pytest.mark.parametrize(("run", "expected"), RECORD_FIELDS)
def test_each_field_holds_the_value_of_its_run(
    run: Run, expected: dict[str, object], shop: Shop, tmp_path: Path
) -> None:
    evaluated(run, b"", shop, tmp_path)

    record = only_record(tmp_path)
    assert {key: record[key] for key in expected} == expected


# Edge 6 and 7 (note 41): the coverage at M has the same four node ids with a
# row, and test_vat's pair is not in the run.
EDGE_6_AND_7 = [
    pytest.param(EDGE_6_RUN, {"tests": 4}, id="Edge 6, tests"),
    pytest.param(EDGE_6_RUN, {"unmeasured": 1}, id="Edge 6, unmeasured"),
    pytest.param(EDGE_6_RUN, {"tests_with_row": 4}, id="Edge 6, with a row"),
    pytest.param(
        EDGE_6_RUN, {"tests_with_row_not_in_run": 1}, id="Edge 6, not in the run"
    ),
    pytest.param(EDGE_7_DELETED_RUN, {"tests": 3}, id="Edge 7 deleted, tests"),
    pytest.param(
        EDGE_7_DELETED_RUN, {"unmeasured": 0}, id="Edge 7 deleted, unmeasured"
    ),
    pytest.param(EDGE_7_DELETED_RUN, {"full_ms": 11000}, id="Edge 7 deleted, full_ms"),
    pytest.param(
        EDGE_7_DELETED_RUN, {"tests_with_row": 4}, id="Edge 7 deleted, with a row"
    ),
    pytest.param(
        EDGE_7_DELETED_RUN,
        {"tests_with_row_not_in_run": 1},
        id="Edge 7 deleted, not in the run",
    ),
    pytest.param(EDGE_7_RENAMED_RUN, {"tests": 4}, id="Edge 7 renamed, tests"),
    pytest.param(
        EDGE_7_RENAMED_RUN, {"unmeasured": 1}, id="Edge 7 renamed, unmeasured"
    ),
    pytest.param(
        EDGE_7_RENAMED_RUN, {"tests_with_row": 4}, id="Edge 7 renamed, with a row"
    ),
    pytest.param(
        EDGE_7_RENAMED_RUN,
        {"tests_with_row_not_in_run": 1},
        id="Edge 7 renamed, not in the run",
    ),
]


@pytest.mark.parametrize(("run", "expected"), EDGE_6_AND_7)
def test_edge_6_and_7_count_the_tests_of_the_run_and_the_tests_with_a_row(
    run: Run, expected: dict[str, object], shop: Shop, tmp_path: Path
) -> None:
    evaluated(run, b"", shop, tmp_path)

    record = only_record(tmp_path)
    assert {key: record[key] for key in expected} == expected


# The full run whose test_vat and test_render have two test cases each: every
# count and every list of the run's tests takes each pair once.
EACH_PAIR_ONCE = [
    pytest.param(REPEATED_RUN, {"tests": 4}, id="tests"),
    pytest.param(REPEATED_RUN, {"unmeasured": 1}, id="unmeasured"),
    pytest.param(
        REPEATED_RUN,
        {
            "failed_left_out": [
                {
                    "pair": ["tests.test_report", "test_render"],
                    "node_id": TEST_RENDER,
                    "row": [PRICING, REPORT],
                }
            ]
        },
        id="failed_left_out",
    ),
    pytest.param(
        REPEATED_WITH_RERUN,
        {"not_reproduced": [["tests.test_report", "test_render"]]},
        id="not_reproduced",
    ),
]


@pytest.mark.parametrize(("run", "expected"), EACH_PAIR_ONCE)
def test_every_count_and_every_list_of_the_runs_tests_takes_each_pair_once(
    run: Run, expected: dict[str, object], shop: Shop, tmp_path: Path
) -> None:
    evaluated(run, b"", shop, tmp_path)

    record = only_record(tmp_path)
    assert {key: record[key] for key in expected} == expected


# Invariant 1, its first half


def record_file_after_evaluating_in(
    directory: Path, shop: Shop, monkeypatch: pytest.MonkeyPatch
) -> bytes:
    """The record file's bytes after evaluating INVARIANT_RUN from directory,
    with an empty record file."""
    directory.mkdir()
    monkeypatch.chdir(directory)
    evaluated(INVARIANT_RUN, b"", shop, directory)
    return record_file(directory).read_bytes()


def test_invariant_1_two_evaluations_of_the_same_inputs_give_byte_identical_records(
    shop: Shop, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The same command line, each time from a working directory of its own.
    first = record_file_after_evaluating_in(tmp_path / "first", shop, monkeypatch)
    second = record_file_after_evaluating_in(tmp_path / "second", shop, monkeypatch)

    assert first == second


# Any other failure

# The classes of OSError that Python defines. A record file that exists but
# cannot be read is any other failure, and the SPEC does not say which class
# names it.
OS_ERRORS = (
    OSError,
    BlockingIOError,
    ChildProcessError,
    ConnectionError,
    BrokenPipeError,
    ConnectionAbortedError,
    ConnectionRefusedError,
    ConnectionResetError,
    FileExistsError,
    FileNotFoundError,
    InterruptedError,
    IsADirectoryError,
    NotADirectoryError,
    PermissionError,
    ProcessLookupError,
    TimeoutError,
)
UNEXPECTED_OS_ERROR_LINES = {
    f"distiller: unexpected failure: {error.__name__}\n" for error in OS_ERRORS
}


def command_line(run: Run, shop: Shop) -> list[str]:
    """run's inputs as the CI step gives them, for a run with no rerun file."""
    return [
        "evaluate",
        "--pr",
        str(run.pr),
        "--head",
        run.head,
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


def make_a_directory(path: Path) -> None:
    path.mkdir()


def make_a_file_that_may_only_be_written(path: Path) -> None:
    # Reading it fails and appending to it would not, so the evaluation has to
    # stop before it appends.
    path.write_bytes(b"")
    path.chmod(0o200)
    if os.access(path, os.R_OK):
        pytest.skip("this user reads a file whatever its mode, as root does")


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(make_a_directory, id="a directory"),
        pytest.param(make_a_file_that_may_only_be_written, id="a file it may not read"),
    ],
)
def test_a_record_file_that_cannot_be_read_is_any_other_failure(
    make: Callable[[Path], None],
    shop: Shop,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    # A record file that exists but cannot be read. evaluate lets the OSError
    # through, and cli prints one line that names only its class and exits with
    # 1 (How a run goes, step 6).
    lay_out(K1_RUN, shop, tmp_path)
    make(record_file(tmp_path))
    capfd.readouterr()

    code = cli.main(command_line(K1_RUN, shop))

    output = capfd.readouterr()
    assert (code, output.out) == (1, "")
    assert output.err in UNEXPECTED_OS_ERROR_LINES
