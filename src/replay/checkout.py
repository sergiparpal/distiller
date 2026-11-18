def has_commit(clone: str, commit: str) -> bool:
    raise NotImplementedError


def base_commit(clone: str, branch: str, started: str) -> str | None:
    raise NotImplementedError


def merge_base(clone: str, a: str, b: str) -> str | None:
    raise NotImplementedError


def add_worktree(clone: str, commit: str, folder: str) -> None:
    raise NotImplementedError


def remove_worktree(clone: str, folder: str) -> None:
    raise NotImplementedError
