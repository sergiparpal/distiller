import os
import shlex
import subprocess
import time
from pathlib import Path

from replay.steps import StepResult, ToolInputs, step_result, text_of

# Runs the tool's evaluate as a process, as Slice 1's CI step did, from a
# checkout of this repository at a fixed commit: that checkout's .venv, as make
# install builds it, runs python -P -m distiller with the checkout's src/ as
# PYTHONPATH, so that the tool is the checkout's, whatever the harness's own
# distiller is. The tool's exit code is the step's: 0 evaluated or already
# recorded, 1 any other failure, 3 rejected. The run has a time limit (Rule 3),
# and a checkout with no .venv raises, as subprocess.run does.

# The time limit of one evaluation, in seconds: Slice 1's tool reads a coverage
# file and runs git, in seconds.
SECONDS_PER_EVALUATION = 600


def evaluate(tool: str, inputs: ToolInputs) -> StepResult:
    checkout = Path(tool)
    python = str(checkout / ".venv" / "bin" / "python")
    command = [python, "-P", "-m", "distiller", *_arguments(inputs)]
    started = time.monotonic()
    printed = ["$ " + shlex.join(command)]
    try:
        result = subprocess.run(  # noqa: S603
            command,
            cwd=checkout,
            env=_variables(checkout),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=SECONDS_PER_EVALUATION,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        printed.append(text_of(error.stdout))
        printed.append(f"stopped at its time limit, {SECONDS_PER_EVALUATION} s")
        return step_result(None, started, printed)
    printed.append(text_of(result.stdout))
    return step_result(result.returncode, started, printed)


def _arguments(inputs: ToolInputs) -> list[str]:
    # Step 6's command line, with --rerun and --floor-config only when given.
    arguments = ["evaluate", "--pr", str(inputs.pull_request), "--head", inputs.head]
    arguments += ["--base", inputs.base, "--coverage", inputs.coverage_file]
    arguments += ["--coverage-commit", inputs.m, "--junit", inputs.junit_file]
    if inputs.rerun_file is not None:
        arguments += ["--rerun", inputs.rerun_file]
    if inputs.floor_config is not None:
        arguments += ["--floor-config", inputs.floor_config]
    arguments += ["--records", inputs.records, "--checkout", inputs.checkout]
    return arguments


def _variables(checkout: Path) -> dict[str, str]:
    # The harness's own variables, git's settings among them, with the
    # checkout's src/ alone on PYTHONPATH.
    return {**os.environ, "PYTHONPATH": str(checkout / "src")}
