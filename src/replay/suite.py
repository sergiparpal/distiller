import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from replay.pilot import Pilot
from replay.steps import StepResult

# Runs a pilot's tests in a worktree's environment, inside bubblewrap and
# through the wrapper of Rule 6: the coverage at M, the full run and the rerun,
# each writing its JUnit file. A run sees no network but the loopback, neither
# the user's home nor /tmp, /run and /mnt but the work directory, reads nothing
# on stdin, and gets no variable of the harness's but HOME, PATH, LANG and
# coverage's (Rule 5). Each test has the pilot's time limit, through
# pytest-timeout, and the run one of its own (Rule 3); a missing bwrap raises,
# as subprocess.run does.

# The time limit of one run, in seconds. The pilots' suites took minutes in the
# samples of 2026-11-17, and each test has its own limit besides.
SECONDS_PER_RUN = 7200

# Hidden like the user's home, when they exist: /run holds the sockets of the
# user's session, and /mnt, on WSL, the Windows drives.
HIDDEN_DIRECTORIES = ("/tmp", "/run", "/mnt")  # noqa: S108, emptied, never written to

# The wrapper of Rule 6, which the run's Python runs from the work directory.
# It notes the node id of each test that failed or erred as soon as a plugin
# hears of it, and ends the process with os._exit once pytest returns, so that
# no thread that a test left behind keeps it alive.
WRAPPER = """\
# Written by replay: runs pytest, notes the tests that failed or erred, and
# ends the process as soon as pytest returns.
import os
import sys

import pytest

failed_file, *arguments = sys.argv[1:]


class FailedTests:
    def pytest_runtest_logreport(self, report):
        if report.failed:
            with open(failed_file, "a", encoding="utf-8") as file:
                file.write(report.nodeid + "\\n")


exit_code = pytest.main(arguments, plugins=[FailedTests()])
sys.stdout.flush()
sys.stderr.flush()
os._exit(int(exit_code))
"""


@dataclass(frozen=True)
class _Kind:
    """What a kind of run adds to pytest's arguments and to its variables."""

    arguments: tuple[str, ...]
    variables: dict[str, str]


def record_coverage(
    pilot: Pilot, worktree: str, work: str, coverage_file: str, junit_file: str
) -> StepResult:
    # Rule 8: test contexts, under ctrace, into the coverage file.
    kind = _Kind(
        arguments=(
            f"--cov={pilot.coverage_source}",
            "--cov-context=test",
            "--cov-report=",
        ),
        variables={"COVERAGE_CORE": "ctrace", "COVERAGE_FILE": coverage_file},
    )
    return _run(pilot, worktree, work, junit_file, kind)


def full_run(pilot: Pilot, worktree: str, work: str, junit_file: str) -> StepResult:
    return _run(pilot, worktree, work, junit_file, _Kind(arguments=(), variables={}))


def rerun(
    pilot: Pilot, worktree: str, work: str, failed: tuple[str, ...], junit_file: str
) -> StepResult:
    # Rule 7: the tests that failed in the full run, once more.
    kind = _Kind(arguments=failed, variables={})
    return _run(pilot, worktree, work, junit_file, kind)


def _run(
    pilot: Pilot, worktree: str, work: str, junit_file: str, kind: _Kind
) -> StepResult:
    work_folder = Path(work)
    (work_folder / "home").mkdir(parents=True, exist_ok=True)
    wrapper = work_folder / "replay-wrapper.py"
    wrapper.write_text(WRAPPER, encoding="utf-8")
    failed_file = work_folder / f"{Path(junit_file).name}.failed"
    failed_file.unlink(missing_ok=True)
    command = [
        *_sandbox(Path(worktree), work_folder, kind.variables),
        str(Path(worktree) / ".venv" / "bin" / "python"),
        str(wrapper),
        str(failed_file),
        *pilot.pytest,
        f"--timeout={pilot.seconds_per_test}",
        f"--junitxml={junit_file}",
        *kind.arguments,
    ]
    started = time.monotonic()
    printed = ["$ " + shlex.join(command)]
    try:
        result = subprocess.run(  # noqa: S603
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=SECONDS_PER_RUN,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        printed.append(_text_of(error.stdout))
        printed.append(f"stopped at its time limit, {SECONDS_PER_RUN} s")
        return _result(None, started, failed_file, printed)
    printed.append(_text_of(result.stdout))
    return _result(result.returncode, started, failed_file, printed)


def _sandbox(worktree: Path, work: Path, variables: dict[str, str]) -> list[str]:
    # Everything read-only and every namespace apart, the network's included, so
    # that only the loopback is left; then the home and the hidden directories
    # emptied, and the work directory, where the worktree is, writable.
    arguments = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session"]
    arguments += ["--ro-bind", "/", "/", "--tmpfs", str(Path.home())]
    for hidden in filter(os.path.isdir, HIDDEN_DIRECTORIES):
        arguments += ["--tmpfs", hidden]
    arguments += ["--bind", str(work), str(work), "--dev", "/dev", "--proc", "/proc"]
    arguments += ["--clearenv", "--chdir", str(worktree)]
    for name, value in _variables(worktree, work, variables).items():
        arguments += ["--setenv", name, value]
    return arguments


def _variables(worktree: Path, work: Path, variables: dict[str, str]) -> dict[str, str]:
    # The only variables that a run gets: its HOME in the work directory, the
    # environment's bin first on its PATH, a UTF-8 locale, and the run's own.
    environment_bin = worktree / ".venv" / "bin"
    path = os.pathsep.join((str(environment_bin), "/usr/local/bin", "/usr/bin", "/bin"))
    return {"HOME": str(work / "home"), "PATH": path, "LANG": "C.UTF-8", **variables}


def _text_of(output: bytes | None) -> str:
    # What the run printed, decoded so that no byte stops the log.
    if output is None:
        return ""
    return output.decode("utf-8", errors="replace")


def _failed_of(failed_file: Path) -> tuple[str, ...]:
    # The node ids that the wrapper noted, once each, in its order: a test can
    # fail in its call and again in its teardown.
    if not failed_file.exists():
        return ()
    names = failed_file.read_text(encoding="utf-8").splitlines()
    return tuple(dict.fromkeys(names))


def _result(
    exit_code: int | None, started: float, failed_file: Path, printed: list[str]
) -> StepResult:
    return StepResult(
        exit_code=exit_code,
        seconds=time.monotonic() - started,
        failed=_failed_of(failed_file),
        output="\n".join(printed),
    )
