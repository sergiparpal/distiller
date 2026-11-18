import os
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from replay import checkout

# Each test builds a pilot's clone in tmp_path, as the harness finds one: the
# base branch, main, checked out, and pull requests' heads kept by refs of their
# own, refs/window/<run id>, on no branch. The tests watch checkout from
# outside: what it returns or raises, how it runs git, and what the clone and
# the work directory hold after. Decided by the user on 2026-11-18, for the
# SPEC: the base commit is the last commit along the base branch's first
# parents whose committer date is before the run started, the dates compared
# as instants, whatever their time zone; a git that fails raises rather than
# answers, as in Slice 1 (note 7); and every git that checkout runs has a time
# limit (Rule 3).

# The real git, found before any test changes the environment.
GIT = shutil.which("git") or "git"

# Commits made with no date of their own are made at this time.
COMMIT_DATE = "2026-03-01T10:00:00+00:00"

# A run's start as the manifest writes it, in UTC with a Z: this run started
# after main's second commit and before its third.
RUN_STARTED = "2026-03-03T12:00:00Z"

# A run that started before main's first commit.
BEFORE_EVERY_COMMIT = "2026-02-01T00:00:00Z"

# A commit id that names no object in any clone of these tests.
UNKNOWN_COMMIT = "0123456789abcdef0123456789abcdef01234567"


@dataclass(frozen=True)
class Clone:
    """A pilot's clone, with main checked out, and a work directory beside it.

    main's three commits were made on 2026-03-01, 03-02 and 03-05. The head of
    run 1001 forks from main's first commit, and the commit of run 1002 shares
    no history with main: refs/window/<run id> alone keeps each.
    """

    path: Path
    work: Path  # the harness's work directory, where the worktrees go
    outside: Path  # a directory in no repository
    first: str
    second: str
    third: str
    head: str  # made on 2026-03-03, kept at refs/window/1001
    unrelated: str  # kept at refs/window/1002


@dataclass(frozen=True)
class Run:
    """A call of subprocess.run: what it was given to run, and two options."""

    command: Any  # as given: an argument list, or a string for a shell
    shell: Any
    timeout: Any


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep git to the repositories' own configuration and the tests' identity.

    Stop runs these tests with neither the user's home directory nor the
    network, so they rely on neither.
    """
    # None of the caller's GIT_ variables, which can point git at another
    # repository or add configuration of their own.
    for name in list(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    # git looks for no repository above tmp_path.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Distiller Tests")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "tests@distiller.invalid")
    monkeypatch.setenv("GIT_AUTHOR_DATE", COMMIT_DATE)
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Distiller Tests")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "tests@distiller.invalid")
    monkeypatch.setenv("GIT_COMMITTER_DATE", COMMIT_DATE)


@pytest.fixture(autouse=True)
def time_zone_behind_utc() -> Iterator[None]:
    """Run each test 5 hours behind UTC, as a machine elsewhere would.

    A run's start read as local time rather than as UTC then finds another
    base commit. Python reads TZ again only at time.tzset(), and git each time
    it starts.
    """
    saved = os.environ.get("TZ")
    os.environ["TZ"] = "<-05>5"  # POSIX: add 5 hours to the local time for UTC
    time.tzset()
    yield
    if saved is None:
        del os.environ["TZ"]
    else:
        os.environ["TZ"] = saved
    time.tzset()


@pytest.fixture
def clone(tmp_path: Path) -> Clone:
    path = new_repository(tmp_path / "clone")
    first = commit_at(
        path,
        "2026-03-01T10:00:00+00:00",
        "Open the shop",
        {"README.md": "A shop.\n", "shop/tax.py": "RATE = 21\n"},
    )
    second = commit_at(
        path,
        "2026-03-02T10:00:00+00:00",
        "Lower the rate",
        {"shop/tax.py": "RATE = 10\n"},
    )
    third = commit_at(
        path,
        "2026-03-05T10:00:00+00:00",
        "Describe the shop",
        {"README.md": "A small shop.\n"},
    )
    # A pull request's head, made from main's first commit, and kept as the
    # user's clones keep the window's heads: by its run's ref, on no branch.
    run_git(path, "switch", "--quiet", "--detach", first)
    head = commit_at(
        path,
        "2026-03-03T10:00:00+00:00",
        "Add a report",
        {"shop/report.py": "TITLE = 'Sales'\n"},
    )
    run_git(path, "update-ref", "refs/window/1001", head)
    # A commit with no history in common with main, kept the same way.
    run_git(path, "switch", "--quiet", "--orphan", "unrelated")
    unrelated = commit_at(
        path,
        "2026-03-03T10:00:00+00:00",
        "Start over",
        {"NOTES.md": "Elsewhere.\n"},
    )
    run_git(path, "update-ref", "refs/window/1002", unrelated)
    run_git(path, "switch", "--quiet", "main")
    run_git(path, "branch", "--quiet", "--delete", "--force", "unrelated")
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    return Clone(
        path=path,
        work=work,
        outside=outside,
        first=first,
        second=second,
        third=third,
        head=head,
        unrelated=unrelated,
    )


def run_git(
    directory: Path, *arguments: str, environment: dict[str, str] | None = None
) -> str:
    """Run the real git in directory, as the tests' setup does; return its stdout.

    environment adds variables to those of the test, or replaces them.
    """
    result = subprocess.run(  # noqa: S603
        [GIT, "-C", str(directory), *arguments],
        capture_output=True,
        check=False,
        env={**os.environ, **(environment or {})},
    )
    assert result.returncode == 0, os.fsdecode(result.stderr)
    return os.fsdecode(result.stdout)


def new_repository(path: Path) -> Path:
    path.mkdir()
    run_git(path, "init", "--quiet", "--initial-branch=main")
    return path


def write_files(directory: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def commit_at(
    repository: Path,
    date: str,
    message: str,
    files: dict[str, str],
    *,
    author_date: str | None = None,
) -> str:
    """Commit the files at date, and return the new commit's full id.

    date is the committer's date, and the author's too unless author_date
    gives it apart.
    """
    write_files(repository, files)
    run_git(repository, "add", "--all")
    dates = {"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": author_date or date}
    run_git(repository, "commit", "--quiet", "--message", message, environment=dates)
    return head_of(repository)


def merge_at(repository: Path, date: str, branch: str) -> str:
    """Merge branch with a merge commit made at date, as GitHub merges a pull
    request; return the merge commit's id."""
    dates = {"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date}
    run_git(
        repository,
        "merge",
        "--quiet",
        "--no-ff",
        "--no-edit",
        branch,
        environment=dates,
    )
    return head_of(repository)


def head_of(directory: Path) -> str:
    return run_git(directory, "rev-parse", "HEAD").strip()


def criss_cross(repository: Path) -> tuple[str, str]:
    """Branches left and right that each merged the other's first commit.

    Return the last commit of each, left's first. They have two best common
    ancestors: the first commit of each branch.
    """
    new_repository(repository)
    commit_at(repository, COMMIT_DATE, "Open the shop", {"README.md": "A shop.\n"})
    run_git(repository, "switch", "--quiet", "--create", "left")
    left_first = commit_at(repository, COMMIT_DATE, "Left", {"left.txt": "left\n"})
    run_git(repository, "switch", "--quiet", "--create", "right", "main")
    right_first = commit_at(repository, COMMIT_DATE, "Right", {"right.txt": "right\n"})
    run_git(repository, "merge", "--quiet", "--no-ff", "--no-edit", left_first)
    right_last = head_of(repository)
    run_git(repository, "switch", "--quiet", "left")
    run_git(repository, "merge", "--quiet", "--no-ff", "--no-edit", right_first)
    left_last = head_of(repository)
    return left_last, right_last


def add_worktree_with_git(clone: Path, commit: str, folder: Path) -> Path:
    """Add a worktree as git itself does, and return its folder.

    A test of remove_worktree then needs nothing else of checkout.
    """
    run_git(clone, "worktree", "add", "--quiet", "--detach", str(folder), commit)
    return folder


def worktrees_of(clone: Path) -> list[Path]:
    """The worktrees that the clone lists, its own first."""
    prefix = "worktree "
    listing = run_git(clone, "worktree", "list", "--porcelain")
    return [
        Path(line.removeprefix(prefix)).resolve()
        for line in listing.splitlines()
        if line.startswith(prefix)
    ]


def files_of(folder: Path) -> dict[str, str]:
    """Each file of a worktree but git's own, by its path, with its text."""
    files: dict[str, str] = {}
    for path in folder.rglob("*"):
        relative = path.relative_to(folder)
        if relative.parts[0] != ".git" and path.is_file():
            files[relative.as_posix()] = path.read_text(encoding="utf-8")
    return files


def snapshot(directory: Path) -> dict[Path, tuple[bytes, int] | None]:
    """Every path under directory, with each file's bytes and modification time."""
    return {path: file_state(path) for path in directory.rglob("*")}


def file_state(path: Path) -> tuple[bytes, int] | None:
    if path.is_dir():
        return None  # a directory counts by its path, and its files by theirs
    return path.read_bytes(), path.stat().st_mtime_ns


def checkout_state(clone: Path) -> tuple[dict[Path, tuple[bytes, int] | None], str]:
    """What Invariant 3 keeps of the clone, and its refs.

    Every path of its work tree, with each file's bytes and time; .git's HEAD
    and index, which hold the commit checked out and what is staged; and each
    ref with its commit.
    """
    git_directory = clone / ".git"
    state: dict[Path, tuple[bytes, int] | None] = {}
    for path in clone.rglob("*"):
        if path != git_directory and git_directory not in path.parents:
            state[path] = file_state(path)
    for name in ("HEAD", "index"):
        state[git_directory / name] = file_state(git_directory / name)
    refs = run_git(clone, "for-each-ref", "--format=%(refname) %(objectname)")
    return state, refs


def change_the_work_tree_as_a_user_might(clone: Clone) -> None:
    """A tracked file changed and not committed, a file not tracked, and one
    whose time no longer matches what the index holds for it.

    A command that refreshes the index, as git status does, would rewrite the
    index for the last one.
    """
    write_files(
        clone.path, {"README.md": "Changed, not committed.\n", "notes.txt": "Mine.\n"}
    )
    os.utime(clone.path / "shop" / "tax.py", ns=(0, 0))


def record_runs(monkeypatch: pytest.MonkeyPatch) -> list[Run]:
    """Make subprocess.run note each call before it runs; return the notes."""
    runs: list[Run] = []
    # One type for subprocess.run's overloads, which, given arguments of any
    # type, would leave its result unknown to pyright.
    real_run = cast("Callable[..., subprocess.CompletedProcess[Any]]", subprocess.run)

    def noting_run(
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> subprocess.CompletedProcess[Any]:
        command = args[0] if args else kwargs.get("args")
        runs.append(
            Run(
                command=command,
                shell=kwargs.get("shell"),
                timeout=kwargs.get("timeout"),
            )
        )
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", noting_run)
    return runs


def is_argument_list(command: object) -> bool:
    """Whether a command is a sequence of arguments, rather than a string."""
    return isinstance(command, list | tuple)


def is_positive_number(value: object) -> bool:
    return isinstance(value, int | float) and value > 0


def assert_each_run_is_git_with_a_time_limit(runs: list[Run]) -> None:
    """Rule 1: git runs through subprocess.run, from an argument list and never
    a shell; Rule 3: every process has a time limit."""
    assert runs, "checkout ran no process through subprocess.run"
    for run in runs:
        assert is_argument_list(run.command), run
        assert Path(run.command[0]).name == "git", run
        assert not run.shell, run
        assert is_positive_number(run.timeout), run


def test_a_commit_of_the_base_branch_is_in_the_clone(clone: Clone) -> None:
    assert checkout.has_commit(str(clone.path), clone.second) is True


def test_a_head_kept_by_its_runs_ref_alone_is_in_the_clone(clone: Clone) -> None:
    assert checkout.has_commit(str(clone.path), clone.head) is True


def test_a_commit_that_the_clone_does_not_hold_is_not_in_it(clone: Clone) -> None:
    assert checkout.has_commit(str(clone.path), UNKNOWN_COMMIT) is False


@pytest.mark.parametrize("suffix", ["^{tree}", ":README.md"], ids=["tree", "blob"])
def test_an_object_that_is_not_a_commit_is_no_commit_in_the_clone(
    clone: Clone, suffix: str
) -> None:
    other = run_git(clone.path, "rev-parse", f"{clone.second}{suffix}").strip()

    assert checkout.has_commit(str(clone.path), other) is False


def test_the_base_commit_is_the_branchs_last_commit_before_the_run_started(
    clone: Clone,
) -> None:
    assert checkout.base_commit(str(clone.path), "main", RUN_STARTED) == clone.second


def test_a_run_that_started_after_the_branchs_last_commit_has_that_commit_as_base(
    clone: Clone,
) -> None:
    started = "2026-03-10T00:00:00Z"

    assert checkout.base_commit(str(clone.path), "main", started) == clone.third


def test_a_run_that_started_before_the_branchs_first_commit_has_no_base_commit(
    clone: Clone,
) -> None:
    assert checkout.base_commit(str(clone.path), "main", BEFORE_EVERY_COMMIT) is None


def test_the_base_commit_is_the_named_branchs_not_the_commit_checked_out(
    clone: Clone,
) -> None:
    # The head of run 1001, made on 2026-03-03 before the run started, is
    # checked out: along its own history, it is the last commit before the run.
    run_git(clone.path, "switch", "--quiet", "--detach", clone.head)

    assert checkout.base_commit(str(clone.path), "main", RUN_STARTED) == clone.second


def test_a_commit_merged_into_the_branch_after_the_run_started_is_not_its_base(
    tmp_path: Path,
) -> None:
    repository = new_repository(tmp_path / "clone")
    commit_at(
        repository,
        "2026-03-01T10:00:00+00:00",
        "Open the shop",
        {"README.md": "A shop.\n"},
    )
    base = commit_at(
        repository,
        "2026-03-02T10:00:00+00:00",
        "Lower the rate",
        {"tax.py": "RATE = 10\n"},
    )
    # A pull request's commit, made after main's last commit before the run,
    # and merged into main after the run started: its date is before the
    # run's, but it was not on main then.
    run_git(repository, "switch", "--quiet", "--create", "feature", "main~1")
    commit_at(
        repository,
        "2026-03-03T10:00:00+00:00",
        "Add a report",
        {"report.py": "TITLE = 'Sales'\n"},
    )
    run_git(repository, "switch", "--quiet", "main")
    merge_at(repository, "2026-03-06T10:00:00+00:00", "feature")

    started = "2026-03-04T00:00:00Z"

    assert checkout.base_commit(str(repository), "main", started) == base


def test_a_commit_that_landed_on_the_branch_after_the_run_started_is_not_its_base(
    tmp_path: Path,
) -> None:
    repository = new_repository(tmp_path / "clone")
    base = commit_at(
        repository,
        "2026-03-01T10:00:00+00:00",
        "Open the shop",
        {"README.md": "A shop.\n"},
    )
    # Written before the run started, and committed onto main after it, as a
    # rebase merge does: its author date is the earlier one.
    commit_at(
        repository,
        "2026-03-06T10:00:00+00:00",
        "Lower the rate",
        {"tax.py": "RATE = 10\n"},
        author_date="2026-03-02T10:00:00+00:00",
    )

    started = "2026-03-04T00:00:00Z"

    assert checkout.base_commit(str(repository), "main", started) == base


def test_commit_times_and_the_runs_start_are_compared_as_instants(
    tmp_path: Path,
) -> None:
    repository = new_repository(tmp_path / "clone")
    commit_at(
        repository,
        "2026-03-01T10:00:00+00:00",
        "Open the shop",
        {"README.md": "A shop.\n"},
    )
    # 15:30 at UTC+2 is 13:30 UTC, before a run that started at 14:00 UTC...
    base = commit_at(
        repository,
        "2026-03-04T15:30:00+02:00",
        "Lower the rate",
        {"tax.py": "RATE = 10\n"},
    )
    # ...and 13:30 at UTC-2 is 15:30 UTC, after it.
    commit_at(
        repository,
        "2026-03-04T13:30:00-02:00",
        "Add a report",
        {"report.py": "TITLE = 'Sales'\n"},
    )

    started = "2026-03-04T14:00:00Z"

    assert checkout.base_commit(str(repository), "main", started) == base


def test_m_is_where_the_base_commit_and_the_tested_head_fork(clone: Clone) -> None:
    m = checkout.merge_base(str(clone.path), clone.third, clone.head)

    assert m == clone.first


def test_commits_with_no_common_history_have_no_merge_base(clone: Clone) -> None:
    m = checkout.merge_base(str(clone.path), clone.third, clone.unrelated)

    assert m is None


def test_with_several_best_common_ancestors_m_is_the_one_git_merge_base_prints(
    tmp_path: Path,
) -> None:
    # The tool takes the one that git merge-base prints for the merge-base,
    # and rejects coverage recorded at a commit that is neither it nor one of
    # its ancestors (K4).
    repository = tmp_path / "clone"
    left, right = criss_cross(repository)
    # The history does have several: git merge-base prints one of the two.
    assert len(run_git(repository, "merge-base", "--all", left, right).split()) == 2
    printed = run_git(repository, "merge-base", left, right).strip()
    printed_reversed = run_git(repository, "merge-base", right, left).strip()

    assert checkout.merge_base(str(repository), left, right) == printed
    assert checkout.merge_base(str(repository), right, left) == printed_reversed


def test_a_worktree_has_its_commit_checked_out_with_the_commits_files(
    clone: Clone,
) -> None:
    folder = clone.work / "head"

    checkout.add_worktree(str(clone.path), clone.head, str(folder))

    assert head_of(folder) == clone.head
    assert files_of(folder) == {
        "README.md": "A shop.\n",
        "shop/report.py": "TITLE = 'Sales'\n",
        "shop/tax.py": "RATE = 21\n",
    }


def test_the_worktrees_of_m_and_of_the_tested_head_are_kept_at_once(
    clone: Clone,
) -> None:
    m_folder = clone.work / "m"
    head_folder = clone.work / "head"

    checkout.add_worktree(str(clone.path), clone.first, str(m_folder))
    checkout.add_worktree(str(clone.path), clone.head, str(head_folder))

    assert head_of(m_folder) == clone.first
    assert head_of(head_folder) == clone.head


def test_a_worktree_may_hold_the_commit_that_the_clone_has_checked_out(
    clone: Clone,
) -> None:
    # main's last commit, checked out in the clone, may be a base commit.
    folder = clone.work / "base"

    checkout.add_worktree(str(clone.path), clone.third, str(folder))

    assert head_of(folder) == clone.third


def test_adding_worktrees_leaves_the_clones_checkout_as_it_was(clone: Clone) -> None:
    change_the_work_tree_as_a_user_might(clone)
    before = checkout_state(clone.path)

    checkout.add_worktree(str(clone.path), clone.first, str(clone.work / "m"))
    checkout.add_worktree(str(clone.path), clone.head, str(clone.work / "head"))

    assert checkout_state(clone.path) == before


def test_a_removed_worktree_is_gone_from_the_disk_and_from_the_clone(
    clone: Clone,
) -> None:
    folder = add_worktree_with_git(clone.path, clone.head, clone.work / "head")

    checkout.remove_worktree(str(clone.path), str(folder))

    assert not folder.exists()
    assert worktrees_of(clone.path) == [clone.path.resolve()]


def test_a_worktree_is_removed_whatever_its_files_hold(clone: Clone) -> None:
    folder = add_worktree_with_git(clone.path, clone.head, clone.work / "head")
    # As an environment built in the work tree and a suite run leave it: a
    # tracked file changed, and files that git does not track, at any depth.
    write_files(
        folder,
        {
            "shop/tax.py": "RATE = 0\n",
            ".venv/lib/python3.12/site-packages/plugin.py": "X = 1\n",
            "junit.xml": "<testsuites/>\n",
        },
    )

    checkout.remove_worktree(str(clone.path), str(folder))

    assert not folder.exists()
    assert worktrees_of(clone.path) == [clone.path.resolve()]


def test_a_folder_whose_worktree_was_removed_takes_a_worktree_again(
    clone: Clone,
) -> None:
    folder = add_worktree_with_git(clone.path, clone.head, clone.work / "head")
    checkout.remove_worktree(str(clone.path), str(folder))

    checkout.add_worktree(str(clone.path), clone.second, str(folder))

    assert head_of(folder) == clone.second


def test_removing_worktrees_leaves_the_clones_checkout_as_it_was(clone: Clone) -> None:
    change_the_work_tree_as_a_user_might(clone)
    before = checkout_state(clone.path)
    add_worktree_with_git(clone.path, clone.first, clone.work / "m")
    add_worktree_with_git(clone.path, clone.head, clone.work / "head")

    checkout.remove_worktree(str(clone.path), str(clone.work / "m"))
    checkout.remove_worktree(str(clone.path), str(clone.work / "head"))

    assert checkout_state(clone.path) == before


# Each query that only reads, with each kind of answer it gives.
QUERIES: dict[str, Callable[[Clone], object]] = {
    "has_commit of a head kept by its run's ref": lambda clone: checkout.has_commit(
        str(clone.path), clone.head
    ),
    "has_commit of a commit that the clone has not": lambda clone: checkout.has_commit(
        str(clone.path), UNKNOWN_COMMIT
    ),
    "base_commit of a run after a commit": lambda clone: checkout.base_commit(
        str(clone.path), "main", RUN_STARTED
    ),
    "base_commit of a run before every commit": lambda clone: checkout.base_commit(
        str(clone.path), "main", BEFORE_EVERY_COMMIT
    ),
    "merge_base of a base commit and a head": lambda clone: checkout.merge_base(
        str(clone.path), clone.third, clone.head
    ),
    "merge_base of commits with no common history": lambda clone: checkout.merge_base(
        str(clone.path), clone.third, clone.unrelated
    ),
}


@pytest.mark.parametrize("query", list(QUERIES))
def test_each_query_leaves_the_clone_byte_for_byte_as_it_was(
    query: str, clone: Clone
) -> None:
    # tax.py's time no longer matches what the index holds for it, so a
    # command that refreshes the index, as git status does, would rewrite it.
    os.utime(clone.path / "shop" / "tax.py", ns=(0, 0))
    before = snapshot(clone.path)

    QUERIES[query](clone)

    assert snapshot(clone.path) == before


@pytest.mark.parametrize("query", list(QUERIES))
def test_each_query_runs_git_from_an_argument_list_with_a_time_limit(
    query: str, clone: Clone, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = record_runs(monkeypatch)

    QUERIES[query](clone)

    assert_each_run_is_git_with_a_time_limit(runs)


def test_add_worktree_runs_git_from_an_argument_list_with_a_time_limit(
    clone: Clone, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = record_runs(monkeypatch)

    checkout.add_worktree(str(clone.path), clone.head, str(clone.work / "head"))

    assert_each_run_is_git_with_a_time_limit(runs)


def test_remove_worktree_runs_git_from_an_argument_list_with_a_time_limit(
    clone: Clone, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = add_worktree_with_git(clone.path, clone.head, clone.work / "head")
    runs = record_runs(monkeypatch)

    checkout.remove_worktree(str(clone.path), str(folder))

    assert_each_run_is_git_with_a_time_limit(runs)


# Each call whose git fails: in a directory outside any repository, for a
# branch or a commit that the clone does not hold.
FAILING_CALLS: dict[str, Callable[[Clone], object]] = {
    "has_commit outside a repository": lambda clone: checkout.has_commit(
        str(clone.outside), clone.head
    ),
    "base_commit outside a repository": lambda clone: checkout.base_commit(
        str(clone.outside), "main", RUN_STARTED
    ),
    "base_commit of a branch that the clone has not": lambda clone: (
        checkout.base_commit(str(clone.path), "no-such-branch", RUN_STARTED)
    ),
    "merge_base with a commit that the clone has not": lambda clone: (
        checkout.merge_base(str(clone.path), clone.third, UNKNOWN_COMMIT)
    ),
    "merge_base outside a repository": lambda clone: checkout.merge_base(
        str(clone.outside), clone.third, clone.head
    ),
    "add_worktree of a commit that the clone has not": lambda clone: (
        checkout.add_worktree(str(clone.path), UNKNOWN_COMMIT, str(clone.work / "head"))
    ),
}


@pytest.mark.parametrize("call", list(FAILING_CALLS))
def test_a_git_that_fails_raises_rather_than_answers(call: str, clone: Clone) -> None:
    # So a clone that is no repository never reads as one that lacks every
    # head, nor a branch that it lacks as one with no commit before the run
    # (note 7). The harness turns any exception into its exit 1. Any type but
    # NotImplementedError, which only a stub raises.
    with pytest.raises(Exception) as raised:  # noqa: PT011
        FAILING_CALLS[call](clone)

    assert not isinstance(raised.value, NotImplementedError)
