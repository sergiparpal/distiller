import subprocess
import sys
import sysconfig
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest
from coverage import CoverageData

from replay import suite
from replay.pilot import Pilot
from replay.steps import StepResult

# Each test writes a small project into a worktree of a work directory in
# tmp_path, with an environment that sees this repository's own pytest,
# pytest-cov and pytest-timeout, and runs its tests through suite, inside
# bubblewrap and with no network. The tests watch the JUnit and coverage files,
# the StepResult, and what the project's own tests saw from inside. Decided by
# the user on 2026-11-18, for the SPEC: besides Rule 5, a run sees /tmp, /run
# and /mnt empty, as Stop's sandbox does, reads nothing on stdin, and gets none
# of the harness's variables but HOME, PATH, LANG and coverage's.

# No test may hang the suite: a run that the wrapper did not end, or a test
# that the pilot's limit did not stop, fails here instead.
pytestmark = pytest.mark.timeout(120)

# The site-packages of the environment that runs these tests, which the
# projects' environments add to their own: pytest and its plugins, no network.
TESTS_SITE_PACKAGES = sysconfig.get_paths()["purelib"]

# The pilot's time limit per test, short so that the tests stay quick.
SECONDS_PER_TEST = 2

# A variable of the harness's environment that must not reach the tests, named
# as a credential is.
HARNESS_VARIABLE = "REPLAY_TESTS_TOKEN"

# The project's package, and its pytest settings: the root on sys.path, as the
# pilots' own environments install their package.
SHOP = "def tax(amount):\n    return amount * 21 // 100\n"
PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["."]\n'

# K16's shape: five tests that fail, all in test/test_response.py, beside
# others that pass.
RESPONSE_TESTS = """\
import pytest

from shop import tax


def test_tax():
    assert tax(100) == 21


def test_decode():
    assert tax(100) == 0


@pytest.mark.parametrize("status", [200, 201, 202, 203])
def test_status(status):
    assert tax(status) == status
"""
OTHER_TESTS = """\
def test_other():
    assert True


def test_excluded():
    raise AssertionError("the pilot's pytest options leave this test out")
"""
K16_FAILED = (
    "test/test_response.py::test_decode",
    "test/test_response.py::test_status[200]",
    "test/test_response.py::test_status[201]",
    "test/test_response.py::test_status[202]",
    "test/test_response.py::test_status[203]",
)
K16_FAILED_CASES = {
    "test.test_response::test_decode",
    "test.test_response::test_status[200]",
    "test.test_response::test_status[201]",
    "test.test_response::test_status[202]",
    "test.test_response::test_status[203]",
}
# The pilot's options of these runs, which leave test_excluded out.
PILOT_OPTIONS = ("-k", "not excluded")

PASSING_TESTS = "def test_passes():\n    assert True\n"

ERRING_TESTS = """\
import pytest


@pytest.fixture
def broken():
    raise RuntimeError("a fixture that breaks")


def test_uses_broken(broken):
    pass
"""

# A test that waits for input that never comes, as poetry's #10956's did.
WAITING_TESTS = """\
import os


def test_waits_for_input():
    read_end, _write_end = os.pipe()
    os.read(read_end, 1)


def test_after():
    assert True
"""

# A test that leaves a thread blocked, as urllib3's HTTP/2 probe test did: the
# thread is no daemon, so Python would wait for it before the process ends.
THREAD_TESTS = """\
import threading


def test_leaves_a_thread_blocked():
    threading.Thread(target=threading.Event().wait).start()
"""

# pytest's internal error, as poetry's #11226's full run ended.
INTERNAL_ERROR_CONFTEST = """\
def pytest_collection_modifyitems(items):
    raise RuntimeError("an internal error of pytest")
"""

# Tests run for the coverage at M: two run the package, one only checks the
# coverage core, and one fails at M.
COVERAGE_TESTS = """\
import os

from shop import tax


def test_tax():
    assert tax(100) == 21


def test_fails_at_m():
    assert tax(1) == 1


def test_core():
    assert os.environ.get("COVERAGE_CORE") == "ctrace"
"""

# Tests that look at the sandbox from inside, against what sandbox.json, which
# the test writes beside them, expects.
SANDBOX_TESTS = """\
import json
import os
import socket
from pathlib import Path

EXPECTED = json.loads(
    (Path(__file__).parent.parent / "sandbox.json").read_text(encoding="utf-8")
)


def test_no_network_but_the_loopback():
    assert [name for _, name in socket.if_nameindex()] == ["lo"]
    server = socket.create_server(("127.0.0.1", 0))
    with socket.create_connection(server.getsockname(), timeout=5):
        pass
    server.close()


def test_an_address_outside_is_unreachable():
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=5).close()
    except OSError:
        return
    raise AssertionError("an address outside the loopback answered")


def test_the_users_home_is_hidden():
    assert not Path(EXPECTED["home_file"]).exists()


def test_home_is_in_the_work_directory_and_writable():
    home = Path(os.environ["HOME"])
    assert home.is_relative_to(EXPECTED["work"])
    home.mkdir(parents=True, exist_ok=True)
    (home / "written.txt").write_text("written", encoding="utf-8")


def test_the_environments_bin_comes_first_on_path():
    assert os.environ["PATH"].split(os.pathsep)[0] == EXPECTED["environment_bin"]


def test_none_of_the_harnesss_variables_reaches_the_tests():
    assert EXPECTED["harness_variable"] not in os.environ


def test_tmp_run_and_mnt_are_empty_but_for_the_way_to_the_work_directory():
    assert not Path(EXPECTED["outside_file"]).exists()
    assert os.listdir("/run") == []
    assert not os.path.isdir("/mnt") or os.listdir("/mnt") == []
"""
SANDBOX_NAMES = (
    "test_no_network_but_the_loopback",
    "test_an_address_outside_is_unreachable",
    "test_the_users_home_is_hidden",
    "test_home_is_in_the_work_directory_and_writable",
    "test_the_environments_bin_comes_first_on_path",
    "test_none_of_the_harnesss_variables_reaches_the_tests",
    "test_tmp_run_and_mnt_are_empty_but_for_the_way_to_the_work_directory",
)
SANDBOX_NODE_IDS = tuple(f"test/test_sandbox.py::{name}" for name in SANDBOX_NAMES)


@dataclass(frozen=True)
class Project:
    """A worktree in a work directory, with its environment and its package.

    home is the harness's home directory, which the runs hide, with a file in
    it; outside_file lies beside the work directory, under /tmp.
    """

    work: Path
    worktree: Path
    home_file: Path
    outside_file: Path

    def write(self, files: dict[str, str]) -> None:
        for name, text in files.items():
            path = self.worktree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")


@dataclass(frozen=True)
class Run:
    """A call of subprocess.run: what it was given to run, and two options."""

    command: Any  # as given: an argument list, or a string for a shell
    shell: Any
    timeout: Any


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Project:
    home = tmp_path / "home"
    home.mkdir()
    home_file = home / "notes.txt"
    home_file.write_text("the user's own\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv(HARNESS_VARIABLE, "a token of the user's")
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("beside the work directory\n", encoding="utf-8")
    work = tmp_path / "work"
    worktree = work / "worktree"
    worktree.mkdir(parents=True)
    make_environment(worktree)
    created = Project(
        work=work, worktree=worktree, home_file=home_file, outside_file=outside_file
    )
    created.write({"shop/__init__.py": SHOP, "pyproject.toml": PYPROJECT})
    return created


def make_environment(worktree: Path) -> None:
    """A .venv in the worktree whose Python sees these tests' own packages.

    Built with no network: a venv with no pip, and a .pth file that adds the
    site-packages of the environment that runs these tests.
    """
    environment = worktree / ".venv"
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "venv", "--without-pip", str(environment)],
        capture_output=True,
        check=True,
    )
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = environment / "lib" / version / "site-packages"
    (site_packages / "tests-packages.pth").write_text(
        TESTS_SITE_PACKAGES + "\n", encoding="utf-8"
    )


def pilot_with(*, pytest_options: tuple[str, ...] = ()) -> Pilot:
    return Pilot(
        project="shop",
        repository="example/shop",
        base_branch="main",
        job="Ubuntu 3.12",
        python="3.12",
        environment=(),
        pytest=pytest_options,
        coverage_source="shop",
        seconds_per_test=SECONDS_PER_TEST,
        adds_timeout_plugin=False,
        floor_config=None,
    )


def full_run_of(
    project: Project, junit: Path, pytest_options: tuple[str, ...] = ()
) -> StepResult:
    pilot = pilot_with(pytest_options=pytest_options)
    return suite.full_run(pilot, str(project.worktree), str(project.work), str(junit))


def outcomes(junit: Path) -> dict[str, str]:
    """Each test case of a JUnit file, as classname::name, with how it ended:
    passed, failure, error or skipped."""
    # The file comes from the test's own pytest run, so xml's parser will do.
    root = ET.parse(junit).getroot()  # noqa: S314
    found: dict[str, str] = {}
    for case in root.iter("testcase"):
        found[f"{case.get('classname')}::{case.get('name')}"] = outcome_of(case)
    return found


def outcome_of(case: ET.Element) -> str:
    for child in case:
        if child.tag in ("failure", "error", "skipped"):
            return child.tag
    return "passed"


def write_sandbox_tests(project: Project) -> None:
    expected = {
        "home_file": str(project.home_file),
        "outside_file": str(project.outside_file),
        "work": str(project.work),
        "environment_bin": str(project.worktree / ".venv" / "bin"),
        "harness_variable": HARNESS_VARIABLE,
    }
    project.write(
        {"test/test_sandbox.py": SANDBOX_TESTS, "sandbox.json": json_text(expected)}
    )


def json_text(values: dict[str, str]) -> str:
    lines = [f"  {key!r}: {value!r}" for key, value in values.items()]
    return "{\n" + ",\n".join(lines).replace("'", '"') + "\n}\n"


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


def test_the_full_runs_junit_holds_the_five_tests_that_failed(project: Project) -> None:
    # K16's shape: 5 failed tests, all in test/test_response.py.
    project.write({"test/test_response.py": RESPONSE_TESTS})
    junit = project.work / "junit.xml"

    full_run_of(project, junit, PILOT_OPTIONS)

    found = outcomes(junit)
    assert {name for name, outcome in found.items() if outcome == "failure"} == (
        K16_FAILED_CASES
    )
    assert found["test.test_response::test_tax"] == "passed"


def test_the_full_run_gives_the_node_ids_of_the_tests_that_failed(
    project: Project,
) -> None:
    project.write({"test/test_response.py": RESPONSE_TESTS})

    result = full_run_of(project, project.work / "junit.xml", PILOT_OPTIONS)

    assert sorted(result.failed) == sorted(K16_FAILED)
    assert result.exit_code == 1


def test_the_rerun_runs_the_tests_that_failed_once_more(project: Project) -> None:
    # K16's shape: the rerun file holds those 5 run again, and nothing else.
    project.write(
        {"test/test_response.py": RESPONSE_TESTS, "test/test_other.py": OTHER_TESTS}
    )
    junit = project.work / "rerun.xml"
    pilot = pilot_with(pytest_options=PILOT_OPTIONS)

    result = suite.rerun(
        pilot, str(project.worktree), str(project.work), K16_FAILED, str(junit)
    )

    assert outcomes(junit) == dict.fromkeys(K16_FAILED_CASES, "failure")
    assert sorted(result.failed) == sorted(K16_FAILED)


def test_each_run_takes_the_pilots_pytest_options(project: Project) -> None:
    project.write({"test/test_other.py": OTHER_TESTS})
    junit = project.work / "junit.xml"

    result = full_run_of(project, junit, PILOT_OPTIONS)

    assert outcomes(junit) == {"test.test_other::test_other": "passed"}
    assert result.exit_code == 0


def test_a_test_that_errs_is_among_those_that_failed(project: Project) -> None:
    project.write({"test/test_errors.py": ERRING_TESTS})

    result = full_run_of(project, project.work / "junit.xml")

    assert result.failed == ("test/test_errors.py::test_uses_broken",)


def test_a_run_whose_tests_all_pass_gives_exit_code_0_and_none_failed(
    project: Project,
) -> None:
    project.write({"test/test_passes.py": PASSING_TESTS})

    result = full_run_of(project, project.work / "junit.xml")

    assert result.exit_code == 0
    assert result.failed == ()


def test_pytests_internal_error_is_the_runs_exit_code(project: Project) -> None:
    # K17's shape: pytest ended with its internal error, exit code 3.
    project.write(
        {"conftest.py": INTERNAL_ERROR_CONFTEST, "test/test_passes.py": PASSING_TESTS}
    )

    result = full_run_of(project, project.work / "junit.xml")

    assert result.exit_code == 3


def test_the_output_holds_the_command_and_what_pytest_printed(
    project: Project,
) -> None:
    project.write({"test/test_response.py": RESPONSE_TESTS})

    result = full_run_of(project, project.work / "junit.xml", PILOT_OPTIONS)

    assert "bwrap" in result.output
    assert "5 failed" in result.output


def test_a_test_that_waits_for_input_fails_at_the_pilots_time_limit(
    project: Project,
) -> None:
    # Replaying 3: that test fails at the pilot's time limit, and the full run
    # ends.
    project.write({"test/test_waits.py": WAITING_TESTS})
    junit = project.work / "junit.xml"

    result = full_run_of(project, junit)

    assert outcomes(junit) == {
        "test.test_waits::test_waits_for_input": "failure",
        "test.test_waits::test_after": "passed",
    }
    assert result.failed == ("test/test_waits.py::test_waits_for_input",)
    assert result.exit_code == 1


def test_a_thread_that_a_test_left_blocked_does_not_keep_the_run_alive(
    project: Project,
) -> None:
    # Replaying 4: when the run ends, the pytest process ends with it.
    project.write({"test/test_thread.py": THREAD_TESTS})

    result = full_run_of(project, project.work / "junit.xml")

    assert result.exit_code == 0
    assert result.seconds < 60


def test_the_coverage_at_m_has_a_test_context_for_each_test_that_ran_the_package(
    project: Project,
) -> None:
    # Rule 8: test contexts, no static context, the pilot's package alone.
    project.write({"test/test_shop.py": COVERAGE_TESTS})
    coverage_file = project.work / "coverage-m"

    suite.record_coverage(
        pilot_with(),
        str(project.worktree),
        str(project.work),
        str(coverage_file),
        str(project.work / "junit-m.xml"),
    )

    data = CoverageData(basename=str(coverage_file))
    data.read()
    assert data.measured_contexts() - {""} == {
        "test/test_shop.py::test_tax|run",
        "test/test_shop.py::test_fails_at_m|run",
    }
    measured = {Path(name) for name in data.measured_files()}
    assert measured == {project.worktree / "shop" / "__init__.py"}


def test_the_coverage_at_m_runs_under_ctrace_and_keeps_the_failures_at_m(
    project: Project,
) -> None:
    # The coverage at M with COVERAGE_CORE=ctrace, its JUnit kept for the
    # failures at M.
    project.write({"test/test_shop.py": COVERAGE_TESTS})
    junit = project.work / "junit-m.xml"

    result = suite.record_coverage(
        pilot_with(),
        str(project.worktree),
        str(project.work),
        str(project.work / "coverage-m"),
        str(junit),
    )

    assert outcomes(junit) == {
        "test.test_shop::test_tax": "passed",
        "test.test_shop::test_fails_at_m": "failure",
        "test.test_shop::test_core": "passed",
    }
    assert result.failed == ("test/test_shop.py::test_fails_at_m",)


# Each kind of run, on the sandbox's tests.
RUNS: dict[str, Callable[[Project, Path], StepResult]] = {
    "full run": full_run_of,
    "coverage at M": lambda project, junit: suite.record_coverage(
        pilot_with(),
        str(project.worktree),
        str(project.work),
        str(project.work / "coverage-m"),
        str(junit),
    ),
    "rerun": lambda project, junit: suite.rerun(
        pilot_with(),
        str(project.worktree),
        str(project.work),
        SANDBOX_NODE_IDS,
        str(junit),
    ),
}


@pytest.mark.parametrize("run", list(RUNS))
def test_each_run_sees_no_network_no_home_and_none_of_the_harnesss_variables(
    run: str, project: Project
) -> None:
    # Invariants 2 and Rule 5. The home of these tests lies under /tmp, which a
    # run also hides, so this test alone cannot tell which hides it; task 9
    # checks the user's own home.
    write_sandbox_tests(project)
    junit = project.work / "junit.xml"

    result = RUNS[run](project, junit)

    expected = {f"test.test_sandbox::{name}": "passed" for name in SANDBOX_NAMES}
    assert outcomes(junit) == expected
    assert result.failed == ()


def test_a_run_past_its_time_limit_gives_no_exit_code(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    project.write({"test/test_passes.py": PASSING_TESTS})

    def run_out_of_time(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[Any]:
        command = args[0] if args else kwargs["args"]
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout") or 1)

    monkeypatch.setattr(subprocess, "run", run_out_of_time)

    result = full_run_of(project, project.work / "junit.xml")

    assert result.exit_code is None


def test_a_missing_bwrap_raises(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    # As when bubblewrap is not installed: every pull request would otherwise
    # end as a failed run.
    project.write({"test/test_passes.py": PASSING_TESTS})
    empty = project.work / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    with pytest.raises(Exception) as raised:  # noqa: PT011
        full_run_of(project, project.work / "junit.xml")

    assert not isinstance(raised.value, NotImplementedError)


def test_each_run_starts_bwrap_from_an_argument_list_with_a_time_limit(
    project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Rule 1: through subprocess.run, from an argument list and never a shell;
    # Rule 3: every process has a time limit; Rule 5: inside bubblewrap.
    project.write({"test/test_passes.py": PASSING_TESTS})
    runs = record_runs(monkeypatch)

    full_run_of(project, project.work / "junit.xml")

    assert runs, "the run started no process through subprocess.run"
    for run in runs:
        assert is_argument_list(run.command), run
        assert Path(run.command[0]).name == "bwrap", run
        assert not run.shell, run
        assert is_positive_number(run.timeout), run
