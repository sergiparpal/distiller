from dataclasses import dataclass


# One field per option of the evaluate command, as given, except that rootdir
# is normalized: "" is the repository root.
@dataclass(frozen=True)
class RunArgs:
    pr: int
    head: str
    base: str
    coverage: str
    coverage_commit: str
    junit: str
    rerun: str | None
    rootdir: str
    floor_config: str | None
    records: str
    checkout: str


def run(args: RunArgs) -> int:
    raise NotImplementedError
