from dataclasses import dataclass


@dataclass(frozen=True)
class ManifestLine:
    project: str
    pull_request: int | None  # None: to be found before the first record
    run: int
    run_started: str  # ISO 8601, UTC
    tested_head: str
    ci_job: str  # the job's outcome, as GitHub gave it on 2026-11-16


def read_manifest(path: str) -> list[ManifestLine]:
    raise NotImplementedError


def problems(lines: list[ManifestLine], others: list[ManifestLine]) -> list[str]:
    raise NotImplementedError


def missing_heads(lines: list[ManifestLine], clone: str) -> list[ManifestLine]:
    raise NotImplementedError
