from dataclasses import dataclass


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
