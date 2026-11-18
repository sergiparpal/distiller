from replay.pilot import Pilot
from replay.steps import StepResult


def record_coverage(
    pilot: Pilot, worktree: str, work: str, coverage_file: str, junit_file: str
) -> StepResult:
    raise NotImplementedError


def full_run(pilot: Pilot, worktree: str, work: str, junit_file: str) -> StepResult:
    raise NotImplementedError


def rerun(
    pilot: Pilot, worktree: str, work: str, failed: tuple[str, ...], junit_file: str
) -> StepResult:
    raise NotImplementedError
