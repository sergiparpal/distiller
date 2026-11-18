from dataclasses import dataclass


@dataclass(frozen=True)
class StepResult:
    exit_code: int | None  # None: stopped at its time limit
    seconds: float
    failed: tuple[str, ...]  # node ids, as the wrapper wrote them
    output: str  # each command that the step ran, and what it printed
