from distiller.git import RepoPath

DEFAULT_PATTERNS: tuple[str, ...]


# The defaults, then the file's; raises Rejected.
def read_floor(path: str | None) -> tuple[str, ...]:
    raise NotImplementedError


def matches(pattern: str, path: RepoPath) -> bool:
    raise NotImplementedError


def floor_hits(
    patterns: tuple[str, ...], changed: list[RepoPath]
) -> list[tuple[str, RepoPath]]:
    raise NotImplementedError
