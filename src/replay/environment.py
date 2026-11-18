from replay.pilot import Pilot
from replay.steps import StepResult


def build(pilot: Pilot, worktree: str, *, for_coverage: bool) -> StepResult:
    raise NotImplementedError
