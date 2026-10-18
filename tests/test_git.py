import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from distiller import git

# Each test builds its own repositories in tmp_path and watches the queries
# from outside: what they return, what reaches stdout and stderr, which
# commands a fake git first on PATH sees, and what the checkout holds after.

# The real git, found before any test puts a fake one first on PATH.
GIT = shutil.which("git") or "git"

# Every commit is made at this time, so that a test builds the same commit ids
# each time it runs.
COMMIT_DATE = "2026-10-10T12:00:00+00:00"

# The subcommands under "Checked" in the SPEC: local, and read-only with the
# options it gives them.
CHECKED_SUBCOMMANDS = frozenset({"rev-parse", "merge-base", "diff", "ls-tree"})

# git's own options whose value is the next argument, as in `git -C <path>`.
GIT_OPTIONS_WITH_A_VALUE = frozenset(
    {
        "-C",
        "-c",
        "--git-dir",
        "--work-tree",
        "--namespace",
        "--config-env",
        "--attr-source",
    }
)

# Paths that git would quote without -z, the last one in bytes that are not
# UTF-8, which os.fsdecode turns into a str.
SPECIAL_PATHS = (
    "src/shop/tarifa año.py",  # a space and a non-ASCII letter (Edge 5)
    'src/shop/"quoted".py',  # quotation marks
    "src/shop/back\\slash.py",  # a backslash
    "src/shop/tab\there.py",  # a control character with a short escape
    "src/shop/new\nline.py",  # a newline, which splits a listing by lines
    "src/shop/escape\x1b.py",  # a control character without one
    os.fsdecode(b"src/shop/caf\xe9.py"),  # Latin-1
)

# A git that appends its arguments to a log, one JSON list per line, and then
# becomes the real git.
FAKE_GIT = """\
#!{python} -I
import json
import os
import sys

with open({log!r}, "a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
os.execv({git!r}, [{git!r}, *sys.argv[1:]])
"""


@dataclass(frozen=True)
class History:
    """A checkout where main and feature fork after their second commit.

    feature is checked out, and the branch unrelated shares no commit with
    either.
    """

    checkout: Path
    outside: Path  # a directory in no repository
    fork: str  # the commit where main and feature fork: their merge-base
    main: str  # main's last commit
    feature: str  # feature's last commit
    unrelated: str  # unrelated's only commit


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


@pytest.fixture
def history(tmp_path: Path) -> History:
    checkout = new_repository(tmp_path / "checkout")
    commit_files(
        checkout,
        "Open the shop",
        {"README.md": "A shop.\n", "src/shop/tax.py": "RATE = 21\n"},
    )
    fork = commit_files(checkout, "Lower the rate", {"src/shop/tax.py": "RATE = 10\n"})
    run_git(checkout, "switch", "--quiet", "--create", "feature")
    feature = commit_files(
        checkout, "Add a report", {"src/shop/report.py": "TITLE = 'Sales'\n"}
    )
    run_git(checkout, "switch", "--quiet", "main")
    main = commit_files(checkout, "Describe the shop", {"README.md": "A small shop.\n"})
    run_git(checkout, "switch", "--quiet", "--orphan", "unrelated")
    unrelated = commit_files(checkout, "Start over", {"NOTES.md": "Elsewhere.\n"})
    run_git(checkout, "switch", "--quiet", "feature")
    outside = tmp_path / "outside"
    outside.mkdir()
    return History(
        checkout=checkout,
        outside=outside,
        fork=fork,
        main=main,
        feature=feature,
        unrelated=unrelated,
    )


@pytest.fixture
def git_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Put first on PATH a git that logs its arguments; return the log's path."""
    directory = tmp_path / "fake-git"
    directory.mkdir()
    log = tmp_path / "git-log.jsonl"
    fake = directory / "git"
    fake.write_text(
        FAKE_GIT.format(python=sys.executable, log=str(log), git=GIT),
        encoding="utf-8",
    )
    fake.chmod(0o700)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")
    return log


def run_git(directory: Path, *arguments: str) -> str:
    """Run the real git in directory, as the tests' setup does; return its stdout."""
    result = subprocess.run(  # noqa: S603
        [GIT, "-C", str(directory), *arguments],
        capture_output=True,
        check=False,
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


def commit_all(checkout: Path, message: str) -> str:
    """Commit every change in the work tree; return the new commit's full id."""
    run_git(checkout, "add", "--all")
    run_git(checkout, "commit", "--quiet", "--message", message)
    return head_of(checkout)


def commit_files(checkout: Path, message: str, files: dict[str, str]) -> str:
    write_files(checkout, files)
    return commit_all(checkout, message)


def head_of(checkout: Path) -> str:
    return run_git(checkout, "rev-parse", "HEAD").strip()


def clone_of(history: History, path: Path, *options: str) -> Path:
    """Clone the history's checkout through file://, which honours --depth."""
    run_git(
        path.parent, "clone", "--quiet", *options, history.checkout.as_uri(), str(path)
    )
    return path


def criss_cross(checkout: Path) -> tuple[str, str]:
    """Branches left and right that each merged the other's first commit.

    Return the last commit of each, left's first. They have two best common
    ancestors: the first commit of each branch.
    """
    new_repository(checkout)
    commit_files(checkout, "Open the shop", {"README.md": "A shop.\n"})
    run_git(checkout, "switch", "--quiet", "--create", "left")
    left_first = commit_files(checkout, "Left", {"left.txt": "left\n"})
    run_git(checkout, "switch", "--quiet", "--create", "right", "main")
    right_first = commit_files(checkout, "Right", {"right.txt": "right\n"})
    run_git(checkout, "merge", "--quiet", "--no-ff", "--no-edit", left_first)
    right_last = head_of(checkout)
    run_git(checkout, "switch", "--quiet", "left")
    run_git(checkout, "merge", "--quiet", "--no-ff", "--no-edit", right_first)
    left_last = head_of(checkout)
    return left_last, right_last


def logged_commands(log: Path) -> list[list[str]]:
    """The arguments of each command that the fake git ran, in order."""
    if not log.exists():
        return []
    lines = log.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def subcommand_of(arguments: list[str]) -> str:
    """The subcommand in a git command's arguments, after git's own options."""
    index = 0
    while index < len(arguments) and arguments[index].startswith("-"):
        if arguments[index] in GIT_OPTIONS_WITH_A_VALUE:
            index += 2  # the option and its value
        else:
            index += 1
    if index >= len(arguments):
        return ""  # no subcommand, as in `git --version`
    return arguments[index]


def snapshot(directory: Path) -> dict[Path, tuple[bytes, int] | None]:
    """Every path under directory, with each file's bytes and modification time."""
    return {path: file_state(path) for path in directory.rglob("*")}


def file_state(path: Path) -> tuple[bytes, int] | None:
    if path.is_dir():
        return None  # a directory counts by its path, and its files by theirs
    return path.read_bytes(), path.stat().st_mtime_ns


def test_a_work_tree_is_a_checkout(history: History) -> None:
    assert git.is_checkout(str(history.checkout)) is True


def test_a_subdirectory_of_a_work_tree_is_a_checkout(history: History) -> None:
    assert git.is_checkout(str(history.checkout / "src" / "shop")) is True


def test_a_directory_outside_any_repository_is_not_a_checkout(
    history: History,
) -> None:
    assert git.is_checkout(str(history.outside)) is False


def test_a_path_that_does_not_exist_is_not_a_checkout(tmp_path: Path) -> None:
    # For evaluate, a path that does not exist is a rejection, never a usage
    # error.
    assert git.is_checkout(str(tmp_path / "no-such-directory")) is False


def test_a_full_clone_is_not_shallow(history: History, tmp_path: Path) -> None:
    clone = clone_of(history, tmp_path / "clone")

    assert git.is_shallow(str(clone)) is False


def test_a_clone_made_with_depth_1_is_shallow(history: History, tmp_path: Path) -> None:
    clone = clone_of(history, tmp_path / "clone", "--depth", "1")

    assert git.is_shallow(str(clone)) is True


def test_a_branch_resolves_to_the_full_id_of_its_last_commit(history: History) -> None:
    assert git.resolve_commit(str(history.checkout), "main") == history.main


def test_head_resolves_to_the_commit_checked_out(history: History) -> None:
    assert git.resolve_commit(str(history.checkout), "HEAD") == history.feature


def test_a_full_commit_id_resolves_to_itself(history: History) -> None:
    assert git.resolve_commit(str(history.checkout), history.fork) == history.fork


def test_an_abbreviated_commit_id_resolves_to_the_full_one(history: History) -> None:
    abbreviated = history.fork[:12]

    assert git.resolve_commit(str(history.checkout), abbreviated) == history.fork


def test_an_annotated_tag_resolves_to_its_commit_not_to_the_tag(
    history: History,
) -> None:
    run_git(
        history.checkout, "tag", "--annotate", "--message", "One", "v1", history.fork
    )

    assert git.resolve_commit(str(history.checkout), "v1") == history.fork


def test_a_base_given_as_origin_and_its_branch_resolves(
    history: History, tmp_path: Path
) -> None:
    # As in a pull request's checkout, main is only a remote-tracking branch.
    clone = clone_of(history, tmp_path / "clone", "--branch", "feature")

    assert git.resolve_commit(str(clone), "origin/main") == history.main


def test_a_branch_name_alone_misses_a_remote_tracking_branch(
    history: History, tmp_path: Path
) -> None:
    # A name alone resolves only through refs/heads/, refs/remotes/<name> and
    # refs/remotes/<name>/HEAD (man gitrevisions): hence origin/<branch>.
    clone = clone_of(history, tmp_path / "clone", "--branch", "feature")

    assert git.resolve_commit(str(clone), "main") is None


def test_an_unknown_name_names_no_commit(history: History) -> None:
    assert git.resolve_commit(str(history.checkout), "no-such-branch") is None


# Options of git rev-parse: each would print something if git took the name
# for an option.
@pytest.mark.parametrize("name", ["--all", "--branches", "--show-toplevel"])
def test_an_option_like_name_names_no_commit(name: str, history: History) -> None:
    assert git.resolve_commit(str(history.checkout), name) is None


def test_a_tree_names_no_commit(history: History) -> None:
    tree = run_git(history.checkout, "rev-parse", f"{history.fork}^{{tree}}").strip()

    assert git.resolve_commit(str(history.checkout), tree) is None


def test_a_blob_names_no_commit(history: History) -> None:
    blob = run_git(history.checkout, "rev-parse", f"{history.fork}:README.md").strip()

    assert git.resolve_commit(str(history.checkout), blob) is None


def test_the_merge_base_of_two_branches_is_where_they_fork(history: History) -> None:
    merge_base = git.merge_base(str(history.checkout), history.main, history.feature)

    assert merge_base == history.fork


def test_commits_with_no_common_history_have_no_merge_base(history: History) -> None:
    checkout = str(history.checkout)

    assert git.merge_base(checkout, history.feature, history.unrelated) is None


def test_with_several_best_common_ancestors_it_is_the_one_git_merge_base_prints(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    left, right = criss_cross(checkout)
    # The history does have several: git merge-base prints one of the two.
    assert len(run_git(checkout, "merge-base", "--all", left, right).split()) == 2
    printed = run_git(checkout, "merge-base", left, right).strip()
    printed_reversed = run_git(checkout, "merge-base", right, left).strip()

    assert git.merge_base(str(checkout), left, right) == printed
    assert git.merge_base(str(checkout), right, left) == printed_reversed


def test_a_commit_is_its_own_ancestor(history: History) -> None:
    checkout = str(history.checkout)

    assert git.is_ancestor(checkout, history.fork, history.fork) is True


def test_an_earlier_commit_is_an_ancestor_of_a_later_one(history: History) -> None:
    checkout = str(history.checkout)

    assert git.is_ancestor(checkout, history.fork, history.feature) is True


def test_a_later_commit_is_not_an_ancestor_of_an_earlier_one(
    history: History,
) -> None:
    checkout = str(history.checkout)

    assert git.is_ancestor(checkout, history.feature, history.fork) is False


def test_a_commit_of_another_branch_is_not_an_ancestor(history: History) -> None:
    checkout = str(history.checkout)

    assert git.is_ancestor(checkout, history.main, history.feature) is False


def test_a_commit_with_no_common_history_is_not_an_ancestor(
    history: History,
) -> None:
    checkout = str(history.checkout)

    assert git.is_ancestor(checkout, history.unrelated, history.feature) is False


def test_the_changed_paths_are_those_that_differ_between_the_two_commits(
    tmp_path: Path,
) -> None:
    checkout = new_repository(tmp_path / "checkout")
    old = commit_files(
        checkout,
        "Old",
        {
            "README.md": "A shop.\n",
            "src/shop/tax.py": "RATE = 21\n",
            "src/shop/db.py": "URL = ''\n",
        },
    )
    new = commit_files(
        checkout,
        "New",
        {"src/shop/tax.py": "RATE = 10\n", "src/shop/orders.py": "ORDERS = []\n"},
    )
    # Changes made after new, staged or not, are in neither commit.
    write_files(
        checkout,
        {
            "README.md": "Staged.\n",
            "src/shop/db.py": "Not staged.\n",
            "untracked.py": "X = 1\n",
        },
    )
    run_git(checkout, "add", "README.md")

    changed = git.changed_paths(str(checkout), old, new)

    assert sorted(changed) == ["src/shop/orders.py", "src/shop/tax.py"]


def test_a_renamed_file_is_listed_under_both_of_its_names(tmp_path: Path) -> None:
    checkout = new_repository(tmp_path / "checkout")
    old = commit_files(checkout, "Old", {"src/shop/tax.py": "RATE = 21\n"})
    run_git(checkout, "mv", "src/shop/tax.py", "src/shop/taxes.py")
    new = commit_all(checkout, "Rename")

    changed = git.changed_paths(str(checkout), old, new)

    assert sorted(changed) == ["src/shop/tax.py", "src/shop/taxes.py"]


def test_a_deleted_file_is_listed_under_its_old_name(tmp_path: Path) -> None:
    checkout = new_repository(tmp_path / "checkout")
    old = commit_files(
        checkout,
        "Old",
        {"src/shop/report.py": "TITLE = 'Sales'\n", "src/shop/tax.py": "RATE = 21\n"},
    )
    run_git(checkout, "rm", "--quiet", "src/shop/report.py")
    new = commit_all(checkout, "Delete the report")

    assert git.changed_paths(str(checkout), old, new) == ["src/shop/report.py"]


def test_two_commits_with_the_same_files_have_no_changed_paths(
    history: History,
) -> None:
    run_git(
        history.checkout, "commit", "--quiet", "--allow-empty", "--message", "Empty"
    )
    same_files = head_of(history.checkout)

    changed = git.changed_paths(str(history.checkout), history.feature, same_files)

    assert changed == []


def test_changed_paths_come_unquoted_whatever_characters_they_hold(
    tmp_path: Path,
) -> None:
    checkout = new_repository(tmp_path / "checkout")
    old = commit_files(checkout, "Old", {"README.md": "A shop.\n"})
    new = commit_files(checkout, "New", dict.fromkeys(SPECIAL_PATHS, "X = 1\n"))

    changed = git.changed_paths(str(checkout), old, new)

    assert sorted(changed) == sorted(SPECIAL_PATHS)


@pytest.mark.parametrize(
    ("key", "value"), [("diff.relative", "true"), ("color.ui", "always")]
)
def test_changed_paths_come_from_the_root_when_the_checkout_is_a_subdirectory(
    key: str, value: str, tmp_path: Path
) -> None:
    checkout = new_repository(tmp_path / "checkout")
    run_git(checkout, "config", key, value)
    paths = ["README.md", "src/shop/tax.py", "templates/invoice.html"]
    old = commit_files(checkout, "Old", dict.fromkeys(paths, "old\n"))
    new = commit_files(checkout, "New", dict.fromkeys(paths, "new\n"))

    changed = git.changed_paths(str(checkout / "src"), old, new)

    assert sorted(changed) == paths


def test_the_tree_files_are_every_file_of_the_commit_at_any_depth(
    history: History,
) -> None:
    files = git.tree_files(str(history.checkout), history.feature)

    assert files == frozenset({"README.md", "src/shop/tax.py", "src/shop/report.py"})


def test_the_tree_files_are_the_commits_not_the_work_trees(history: History) -> None:
    # The work tree holds feature's files but README.md, and one untracked.
    (history.checkout / "README.md").unlink()
    write_files(history.checkout, {"untracked.py": "X = 1\n"})

    files = git.tree_files(str(history.checkout), history.fork)

    assert files == frozenset({"README.md", "src/shop/tax.py"})


def test_the_tree_files_come_from_the_root_when_the_checkout_is_a_subdirectory(
    history: History,
) -> None:
    files = git.tree_files(str(history.checkout / "src"), history.feature)

    assert files == frozenset({"README.md", "src/shop/tax.py", "src/shop/report.py"})


def test_the_tree_files_come_unquoted_whatever_characters_they_hold(
    tmp_path: Path,
) -> None:
    checkout = new_repository(tmp_path / "checkout")
    commit = commit_files(checkout, "New", dict.fromkeys(SPECIAL_PATHS, "X = 1\n"))

    assert git.tree_files(str(checkout), commit) == frozenset(SPECIAL_PATHS)


# Each query, with each kind of answer it gives: in a checkout and outside any
# repository, for a commit and for names that name none, for commits with and
# without a common history.
QUERIES: dict[str, Callable[[History], object]] = {
    "is_checkout of a work tree": lambda history: git.is_checkout(
        str(history.checkout)
    ),
    "is_checkout outside a repository": lambda history: git.is_checkout(
        str(history.outside)
    ),
    "is_shallow of a full checkout": lambda history: git.is_shallow(
        str(history.checkout)
    ),
    "resolve_commit of a branch": lambda history: git.resolve_commit(
        str(history.checkout), "main"
    ),
    "resolve_commit of an unknown name": lambda history: git.resolve_commit(
        str(history.checkout), "no-such-branch"
    ),
    "resolve_commit of an option-like name": lambda history: git.resolve_commit(
        str(history.checkout), "--all"
    ),
    "merge_base of two branches": lambda history: git.merge_base(
        str(history.checkout), history.main, history.feature
    ),
    "merge_base of unrelated commits": lambda history: git.merge_base(
        str(history.checkout), history.feature, history.unrelated
    ),
    "is_ancestor of an ancestor": lambda history: git.is_ancestor(
        str(history.checkout), history.fork, history.feature
    ),
    "is_ancestor of a descendant": lambda history: git.is_ancestor(
        str(history.checkout), history.feature, history.fork
    ),
    "changed_paths": lambda history: git.changed_paths(
        str(history.checkout), history.fork, history.feature
    ),
    "tree_files": lambda history: git.tree_files(
        str(history.checkout), history.feature
    ),
}


@pytest.mark.parametrize("query", list(QUERIES))
def test_each_query_runs_only_local_git_commands_that_read(
    query: str, history: History, git_log: Path
) -> None:
    git_log.unlink(missing_ok=True)  # only the query's own commands count

    QUERIES[query](history)

    commands = logged_commands(git_log)
    assert commands, "the query ran no git found through PATH"
    subcommands = {subcommand_of(command) for command in commands}
    assert subcommands <= CHECKED_SUBCOMMANDS, commands


@pytest.mark.parametrize("query", list(QUERIES))
def test_nothing_git_prints_reaches_the_tools_stdout_or_stderr(
    query: str, history: History, capfd: pytest.CaptureFixture[str]
) -> None:
    capfd.readouterr()  # drop what was written before the query

    QUERIES[query](history)

    assert capfd.readouterr() == ("", "")


@pytest.mark.parametrize("query", list(QUERIES))
def test_each_query_leaves_the_checkout_byte_for_byte_as_it_was(
    query: str, history: History
) -> None:
    # README.md's time no longer matches what the index holds for it, so a
    # command that refreshes the index, as git status does, would rewrite it.
    os.utime(history.checkout / "README.md", ns=(0, 0))
    before = snapshot(history.checkout)

    QUERIES[query](history)

    assert snapshot(history.checkout) == before
