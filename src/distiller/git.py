import os
import subprocess

# The seven git queries. Each runs `git -C checkout ...` with only the
# subcommands and options under "Checked" in the SPEC, all of which only read.
# When git fails in a way that is not one of a query's answers, the query
# raises CalledProcessError, through check_returncode, rather than guess one.

Commit = str  # a full commit id
RepoPath = str  # "/"-separated, from the repository root


def is_checkout(checkout: str) -> bool:
    # git prints true inside a work tree and false inside .git. Outside any
    # repository, and at a path that does not exist, it fails and prints
    # nothing.
    result = _run_git(checkout, "rev-parse", "--is-inside-work-tree")
    return _printed_line(result) == "true"


def is_shallow(checkout: str) -> bool:
    result = _run_git(checkout, "rev-parse", "--is-shallow-repository")
    result.check_returncode()
    return _printed_line(result) == "true"


def resolve_commit(checkout: str, name: str) -> Commit | None:
    # --end-of-options keeps a name such as --all from being read as an
    # option, and ^{commit} turns an annotated tag into its commit and fails
    # for a tree or a blob. git exits with 1 for most names that name no
    # commit, but with 128 for some, such as HEAD@{99} with a shorter reflog.
    result = _run_git(
        checkout,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        name + "^{commit}",
    )
    if result.returncode != 0:
        return None
    return _printed_line(result)


def merge_base(checkout: str, a: Commit, b: Commit) -> Commit | None:
    # With several best common ancestors, git prints one of them.
    result = _run_git(checkout, "merge-base", a, b)
    if result.returncode == 1:
        return None  # no common history: git prints nothing
    result.check_returncode()
    return _printed_line(result)


def is_ancestor(checkout: str, ancestor: Commit, descendant: Commit) -> bool:
    # git exits with 0 when ancestor is descendant or one of its ancestors,
    # and with 1 when it is neither.
    result = _run_git(checkout, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode == 1:
        return False
    result.check_returncode()
    return True


def changed_paths(checkout: str, old: Commit, new: Commit) -> list[RepoPath]:
    # --no-renames lists a renamed file under both of its names, --no-relative
    # lists paths from the root even with diff.relative set, and -z leaves
    # them unquoted.
    result = _run_git(
        checkout,
        "diff",
        "--name-only",
        "--no-renames",
        "--no-relative",
        "-z",
        old,
        new,
    )
    result.check_returncode()
    return _paths_of(result.stdout)


def tree_files(checkout: str, commit: Commit) -> frozenset[RepoPath]:
    # -r lists the files in every subdirectory, and --full-tree lists them
    # from the root even when the checkout is a subdirectory.
    result = _run_git(
        checkout, "ls-tree", "-r", "--name-only", "-z", "--full-tree", commit
    )
    result.check_returncode()
    return frozenset(_paths_of(result.stdout))


def _run_git(checkout: str, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    # git by name, found through PATH, with an argument list and no shell.
    # Its stdout and stderr are captured, so nothing it prints reaches the
    # tool's own.
    return subprocess.run(  # noqa: S603
        ["git", "-C", checkout, *arguments],  # noqa: S607
        capture_output=True,
        check=False,
    )


def _printed_line(result: subprocess.CompletedProcess[bytes]) -> str:
    # The one line that git printed, without its newline.
    return os.fsdecode(result.stdout).strip()


def _paths_of(output: bytes) -> list[RepoPath]:
    # With -z, git ends each path with a NUL, so splitting leaves an empty
    # piece after the last one. os.fsdecode decodes even a path that is not
    # UTF-8, and os.fsencode gives its bytes back.
    return [os.fsdecode(path) for path in output.split(b"\0") if path]
