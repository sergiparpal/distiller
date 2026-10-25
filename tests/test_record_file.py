import contextlib
import dataclasses
import os
import signal
from collections.abc import Generator
from pathlib import Path
from types import FrameType

import pytest

from distiller import records, selection

# Each test writes its own record file in tmp_path, or hands has_evaluated and
# has_rejected records built as literals, and watches records from outside:
# what read_record_file, has_evaluated, has_rejected and append_record return
# or raise, and the bytes each file holds after. Each test calls one of them,
# and only that one. K1's and K4's lines are written out as the SPEC gives
# them, and K10's as K4's with K8's reason; the other lines are built from
# them.
#
# Where the SPEC leaves the record file open, these tests follow the answers
# given in task 12's tests phase, 2026-10-25: NotARecord keeps the path it is
# given, as given, and the line number, as path and line_number; K11's
# evaluated record is K1's, since K11 names no diff or failed test; a record
# file that exists and is empty holds no records, and is not None; a record
# file that may only be read is read; reading a record file that does not
# exist creates nothing; read_record_file prints nothing; append_record writes
# the line after whatever the file holds, without looking at it; a line that a
# file holds twice gives its record twice; and append_record checks the path
# before it opens it, as Rule 3 says, so that a FIFO raises OSError without
# blocking, as do a directory, a path in a directory that does not exist and a
# file that the tool may not write.

# How long a call may run before fails_if_it_blocks stops it.
BLOCKING_SECONDS = 5

# The record file's path as a command line could give it, from the working
# directory, which the record_file fixture sets to tmp_path. NotARecord names
# it exactly, ./ included.
RECORDS = "./ci/records.jsonl"

# A record file's path in a directory that does not exist.
IN_A_MISSING_DIRECTORY = "./missing/records.jsonl"

# The fixture's commit ids and its JUnit file's SHA-256, as
# tests/test_records.py, tests/test_decode.py and tests/test_messages.py write
# them: <H>, <M> and <sha>, so that K4's line is the first line of K15's record
# file, and <merge-base>, which differs from <M>.
HEAD = "c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4"
MERGE_BASE = "9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e"
M = "e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9"
JUNIT_SHA256 = "5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a"
KEY = records.RunKey(head=HEAD, junit_sha256=JUNIT_SHA256)

# The fixture's run's key with no SHA-256, as when its full-run JUnit file is
# missing or cannot be read.
KEY_WITH_NO_SHA256 = records.RunKey(head=HEAD, junit_sha256=None)

# Another run's key, as tests/test_messages.py writes it, and keys that share
# one half of the fixture's run's key.
OTHER_HEAD = "0a9b8c7d6e5f40312a3b4c5d6e7f8091a2b3c4d5"
OTHER_JUNIT_SHA256 = "f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d2c3b4a5968778695a4b3c2d1e0f"
OTHER_KEY = records.RunKey(head=OTHER_HEAD, junit_sha256=OTHER_JUNIT_SHA256)
ANOTHER_HEADS_KEY = records.RunKey(head=OTHER_HEAD, junit_sha256=JUNIT_SHA256)
ANOTHER_JUNITS_KEY = records.RunKey(head=HEAD, junit_sha256=OTHER_JUNIT_SHA256)

# The byte order mark that a file saved as UTF-8 can start with.
BOM = b"\xef\xbb\xbf"


# K1 and K13: a diff that modifies only templates/invoice.html, and a full run
# of pull request 7 in which test_render failed, with no rerun file.

K1_RECORD = records.EvaluatedRecord(
    key=KEY,
    pr=7,
    verdict="missed",
    merge_base=MERGE_BASE,
    coverage_commit=M,
    selected_ms=0,
    full_ms=12000,
    tests=4,
    unmeasured=0,
    tests_with_row=4,
    tests_with_row_not_in_run=0,
    floor_matched=False,
    rerun_given=False,
    not_reproduced=(),
    failed_left_out=(
        selection.Test(
            pair=("tests.test_report", "test_render"),
            node_id="tests/test_report.py::test_render",
            row=frozenset({"src/shop/pricing.py", "src/shop/report.py"}),
        ),
    ),
    no_column=("templates/invoice.html",),
    import_only=(),
)

# K1's line, as the SPEC gives it, with the values above for <H>, <sha>,
# <merge-base> and <M>.
K1_LINE = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
    b'"junit_sha256":'
    b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
    b'"pr":7,"verdict":"missed",'
    b'"merge_base":"9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e",'
    b'"coverage_commit":"e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9",'
    b'"selected_ms":0,"full_ms":12000,'
    b'"tests":4,"unmeasured":0,"tests_with_row":4,"tests_with_row_not_in_run":0,'
    b'"floor_matched":false,"rerun_given":false,'
    b'"not_reproduced":[],'
    b'"failed_left_out":[{"pair":["tests.test_report","test_render"],'
    b'"node_id":"tests/test_report.py::test_render",'
    b'"row":["src/shop/pricing.py","src/shop/report.py"]}],'
    b'"no_column":["templates/invoice.html"],'
    b'"import_only":[]}\n'
)

# K1's line torn by an append that a killed runner or a full disk cut short,
# 20 digits into its commit id.
TORN_K1 = b'{"format":1,"head":"c7d2f4a91b3e5f6082a4'


# K4: coverage recorded at a commit that is neither the merge-base nor one of
# its ancestors. K15's record file starts with its line.

K4_RECORD = records.RejectedRecord(
    key=KEY, pr=7, reason="coverage-not-ancestor", input_name="coverage"
)
K4_LINE = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
    b'"junit_sha256":'
    b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
    b'"pr":7,"verdict":"rejected","reason":"coverage-not-ancestor",'
    b'"input":"coverage"}\n'
)


# K10 and K11: the fixture's run rejected because its coverage file was
# missing, as in K8, and its line. K11 evaluates that run again with its
# coverage file and names no diff or failed test, so its evaluated record is
# K1's, which has the same key.

K10_RECORD = records.RejectedRecord(
    key=KEY, pr=7, reason="unusable-input", input_name="coverage"
)
K10_LINE = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
    b'"junit_sha256":'
    b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
    b'"pr":7,"verdict":"rejected","reason":"unusable-input",'
    b'"input":"coverage"}\n'
)


# K15: a record file whose first line is a record and whose second line is
# not one and holds the text canary, as tests/test_messages.py writes it.

CANARY = "canary"
K15_SECOND_LINE = CANARY.encode("ascii") + b"\n"
K15_RECORD_FILE = K4_LINE + K15_SECOND_LINE


class BlockedError(BaseException):
    """A call was still running when the alarm went off.

    A BaseException, so that no `except Exception` in the code under test
    catches it.
    """


@contextlib.contextmanager
def fails_if_it_blocks() -> Generator[None]:
    """Stop with BlockedError a call that blocks, so that the test fails.

    Opening a FIFO for reading waits until something opens it for writing, and
    opening one for writing waits until something opens it for reading, which
    nothing does here: without the alarm, the test would hang.
    """

    def interrupt(_signal_number: int, _frame: FrameType | None) -> None:
        raise BlockedError

    previous = signal.signal(signal.SIGALRM, interrupt)
    signal.alarm(BLOCKING_SECONDS)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


@pytest.fixture
def record_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The file that RECORDS names, with tmp_path as the working directory.

    Nothing is there yet: each test puts there what it needs.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ci").mkdir()
    return tmp_path / "ci" / "records.jsonl"


def everything_under(directory: Path) -> list[Path]:
    """Every file and directory under this one, sorted."""
    return sorted(directory.rglob("*"))


def records_read_from(data: bytes, record_file: Path) -> list[records.Record] | None:
    """What read_record_file gives for a record file that holds data."""
    record_file.write_bytes(data)
    return records.read_record_file(RECORDS)


def not_a_record_at(data: bytes, record_file: Path) -> tuple[str, int]:
    """The path and line number that read_record_file's NotARecord names, for a
    record file that holds data."""
    record_file.write_bytes(data)
    with pytest.raises(records.NotARecord) as caught:
        records.read_record_file(RECORDS)
    return caught.value.path, caught.value.line_number


# Reading

# A record file's lines, as read_record_file finds them: the file's bytes cut
# right after each newline, each line keeping its newline, as decode needs it.
# The empty piece after a last newline is no line, so a file that ends in a
# newline has no empty last line, and an empty file has no line at all; what
# follows the last newline, if anything, is a line that lacks its newline,
# which is not a record. Lines are numbered from 1.


@pytest.mark.usefixtures("record_file")
@pytest.mark.parametrize(
    "path",
    [
        pytest.param(RECORDS, id="K13, nothing at the path"),
        pytest.param(
            IN_A_MISSING_DIRECTORY, id="a directory on the path that does not exist"
        ),
    ],
)
def test_with_no_file_at_the_path_reading_gives_none_and_creates_nothing(
    path: str, tmp_path: Path
) -> None:
    # Only the append creates the record file; the report never takes a
    # missing one as empty.
    before = everything_under(tmp_path)

    found = records.read_record_file(path)

    assert found is None
    assert everything_under(tmp_path) == before


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param(K1_LINE, [K1_RECORD], id="K13's record file, K1's line"),
        pytest.param(
            K10_LINE + K1_LINE,
            [K10_RECORD, K1_RECORD],
            id="K11's record file, K10's record and then K1's",
        ),
        pytest.param(
            K1_LINE + K4_LINE,
            [K1_RECORD, K4_RECORD],
            id="an evaluated record and then a rejected one",
        ),
        pytest.param(
            K10_LINE + K10_LINE,
            [K10_RECORD, K10_RECORD],
            id="the same line twice, as two records",
        ),
    ],
)
def test_a_file_of_records_gives_them_in_the_order_of_its_lines(
    data: bytes, expected: list[records.Record], record_file: Path
) -> None:
    assert records_read_from(data, record_file) == expected


def test_an_empty_record_file_gives_no_records(record_file: Path) -> None:
    # It exists, so it is not None, which the report takes for a record file
    # that does not exist or cannot be read.
    assert records_read_from(b"", record_file) == []


def test_k15_the_line_that_is_not_a_record_is_named_line_2(record_file: Path) -> None:
    # The message that names the record file and line 2 is messages'; the
    # path, as given, and the number are NotARecord's.
    assert not_a_record_at(K15_RECORD_FILE, record_file) == (RECORDS, 2)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(K15_RECORD_FILE, id="K15"),
        pytest.param(K10_LINE + K1_LINE, id="K11's record file"),
        pytest.param(K10_LINE + TORN_K1, id="a last line torn"),
    ],
)
def test_reading_leaves_the_record_file_byte_for_byte_as_it_was(
    data: bytes, record_file: Path
) -> None:
    record_file.write_bytes(data)
    os.utime(record_file, ns=(0, 0))  # an old time, which any write would replace

    with contextlib.suppress(records.NotARecord):
        records.read_record_file(RECORDS)

    assert record_file.read_bytes() == data
    assert record_file.stat().st_mtime_ns == 0


def test_k15_reading_prints_nothing_so_nothing_it_prints_holds_canary(
    record_file: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    # Every text on stderr comes from messages, printed by evaluate, report
    # and cli.
    record_file.write_bytes(K15_RECORD_FILE)
    capfd.readouterr()  # drop what was written before the read

    with contextlib.suppress(records.NotARecord):
        records.read_record_file(RECORDS)

    assert capfd.readouterr() == ("", "")


# Record files with exactly one line that is not a record, and that line's
# number: the SPEC does not say which line is named when there are several.
ONE_LINE_THAT_IS_NOT_A_RECORD = [
    pytest.param(K4_LINE + b"\n" + K1_LINE, 2, id="an empty line between two records"),
    pytest.param(
        K4_LINE + K1_LINE + b"\n", 3, id="an empty line after the last record"
    ),
    pytest.param(b"\n", 1, id="an empty line alone"),
    pytest.param(
        K4_LINE + K1_LINE.removesuffix(b"\n"),
        2,
        id="a last line that lacks its newline",
    ),
    pytest.param(K4_LINE + TORN_K1, 2, id="a last line torn"),
    pytest.param(
        K4_LINE + K1_LINE.removesuffix(b"\n") + b"\r\n" + K10_LINE,
        2,
        id="a line that ends in a carriage return and a newline",
    ),
    pytest.param(
        K4_LINE + K1_LINE.removesuffix(b"\n") + b"\r" + K10_LINE,
        2,
        id="a carriage return in place of a newline",
    ),
    pytest.param(K4_LINE + b"\xff" + K1_LINE, 2, id="a byte that UTF-8 never uses"),
    pytest.param(BOM + K4_LINE + K1_LINE, 1, id="a UTF-8 byte order mark first"),
    pytest.param(K4_LINE * 11 + K15_SECOND_LINE, 12, id="the twelfth line"),
]


@pytest.mark.parametrize(("data", "line_number"), ONE_LINE_THAT_IS_NOT_A_RECORD)
def test_a_line_that_is_not_a_record_is_named_by_its_number(
    data: bytes, line_number: int, record_file: Path
) -> None:
    assert not_a_record_at(data, record_file) == (RECORDS, line_number)


# A record file that exists but cannot be read is any other failure, which
# read_record_file raises as OSError. The SPEC names only that class, not which
# subclass or what text, so pytest.raises(OSError) carries no match, and ruff's
# PT011, which asks for one, is silenced on its line.


def test_a_directory_cannot_be_read(record_file: Path) -> None:
    record_file.mkdir()

    with pytest.raises(OSError):  # noqa: PT011
        records.read_record_file(RECORDS)


def test_a_record_file_the_tool_is_not_allowed_to_read_cannot_be_read(
    record_file: Path,
) -> None:
    record_file.write_bytes(K10_LINE)
    record_file.chmod(0)
    if os.access(record_file, os.R_OK):
        pytest.skip("this user reads a file whatever its mode, as root does")

    with pytest.raises(OSError):  # noqa: PT011
        records.read_record_file(RECORDS)


def test_a_fifo_cannot_be_read_and_reading_it_does_not_block(record_file: Path) -> None:
    # Rule 3: the path is checked with os.stat before it is opened.
    os.mkfifo(record_file)

    with fails_if_it_blocks(), pytest.raises(OSError):  # noqa: PT011
        records.read_record_file(RECORDS)


def test_a_record_file_that_may_only_be_read_is_read(record_file: Path) -> None:
    # The report reads record files that exist and can be read.
    record_file.write_bytes(K10_LINE + K1_LINE)
    record_file.chmod(0o444)

    assert records.read_record_file(RECORDS) == [K10_RECORD, K1_RECORD]


@pytest.mark.parametrize(
    ("path", "line_number"),
    [
        pytest.param(RECORDS, 2, id="K15's record file and line"),
        pytest.param("records.jsonl", 15, id="another file and line"),
    ],
)
def test_not_a_record_keeps_its_path_and_line_number(
    path: str, line_number: int
) -> None:
    error = records.NotARecord(path, line_number)

    assert error.path == path
    assert error.line_number == line_number


# Looking up a key

# The fixture's run recorded for pull request 12: pr is not part of the key.
K1_FOR_PR_12 = dataclasses.replace(K1_RECORD, pr=12)
K10_FOR_PR_12 = dataclasses.replace(K10_RECORD, pr=12)

# Another run's records, one evaluated and one rejected as K10's was.
OTHER_RUN_EVALUATED = dataclasses.replace(K1_RECORD, key=OTHER_KEY, pr=12)
OTHER_RUN_REJECTED = dataclasses.replace(K10_RECORD, key=OTHER_KEY, pr=12)

# K8's rejected records for a full-run JUnit file that is missing, whose key
# has no SHA-256, and for an H that names no commit, which the key holds as
# given.
MISSING_JUNIT_RECORD = records.RejectedRecord(
    key=KEY_WITH_NO_SHA256, pr=7, reason="unusable-input", input_name="junit"
)
H_AS_GIVEN_KEY = records.RunKey(head="no-such-head", junit_sha256=JUNIT_SHA256)
H_AS_GIVEN_RECORD = records.RejectedRecord(
    key=H_AS_GIVEN_KEY, pr=7, reason="unusable-input", input_name="head"
)


def test_k11_a_rejected_record_with_the_runs_key_is_no_evaluated_record() -> None:
    # K11's record file holds only K10's record, so the run is evaluated.
    assert records.has_evaluated([K10_RECORD], KEY) is False


@pytest.mark.parametrize(
    "recorded",
    [
        pytest.param([K1_RECORD], id="the run's evaluated record alone"),
        pytest.param([K10_RECORD, K1_RECORD], id="after K10's, as K11 leaves them"),
        pytest.param(
            [OTHER_RUN_EVALUATED, K1_RECORD, OTHER_RUN_REJECTED],
            id="among another run's records",
        ),
        pytest.param([K1_FOR_PR_12], id="recorded for another pull request"),
    ],
)
def test_an_evaluated_record_with_the_runs_key_is_found(
    recorded: list[records.Record],
) -> None:
    assert records.has_evaluated(recorded, KEY) is True


@pytest.mark.parametrize(
    ("recorded", "key"),
    [
        pytest.param([], KEY, id="an empty record file, as a missing one is taken"),
        pytest.param([K1_RECORD], ANOTHER_HEADS_KEY, id="another head"),
        pytest.param([K1_RECORD], ANOTHER_JUNITS_KEY, id="another JUnit file"),
        pytest.param(
            [K1_RECORD],
            KEY_WITH_NO_SHA256,
            id="a key with no SHA-256, a record with one",
        ),
        pytest.param(
            [dataclasses.replace(K1_RECORD, key=KEY_WITH_NO_SHA256)],
            KEY,
            id="a record with no SHA-256, a key with one",
        ),
    ],
)
def test_no_evaluated_record_with_the_runs_key_is_found(
    recorded: list[records.Record], key: records.RunKey
) -> None:
    assert records.has_evaluated(recorded, key) is False


@pytest.mark.parametrize(
    ("recorded", "key", "reason", "input_name"),
    [
        pytest.param(
            [K10_RECORD],
            KEY,
            "unusable-input",
            "coverage",
            id="K10, the run rejected again for its missing coverage file",
        ),
        pytest.param(
            [K10_FOR_PR_12],
            KEY,
            "unusable-input",
            "coverage",
            id="recorded for another pull request",
        ),
        pytest.param(
            [MISSING_JUNIT_RECORD],
            KEY_WITH_NO_SHA256,
            "unusable-input",
            "junit",
            id="a missing JUnit file, so a key with no SHA-256",
        ),
        pytest.param(
            [H_AS_GIVEN_RECORD],
            H_AS_GIVEN_KEY,
            "unusable-input",
            "head",
            id="an H that names no commit, as given",
        ),
        pytest.param(
            [K4_RECORD, K10_RECORD, OTHER_RUN_REJECTED],
            KEY,
            "unusable-input",
            "coverage",
            id="between another rejection of the run and another run's",
        ),
    ],
)
def test_the_same_rejection_of_the_run_is_found_whatever_its_pr(
    recorded: list[records.Record], key: records.RunKey, reason: str, input_name: str
) -> None:
    assert records.has_rejected(recorded, key, reason, input_name) is True


@pytest.mark.parametrize(
    ("recorded", "key"),
    [
        pytest.param([], KEY, id="an empty record file, as a missing one is taken"),
        pytest.param(
            [K4_RECORD], KEY, id="the run rejected for another reason, same input"
        ),
        pytest.param(
            [dataclasses.replace(K10_RECORD, input_name="junit")],
            KEY,
            id="the run rejected for the same reason, another input",
        ),
        pytest.param([K10_RECORD], ANOTHER_HEADS_KEY, id="another head"),
        pytest.param([K10_RECORD], ANOTHER_JUNITS_KEY, id="another JUnit file"),
        pytest.param(
            [K10_RECORD],
            KEY_WITH_NO_SHA256,
            id="a key with no SHA-256, a record with one",
        ),
        pytest.param(
            [dataclasses.replace(K10_RECORD, key=KEY_WITH_NO_SHA256)],
            KEY,
            id="a record with no SHA-256, a key with one",
        ),
        pytest.param([K1_RECORD], KEY, id="only the run's evaluated record"),
    ],
)
def test_no_rejection_with_that_key_reason_and_input_is_found(
    recorded: list[records.Record], key: records.RunKey
) -> None:
    # Each looks up K10's rejection: unusable-input, with coverage.
    assert records.has_rejected(recorded, key, "unusable-input", "coverage") is False


# Appending

# What Rule 8 asks of the append can be seen from outside only in part: the
# bytes that the file holds after, the file it creates, and that the line goes
# to the file already at the path, whose inode stays. That the line is written
# with one write, to a file opened for appending, rather than with two, or by
# rewriting the file in place, leaves the same bytes and the same inode.


def test_k13_appending_to_no_file_creates_it_holding_only_k1s_line(
    record_file: Path,
) -> None:
    records.append_record(RECORDS, K1_RECORD)

    assert record_file.read_bytes() == K1_LINE


def test_k11_the_evaluated_record_is_appended_after_the_rejected_one(
    record_file: Path,
) -> None:
    record_file.write_bytes(K10_LINE)

    records.append_record(RECORDS, K1_RECORD)

    assert record_file.read_bytes() == K10_LINE + K1_LINE


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"", id="an empty file"),
        pytest.param(K15_RECORD_FILE, id="K15's record file, which it does not read"),
    ],
)
def test_appending_keeps_every_byte_already_there(
    data: bytes, record_file: Path
) -> None:
    record_file.write_bytes(data)

    records.append_record(RECORDS, K10_RECORD)

    assert record_file.read_bytes() == data + K10_LINE


def test_the_line_goes_to_the_file_at_the_path_not_to_a_new_one(
    record_file: Path,
) -> None:
    # A new file written and renamed over the record file would have another
    # inode.
    record_file.write_bytes(K10_LINE)
    before = record_file.stat()

    records.append_record(RECORDS, K1_RECORD)

    after = record_file.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)


# Appending where the line cannot go raises OSError, with no match for the
# reason given above. Rule 3 checks the record file's path before each time it
# is opened, for appending too: opening a FIFO for writing blocks.


def test_a_directory_cannot_be_appended_to(record_file: Path) -> None:
    record_file.mkdir()

    with pytest.raises(OSError):  # noqa: PT011
        records.append_record(RECORDS, K10_RECORD)


def test_a_fifo_cannot_be_appended_to_and_appending_does_not_block(
    record_file: Path,
) -> None:
    os.mkfifo(record_file)

    with fails_if_it_blocks(), pytest.raises(OSError):  # noqa: PT011
        records.append_record(RECORDS, K10_RECORD)


@pytest.mark.usefixtures("record_file")
def test_a_directory_that_does_not_exist_cannot_be_appended_to() -> None:
    with pytest.raises(OSError):  # noqa: PT011
        records.append_record(IN_A_MISSING_DIRECTORY, K10_RECORD)


def test_a_record_file_the_tool_is_not_allowed_to_write_cannot_be_appended_to(
    record_file: Path,
) -> None:
    record_file.write_bytes(K10_LINE)
    record_file.chmod(0o444)
    if os.access(record_file, os.W_OK):
        pytest.skip("this user writes a file whatever its mode, as root does")

    with pytest.raises(OSError):  # noqa: PT011
        records.append_record(RECORDS, K1_RECORD)
