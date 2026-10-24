from dataclasses import dataclass

from distiller.git import Commit, RepoPath
from distiller.junit import Pair
from distiller.selection import Test


@dataclass(frozen=True)
class RunKey:
    head: str  # H's full commit id, or H as given
    junit_sha256: str | None


@dataclass(frozen=True)
class RejectedRecord:
    key: RunKey
    pr: int
    reason: str
    input_name: str


@dataclass(frozen=True)
class EvaluatedRecord:
    key: RunKey
    pr: int
    verdict: str
    merge_base: Commit
    coverage_commit: Commit
    selected_ms: int
    full_ms: int
    tests: int
    unmeasured: int
    tests_with_row: int
    tests_with_row_not_in_run: int
    floor_matched: bool
    rerun_given: bool
    not_reproduced: tuple[Pair, ...]
    failed_left_out: tuple[Test, ...]
    no_column: tuple[RepoPath, ...]
    import_only: tuple[RepoPath, ...]


Record = EvaluatedRecord | RejectedRecord


def encode(record: Record) -> bytes:
    raise NotImplementedError
