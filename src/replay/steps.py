import time
from dataclasses import dataclass

# What the steps of a replay share: the result that each step gives the
# harness, the inputs of the tool's step, and the two functions with which
# environment, suite and tool turn what a step printed into its result. steps
# imports no other module of replay.


@dataclass(frozen=True)
class StepResult:
    exit_code: int | None  # None: stopped at its time limit
    seconds: float
    failed: tuple[str, ...]  # node ids, as the wrapper wrote them
    output: str  # each command that the step ran, and what it printed


@dataclass(frozen=True)
class ToolInputs:
    pull_request: int
    head: str
    base: str
    m: str
    coverage_file: str
    junit_file: str
    rerun_file: str | None
    floor_config: str | None
    records: str
    checkout: str


def text_of(output: bytes | None) -> str:
    # What a process printed, decoded so that no byte stops the log.
    if output is None:
        return ""
    return output.decode("utf-8", errors="replace")


def step_result(
    exit_code: int | None,
    started: float,
    printed: list[str],
    failed: tuple[str, ...] = (),
) -> StepResult:
    # A step that started at started, a reading of time.monotonic(), and ends
    # now; printed holds each command that it ran, and what that printed.
    return StepResult(
        exit_code=exit_code,
        seconds=time.monotonic() - started,
        failed=failed,
        output="\n".join(printed),
    )
