import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import coverage
import pytest

from replay import tool
from replay.steps import ToolInputs

# Each test runs the tool through tool.evaluate, as step 6 of a replay does:
# either a fake tool, a checkout whose distiller notes how it was run, or this
# repository itself, the real tool, on a small project of K16's and K17's
# shapes. The tests watch what the tool was given, the record file, and the
# StepResult. The tool runs as the user's terminal would run it from its
# checkout: that checkout's .venv/bin/python, -P -m distiller evaluate, with the
# checkout's src/ on PYTHONPATH.

# The real git, found before any test changes the environment.
GIT = shutil.which("git") or "git"

# This repository: the real tool, with its own .venv.
REPOSITORY = Path(__file__).resolve().parents[2]

# A distiller that notes, beside its checkout, what it was given and how
# Python ran it, prints on both streams, and exits with the code that its
# checkout's exit-code file holds, 0 if none.
FAKE_DISTILLER = """\
import json
import os
import sys
from pathlib import Path

checkout = Path(__file__).resolve().parents[2]
noted = {
    "argv": sys.argv[1:],
    "safe_path": sys.flags.safe_path,
}
(checkout / "ran.json").write_text(json.dumps(noted), encoding="utf-8")
print("the fake tool's stdout")
print("the fake tool's stderr", file=sys.stderr)
code_file = checkout / "exit-code"
raise SystemExit(int(code_file.read_text()) if code_file.exists() else 0)
"""

# The inputs of K16's pull request, as a replay gives them.
PULL_REQUEST = 5375
HEAD = "b66457156bf78d4683690a5004058ec09635e4f8"
BASE = "0123456789abcdef0123456789abcdef01234567"
M = "89abcdef0123456789abcdef0123456789abcdef"

# The checkout where the coverage at M was recorded: coverage records each file
# by its absolute path under it.
RUNNER_ROOT = "/runner/work/shop/"

TAX_AT_M = "RATE = 21\n\n\ndef vat(amount):\n    return amount * RATE // 100\n"
TAX_AT_HEAD = "RATE = 10\n\n\ndef vat(amount):\n    return amount * RATE // 100\n"
TESTS = "from shop.tax import vat\n\n\ndef test_vat():\n    assert vat(100) == 21\n"

# The coverage at M as pytest-cov records it with --cov-context=test: line 5 of
# shop/tax.py ran for both tests, so it is not rejected as no-shared-lines.
COVERAGE_LINES = {
    "": {"shop/__init__.py": [1], "shop/tax.py": [1, 4]},
    "tests/test_tax.py::test_vat|run": {"shop/tax.py": [5]},
    "tests/test_tax.py::test_total|run": {"shop/tax.py": [5]},
}

FAILURE = '<failure message="assert 10 == 21">assert 10 == 21</failure>'
INTERNAL_ERROR = '<error message="internal error">Traceback</error>'


@dataclass(frozen=True)
class Run:
    """A call of subprocess.run: what it was given to run, and two options."""

    command: Any  # as given: an argument list, or a string for a shell
    shell: Any
    timeout: Any


@dataclass(frozen=True)
class Shop:
    """A small project of K16's shape, as a replay leaves it for the tool."""

    checkout: Path
    base: str  # main, at M
    m: str
    head: str  # the pull request's head, which changes shop/tax.py
    coverage_file: Path
    records: Path
    work: Path


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep git, the tests' and the tool's, to the repositories' own settings."""
    for name in list(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "Distiller Tests")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "tests@distiller.invalid")
        monkeypatch.setenv(f"GIT_{role}_DATE", "2026-03-01T10:00:00+00:00")


@pytest.fixture
def fake_tool(tmp_path: Path) -> Path:
    """A checkout of a tool whose distiller notes how it was run."""
    checkout = tmp_path / "tool"
    package = checkout / "src" / "distiller"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "__main__.py").write_text(FAKE_DISTILLER, encoding="utf-8")
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "venv", "--without-pip", str(checkout / ".venv")],
        capture_output=True,
        check=True,
    )
    return checkout


@pytest.fixture
def shop(tmp_path: Path) -> Shop:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    run_git(checkout, "init", "--quiet", "--initial-branch=main")
    m = commit(
        checkout,
        {"shop/__init__.py": "", "shop/tax.py": TAX_AT_M, "tests/test_tax.py": TESTS},
    )
    run_git(checkout, "switch", "--quiet", "--create", "change")
    head = commit(checkout, {"shop/tax.py": TAX_AT_HEAD})
    run_git(checkout, "switch", "--quiet", "main")
    work = tmp_path / "work"
    work.mkdir()
    coverage_file = work / "m.coverage"
    write_coverage_at_m(coverage_file)
    return Shop(
        checkout=checkout,
        base=m,
        m=m,
        head=head,
        coverage_file=coverage_file,
        records=work / "records.jsonl",
        work=work,
    )


def run_git(directory: Path, *arguments: str) -> str:
    """Run the real git in directory, as the tests' setup does; return its stdout."""
    result = subprocess.run(  # noqa: S603
        [GIT, "-C", str(directory), *arguments],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, os.fsdecode(result.stderr)
    return os.fsdecode(result.stdout)


def commit(checkout: Path, files: dict[str, str]) -> str:
    for name, text in files.items():
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    run_git(checkout, "add", "--all")
    run_git(checkout, "commit", "--quiet", "--message", "Change the shop")
    return run_git(checkout, "rev-parse", "HEAD").strip()


def write_coverage_at_m(path: Path) -> None:
    """Write the coverage at M through coverage's public API."""
    data = coverage.CoverageData(basename=str(path))
    for context, lines_by_file in COVERAGE_LINES.items():
        data.set_context(context)
        data.add_lines(
            {RUNNER_ROOT + name: numbers for name, numbers in lines_by_file.items()}
        )
    data.write()
    data.close()


def case(classname: str, name: str, time: str, *children: str) -> str:
    """A testcase element with these attributes and children."""
    attributes = f'classname="{classname}" name="{name}" time="{time}"'
    return f"<testcase {attributes}>{''.join(children)}</testcase>"


def write_junit(path: Path, *testcases: str) -> Path:
    """A JUnit file as pytest writes it, around these test cases."""
    failures = sum("<failure" in testcase for testcase in testcases)
    errors = sum("<error" in testcase for testcase in testcases)
    suite = (
        f'<testsuite name="pytest" errors="{errors}" failures="{failures}" '
        f'skipped="0" tests="{len(testcases)}" time="3.000" '
        'timestamp="2026-11-14T21:02:34.000000+00:00" hostname="replay">'
    )
    text = (
        '<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests">'
        f"{suite}{''.join(testcases)}</testsuite></testsuites>"
    )
    path.write_text(text, encoding="utf-8")
    return path


def inputs_for(
    shop: Shop, junit: Path, rerun: Path | None = None, floor: Path | None = None
) -> ToolInputs:
    return ToolInputs(
        pull_request=PULL_REQUEST,
        head=shop.head,
        base=shop.base,
        m=shop.m,
        coverage_file=str(shop.coverage_file),
        junit_file=str(junit),
        rerun_file=None if rerun is None else str(rerun),
        floor_config=None if floor is None else str(floor),
        records=str(shop.records),
        checkout=str(shop.checkout),
    )


def fake_inputs(*, rerun_file: str | None, floor_config: str | None) -> ToolInputs:
    return ToolInputs(
        pull_request=PULL_REQUEST,
        head=HEAD,
        base=BASE,
        m=M,
        coverage_file="/work/m.coverage",
        junit_file="/work/junit.xml",
        rerun_file=rerun_file,
        floor_config=floor_config,
        records="/work/urllib3.jsonl",
        checkout="/clones/urllib3",
    )


def noted_by(fake_tool: Path) -> dict[str, Any]:
    """What the fake tool noted of the run, which it wrote only if it ran."""
    return cast("dict[str, Any]", json.loads((fake_tool / "ran.json").read_text()))


def options_of(arguments: list[str]) -> dict[str, str]:
    """The evaluate command's options, each with its value."""
    assert arguments[0] == "evaluate", arguments
    options = arguments[1:]
    assert len(options) % 2 == 0, options
    return dict(zip(options[0::2], options[1::2], strict=True))


def records_of(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [cast("dict[str, Any]", json.loads(line)) for line in lines]


def record_runs(monkeypatch: pytest.MonkeyPatch) -> list[Run]:
    """Make subprocess.run note each call before it runs; return the notes."""
    runs: list[Run] = []
    # One type for subprocess.run's overloads, which, given arguments of any
    # type, would leave its result unknown to pyright.
    real_run = cast("Callable[..., subprocess.CompletedProcess[Any]]", subprocess.run)

    def noting_run(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[Any]:
        command = args[0] if args else kwargs.get("args")
        runs.append(
            Run(
                command=command,
                shell=kwargs.get("shell"),
                timeout=kwargs.get("timeout"),
            )
        )
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", noting_run)
    return runs


def is_argument_list(command: object) -> bool:
    return isinstance(command, list | tuple)


def is_positive_number(value: object) -> bool:
    return isinstance(value, int | float) and value > 0


def test_the_tool_runs_its_own_distiller_evaluate_with_a_safe_path(
    fake_tool: Path,
) -> None:
    tool.evaluate(str(fake_tool), fake_inputs(rerun_file=None, floor_config=None))

    noted = noted_by(fake_tool)
    assert noted["argv"][0] == "evaluate"
    assert noted["safe_path"] is True  # python -P


def test_each_input_goes_to_its_option(fake_tool: Path) -> None:
    inputs = fake_inputs(rerun_file="/work/rerun.xml", floor_config="/pilots/floor.txt")

    tool.evaluate(str(fake_tool), inputs)

    assert options_of(noted_by(fake_tool)["argv"]) == {
        "--pr": str(PULL_REQUEST),
        "--head": HEAD,
        "--base": BASE,
        "--coverage": "/work/m.coverage",
        "--coverage-commit": M,
        "--junit": "/work/junit.xml",
        "--rerun": "/work/rerun.xml",
        "--floor-config": "/pilots/floor.txt",
        "--records": "/work/urllib3.jsonl",
        "--checkout": "/clones/urllib3",
    }


def test_no_rerun_file_and_no_floor_configuration_leave_their_options_out(
    fake_tool: Path,
) -> None:
    tool.evaluate(str(fake_tool), fake_inputs(rerun_file=None, floor_config=None))

    options = options_of(noted_by(fake_tool)["argv"])
    assert "--rerun" not in options
    assert "--floor-config" not in options
    assert len(options) == 8


@pytest.mark.parametrize("code", [0, 1, 3])
def test_the_tools_exit_code_is_the_steps(fake_tool: Path, code: int) -> None:
    # 0 evaluated or already recorded, 1 any other failure, 3 rejected.
    (fake_tool / "exit-code").write_text(str(code), encoding="utf-8")

    result = tool.evaluate(
        str(fake_tool), fake_inputs(rerun_file=None, floor_config=None)
    )

    assert result.exit_code == code


def test_the_output_holds_the_command_and_what_the_tool_printed(
    fake_tool: Path,
) -> None:
    result = tool.evaluate(
        str(fake_tool), fake_inputs(rerun_file=None, floor_config=None)
    )

    assert "distiller evaluate" in result.output
    assert "the fake tool's stdout" in result.output
    assert "the fake tool's stderr" in result.output
    assert result.failed == ()


def test_a_run_past_its_time_limit_gives_no_exit_code(
    fake_tool: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run_out_of_time(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[Any]:
        command = args[0] if args else kwargs["args"]
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout") or 1)

    monkeypatch.setattr(subprocess, "run", run_out_of_time)

    result = tool.evaluate(
        str(fake_tool), fake_inputs(rerun_file=None, floor_config=None)
    )

    assert result.exit_code is None


def test_a_tool_checkout_with_no_environment_raises(tmp_path: Path) -> None:
    # As when --tool names a checkout where make install never ran: every pull
    # request would otherwise end with no record.
    with pytest.raises(Exception) as raised:  # noqa: PT011
        tool.evaluate(
            str(tmp_path / "no-tool"), fake_inputs(rerun_file=None, floor_config=None)
        )

    assert not isinstance(raised.value, NotImplementedError)


def test_the_tool_runs_from_an_argument_list_with_a_time_limit(
    fake_tool: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Rule 1: through subprocess.run, from an argument list and never a shell;
    # Rule 3: every process has a time limit.
    runs = record_runs(monkeypatch)

    tool.evaluate(str(fake_tool), fake_inputs(rerun_file=None, floor_config=None))

    assert runs, "the tool ran no process through subprocess.run"
    for run in runs:
        assert is_argument_list(run.command), run
        assert Path(run.command[0]) == fake_tool / ".venv" / "bin" / "python", run
        assert not run.shell, run
        assert is_positive_number(run.timeout), run


def test_an_evaluated_run_appends_one_record_to_the_record_file(shop: Shop) -> None:
    # K16's shape: the real tool evaluates the run of a pull request whose test
    # failed in the full run and again in the rerun, and one record is
    # appended to the pilot's record file.
    junit = write_junit(
        shop.work / "junit.xml",
        case("tests.test_tax", "test_vat", "1.000", FAILURE),
        case("tests.test_tax", "test_total", "2.000"),
    )
    rerun = write_junit(
        shop.work / "rerun.xml", case("tests.test_tax", "test_vat", "1.000", FAILURE)
    )

    result = tool.evaluate(str(REPOSITORY), inputs_for(shop, junit, rerun))

    assert result.exit_code == 0, result.output
    (record,) = records_of(shop.records)
    assert record["pr"] == PULL_REQUEST
    assert record["head"] == shop.head
    assert record["verdict"] in {"green", "caught", "missed"}
    assert record["rerun_given"] is True


def test_a_full_run_that_ends_in_pytests_internal_error_is_rejected(
    shop: Shop,
) -> None:
    # K17's shape: the run is rejected with unusable-input and junit, as Slice
    # 1 rejects such a JUnit file, and the tool exits with 3.
    junit = write_junit(
        shop.work / "junit.xml",
        case("tests.test_tax", "test_vat", "1.000"),
        case("pytest", "internal", "0.000", INTERNAL_ERROR),
    )

    result = tool.evaluate(str(REPOSITORY), inputs_for(shop, junit))

    assert result.exit_code == 3, result.output
    (record,) = records_of(shop.records)
    assert record["verdict"] == "rejected"
    assert record["reason"] == "unusable-input"
    assert record["input"] == "junit"
