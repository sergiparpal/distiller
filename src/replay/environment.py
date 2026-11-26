import os
import shlex
import subprocess
import time
from pathlib import Path

from replay.pilot import Pilot
from replay.steps import StepResult, step_result, text_of

# Builds a commit's environment in its worktree: the pilot's commands, run there
# in order, so that each reads that commit's own lock file, then the plugins of
# Rule 4, installed from the folder that holds the worktree, so that no
# required-version of the commit's own pyproject.toml refuses the uv that
# installs them (Slice 3). Both pilots' environments end in <worktree>/.venv:
# uv's by default, and poetry's through POETRY_VIRTUALENVS_IN_PROJECT. Every
# command runs through subprocess.run, from an argument list, with a time limit
# (Rules 1 and 3). The first command that fails ends the build with its exit
# code, and one that outlives its limit with none; a program that cannot start
# raises, as subprocess.run does, so that a missing uv or poetry stops the
# replay.

# The time limit of one command, in seconds: an install from PyPI took a few
# minutes in the samples of 2026-11-17.
SECONDS_PER_COMMAND = 1800

# Rule 4's plugins: coverage at the version that Slice 1's Deployment asks for,
# and pytest-cov and pytest-timeout at the versions of the pilots' latest lock
# files, fixed on 2026-11-19 before the window's first record. pytest-cov
# 7.1.0 recorded the coverage at M with every pytest of the window
# (notes/2026-11-19-window-replay.md).
COVERAGE_PLUGINS = ("coverage==7.16.2", "pytest-cov==7.1.0")
TIMEOUT_PLUGIN = "pytest-timeout==2.4.0"

# The harness's variables that no command of a build gets (Rule 4, note 95): a
# PYTHONPATH, relative as in PYTHONPATH=src, names a folder of the worktree,
# from which poetry imported the pilot's own code, and a VIRTUAL_ENV makes
# poetry install there and make no <worktree>/.venv, as poetry 2.5.1 did on
# 2026-11-20 (note 95).
DROPPED_VARIABLES = ("PYTHONPATH", "VIRTUAL_ENV")


def build(pilot: Pilot, worktree: str, *, for_coverage: bool) -> StepResult:
    started = time.monotonic()
    printed: list[str] = []
    for command, folder in _commands(pilot, worktree, for_coverage=for_coverage):
        exit_code = _run(command, folder, printed)
        if exit_code != 0:
            return step_result(exit_code, started, printed)
    return step_result(0, started, printed)


def _commands(
    pilot: Pilot, worktree: str, *, for_coverage: bool
) -> list[tuple[tuple[str, ...], str]]:
    # Each command with the folder it runs in: the pilot's commands in the
    # worktree, then one that installs the plugins, if there are any, from the
    # folder that holds the worktree, <work>/<project>/<number>/. uv would read a
    # required-version in the worktree's pyproject.toml, and refuse to run.
    commands = [(command, worktree) for command in pilot.environment]
    plugins = _plugins(pilot, for_coverage=for_coverage)
    if plugins:
        python = str(Path(worktree) / ".venv" / "bin" / "python")
        install = ("uv", "pip", "install", "--python", python, *plugins)
        commands.append((install, str(Path(worktree).parent)))
    return commands


def _plugins(pilot: Pilot, *, for_coverage: bool) -> list[str]:
    plugins: list[str] = []
    if for_coverage:
        plugins.extend(COVERAGE_PLUGINS)
    if pilot.adds_timeout_plugin:
        plugins.append(TIMEOUT_PLUGIN)
    return plugins


def _run(command: tuple[str, ...], folder: str, printed: list[str]) -> int | None:
    # Runs the command in folder, adds the command, and what it printed, to
    # printed, and gives its exit code, or None past its time limit. stderr goes
    # into stdout, so that the two keep the order in which the command printed
    # them.
    printed.append("$ " + shlex.join(command))
    try:
        result = subprocess.run(  # noqa: S603
            list(command),
            cwd=folder,
            env=_variables(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=SECONDS_PER_COMMAND,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        printed.append(text_of(error.stdout))
        printed.append(f"stopped at its time limit, {SECONDS_PER_COMMAND} s")
        return None
    printed.append(text_of(result.stdout))
    return result.returncode


def _variables() -> dict[str, str]:
    # The harness's own variables but the dropped ones, and poetry's
    # environment in the work tree.
    kept = {
        name: value
        for name, value in os.environ.items()
        if name not in DROPPED_VARIABLES
    }
    return {**kept, "POETRY_VIRTUALENVS_IN_PROJECT": "true"}
