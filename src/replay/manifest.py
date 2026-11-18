import csv
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from replay import checkout

# Reads the window's manifest, a CSV with one row per pull request, into
# ManifestLines; finds the problems that keep a replay from starting; and lists
# the lines whose head the clone lacks, which are not replayed. A file that
# cannot be read as the manifest makes read_manifest raise: a ValueError that
# names the file, or, for a path with no file, the OSError of opening it. The
# harness turns either into its exit 1.

# The columns that the manifest needs. Any other, such as failed_steps, is left
# aside.
NEEDED_COLUMNS = ("project", "pull_request", "run_id", "run_started", "head", "job")


@dataclass(frozen=True)
class ManifestLine:
    project: str
    pull_request: int | None  # None: to be found before the first record
    run: int
    run_started: str  # ISO 8601, UTC
    tested_head: str
    ci_job: str  # the job's outcome, as GitHub gave it on 2026-11-16


def read_manifest(path: str) -> list[ManifestLine]:
    # Every row, in the file's order, whatever its project: the harness keeps
    # its pilot's lines and passes the others to problems.
    with Path(path).open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        _refuse_missing_columns(path, reader.fieldnames)
        return [_line_of(path, row) for row in reader]


def problems(lines: list[ManifestLine], others: list[ManifestLine]) -> list[str]:
    # One message for each problem. lines are the pilot's own; others, the other
    # pilot's, count only for the numbers that two lines hold.
    no_number = [
        _no_number_message(line) for line in lines if line.pull_request is None
    ]
    held_twice = [
        _held_twice_message(number) for number in _numbers_held_twice(lines, others)
    ]
    return no_number + held_twice


def missing_heads(lines: list[ManifestLine], clone: str) -> list[ManifestLine]:
    # The lines whose head the clone lacks, in order. A git that fails raises,
    # as has_commit does, rather than leave every pull request out.
    return [line for line in lines if not checkout.has_commit(clone, line.tested_head)]


def _no_number_message(line: ManifestLine) -> str:
    return (
        f"the row of run {line.run} has no pull request number: "
        "find it before the replay starts"
    )


def _held_twice_message(number: int) -> str:
    return (
        f"pull request #{number} is in two rows of the manifest, which holds "
        "one row for each pull request"
    )


def _refuse_missing_columns(path: str, columns: Sequence[str] | None) -> None:
    # columns is None when the file is empty, with not even a header.
    for column in NEEDED_COLUMNS:
        if columns is None or column not in columns:
            message = f"{path}: the manifest has no column {column}"
            raise ValueError(message)


def _line_of(path: str, row: dict[str, str]) -> ManifestLine:
    return ManifestLine(
        project=row["project"],
        pull_request=_number_or_none(path, row["pull_request"]),
        run=_whole_number(path, "run_id", row["run_id"]),
        run_started=_run_start(path, row["run_started"]),
        tested_head=row["head"],
        ci_job=row["job"],
    )


def _number_or_none(path: str, text: str) -> int | None:
    if text == "":
        return None  # to be found before the first record
    return _whole_number(path, "pull_request", text)


def _whole_number(path: str, column: str, text: str) -> int:
    try:
        return int(text)
    except ValueError as error:
        message = f"{path}: {column} is not a whole number: {text!r}"
        raise ValueError(message) from error


def _run_start(path: str, text: str) -> str:
    # A start with no time zone would be read as local time, and give another
    # base commit unseen.
    try:
        started = datetime.fromisoformat(text)
    except ValueError as error:
        message = f"{path}: run_started is not an ISO 8601 date: {text!r}"
        raise ValueError(message) from error
    if started.tzinfo is None:
        message = f"{path}: run_started has no time zone: {text!r}"
        raise ValueError(message)
    return text


def _numbers_held_twice(
    lines: list[ManifestLine], others: list[ManifestLine]
) -> list[int]:
    # The numbers of the pilot's lines that another line holds too, of this
    # pilot or of the other, each once, in the order of its first line: Slice
    # 1's report counts pull requests by number alone. A line with no number
    # shares none.
    counts = Counter(line.pull_request for line in [*lines, *others])
    held_twice: list[int] = []
    for line in lines:
        number = line.pull_request
        if number is not None and counts[number] > 1 and number not in held_twice:
            held_twice.append(number)
    return held_twice
