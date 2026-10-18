# The seven git queries. Each runs `git -C checkout ...`.

Commit = str  # a full commit id
RepoPath = str  # "/"-separated, from the repository root


def is_checkout(checkout: str) -> bool:
    raise NotImplementedError


def is_shallow(checkout: str) -> bool:
    raise NotImplementedError


def resolve_commit(checkout: str, name: str) -> Commit | None:
    raise NotImplementedError


def merge_base(checkout: str, a: Commit, b: Commit) -> Commit | None:
    # None: no common history.
    raise NotImplementedError


def is_ancestor(checkout: str, ancestor: Commit, descendant: Commit) -> bool:
    raise NotImplementedError


def changed_paths(checkout: str, old: Commit, new: Commit) -> list[RepoPath]:
    raise NotImplementedError


def tree_files(checkout: str, commit: Commit) -> frozenset[RepoPath]:
    raise NotImplementedError
