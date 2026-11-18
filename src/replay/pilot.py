from dataclasses import dataclass


@dataclass(frozen=True)
class Pilot:
    project: str
    repository: str
    base_branch: str
    job: str
    python: str
    environment: tuple[tuple[str, ...], ...]
    pytest: tuple[str, ...]
    coverage_source: str
    seconds_per_test: int
    adds_timeout_plugin: bool
    floor_config: str | None


def read_pilot(path: str) -> Pilot:
    raise NotImplementedError
