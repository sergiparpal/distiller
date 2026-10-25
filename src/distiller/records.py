import itertools
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from distiller.git import Commit, RepoPath
from distiller.junit import Pair
from distiller.selection import Test

# The records that the tool appends to the record file, an evaluated run's and
# a rejected run's, both with the run's key; the line that encode writes for
# each: ASCII JSON with no spaces between tokens, its keys in the SPEC's order,
# every list sorted by code point, and a newline at the end; decode, which
# takes a line of a record file back into its record only if the line is byte
# for byte what encode writes for that record, and gives None for any other
# line, whatever it holds, without raising; and the record file itself: read,
# opened for reading only, into one record per line, with NotARecord for the
# first line that is not one; searched for an evaluated run's record with a
# run's key, or a rejected run's with its key, reason and input, whatever its
# pr; and appended to with one write of a record's line, after whatever the
# file holds, which is not read. Before each open, os.stat checks that
# anything at the path is a regular file, since opening a FIFO blocks.


@dataclass(frozen=True)
class RunKey:
    head: str  # H's full commit id, or H as given
    junit_sha256: str | None


@dataclass(frozen=True)
class RejectedRecord:
    key: RunKey
    pr: int
    reason: str
    input_name: str


@dataclass(frozen=True)
class EvaluatedRecord:
    key: RunKey
    pr: int
    verdict: str
    merge_base: Commit
    coverage_commit: Commit
    selected_ms: int
    full_ms: int
    tests: int
    unmeasured: int
    tests_with_row: int
    tests_with_row_not_in_run: int
    floor_matched: bool
    rerun_given: bool
    not_reproduced: tuple[Pair, ...]
    failed_left_out: tuple[Test, ...]
    no_column: tuple[RepoPath, ...]
    import_only: tuple[RepoPath, ...]


Record = EvaluatedRecord | RejectedRecord


class NotARecord(Exception):  # noqa: N818
    path: str
    line_number: int

    def __init__(self, path: str, line_number: int) -> None:
        # The record file's path, as given on the command line, and the number
        # of the line that is not a record, counting from 1.
        super().__init__(path, line_number)
        self.path = path
        self.line_number = line_number


# What json.loads gives for a line, which decode checks: an object, a list, a
# string, a number, true or false, or null, each object and list holding more
# of the same.
type _Json = dict[str, _Json] | list[_Json] | str | int | float | bool | None

# The keys of each kind of record, and of an entry of failed_left_out, in the
# SPEC's order: decode tells the two kinds apart by their keys.
_REJECTED_KEYS = ("format", "head", "junit_sha256", "pr", "verdict", "reason", "input")
_EVALUATED_KEYS = (
    "format",
    "head",
    "junit_sha256",
    "pr",
    "verdict",
    "merge_base",
    "coverage_commit",
    "selected_ms",
    "full_ms",
    "tests",
    "unmeasured",
    "tests_with_row",
    "tests_with_row_not_in_run",
    "floor_matched",
    "rerun_given",
    "not_reproduced",
    "failed_left_out",
    "no_column",
    "import_only",
)
_LEFT_OUT_KEYS = ("pair", "node_id", "row")

# An evaluated record's durations and counts, each an int of 0 or more.
_COUNT_KEYS = (
    "selected_ms",
    "full_ms",
    "tests",
    "unmeasured",
    "tests_with_row",
    "tests_with_row_not_in_run",
)

# The values that the SPEC allows for an evaluated record's verdict, and for a
# rejected record's reason and input, each in the SPEC's order.
_EVALUATED_VERDICTS = ("green", "caught", "missed")
_REASONS = (
    "coverage-not-ancestor",
    "missing-history",
    "unsafe-xml",
    "no-shared-lines",
    "collection-error",
    "unusable-input",
)
_INPUTS = ("head", "base", "coverage", "junit", "rerun", "floor", "checkout")

# A line writes a pair as a list of two strings: classname and name.
_PAIR_LENGTH = 2

# A full commit id as git writes it, with SHA-1 or SHA-256, and a SHA-256 as
# hashlib writes it: lowercase hex digits. [0-9a-f], so that neither upper case
# nor the digits of another script, which an escape can write, pass.
_COMMIT_ID_PATTERN = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def encode(record: Record) -> bytes:
    # Rule 7: a dict in the SPEC's key order, which json.dumps keeps, written
    # with no spaces between tokens and a newline at the end. The default
    # ensure_ascii writes the SPEC's escapes, so the line is ASCII: a character
    # outside printable ASCII with no short escape becomes a backslash, u and
    # four lowercase hex digits, one beyond U+FFFF a surrogate pair, and a lone
    # surrogate from os.fsdecode a single escape. encode checks nothing, not
    # even whether the fields agree: it writes what the record holds, with its
    # lists sorted.
    if isinstance(record, EvaluatedRecord):
        fields = _evaluated_fields(record)
    else:
        fields = _rejected_fields(record)
    line = json.dumps(fields, separators=(",", ":")) + "\n"
    return line.encode("ascii")


def decode(line: bytes) -> Record | None:  # None: not a record
    # Rule 7's checks, in its order, each counting on those before it: the
    # line is ASCII; json.loads reads it into an object; the object's keys are
    # those of one kind of record, in the SPEC's order; then, in that kind's
    # own function, every value has its exact type, every value is one that
    # its field allows, and every list is sorted with no repeats. Last, the
    # record is rebuilt from the values, and the line is one only if encode
    # writes that record back as the very same bytes: that finds what the
    # other checks let through, such as a space between tokens, an escape
    # that encode would not write, or a key written twice. Whether the fields
    # agree with each other is not checked.
    if not line.isascii():
        return None
    fields = _json_object(line)
    if fields is None:
        return None
    keys = tuple(fields)  # in the line's order
    if keys == _REJECTED_KEYS:
        record = _rejected_record(fields)
    elif keys == _EVALUATED_KEYS:
        record = _evaluated_record(fields)
    else:
        return None  # a key missing or one too many, or keys in another order
    if record is None or encode(record) != line:
        return None
    return record


def read_record_file(path: str) -> list[Record] | None:
    # None: no file; raises NotARecord, or OSError if the file exists but
    # cannot be read. Rule 3: the path is checked before the file is opened.
    status = _status_of(path)
    if status is None:
        return None  # evaluate takes it as empty, and nothing is created
    _check_regular_file(status)
    data = Path(path).read_bytes()  # opened for reading only
    # One record per line, in the file's order, so a line held twice gives its
    # record twice. The first line that is not a record is the one named.
    records: list[Record] = []
    for line_number, line in enumerate(_lines_of(data), start=1):
        record = decode(line)
        if record is None:
            raise NotARecord(path, line_number)
        records.append(record)
    return records


def has_evaluated(records: list[Record], key: RunKey) -> bool:
    # An evaluated run's record with the run's key, whatever its pr, which is
    # not part of the key. A rejected run's record with that key is not one.
    return any(
        isinstance(record, EvaluatedRecord) and record.key == key for record in records
    )


def has_rejected(
    records: list[Record], key: RunKey, reason: str, input_name: str
) -> bool:
    # A rejected run's record with the run's key, reason and input, whatever
    # its pr, which is not part of the key.
    return any(
        isinstance(record, RejectedRecord)
        and record.key == key
        and record.reason == reason
        and record.input_name == input_name
        for record in records
    )


def append_record(path: str, record: Record) -> None:
    # Raises OSError if it cannot append. The line is encoded before anything
    # is opened, so a record that encode cannot write creates no file.
    line = encode(record)
    # Rule 3: the path is checked again before the append opens it, if
    # something is there; if nothing is, the open creates the file.
    status = _status_of(path)
    if status is not None:
        _check_regular_file(status)
    # Rule 8: "ab" opens the file for writing only, with O_APPEND, so that the
    # line goes after whatever the file holds, which nothing reads, and with
    # O_CREAT, so that a missing file is created. The default buffer hands the
    # system the whole line in one write. If the system writes only part of
    # it, as when the disk fills, the buffer tries to write the rest and, if
    # it cannot, raises OSError: the torn line stays, but the append fails.
    with Path(path).open("ab") as file:
        file.write(line)


def _evaluated_fields(record: EvaluatedRecord) -> dict[str, object]:
    # The first keys, then an evaluated run's own, in the SPEC's order, every
    # list sorted by code point whatever order the record holds it in (Rule 8).
    # json.dumps writes a tuple as a list, so a pair is a list of two strings,
    # and pairs compare as tuples do, by classname and then name.
    return _first_fields(record.key, record.pr, record.verdict) | {
        "merge_base": record.merge_base,
        "coverage_commit": record.coverage_commit,
        "selected_ms": record.selected_ms,
        "full_ms": record.full_ms,
        "tests": record.tests,
        "unmeasured": record.unmeasured,
        "tests_with_row": record.tests_with_row,
        "tests_with_row_not_in_run": record.tests_with_row_not_in_run,
        "floor_matched": record.floor_matched,
        "rerun_given": record.rerun_given,
        "not_reproduced": sorted(record.not_reproduced),
        "failed_left_out": _left_out_entries(record.failed_left_out),
        "no_column": sorted(record.no_column),
        "import_only": sorted(record.import_only),
    }


def _rejected_fields(record: RejectedRecord) -> dict[str, object]:
    # The first keys, with the verdict rejected, which no field holds, then the
    # reason and the input, whose key is input.
    return _first_fields(record.key, record.pr, "rejected") | {
        "reason": record.reason,
        "input": record.input_name,
    }


def _first_fields(key: RunKey, pr: int, verdict: str) -> dict[str, object]:
    # The keys that every record starts with, in the SPEC's order. The record
    # format version is always 1, since no record class holds it (open
    # question 2), and a junit_sha256 of None is written as null.
    return {
        "format": 1,
        "head": key.head,
        "junit_sha256": key.junit_sha256,
        "pr": pr,
        "verdict": verdict,
    }


def _left_out_entries(tests: tuple[Test, ...]) -> list[dict[str, object]]:
    # The failed tests left out, sorted by their pairs, since a Test has no
    # order of its own. sorted is stable, so two tests with one pair, which
    # Judgement never gives, would keep the record's order.
    in_pair_order = sorted(tests, key=lambda test: test.pair)
    return [_left_out_entry(test) for test in in_pair_order]


def _left_out_entry(test: Test) -> dict[str, object]:
    # A failed test left out, as an object with pair, node_id and row, in that
    # order, its row sorted by code point: a frozenset keeps no order. The
    # failed tests that Judgement leaves out are all measured, so the row is
    # set (Data model): cast tells pyright so, and checks nothing at run time.
    row = cast(frozenset[RepoPath], test.row)
    return {"pair": test.pair, "node_id": test.node_id, "row": sorted(row)}


def _json_object(line: bytes) -> dict[str, Any] | None:  # None: no object
    # Rule 7: None whatever json.loads raises. Given bytes, it reads them as
    # UTF-8, or as UTF-16 or UTF-32 when their first bytes hold NULs; it
    # raises JSONDecodeError for text that is not JSON, UnicodeDecodeError for
    # bytes that do not decode, ValueError for a number of more digits than
    # Python converts by default, and RecursionError for lists nested too
    # deep. Exception is caught, and not only those, so that decode never
    # raises; KeyboardInterrupt, which is not an Exception, still goes through.
    try:
        value: _Json = json.loads(line)
    except Exception:  # noqa: BLE001
        return None
    if type(value) is not dict:
        return None  # a list, a string, a number, true, false or null: no keys
    # Any, as json.loads gives them: what each value is, decode learns when it
    # checks the types, and then it uses each one as such, with no cast.
    return value


def _rejected_record(fields: dict[str, Any]) -> RejectedRecord | None:
    # Exact types, then allowed values; a rejected run's record holds no list.
    # Then the record, in which no field holds the verdict, always rejected.
    if not _has_rejected_types(fields):
        return None
    if not _has_rejected_values(fields):
        return None
    return RejectedRecord(
        key=_run_key(fields),
        pr=fields["pr"],
        reason=fields["reason"],
        input_name=fields["input"],
    )


def _evaluated_record(fields: dict[str, Any]) -> EvaluatedRecord | None:
    # Exact types, then allowed values, then lists sorted with no repeats.
    # Then the record, with each list as a tuple in the line's order, which is
    # sorted, and each row as the set that a Test holds.
    if not _has_evaluated_types(fields):
        return None
    if not _has_evaluated_values(fields):
        return None
    if not _has_sorted_lists(fields):
        return None
    return EvaluatedRecord(
        key=_run_key(fields),
        pr=fields["pr"],
        verdict=fields["verdict"],
        merge_base=fields["merge_base"],
        coverage_commit=fields["coverage_commit"],
        selected_ms=fields["selected_ms"],
        full_ms=fields["full_ms"],
        tests=fields["tests"],
        unmeasured=fields["unmeasured"],
        tests_with_row=fields["tests_with_row"],
        tests_with_row_not_in_run=fields["tests_with_row_not_in_run"],
        floor_matched=fields["floor_matched"],
        rerun_given=fields["rerun_given"],
        not_reproduced=tuple(
            _pair_from_list(pair) for pair in fields["not_reproduced"]
        ),
        failed_left_out=tuple(
            _left_out_test(entry) for entry in fields["failed_left_out"]
        ),
        no_column=tuple(fields["no_column"]),
        import_only=tuple(fields["import_only"]),
    )


def _has_first_types(fields: dict[str, Any]) -> bool:
    # The keys that every record starts with: format an int, head a string,
    # junit_sha256 a string or null, pr an int and verdict a string.
    return (
        _is_int(fields["format"])
        and _is_text(fields["head"])
        and _is_text_or_null(fields["junit_sha256"])
        and _is_int(fields["pr"])
        and _is_text(fields["verdict"])
    )


def _has_rejected_types(fields: dict[str, Any]) -> bool:
    # Then reason and input, both strings.
    return (
        _has_first_types(fields)
        and _is_text(fields["reason"])
        and _is_text(fields["input"])
    )


def _has_evaluated_types(fields: dict[str, Any]) -> bool:
    # Then merge_base and coverage_commit, strings; the durations and counts,
    # ints; floor_matched and rerun_given, booleans; not_reproduced, a list of
    # pairs; failed_left_out, a list of entries; and no_column and
    # import_only, lists of strings.
    return (
        _has_first_types(fields)
        and _is_text(fields["merge_base"])
        and _is_text(fields["coverage_commit"])
        and all(_is_int(fields[key]) for key in _COUNT_KEYS)
        and _is_bool(fields["floor_matched"])
        and _is_bool(fields["rerun_given"])
        and _is_list_of_pairs(fields["not_reproduced"])
        and _is_list_of_entries(fields["failed_left_out"])
        and _is_list_of_texts(fields["no_column"])
        and _is_list_of_texts(fields["import_only"])
    )


def _is_int(value: _Json) -> bool:
    # type, not isinstance: JSON's true and false are bools, which Python
    # also takes for 1 and 0, since bool is a subclass of int. And 7.0, which
    # equals 7, is a float.
    return type(value) is int


def _is_text(value: _Json) -> bool:
    return type(value) is str


def _is_text_or_null(value: _Json) -> bool:
    return value is None or type(value) is str


def _is_bool(value: _Json) -> bool:
    return type(value) is bool


def _is_list_of_texts(value: _Json) -> bool:
    return type(value) is list and all(_is_text(item) for item in value)


def _is_pair(value: _Json) -> bool:
    # A list of two strings, classname and name.
    return (
        type(value) is list
        and len(value) == _PAIR_LENGTH
        and all(_is_text(item) for item in value)
    )


def _is_list_of_pairs(value: _Json) -> bool:
    return type(value) is list and all(_is_pair(item) for item in value)


def _is_list_of_entries(value: _Json) -> bool:
    return type(value) is list and all(_is_left_out_entry(item) for item in value)


def _is_left_out_entry(value: _Json) -> bool:
    # An object whose keys are pair, node_id and row, in that order, which can
    # be checked only here, once the entry is known to be an object; its pair
    # a pair, its node id a string or null, as a Test's, and its row a list
    # of strings. A node id of null has the right type but is not allowed,
    # which the check of allowed values finds.
    return (
        type(value) is dict
        and tuple(value) == _LEFT_OUT_KEYS
        and _is_pair(value["pair"])
        and _is_text_or_null(value["node_id"])
        and _is_list_of_texts(value["row"])
    )


def _has_first_values(fields: dict[str, Any]) -> bool:
    # format is 1, junit_sha256 a SHA-256 or null, and pr 1 or more, with no
    # upper bound. head may be any string, an empty one included, and which
    # verdicts are allowed depends on the kind of record.
    return (
        fields["format"] == 1
        and _is_sha256_or_null(fields["junit_sha256"])
        and fields["pr"] >= 1
    )


def _has_rejected_values(fields: dict[str, Any]) -> bool:
    # The verdict is rejected, and reason and input are each one of their own
    # list, not checked as a pair: any reason may come with any input.
    return (
        _has_first_values(fields)
        and fields["verdict"] == "rejected"
        and fields["reason"] in _REASONS
        and fields["input"] in _INPUTS
    )


def _has_evaluated_values(fields: dict[str, Any]) -> bool:
    # The verdict is green, caught or missed; merge_base and coverage_commit
    # are full commit ids; the durations and counts are 0 or more, with no
    # upper bound; and every failed test left out is measured. Any string
    # elsewhere may be empty, and floor_matched and rerun_given any boolean.
    return (
        _has_first_values(fields)
        and fields["verdict"] in _EVALUATED_VERDICTS
        and _is_commit_id(fields["merge_base"])
        and _is_commit_id(fields["coverage_commit"])
        and all(fields[key] >= 0 for key in _COUNT_KEYS)
        and all(_is_measured(entry) for entry in fields["failed_left_out"])
    )


def _is_sha256_or_null(value: str | None) -> bool:
    return value is None or _SHA256_PATTERN.fullmatch(value) is not None


def _is_commit_id(value: str) -> bool:
    return _COMMIT_ID_PATTERN.fullmatch(value) is not None


def _is_measured(entry: dict[str, Any]) -> bool:
    # The failed tests that Judgement leaves out are all measured, so each has
    # a node id, not null, and a row that is not empty: an empty row is no
    # row.
    return entry["node_id"] is not None and len(entry["row"]) > 0


def _has_sorted_lists(fields: dict[str, Any]) -> bool:
    # not_reproduced by classname and then name; failed_left_out by its
    # pairs, so that two entries with one pair are a repeat, whatever their
    # node ids; each row; no_column; and import_only.
    entries = fields["failed_left_out"]
    return (
        _is_sorted_without_repeats(fields["not_reproduced"])
        and _is_sorted_without_repeats([entry["pair"] for entry in entries])
        and all(_is_sorted_without_repeats(entry["row"]) for entry in entries)
        and _is_sorted_without_repeats(fields["no_column"])
        and _is_sorted_without_repeats(fields["import_only"])
    )


def _is_sorted_without_repeats(items: list[Any]) -> bool:
    # Each item comes before the next one, so the list is in order and holds
    # nothing twice. Strings compare by code point, which is Python's order
    # for str, and pairs, lists of two strings, by classname and then name.
    return all(earlier < later for earlier, later in itertools.pairwise(items))


def _run_key(fields: dict[str, Any]) -> RunKey:
    return RunKey(head=fields["head"], junit_sha256=fields["junit_sha256"])


def _pair_from_list(pair: list[str]) -> Pair:
    # A pair, which a line writes as a list of two strings, as the tuple of
    # classname and name that a record holds.
    return (pair[0], pair[1])


def _left_out_test(entry: dict[str, Any]) -> Test:
    # An entry of failed_left_out as the Test that it was written from, its
    # row as a set.
    return Test(
        pair=_pair_from_list(entry["pair"]),
        node_id=entry["node_id"],
        row=frozenset(entry["row"]),
    )


def _status_of(path: str) -> os.stat_result | None:  # None: nothing there
    # Rule 3's os.stat, which Path.stat runs. It follows a symbolic link to
    # what the link names, so a link that names nothing is nothing there. Any
    # other error, such as for a loop of links, a regular file used as a
    # directory or a directory that the tool may not search, goes through as
    # the OSError it is: the record file cannot be read or appended to.
    try:
        return Path(path).stat()
    except FileNotFoundError:
        return None  # nothing at the path, or a directory on it is missing


def _check_regular_file(status: os.stat_result) -> None:
    # Rule 3: only a regular file is opened, since opening a FIFO blocks, for
    # reading until something opens it for writing and for writing until
    # something opens it for reading. A directory, a FIFO, a device or a
    # socket is there, but can be neither read nor appended to: any other
    # failure, raised as a plain OSError.
    if not stat.S_ISREG(status.st_mode):
        message = "the record file is not a regular file"
        raise OSError(message)


def _lines_of(data: bytes) -> list[bytes]:
    # Rule 7: the bytes cut after each \n only, not with splitlines(), which
    # also cuts at a \r alone. Every piece but the last came before a \n,
    # which it gets back, since decode takes a line with its newline.
    pieces = data.split(b"\n")
    lines = [piece + b"\n" for piece in pieces[:-1]]
    # The last piece is what follows the last \n: nothing when the file is
    # empty or ends in a newline, and then no line; anything else is a line
    # that lacks its newline, which is not a record.
    if pieces[-1] != b"":
        lines.append(pieces[-1])
    return lines
