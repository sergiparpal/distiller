import csv
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from replay import manifest
from replay.manifest import ManifestLine

# Each test writes a manifest in tmp_path, or reads the window's own, and
# watches the module from outside: the lines that read_manifest gives or that
# it raises, the problems that keep a replay from starting, and the lines whose
# head the clone lacks. Decided by the user on 2026-11-18, for the SPEC:
# read_manifest gives every row of the file, in its order, and the harness
# keeps its pilot's; each problem is one message, which names the run of a row
# with no number, or the number that two rows hold, of one pilot or of both;
# and a file that cannot be read as the manifest makes read_manifest raise, of
# any type, as read_pilot does, columns that it does not need left aside.

# The real git, found before any test changes the environment.
GIT = shutil.which("git") or "git"

# The window's manifest, in this repository.
WINDOW_MANIFEST = (
    Path(__file__).resolve().parents[2] / "notes" / "2026-11-17-window-red-runs.csv"
)

# The window's CSV's columns, in its order, and those that the manifest needs.
COLUMNS = (
    "project",
    "pull_request",
    "run_id",
    "run_started",
    "head",
    "job",
    "failed_steps",
)
NEEDED_COLUMNS = ("project", "pull_request", "run_id", "run_started", "head", "job")

# K16's tested head, urllib3's #5375's.
K16_HEAD = "b66457156bf78d4683690a5004058ec09635e4f8"

# Commit ids that name no object in the clone of these tests.
UNKNOWN_COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER_UNKNOWN_COMMIT = "89abcdef0123456789abcdef0123456789abcdef"

# Rows as the window's CSV holds them, and the lines they read into: K16's
# pull request, urllib3's #5375...
ROW_5375 = {
    "project": "urllib3",
    "pull_request": "5375",
    "run_id": "43640664881",
    "run_started": "2026-11-14T21:02:34Z",
    "head": K16_HEAD,
    "job": "failed in a test step",
    "failed_steps": "Run tests",
}
LINE_5375 = ManifestLine(
    project="urllib3",
    pull_request=5375,
    run=43640664881,
    run_started="2026-11-14T21:02:34Z",
    tested_head=K16_HEAD,
    ci_job="failed in a test step",
)

# ...K17's, poetry's #11226...
ROW_11226 = {
    "project": "poetry",
    "pull_request": "11226",
    "run_id": "43162239778",
    "run_started": "2026-11-12T05:34:07Z",
    "head": "0e45d518af97fa0aabe673ecbc44a95e0eb30e39",
    "job": "failed in a test step",
    "failed_steps": "Run poetry run pytest --integration -v",
}
LINE_11226 = ManifestLine(
    project="poetry",
    pull_request=11226,
    run=43162239778,
    run_started="2026-11-12T05:34:07Z",
    tested_head="0e45d518af97fa0aabe673ecbc44a95e0eb30e39",
    ci_job="failed in a test step",
)

# ...and an old one, whose job's outcome holds a comma, and whose failed steps
# GitHub no longer gave.
ROW_3720 = {
    "project": "urllib3",
    "pull_request": "3720",
    "run_id": "19903409392",
    "run_started": "2025-12-03T17:46:25Z",
    "head": "b94cb76397e9626eaec64939dcade5c20c7081ff",
    "job": "failed, steps no longer given",
    "failed_steps": "",
}
LINE_3720 = ManifestLine(
    project="urllib3",
    pull_request=3720,
    run=19903409392,
    run_started="2025-12-03T17:46:25Z",
    tested_head="b94cb76397e9626eaec64939dcade5c20c7081ff",
    ci_job="failed, steps no longer given",
)

# A value of K16's row that the manifest cannot use, by what is wrong with it.
WRONG_VALUES: dict[str, tuple[str, str]] = {
    "a run id that is empty": ("run_id", ""),
    "a run id that is not a whole number": ("run_id", "43640664881.0"),
    "a run id that is a word": ("run_id", "latest"),
    "a pull request number with its #": ("pull_request", "#5375"),
    "a pull request number that is not a whole number": ("pull_request", "5375.0"),
    "a pull request number that is a word": ("pull_request", "unknown"),
    # Read as local time, it would find another base commit, and say nothing.
    "a run start with no time zone": ("run_started", "2026-11-14T21:02:34"),
    "a run start that is no date": ("run_started", "yesterday"),
}


@dataclass(frozen=True)
class Clone:
    """A pilot's clone, with two heads kept by refs/window/<run id> alone."""

    path: Path
    outside: Path  # a directory in no repository
    first_head: str  # kept at refs/window/1001
    second_head: str  # kept at refs/window/1002


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep git to the repositories' own configuration and the tests' identity.

    Stop runs these tests with neither the user's home directory nor the
    network, so they rely on neither.
    """
    for name in list(os.environ):
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Distiller Tests")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "tests@distiller.invalid")
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-03-01T10:00:00+00:00")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Distiller Tests")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "tests@distiller.invalid")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-03-01T10:00:00+00:00")


@pytest.fixture
def clone(tmp_path: Path) -> Clone:
    path = tmp_path / "clone"
    path.mkdir()
    run_git(path, "init", "--quiet", "--initial-branch=main")
    commit_files(path, "Open the shop", {"README.md": "A shop.\n"})
    # Two pull requests' heads, kept as the user's clones keep the window's:
    # by their runs' refs, on no branch.
    run_git(path, "switch", "--quiet", "--detach", "main")
    first_head = commit_files(path, "Add a report", {"report.py": "TITLE = 1\n"})
    run_git(path, "update-ref", "refs/window/1001", first_head)
    run_git(path, "switch", "--quiet", "--detach", "main")
    second_head = commit_files(path, "Lower the rate", {"tax.py": "RATE = 10\n"})
    run_git(path, "update-ref", "refs/window/1002", second_head)
    run_git(path, "switch", "--quiet", "main")
    outside = tmp_path / "outside"
    outside.mkdir()
    return Clone(
        path=path, outside=outside, first_head=first_head, second_head=second_head
    )


def run_git(directory: Path, *arguments: str) -> str:
    """Run the real git in directory, as the tests' setup does; return its stdout."""
    result = subprocess.run(  # noqa: S603
        [GIT, "-C", str(directory), *arguments],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, os.fsdecode(result.stderr)
    return os.fsdecode(result.stdout)


def commit_files(repository: Path, message: str, files: dict[str, str]) -> str:
    """Commit the files, and return the new commit's full id."""
    for name, text in files.items():
        (repository / name).write_text(text, encoding="utf-8")
    run_git(repository, "add", "--all")
    run_git(repository, "commit", "--quiet", "--message", message)
    return run_git(repository, "rev-parse", "HEAD").strip()


def write_manifest(
    tmp_path: Path, rows: list[dict[str, str]], columns: tuple[str, ...] = COLUMNS
) -> str:
    """Write the rows as a CSV with these columns, and return its path."""
    path = tmp_path / "manifest.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(column, "") for column in columns])
    return str(path)


def line_of(
    pull_request: int | None,
    run: int,
    *,
    project: str = "urllib3",
    head: str = K16_HEAD,
) -> ManifestLine:
    return ManifestLine(
        project=project,
        pull_request=pull_request,
        run=run,
        run_started="2026-11-14T21:02:34Z",
        tested_head=head,
        ci_job="failed in a test step",
    )


def assert_refused(path: str) -> None:
    """read_manifest refuses the file: it raises, and not as a stub."""
    with pytest.raises(Exception) as raised:  # noqa: PT011
        manifest.read_manifest(path)

    assert not isinstance(raised.value, NotImplementedError)


def test_a_row_reads_into_its_manifest_line(tmp_path: Path) -> None:
    # Manifest 1: its tested head is the row's head.
    path = write_manifest(tmp_path, [ROW_5375])

    assert manifest.read_manifest(path) == [LINE_5375]


def test_a_jobs_outcome_that_holds_a_comma_reads_whole(tmp_path: Path) -> None:
    path = write_manifest(tmp_path, [ROW_3720])

    assert manifest.read_manifest(path) == [LINE_3720]


def test_a_row_with_no_pull_request_number_reads_as_none(tmp_path: Path) -> None:
    path = write_manifest(tmp_path, [{**ROW_5375, "pull_request": ""}])

    (line,) = manifest.read_manifest(path)

    assert line.pull_request is None


def test_every_row_is_read_in_the_files_order_whatever_its_project(
    tmp_path: Path,
) -> None:
    path = write_manifest(tmp_path, [ROW_5375, ROW_11226, ROW_3720])

    assert manifest.read_manifest(path) == [LINE_5375, LINE_11226, LINE_3720]


def test_columns_that_the_manifest_does_not_need_are_left_aside(
    tmp_path: Path,
) -> None:
    # No failed_steps, which no field holds, and a column of its own.
    columns = (*NEEDED_COLUMNS, "notes")
    path = write_manifest(tmp_path, [{**ROW_5375, "notes": "K16"}], columns)

    assert manifest.read_manifest(path) == [LINE_5375]


def test_the_windows_manifest_holds_48_lines_of_urllib3_and_42_of_poetry() -> None:
    lines = manifest.read_manifest(str(WINDOW_MANIFEST))

    projects = [line.project for line in lines]
    assert projects.count("urllib3") == 48
    assert projects.count("poetry") == 42
    assert len(lines) == 90


def test_the_windows_manifest_holds_k16s_pull_request_at_its_tested_head() -> None:
    lines = manifest.read_manifest(str(WINDOW_MANIFEST))

    assert LINE_5375 in lines


def test_the_windows_manifest_has_no_problem_for_either_pilot() -> None:
    lines = manifest.read_manifest(str(WINDOW_MANIFEST))
    urllib3 = [line for line in lines if line.project == "urllib3"]
    poetry = [line for line in lines if line.project == "poetry"]

    assert manifest.problems(urllib3, poetry) == []
    assert manifest.problems(poetry, urllib3) == []


def test_a_manifest_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    assert_refused(str(tmp_path / "missing.csv"))


@pytest.mark.parametrize("column", NEEDED_COLUMNS)
def test_a_manifest_that_lacks_a_column_it_needs_is_refused(
    tmp_path: Path, column: str
) -> None:
    columns = tuple(name for name in COLUMNS if name != column)

    assert_refused(write_manifest(tmp_path, [ROW_5375], columns))


@pytest.mark.parametrize(
    ("column", "value"), list(WRONG_VALUES.values()), ids=list(WRONG_VALUES)
)
def test_a_row_with_a_value_that_the_manifest_cannot_use_is_refused(
    tmp_path: Path, column: str, value: str
) -> None:
    assert_refused(write_manifest(tmp_path, [{**ROW_5375, column: value}]))


def test_lines_whose_numbers_are_their_own_have_no_problem() -> None:
    lines = [line_of(5375, 43640664881), line_of(5278, 43653393732)]
    others = [line_of(11226, 43162239778, project="poetry")]

    assert manifest.problems(lines, others) == []


def test_a_line_with_no_number_is_a_problem_that_names_its_run() -> None:
    # Manifest 2: the replay does not start, and says that the number must be
    # found first.
    lines = [line_of(5375, 43640664881), line_of(None, 26447918898)]

    found = manifest.problems(lines, [])

    assert len(found) == 1
    assert "26447918898" in found[0]


def test_each_line_with_no_number_is_a_problem_of_its_own() -> None:
    # Two lines with no number do not share one.
    lines = [line_of(None, 26447918898), line_of(None, 41279644934)]

    found = manifest.problems(lines, [])

    assert len(found) == 2
    assert any("26447918898" in problem for problem in found)
    assert any("41279644934" in problem for problem in found)


def test_a_number_that_both_pilots_hold_is_a_problem_that_names_it() -> None:
    # Manifest 3: Slice 1's report counts pull requests by number alone.
    lines = [line_of(5375, 43640664881)]
    others = [line_of(5375, 43162239778, project="poetry")]

    found = manifest.problems(lines, others)

    assert len(found) == 1
    assert "5375" in found[0]


def test_a_number_that_two_lines_of_one_pilot_hold_is_a_problem_that_names_it() -> None:
    lines = [line_of(5375, 43640664881), line_of(5375, 36813215434)]

    found = manifest.problems(lines, [])

    assert len(found) == 1
    assert "5375" in found[0]


def test_the_lines_whose_head_the_clone_lacks_are_listed_in_order(
    clone: Clone,
) -> None:
    # Manifest 4: those pull requests are listed as not replayed.
    lines = [
        line_of(5375, 1001, head=clone.first_head),
        line_of(5278, 2001, head=UNKNOWN_COMMIT),
        line_of(5357, 1002, head=clone.second_head),
        line_of(5296, 2002, head=OTHER_UNKNOWN_COMMIT),
    ]

    missing = manifest.missing_heads(lines, str(clone.path))

    assert missing == [lines[1], lines[3]]


def test_a_clone_that_holds_every_head_lists_no_line(clone: Clone) -> None:
    lines = [
        line_of(5375, 1001, head=clone.first_head),
        line_of(5357, 1002, head=clone.second_head),
    ]

    assert manifest.missing_heads(lines, str(clone.path)) == []


def test_missing_heads_raises_for_a_clone_that_is_no_repository(clone: Clone) -> None:
    # Rather than list every pull request as not replayed, which would end
    # the replay with exit 0 and nothing replayed.
    lines = [line_of(5375, 1001, head=clone.first_head)]

    with pytest.raises(Exception) as raised:  # noqa: PT011
        manifest.missing_heads(lines, str(clone.outside))

    assert not isinstance(raised.value, NotImplementedError)
