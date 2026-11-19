import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from replay import environment
from replay.pilot import Pilot

# Each test builds an environment in a worktree of tmp_path, with no network:
# the pilot's commands are local scripts that note what they see, and a fake
# uv first on PATH notes its arguments instead of installing. The tests watch
# build from outside: the commands that ran, where and in what order, the
# plugins it installed, and the StepResult it gives. Decided by the user on
# 2026-11-18, for the SPEC: StepResult has an output, each command that the step
# ran and what it printed, which the harness writes to the log; build runs the
# pilot's commands with POETRY_VIRTUALENVS_IN_PROJECT=true, so that both
# pilots' environments are <worktree>/.venv, then installs the plugins with
# uv pip install --python <worktree>/.venv/bin/python, coverage at 7.16.2 and
# the other two at versions that task 9 fixes; and it stops at the first
# command that fails, with its exit code, or with None past its time limit,
# while a program that cannot start makes it raise.

# A command of a pilot's environment that notes, in the log that both it and
# the fake uv write, its name, its folder, the variable that puts poetry's
# environment in the work tree, and the lock file it finds there; then prints
# a line on stdout and one on stderr.
RECORDER = """\
import json
import os
import sys
from pathlib import Path

name, log = sys.argv[1], sys.argv[2]
lock = Path("uv.lock")
entry = {
    "name": name,
    "cwd": os.getcwd(),
    "in_project": os.environ.get("POETRY_VIRTUALENVS_IN_PROJECT"),
    "lock": lock.read_text(encoding="utf-8") if lock.exists() else None,
}
with open(log, "a", encoding="utf-8") as file:
    file.write(json.dumps(entry) + "\\n")
print(name + " printed this")
print(name + " warned this", file=sys.stderr)
"""

# A uv that notes its arguments in the same log, installs nothing, and exits
# with FAKE_UV_EXIT, 0 when unset.
FAKE_UV = """\
#!{python} -I
import json
import os
import sys

with open({log!r}, "a", encoding="utf-8") as file:
    file.write(json.dumps({{"name": "uv", "argv": sys.argv[1:]}}) + "\\n")
raise SystemExit(int(os.environ.get("FAKE_UV_EXIT", "0")))
"""

# A command of a pilot's environment that notes, in the file it is given, the
# two variables that would make it import or install from elsewhere than the
# worktree, the one that puts poetry's environment there, and one of the
# tests' own.
VARIABLES_RECORDER = """\
import json
import os
import sys

names = (
    "PYTHONPATH",
    "VIRTUAL_ENV",
    "POETRY_VIRTUALENVS_IN_PROJECT",
    "REPLAY_TESTS_CANARY",
)
with open(sys.argv[1], "a", encoding="utf-8") as file:
    file.write(json.dumps({name: os.environ.get(name) for name in names}) + "\\n")
"""


@dataclass(frozen=True)
class Setup:
    """A worktree with a lock file, the scripts, and the log they write."""

    worktree: Path
    recorder: Path
    log: Path

    def record(self, name: str) -> tuple[str, ...]:
        """A command that notes what it sees under name."""
        return (sys.executable, str(self.recorder), name, str(self.log))


@dataclass(frozen=True)
class Run:
    """A call of subprocess.run: what it was given to run, and two options."""

    command: Any  # as given: an argument list, or a string for a shell
    shell: Any
    timeout: Any


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    log = tmp_path / "steps.jsonl"
    recorder = tmp_path / "recorder.py"
    recorder.write_text(RECORDER, encoding="utf-8")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(
        FAKE_UV.format(python=sys.executable, log=str(log)), encoding="utf-8"
    )
    fake_uv.chmod(0o700)
    # The fake uv comes first, so that no test reaches the real one, or PyPI.
    monkeypatch.setenv(
        "PATH", f"{fake_bin}:{Path(sys.executable).parent}:/usr/bin:/bin"
    )
    monkeypatch.delenv("FAKE_UV_EXIT", raising=False)
    monkeypatch.delenv("POETRY_VIRTUALENVS_IN_PROJECT", raising=False)
    worktree = new_worktree(tmp_path / "worktree", "the head's lock\n")
    return Setup(worktree=worktree, recorder=recorder, log=log)


def new_worktree(path: Path, lock: str) -> Path:
    path.mkdir()
    (path / "uv.lock").write_text(lock, encoding="utf-8")
    return path


def pilot_with(*commands: tuple[str, ...], adds_timeout_plugin: bool = False) -> Pilot:
    return Pilot(
        project="urllib3",
        repository="urllib3/urllib3",
        base_branch="main",
        job="Ubuntu 3.12",
        python="3.12",
        environment=commands,
        pytest=(),
        coverage_source="urllib3",
        seconds_per_test=120,
        adds_timeout_plugin=adds_timeout_plugin,
        floor_config=None,
    )


def failing(code: int) -> tuple[str, ...]:
    """A command that exits with code."""
    return (sys.executable, "-c", f"raise SystemExit({code})")


def sleeping(seconds: float) -> tuple[str, ...]:
    return (sys.executable, "-c", f"import time; time.sleep({seconds})")


def entries(log: Path) -> list[dict[str, Any]]:
    """What the commands and the fake uv noted, in order."""
    if not log.exists():
        return []
    lines = log.read_text(encoding="utf-8").splitlines()
    return [cast("dict[str, Any]", json.loads(line)) for line in lines]


def uv_calls(log: Path) -> list[list[str]]:
    """The arguments of each call of the fake uv, in order."""
    return [entry["argv"] for entry in entries(log) if entry["name"] == "uv"]


def requirements_installed(log: Path) -> list[str]:
    """Every requirement that a uv pip install named, in order."""
    requirements: list[str] = []
    for argv in uv_calls(log):
        assert "pip" in argv, argv
        install = argv.index("pip") + 1
        assert argv[install] == "install", argv
        rest = argv[install + 1 :]
        index = 0
        while index < len(rest):
            if rest[index] == "--python":
                index += 2  # the option and its value
            elif rest[index].startswith("-"):
                index += 1
            else:
                requirements.append(rest[index])
                index += 1
    return requirements


def python_of(argv: list[str]) -> str | None:
    """The interpreter that a uv pip install names with --python."""
    for index, argument in enumerate(argv):
        if argument == "--python" and index + 1 < len(argv):
            return argv[index + 1]
        if argument.startswith("--python="):
            return argument.removeprefix("--python=")
    return None


def named(requirements: list[str], package: str) -> bool:
    """Whether one of the requirements is of the package, at any version."""
    return package in [package_of(requirement) for requirement in requirements]


def package_of(requirement: str) -> str:
    """The package that a requirement names, before its version or extras."""
    return re.split(r"[=<>~!\[;@ ]", requirement, maxsplit=1)[0]


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


def test_the_pilots_commands_run_in_order_in_the_worktree(setup: Setup) -> None:
    pilot = pilot_with(setup.record("first"), setup.record("second"))

    environment.build(pilot, str(setup.worktree), for_coverage=False)

    noted = entries(setup.log)
    assert [entry["name"] for entry in noted] == ["first", "second"]
    assert all(Path(entry["cwd"]) == setup.worktree for entry in noted)


def test_each_environment_is_built_from_its_own_commits_lock_file(
    setup: Setup, tmp_path: Path
) -> None:
    # Replaying 2: a tested head whose lock file differs from its M's.
    m_worktree = new_worktree(tmp_path / "m", "M's lock\n")
    pilot = pilot_with(setup.record("sync"))

    environment.build(pilot, str(m_worktree), for_coverage=True)
    environment.build(pilot, str(setup.worktree), for_coverage=False)

    seen = [entry["lock"] for entry in entries(setup.log) if entry["name"] == "sync"]
    assert seen == ["M's lock\n", "the head's lock\n"]


def test_the_commands_put_poetrys_environment_in_the_work_tree(setup: Setup) -> None:
    pilot = pilot_with(setup.record("install"))

    environment.build(pilot, str(setup.worktree), for_coverage=False)

    (noted,) = entries(setup.log)
    assert noted["in_project"] == "true"


def test_the_pilots_commands_get_neither_pythonpath_nor_virtual_env(
    setup: Setup, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Note 95: a harness started with PYTHONPATH=src made poetry, run in a
    # worktree of poetry's, import that worktree's own src/. Decided by the user
    # on 2026-11-19, for the SPEC's Rule 4: build gives the pilot's commands
    # neither variable, while the harness's other variables still reach them.
    recorder = tmp_path / "variables.py"
    recorder.write_text(VARIABLES_RECORDER, encoding="utf-8")
    noted = tmp_path / "variables.jsonl"
    monkeypatch.setenv("PYTHONPATH", "src")
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "activated"))
    monkeypatch.setenv("REPLAY_TESTS_CANARY", "kept")
    pilot = pilot_with((sys.executable, str(recorder), str(noted)))

    result = environment.build(pilot, str(setup.worktree), for_coverage=False)

    assert result.exit_code == 0
    lines = noted.read_text(encoding="utf-8").splitlines()
    (seen,) = [cast("dict[str, Any]", json.loads(line)) for line in lines]
    assert seen == {
        "PYTHONPATH": None,
        "VIRTUAL_ENV": None,
        "POETRY_VIRTUALENVS_IN_PROJECT": "true",
        "REPLAY_TESTS_CANARY": "kept",
    }


def test_a_built_environment_gives_exit_code_0_and_no_failed_test(
    setup: Setup,
) -> None:
    pilot = pilot_with(setup.record("sync"))

    result = environment.build(pilot, str(setup.worktree), for_coverage=True)

    assert result.exit_code == 0
    assert result.failed == ()


def test_the_seconds_are_the_whole_builds(setup: Setup) -> None:
    pilot = pilot_with(sleeping(0.2), sleeping(0.2))

    result = environment.build(pilot, str(setup.worktree), for_coverage=False)

    assert result.seconds >= 0.4


def test_the_output_holds_each_command_and_what_it_printed(setup: Setup) -> None:
    pilot = pilot_with(setup.record("first"), setup.record("second"))

    result = environment.build(pilot, str(setup.worktree), for_coverage=False)

    assert "recorder.py" in result.output  # the command, and not only its output
    for name in ("first", "second"):
        assert f"{name} printed this" in result.output
        assert f"{name} warned this" in result.output


def test_ms_environment_gets_coverage_7_16_2_and_pytest_cov(setup: Setup) -> None:
    pilot = pilot_with(setup.record("sync"))

    environment.build(pilot, str(setup.worktree), for_coverage=True)

    requirements = requirements_installed(setup.log)
    assert "coverage==7.16.2" in requirements
    assert named(requirements, "pytest-cov")
    assert not named(requirements, "pytest-timeout")


def test_a_poetry_environment_gets_pytest_timeout(setup: Setup) -> None:
    pilot = pilot_with(setup.record("install"), adds_timeout_plugin=True)

    environment.build(pilot, str(setup.worktree), for_coverage=False)

    requirements = requirements_installed(setup.log)
    assert named(requirements, "pytest-timeout")
    assert not named(requirements, "coverage")
    assert not named(requirements, "pytest-cov")


def test_ms_environment_of_poetry_gets_the_three_plugins(setup: Setup) -> None:
    pilot = pilot_with(setup.record("install"), adds_timeout_plugin=True)

    environment.build(pilot, str(setup.worktree), for_coverage=True)

    requirements = requirements_installed(setup.log)
    assert "coverage==7.16.2" in requirements
    assert named(requirements, "pytest-cov")
    assert named(requirements, "pytest-timeout")


def test_a_tested_heads_environment_of_urllib3_gets_no_plugin(setup: Setup) -> None:
    pilot = pilot_with(setup.record("sync"))

    environment.build(pilot, str(setup.worktree), for_coverage=False)

    assert uv_calls(setup.log) == []


@pytest.mark.parametrize(
    ("for_coverage", "adds_timeout_plugin"),
    [(True, False), (False, True), (True, True)],
    ids=["coverage", "timeout", "both"],
)
def test_the_plugins_go_into_the_worktrees_environment_after_its_commands(
    setup: Setup, *, for_coverage: bool, adds_timeout_plugin: bool
) -> None:
    pilot = pilot_with(setup.record("sync"), adds_timeout_plugin=adds_timeout_plugin)

    environment.build(pilot, str(setup.worktree), for_coverage=for_coverage)

    noted = entries(setup.log)
    assert noted[0]["name"] == "sync"
    calls = uv_calls(setup.log)
    assert calls
    expected = str(setup.worktree / ".venv" / "bin" / "python")
    assert all(python_of(argv) == expected for argv in calls)


def test_the_output_names_each_plugin_installed(setup: Setup) -> None:
    # Rule 4: the log names each.
    pilot = pilot_with(setup.record("install"), adds_timeout_plugin=True)

    result = environment.build(pilot, str(setup.worktree), for_coverage=True)

    for plugin in ("coverage==7.16.2", "pytest-cov", "pytest-timeout"):
        assert plugin in result.output


def test_a_command_that_fails_ends_the_build_with_its_exit_code(setup: Setup) -> None:
    pilot = pilot_with(setup.record("first"), failing(3), setup.record("third"))

    result = environment.build(pilot, str(setup.worktree), for_coverage=True)

    assert result.exit_code == 3
    # Neither the commands after it nor the plugins run.
    assert [entry["name"] for entry in entries(setup.log)] == ["first"]


def test_a_plugin_install_that_fails_ends_the_build_with_its_exit_code(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_UV_EXIT", "2")
    pilot = pilot_with(setup.record("sync"))

    result = environment.build(pilot, str(setup.worktree), for_coverage=True)

    assert result.exit_code == 2


def test_a_command_past_its_time_limit_ends_the_build_with_no_exit_code(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[object] = []

    def run_out_of_time(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[Any]:
        command = args[0] if args else kwargs["args"]
        started.append(command)
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout") or 1)

    monkeypatch.setattr(subprocess, "run", run_out_of_time)
    pilot = pilot_with(setup.record("first"), setup.record("second"))

    result = environment.build(pilot, str(setup.worktree), for_coverage=True)

    assert result.exit_code is None
    assert len(started) == 1  # the build stops at the command that ran out


def test_a_program_that_cannot_start_raises(setup: Setup) -> None:
    # As when uv or poetry is not installed: every pull request would otherwise
    # be listed as not replayed, and the replay end with exit 0.
    pilot = pilot_with(("no-such-program-for-the-replay-tests",))

    with pytest.raises(Exception) as raised:  # noqa: PT011
        environment.build(pilot, str(setup.worktree), for_coverage=False)

    assert not isinstance(raised.value, NotImplementedError)


@pytest.mark.parametrize(
    ("for_coverage", "adds_timeout_plugin"),
    [(False, False), (True, True)],
    ids=["commands alone", "commands and plugins"],
)
def test_each_process_runs_from_an_argument_list_with_a_time_limit(
    setup: Setup,
    monkeypatch: pytest.MonkeyPatch,
    *,
    for_coverage: bool,
    adds_timeout_plugin: bool,
) -> None:
    # Rule 1: through subprocess.run, from an argument list and never a shell;
    # Rule 3: every process has a time limit.
    pilot = pilot_with(setup.record("sync"), adds_timeout_plugin=adds_timeout_plugin)
    runs = record_runs(monkeypatch)

    environment.build(pilot, str(setup.worktree), for_coverage=for_coverage)

    assert runs, "build ran no process through subprocess.run"
    for run in runs:
        assert is_argument_list(run.command), run
        assert not run.shell, run
        assert is_positive_number(run.timeout), run
