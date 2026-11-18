import os
import subprocess
from datetime import datetime

# Runs git on a pilot's clone: three queries that only read it, and adding and
# removing the worktrees where the harness checks commits out, so that the
# clone's own checked-out commit and work tree never change (Invariant 3). git
# runs by name, from an argument list, never through a shell, and with a time
# limit (Rules 1 and 3). When git fails in a way that is not one of a query's
# answers, the function raises CalledProcessError, through check_returncode,
# and a git that outlives its limit raises TimeoutExpired: no failure reads as
# an answer.

# The time limit of one git command, in seconds. The queries take well under
# one; adding or removing a pilot's worktree, with an environment built in it,
# a few.
GIT_SECONDS = 300

# git's exit code when its answer is no: no such commit for rev-parse --verify
# --quiet, and no common history for merge-base.
NO = 1


def has_commit(clone: str, commit: str) -> bool:
    # ^{commit} makes git read the object, so that an id that names no object
    # here, or names a tree or a blob, is no commit; --end-of-options keeps a
    # name such as --all from being read as an option.
    result = _run_git(
        clone,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        commit + "^{commit}",
    )
    if result.returncode == NO:
        return False
    result.check_returncode()
    return True


def base_commit(clone: str, branch: str, started: str) -> str | None:
    # started is ISO 8601 with its offset, as the manifest writes it, with a Z
    # for UTC. --first-parent walks only the commits that were the branch's tip,
    # one after another, from its last: a pull request's commits, merged into
    # it later, are not among them. --timestamp gives each one's committer date,
    # in seconds since 1970, an instant whatever its time zone.
    start = datetime.fromisoformat(started).timestamp()
    result = _run_git(
        clone,
        "rev-list",
        "--first-parent",
        "--timestamp",
        "--end-of-options",
        branch,
        "--",
    )
    result.check_returncode()
    for line in _printed_lines(result):
        committed, commit = line.split()
        if int(committed) < start:
            return commit
    return None  # every commit of the branch came after the run started


def merge_base(clone: str, a: str, b: str) -> str | None:
    # With several best common ancestors, git prints one of them: the one
    # that the tool's own git merge-base prints.
    result = _run_git(clone, "merge-base", a, b)
    if result.returncode == NO:
        return None  # no common history: git prints nothing
    result.check_returncode()
    return _printed_line(result)


def add_worktree(clone: str, commit: str, folder: str) -> None:
    # --detach checks the commit out on no branch, so that no ref of the clone
    # changes, and the commit that the clone has checked out may be added too.
    result = _run_git(clone, "worktree", "add", "--quiet", "--detach", folder, commit)
    result.check_returncode()


def remove_worktree(clone: str, folder: str) -> None:
    # --force removes a worktree whatever it holds: the environment built in
    # it and what the suite wrote, which git does not track.
    result = _run_git(clone, "worktree", "remove", "--force", folder)
    result.check_returncode()


def _run_git(clone: str, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    # git by name, found through PATH, with an argument list, no shell and a
    # time limit. Its stdout and stderr are captured.
    return subprocess.run(  # noqa: S603
        ["git", "-C", clone, *arguments],  # noqa: S607
        capture_output=True,
        timeout=GIT_SECONDS,
        check=False,
    )


def _printed_line(result: subprocess.CompletedProcess[bytes]) -> str:
    # The one line that git printed, without its newline.
    return os.fsdecode(result.stdout).strip()


def _printed_lines(result: subprocess.CompletedProcess[bytes]) -> list[str]:
    return os.fsdecode(result.stdout).splitlines()
