import dataclasses
import json

import pytest

from distiller import records, selection

# Each test hands decode one line of a record file, as bytes, and compares the
# whole result with the record that the line holds, or with None for a line
# that is not a record: decode never raises. K1's and K4's lines are written
# out as the SPEC gives them. A line that is not a record is, where it can be,
# one of them with a single change, so that it is not a record for one reason
# alone; the comment above each list names the check of Rule 7 that finds it.
# Other records are written with encode, since decode takes back every line
# that encode writes.
#
# Where the SPEC leaves a field's values open, these tests follow the answers
# given in task 11's tests phase, 2026-10-24: merge_base and coverage_commit
# are 40 or 64 lowercase hex digits, and a SHA-256 is 64 of them; pr is 1 or
# more, and the durations and counts 0 or more, with no upper bound; any string
# may be empty; a failed test left out has a node id and a row that is not
# empty; an evaluated record's verdict is green, caught or missed; reason and
# input are each checked against their own list, not as a pair; and two failed
# tests left out with one pair are a repeat, whatever their node ids.

# The fixture's commit ids and its JUnit file's SHA-256, as
# tests/test_records.py and tests/test_messages.py write them: <H>, <M> and
# <sha>, so that K4's line is the first line of K15's record file, and
# <merge-base>, which differs from <M>.
HEAD = "c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4"
MERGE_BASE = "9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e"
M = "e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9"
JUNIT_SHA256 = "5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a"
KEY = records.RunKey(head=HEAD, junit_sha256=JUNIT_SHA256)

# Another run's key, as tests/test_messages.py writes it.
OTHER_HEAD = "0a9b8c7d6e5f40312a3b4c5d6e7f8091a2b3c4d5"
OTHER_JUNIT_SHA256 = "f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d2c3b4a5968778695a4b3c2d1e0f"

# The merge-base and M as 64-digit commit ids, which git writes in a repository
# that names its objects by SHA-256.
SHA256_MERGE_BASE = MERGE_BASE + "1a2b3c4d5e6f7a8b9c0d1e2f"
SHA256_M = M + "0f1e2d3c4b5a69788796a5b4"

# Two of the fixture's tests, by node id and by the pair that pytest writes for
# each in the JUnit, and the node id of a third.
TEST_TOTAL = "tests/test_pricing.py::test_total"
TEST_RENDER = "tests/test_report.py::test_render"
TEST_VAT = "tests/test_tax.py::test_vat"
TOTAL_PAIR = ("tests.test_pricing", "test_total")
RENDER_PAIR = ("tests.test_report", "test_render")

# A backslash. Every escape made of a backslash, u and four hex digits is built
# from it: typed in one piece in a Write or Edit call, such an escape lands in
# the file as the character it stands for (CLAUDE.md).
BACKSLASH = b"\\"


def u_escape(hex_digits: bytes) -> bytes:
    """How a record writes a character outside printable ASCII that has no
    short escape: a backslash, u and these four hex digits."""
    return BACKSLASH + b"u" + hex_digits


def replaced(line: bytes, old: bytes, new: bytes) -> bytes:
    """The line with old, which it holds exactly once, replaced by new."""
    assert line.count(old) == 1
    return line.replace(old, new)


def string_field(key: str, value: str) -> bytes:
    """A key and its value, ASCII text, as a line writes them."""
    return b'"' + key.encode("ascii") + b'":"' + value.encode("ascii") + b'"'


# K1: a diff that modifies only templates/invoice.html, and a full run of pull
# request 7 in which test_render failed, with no rerun file.

# test_render, failed and left out.
K1_TEST_RENDER = selection.Test(
    pair=RENDER_PAIR,
    node_id=TEST_RENDER,
    row=frozenset({"src/shop/pricing.py", "src/shop/report.py"}),
)

# The record that K1's line holds: the values it shows.
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
    failed_left_out=(K1_TEST_RENDER,),
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


def test_k1_its_line_is_a_record_with_the_values_it_shows() -> None:
    assert records.decode(K1_LINE) == K1_RECORD


# K2's record: test_render failed in the full run and passed in the rerun file.
# K2 names no diff, so its other values are K1's.
K2_RECORD = dataclasses.replace(
    K1_RECORD,
    verdict="green",
    rerun_given=True,
    not_reproduced=(RENDER_PAIR,),
    failed_left_out=(),
)


# K4: coverage recorded at a commit that is neither the merge-base nor one of
# its ancestors.
K4_RECORD = records.RejectedRecord(
    key=KEY, pr=7, reason="coverage-not-ancestor", input_name="coverage"
)

# K4's line, as the SPEC gives it, with the values above for <H> and <sha>.
K4_LINE = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
    b'"junit_sha256":'
    b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
    b'"pr":7,"verdict":"rejected","reason":"coverage-not-ancestor",'
    b'"input":"coverage"}\n'
)


def test_k4_its_line_is_a_record_with_the_values_it_shows() -> None:
    # K15's record file starts with this line.
    assert records.decode(K4_LINE) == K4_RECORD


# K15's second line, as tests/test_messages.py writes it: the SPEC says only
# that it holds the text canary.
K15_SECOND_LINE = b"canary\n"


def test_k15_the_line_holding_canary_is_not_a_record() -> None:
    # json.loads cannot read it.
    assert records.decode(K15_SECOND_LINE) is None


def k4_with(old: bytes, new: bytes) -> bytes:
    """K4's line, with old, which it holds once, replaced by new."""
    return replaced(K4_LINE, old, new)


def k1_with(old: bytes, new: bytes) -> bytes:
    """K1's line, with old, which it holds once, replaced by new."""
    return replaced(K1_LINE, old, new)


# Pieces of K1's and K4's lines that tests below change, as the lines write them.
HEAD_FIELD = string_field("head", HEAD)
SHA256_FIELD = string_field("junit_sha256", JUNIT_SHA256)
MERGE_BASE_FIELD = string_field("merge_base", MERGE_BASE)
M_FIELD = string_field("coverage_commit", M)
REASON_FIELD = string_field("reason", "coverage-not-ancestor")
INPUT_FIELD = string_field("input", "coverage")
NODE_ID_FIELD = string_field("node_id", TEST_RENDER)
RENDER_PAIR_FIELD = b'"pair":["tests.test_report","test_render"]'
K1_ROW_FIELD = b'"row":["src/shop/pricing.py","src/shop/report.py"]'

# test_render's entry in K1's failed_left_out.
RENDER_ENTRY = (
    b'{"pair":["tests.test_report","test_render"],'
    b'"node_id":"tests/test_report.py::test_render",'
    b'"row":["src/shop/pricing.py","src/shop/report.py"]}'
)


def k1_not_reproduced(value: bytes) -> bytes:
    """K1's line, with this JSON as not_reproduced's value."""
    return k1_with(b'"not_reproduced":[]', b'"not_reproduced":' + value)


def k1_failed_left_out(value: bytes) -> bytes:
    """K1's line, with this JSON as failed_left_out's value."""
    return k1_with(
        b'"failed_left_out":[' + RENDER_ENTRY + b"]", b'"failed_left_out":' + value
    )


def k1_no_column(value: bytes) -> bytes:
    """K1's line, with this JSON as no_column's value."""
    return k1_with(b'"no_column":["templates/invoice.html"]', b'"no_column":' + value)


def k1_import_only(value: bytes) -> bytes:
    """K1's line, with this JSON as import_only's value."""
    return k1_with(b'"import_only":[]', b'"import_only":' + value)


def k1_row(value: bytes) -> bytes:
    """K1's line, with this JSON as the row of test_render's entry."""
    return k1_with(K1_ROW_FIELD, b'"row":' + value)


# The SPEC's examples of lines that are not records. json.loads cannot read an
# empty line. It reads the others, taking a carriage return and a newline alike
# as white space, so that only Rule 7's last check finds how such a line ends:
# encode ends a record's line with one newline. A record of format 2 has a
# value that is not allowed, which the last check would also find, since
# encode writes "format":1.
NOT_RECORDS_IN_THE_SPEC = [
    pytest.param(b"\n", id="an empty line"),
    pytest.param(b"", id="an empty line that lacks its newline"),
    pytest.param(
        K1_LINE.removesuffix(b"\n") + b"\r\n",
        id="K1 ending in a carriage return and a newline",
    ),
    pytest.param(
        K4_LINE.removesuffix(b"\n") + b"\r\n",
        id="K4 ending in a carriage return and a newline",
    ),
    pytest.param(
        K1_LINE.removesuffix(b"\n") + b"\r",
        id="K1 ending in a carriage return instead of a newline",
    ),
    pytest.param(
        K4_LINE.removesuffix(b"\n") + b"\r",
        id="K4 ending in a carriage return instead of a newline",
    ),
    pytest.param(K1_LINE.removesuffix(b"\n"), id="K1 lacking its newline"),
    pytest.param(K4_LINE.removesuffix(b"\n"), id="K4 lacking its newline"),
    pytest.param(k1_with(b'"format":1', b'"format":2'), id="K1 of format 2"),
    pytest.param(k4_with(b'"format":1', b'"format":2'), id="K4 of format 2"),
]


@pytest.mark.parametrize("line", NOT_RECORDS_IN_THE_SPEC)
def test_the_specs_examples_of_lines_that_are_not_records(line: bytes) -> None:
    assert records.decode(line) is None


# The rejected record of a run whose H, given as origin/caf\xe9, names no
# commit, and its line, which writes the e with an acute accent as an escape.
H_AS_GIVEN_RECORD = records.RejectedRecord(
    key=records.RunKey(head="origin/caf\xe9", junit_sha256=JUNIT_SHA256),
    pr=7,
    reason="unusable-input",
    input_name="head",
)
H_AS_GIVEN_LINE = records.encode(H_AS_GIVEN_RECORD)
E_ACUTE_ESCAPE = u_escape(b"00e9")

# ASCII, Rule 7's first check. Each line holds a byte beyond ASCII. Rule 7's
# last check would also find it, since encode writes ASCII only.
BEYOND_ASCII = [
    pytest.param(
        replaced(H_AS_GIVEN_LINE, E_ACUTE_ESCAPE, "\xe9".encode()),
        id="H as given with its e with an acute accent in UTF-8",
    ),
    pytest.param(
        replaced(H_AS_GIVEN_LINE, E_ACUTE_ESCAPE, "\xe9".encode("latin-1")),
        id="H as given with its e with an acute accent in Latin-1, not UTF-8",
    ),
    pytest.param(chr(0xFEFF).encode() + K4_LINE, id="K4 after a UTF-8 byte order mark"),
]


@pytest.mark.parametrize("line", BEYOND_ASCII)
def test_a_line_with_a_byte_beyond_ascii_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


# Lines that json.loads cannot read, which Rule 7's second check finds: decode
# gives None, whatever json.loads raises. With Python's default limit of 4300
# digits on converting between int and str, a number of 4301 digits makes it
# raise ValueError, which is not a JSONDecodeError, and 100,000 nested lists
# RecursionError, which is not a ValueError. K4's line saved as UTF-16-LE with
# no byte order mark has only ASCII bytes; cut right after its newline byte, as
# a reader that splits the file on newlines cuts it, it leaves an odd byte that
# json.loads, reading the bytes as UTF-16, raises UnicodeDecodeError for. All
# three checked on 2026-10-24.

# K4's line torn by an append that a killed runner or a full disk cut short,
# 20 digits into its commit id.
TORN_K4 = b'{"format":1,"head":"c7d2f4a91b3e5f6082a4'

UNREADABLE = [
    pytest.param(TORN_K4, id="K4 torn"),
    pytest.param(TORN_K4 + K4_LINE, id="K4 torn, then the next append's line"),
    pytest.param(
        k1_no_column(b'["templates/a\tb.html"]'),
        id="a tab as itself in a string, which JSON does not allow",
    ),
    pytest.param(k4_with(b'"pr":7', b'"pr":1' + b"0" * 4300), id="a pr of 4301 digits"),
    pytest.param(
        k1_import_only(b"[" * 100_000 + b"]" * 100_000), id="100,000 nested lists"
    ),
    pytest.param(
        K4_LINE.decode("ascii").encode("utf-16-le").removesuffix(b"\x00"),
        id="K4 saved as UTF-16-LE, cut after its newline byte",
    ),
]


@pytest.mark.parametrize("line", UNREADABLE)
def test_a_line_that_json_cannot_read_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


# Keys and their order, Rule 7's third check. decode tells the two kinds of
# record apart by their keys, which must be those of one kind, in the SPEC's
# order. Rule 7's last check would also find a key too many or keys in another
# order, since encode writes a record's keys alone and in that order, but not
# a key that is missing.

# JSON that is not an object.
NOT_AN_OBJECT = [
    pytest.param(b"[]\n", id="a list"),
    pytest.param(b'"canary"\n', id="a string, K15's text"),
    pytest.param(b"7\n", id="a number"),
    pytest.param(b"null\n", id="null"),
    pytest.param(b"true\n", id="true"),
    pytest.param(b"[" + K4_LINE.removesuffix(b"\n") + b"]\n", id="K4 in a list"),
]


@pytest.mark.parametrize("line", NOT_AN_OBJECT)
def test_json_that_is_not_an_object_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


# The keys of each kind of record, in the SPEC's order.
REJECTED_KEYS = ["format", "head", "junit_sha256", "pr", "verdict", "reason", "input"]
EVALUATED_KEYS = [
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
]


def without_key(line: bytes, key: str) -> bytes:
    """The line with this key and its value left out, and the rest written as
    encode writes a line: json.dumps with no spaces, then a newline."""
    fields: dict[str, object] = json.loads(line)
    del fields[key]
    return json.dumps(fields, separators=(",", ":")).encode("ascii") + b"\n"


K4_WITHOUT_A_KEY = [
    pytest.param(without_key(K4_LINE, key), id=f"K4 without {key}")
    for key in REJECTED_KEYS
]
K1_WITHOUT_A_KEY = [
    pytest.param(without_key(K1_LINE, key), id=f"K1 without {key}")
    for key in EVALUATED_KEYS
]
ENTRY_WITHOUT_A_KEY = [
    pytest.param(
        k1_with(RENDER_PAIR_FIELD + b",", b""), id="test_render's entry without pair"
    ),
    pytest.param(
        k1_with(NODE_ID_FIELD + b",", b""), id="test_render's entry without node_id"
    ),
    pytest.param(
        k1_with(b"," + K1_ROW_FIELD, b""), id="test_render's entry without row"
    ),
]
NO_KEY_AT_ALL = [pytest.param(b"{}\n", id="an object with no keys")]


@pytest.mark.parametrize(
    "line", K4_WITHOUT_A_KEY + K1_WITHOUT_A_KEY + ENTRY_WITHOUT_A_KEY + NO_KEY_AT_ALL
)
def test_a_line_missing_a_key_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


# The time of an evaluation, which a record never holds (the SPEC's sentence
# on records), as a key too many.
TIME_FIELD = b'"time":"2026-10-24T09:30:00Z"'

KEY_TOO_MANY = [
    pytest.param(
        k4_with(b'"input":"coverage"}', b'"input":"coverage",' + TIME_FIELD + b"}"),
        id="K4 with the time",
    ),
    pytest.param(
        k1_with(b'"import_only":[]}', b'"import_only":[],' + TIME_FIELD + b"}"),
        id="K1 with the time",
    ),
    pytest.param(
        k1_with(K1_ROW_FIELD + b"}", K1_ROW_FIELD + b"," + TIME_FIELD + b"}"),
        id="test_render's entry with the time",
    ),
    pytest.param(
        k4_with(b'"input":', b'"input_name":'),
        id="K4 with input_name, the Python name, in place of input",
    ),
    pytest.param(
        k1_with(
            b'"verdict":"missed",',
            b'"verdict":"missed","reason":"unusable-input","input":"coverage",',
        ),
        id="K1 with a rejected record's reason and input",
    ),
]


@pytest.mark.parametrize("line", KEY_TOO_MANY)
def test_a_line_with_a_key_too_many_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


KEYS_IN_ANOTHER_ORDER = [
    pytest.param(
        k4_with(REASON_FIELD + b"," + INPUT_FIELD, INPUT_FIELD + b"," + REASON_FIELD),
        id="K4 with input before reason",
    ),
    pytest.param(
        k4_with(HEAD_FIELD + b"," + SHA256_FIELD, SHA256_FIELD + b"," + HEAD_FIELD),
        id="K4 with junit_sha256 before head",
    ),
    pytest.param(
        k1_with(b'"pr":7,"verdict":"missed"', b'"verdict":"missed","pr":7'),
        id="K1 with verdict before pr",
    ),
    pytest.param(
        k1_with(
            b'"no_column":["templates/invoice.html"],"import_only":[]',
            b'"import_only":[],"no_column":["templates/invoice.html"]',
        ),
        id="K1 with import_only before no_column",
    ),
    pytest.param(
        k1_with(
            RENDER_PAIR_FIELD + b"," + NODE_ID_FIELD,
            NODE_ID_FIELD + b"," + RENDER_PAIR_FIELD,
        ),
        id="test_render's entry with node_id before pair",
    ),
    pytest.param(
        k1_with(
            NODE_ID_FIELD + b"," + K1_ROW_FIELD, K1_ROW_FIELD + b"," + NODE_ID_FIELD
        ),
        id="test_render's entry with row before node_id",
    ),
]


@pytest.mark.parametrize("line", KEYS_IN_ANOTHER_ORDER)
def test_a_line_with_its_keys_in_another_order_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


# Types, Rule 7's fourth check: type(x) is int, so true is not 1. JSON's true
# and false are bools, which Python also takes for 1 and 0, since bool is a
# subclass of int, and 7.0 equals 7. encode would write each of these values
# back as it is, so Rule 7's last check would not find them, but for format,
# which encode always writes as 1. For verdict, reason and input, the check of
# allowed values would also find them; a list is one that looking up in a set
# of allowed values would raise TypeError for.
OF_ANOTHER_TYPE = [
    # format: an int
    pytest.param(k4_with(b'"format":1', b'"format":true'), id="format true"),
    pytest.param(k4_with(b'"format":1', b'"format":1.0'), id="format 1.0"),
    pytest.param(k4_with(b'"format":1', b'"format":"1"'), id="format as a string"),
    # head: a string
    pytest.param(k4_with(HEAD_FIELD, b'"head":null'), id="K4 head null"),
    pytest.param(k1_with(HEAD_FIELD, b'"head":null'), id="K1 head null"),
    pytest.param(k4_with(HEAD_FIELD, b'"head":7'), id="head a number"),
    pytest.param(
        k4_with(HEAD_FIELD, b'"head":["' + HEAD.encode() + b'"]'), id="head in a list"
    ),
    # junit_sha256: a string, or null
    pytest.param(
        k4_with(SHA256_FIELD, b'"junit_sha256":7'), id="junit_sha256 a number"
    ),
    pytest.param(
        k4_with(SHA256_FIELD, b'"junit_sha256":false'), id="junit_sha256 false"
    ),
    pytest.param(
        k1_with(SHA256_FIELD, b'"junit_sha256":7'), id="K1 junit_sha256 a number"
    ),
    # pr: an int
    pytest.param(k4_with(b'"pr":7', b'"pr":true'), id="K4 pr true"),
    pytest.param(k1_with(b'"pr":7', b'"pr":true'), id="K1 pr true"),
    pytest.param(k4_with(b'"pr":7', b'"pr":7.0'), id="pr 7.0"),
    pytest.param(k4_with(b'"pr":7', b'"pr":"7"'), id="pr as a string"),
    pytest.param(k4_with(b'"pr":7', b'"pr":null'), id="pr null"),
    pytest.param(k4_with(b'"pr":7', b'"pr":[7]'), id="pr in a list"),
    # verdict, reason and input: strings
    pytest.param(
        k4_with(b'"verdict":"rejected"', b'"verdict":["rejected"]'),
        id="K4 verdict in a list",
    ),
    pytest.param(
        k1_with(b'"verdict":"missed"', b'"verdict":["missed"]'),
        id="K1 verdict in a list",
    ),
    pytest.param(k1_with(b'"verdict":"missed"', b'"verdict":null'), id="verdict null"),
    pytest.param(
        k4_with(REASON_FIELD, b'"reason":["coverage-not-ancestor"]'),
        id="reason in a list",
    ),
    pytest.param(k4_with(REASON_FIELD, b'"reason":null'), id="reason null"),
    pytest.param(k4_with(INPUT_FIELD, b'"input":["coverage"]'), id="input in a list"),
    pytest.param(k4_with(INPUT_FIELD, b'"input":7'), id="input a number"),
    # merge_base and coverage_commit: strings
    pytest.param(k1_with(MERGE_BASE_FIELD, b'"merge_base":null'), id="merge_base null"),
    pytest.param(
        k1_with(MERGE_BASE_FIELD, b'"merge_base":7'), id="merge_base a number"
    ),
    pytest.param(
        k1_with(M_FIELD, b'"coverage_commit":null'), id="coverage_commit null"
    ),
    pytest.param(
        k1_with(M_FIELD, b'"coverage_commit":["' + M.encode() + b'"]'),
        id="coverage_commit in a list",
    ),
    # the durations and counts: ints
    pytest.param(
        k1_with(b'"selected_ms":0', b'"selected_ms":false'), id="selected_ms false"
    ),
    pytest.param(
        k1_with(b'"selected_ms":0', b'"selected_ms":0.0'), id="selected_ms 0.0"
    ),
    pytest.param(
        k1_with(b'"selected_ms":0', b'"selected_ms":null'), id="selected_ms null"
    ),
    pytest.param(k1_with(b'"full_ms":12000', b'"full_ms":true'), id="full_ms true"),
    pytest.param(
        k1_with(b'"full_ms":12000', b'"full_ms":12000.0'), id="full_ms 12000.0"
    ),
    pytest.param(
        k1_with(b'"full_ms":12000', b'"full_ms":"12000"'), id="full_ms as a string"
    ),
    pytest.param(k1_with(b'"tests":4', b'"tests":true'), id="tests true"),
    pytest.param(k1_with(b'"tests":4', b'"tests":4.0'), id="tests 4.0"),
    pytest.param(k1_with(b'"tests":4', b'"tests":null'), id="tests null"),
    pytest.param(
        k1_with(b'"unmeasured":0', b'"unmeasured":false'), id="unmeasured false"
    ),
    pytest.param(k1_with(b'"unmeasured":0', b'"unmeasured":0.0'), id="unmeasured 0.0"),
    pytest.param(
        k1_with(b'"tests_with_row":4', b'"tests_with_row":true'),
        id="tests_with_row true",
    ),
    pytest.param(
        k1_with(b'"tests_with_row":4', b'"tests_with_row":4.0'),
        id="tests_with_row 4.0",
    ),
    pytest.param(
        k1_with(b'"tests_with_row_not_in_run":0', b'"tests_with_row_not_in_run":false'),
        id="tests_with_row_not_in_run false",
    ),
    pytest.param(
        k1_with(b'"tests_with_row_not_in_run":0', b'"tests_with_row_not_in_run":0.0'),
        id="tests_with_row_not_in_run 0.0",
    ),
    # floor_matched and rerun_given: bools
    pytest.param(
        k1_with(b'"floor_matched":false', b'"floor_matched":0'), id="floor_matched 0"
    ),
    pytest.param(
        k1_with(b'"floor_matched":false', b'"floor_matched":null'),
        id="floor_matched null",
    ),
    pytest.param(
        k1_with(b'"rerun_given":false', b'"rerun_given":0'), id="rerun_given 0"
    ),
    pytest.param(
        k1_with(b'"rerun_given":false', b'"rerun_given":1'), id="rerun_given 1"
    ),
    pytest.param(
        k1_with(b'"rerun_given":false', b'"rerun_given":"false"'),
        id="rerun_given as a string",
    ),
    # not_reproduced: a list of pairs, each a list of two strings
    pytest.param(k1_not_reproduced(b"null"), id="not_reproduced null"),
    pytest.param(k1_not_reproduced(b"{}"), id="not_reproduced an object"),
    pytest.param(
        k1_not_reproduced(b'["tests.test_report"]'),
        id="not_reproduced holding a string",
    ),
    pytest.param(
        k1_not_reproduced(b'[["tests.test_report"]]'), id="a pair of one string"
    ),
    pytest.param(
        k1_not_reproduced(b'[["tests.test_report","test_render","test_render"]]'),
        id="a pair of three strings",
    ),
    pytest.param(
        k1_not_reproduced(b'[["tests.test_report",7]]'), id="a pair with a number"
    ),
    pytest.param(k1_not_reproduced(b'[[null,"test_render"]]'), id="a pair with null"),
    pytest.param(
        k1_not_reproduced(b'[{"classname":"tests.test_report","name":"test_render"}]'),
        id="a pair as an object",
    ),
    # failed_left_out: a list of objects, each with a pair, a node id and a row
    pytest.param(k1_failed_left_out(b"null"), id="failed_left_out null"),
    pytest.param(k1_failed_left_out(b"[null]"), id="an entry null"),
    pytest.param(
        k1_failed_left_out(
            b'[[["tests.test_report","test_render"],'
            b'"tests/test_report.py::test_render",'
            b'["src/shop/pricing.py","src/shop/report.py"]]]'
        ),
        id="an entry as a list of its values",
    ),
    pytest.param(
        k1_with(RENDER_PAIR_FIELD, b'"pair":["tests.test_report"]'),
        id="an entry's pair of one string",
    ),
    pytest.param(
        k1_with(RENDER_PAIR_FIELD, b'"pair":"tests.test_report"'),
        id="an entry's pair a string",
    ),
    pytest.param(k1_with(NODE_ID_FIELD, b'"node_id":7'), id="node_id a number"),
    pytest.param(
        k1_with(NODE_ID_FIELD, b'"node_id":["' + TEST_RENDER.encode() + b'"]'),
        id="node_id in a list",
    ),
    pytest.param(k1_row(b"null"), id="row null"),
    pytest.param(k1_row(b'"src/shop/pricing.py"'), id="row a string"),
    pytest.param(k1_row(b"[7]"), id="a row holding a number"),
    # no_column and import_only: lists of strings
    pytest.param(k1_no_column(b'"templates/invoice.html"'), id="no_column a string"),
    pytest.param(k1_no_column(b"null"), id="no_column null"),
    pytest.param(k1_no_column(b"[7]"), id="no_column holding a number"),
    pytest.param(k1_no_column(b"[null]"), id="no_column holding null"),
    pytest.param(k1_import_only(b"{}"), id="import_only an object"),
    pytest.param(
        k1_import_only(b'[["src/shop/constants.py"]]'), id="import_only holding a list"
    ),
]


@pytest.mark.parametrize("line", OF_ANOTHER_TYPE)
def test_a_value_of_another_type_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


def k1_merge_base(value: str) -> bytes:
    """K1's line, with this text as merge_base."""
    return k1_with(MERGE_BASE_FIELD, string_field("merge_base", value))


def k4_sha256(value: str) -> bytes:
    """K4's line, with this text as junit_sha256."""
    return k4_with(SHA256_FIELD, string_field("junit_sha256", value))


# Allowed values, Rule 7's fifth check: values of the right type that a field
# does not allow. encode would write each back as it is, so Rule 7's last check
# would not find them, but for format, which encode writes as 1, and for a
# rejected record's verdict, which no field holds: encode writes rejected.
NOT_ALLOWED = [
    pytest.param(k4_with(b'"format":1', b'"format":0'), id="format 0"),
    # an evaluated record's verdict: green, caught or missed
    pytest.param(
        k1_with(b'"verdict":"missed"', b'"verdict":"rejected"'),
        id="an evaluated record's verdict rejected",
    ),
    pytest.param(
        k1_with(b'"verdict":"missed"', b'"verdict":"red"'),
        id="verdict red, which a run is, but no verdict",
    ),
    pytest.param(
        k1_with(b'"verdict":"missed"', b'"verdict":"Missed"'),
        id="verdict Missed, capitalized",
    ),
    pytest.param(k1_with(b'"verdict":"missed"', b'"verdict":""'), id="verdict empty"),
    # a rejected record's verdict: rejected
    pytest.param(
        k4_with(b'"verdict":"rejected"', b'"verdict":"missed"'),
        id="a rejected record's verdict missed",
    ),
    pytest.param(
        k4_with(b'"verdict":"rejected"', b'"verdict":"green"'),
        id="a rejected record's verdict green",
    ),
    # reason
    pytest.param(
        k4_with(REASON_FIELD, b'"reason":"coverage_not_ancestor"'),
        id="reason with underscores",
    ),
    pytest.param(
        k4_with(REASON_FIELD, b'"reason":"Coverage-not-ancestor"'),
        id="reason capitalized",
    ),
    pytest.param(
        k4_with(REASON_FIELD, b'"reason":"not-ancestor"'), id="reason not-ancestor"
    ),
    pytest.param(k4_with(REASON_FIELD, b'"reason":""'), id="reason empty"),
    # input
    pytest.param(
        k4_with(INPUT_FIELD, b'"input":"records"'),
        id="input records, the record file, which is not an input",
    ),
    pytest.param(
        k4_with(INPUT_FIELD, b'"input":"coverage-commit"'),
        id="input coverage-commit, M's option, which a rejection records as coverage",
    ),
    pytest.param(k4_with(INPUT_FIELD, b'"input":"Coverage"'), id="input capitalized"),
    pytest.param(k4_with(INPUT_FIELD, b'"input":""'), id="input empty"),
    # pr, which is 1 or more
    pytest.param(k4_with(b'"pr":7', b'"pr":0'), id="K4 pr 0"),
    pytest.param(k1_with(b'"pr":7', b'"pr":0'), id="K1 pr 0"),
    pytest.param(k4_with(b'"pr":7', b'"pr":-7'), id="pr -7"),
    # the durations and counts: 0 or more
    pytest.param(k1_with(b'"selected_ms":0', b'"selected_ms":-1'), id="selected_ms -1"),
    pytest.param(k1_with(b'"full_ms":12000', b'"full_ms":-12000'), id="full_ms -12000"),
    pytest.param(k1_with(b'"tests":4', b'"tests":-4'), id="tests -4"),
    pytest.param(k1_with(b'"unmeasured":0', b'"unmeasured":-1'), id="unmeasured -1"),
    pytest.param(
        k1_with(b'"tests_with_row":4', b'"tests_with_row":-4'),
        id="tests_with_row -4",
    ),
    pytest.param(
        k1_with(b'"tests_with_row_not_in_run":0', b'"tests_with_row_not_in_run":-1'),
        id="tests_with_row_not_in_run -1",
    ),
    # merge_base and coverage_commit: 40 or 64 lowercase hex digits
    pytest.param(k1_merge_base(MERGE_BASE[:7]), id="merge_base abbreviated to 7"),
    pytest.param(k1_merge_base(MERGE_BASE[:39]), id="merge_base of 39 digits"),
    pytest.param(k1_merge_base(MERGE_BASE + "0"), id="merge_base of 41 digits"),
    pytest.param(k1_merge_base(SHA256_MERGE_BASE[:63]), id="merge_base of 63 digits"),
    pytest.param(k1_merge_base(SHA256_MERGE_BASE + "0"), id="merge_base of 65 digits"),
    pytest.param(k1_merge_base(MERGE_BASE.upper()), id="merge_base in upper case"),
    pytest.param(
        k1_merge_base("g" + MERGE_BASE[1:]), id="merge_base with a g, not a hex digit"
    ),
    pytest.param(k1_merge_base("origin/main"), id="merge_base a branch's name"),
    pytest.param(k1_merge_base(""), id="merge_base empty"),
    pytest.param(
        k1_with(M_FIELD, string_field("coverage_commit", M[:7])),
        id="coverage_commit abbreviated to 7",
    ),
    pytest.param(
        k1_with(M_FIELD, string_field("coverage_commit", M.upper())),
        id="coverage_commit in upper case",
    ),
    # junit_sha256: 64 lowercase hex digits, or null
    pytest.param(k4_sha256(JUNIT_SHA256[:63]), id="junit_sha256 of 63 digits"),
    pytest.param(k4_sha256(JUNIT_SHA256 + "0"), id="junit_sha256 of 65 digits"),
    pytest.param(k4_sha256(HEAD), id="junit_sha256 of 40 digits, a SHA-1's length"),
    pytest.param(k4_sha256(JUNIT_SHA256.upper()), id="junit_sha256 in upper case"),
    pytest.param(
        k4_sha256("g" + JUNIT_SHA256[1:]), id="junit_sha256 with a g, not a hex digit"
    ),
    pytest.param(k4_sha256(""), id="junit_sha256 empty"),
    pytest.param(
        k1_with(SHA256_FIELD, string_field("junit_sha256", JUNIT_SHA256.upper())),
        id="K1 junit_sha256 in upper case",
    ),
    # a failed test left out is measured, so it has a node id and a row, and a
    # row is never empty (the Data model's Judgement, and "an empty row is no
    # row")
    pytest.param(k1_with(NODE_ID_FIELD, b'"node_id":null'), id="node_id null"),
    pytest.param(k1_row(b"[]"), id="an empty row"),
]


@pytest.mark.parametrize("line", NOT_ALLOWED)
def test_a_value_that_its_field_does_not_allow_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


# test_total's entry in failed_left_out, its row being the fixture's.
TOTAL_ENTRY = (
    b'{"pair":["tests.test_pricing","test_total"],'
    b'"node_id":"tests/test_pricing.py::test_total",'
    b'"row":["src/shop/db.py","src/shop/pricing.py","src/shop/tax.py"]}'
)

# The entries of the SPEC's two node ids with one pair, (tests.v1.2.test_x,
# test_m), in the order of their node ids: a point comes before a slash.
V1_DOT_2_ENTRY = (
    b'{"pair":["tests.v1.2.test_x","test_m"],'
    b'"node_id":"tests/v1.2/test_x.py::test_m","row":["src/shop/tax.py"]}'
)
V1_SLASH_2_ENTRY = (
    b'{"pair":["tests.v1.2.test_x","test_m"],'
    b'"node_id":"tests/v1/2/test_x.py::test_m","row":["src/shop/tax.py"]}'
)

# Lists sorted with no repeats, Rule 7's sixth check. encode sorts every list
# it writes, so Rule 7's last check would also find a list out of order, but a
# repeat only in a row, which a set holds once: encode writes any other repeat
# back as it is.
OUT_OF_ORDER = [
    pytest.param(
        k1_not_reproduced(
            b'[["tests.test_tax","test_vat"],["tests.test_report","test_render"]]'
        ),
        id="not_reproduced",
    ),
    pytest.param(
        k1_failed_left_out(b"[" + RENDER_ENTRY + b"," + TOTAL_ENTRY + b"]"),
        id="failed_left_out",
    ),
    pytest.param(
        k1_no_column(b'["templates/invoice.html","docs/guide.md"]'), id="no_column"
    ),
    pytest.param(
        k1_import_only(b'["src/shop/constants.py","src/shop/config.py"]'),
        id="import_only",
    ),
    pytest.param(
        k1_row(b'["src/shop/report.py","src/shop/pricing.py"]'),
        id="a row, in the order of the fixture's table",
    ),
    pytest.param(
        k1_no_column(b'["docs/' + E_ACUTE_ESCAPE + b'cole.md","docs/zebra.md"]'),
        id="paths in the order of their escaped text, a backslash before z",
    ),
]


@pytest.mark.parametrize("line", OUT_OF_ORDER)
def test_a_list_out_of_order_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


REPEATED = [
    pytest.param(
        k1_not_reproduced(
            b'[["tests.test_report","test_render"],["tests.test_report","test_render"]]'
        ),
        id="a pair twice in not_reproduced",
    ),
    pytest.param(
        k1_failed_left_out(b"[" + RENDER_ENTRY + b"," + RENDER_ENTRY + b"]"),
        id="test_render's entry twice",
    ),
    pytest.param(
        k1_failed_left_out(b"[" + V1_DOT_2_ENTRY + b"," + V1_SLASH_2_ENTRY + b"]"),
        id="two entries with one pair, the SPEC's tests/v1.2 and tests/v1/2",
    ),
    pytest.param(
        k1_no_column(b'["templates/invoice.html","templates/invoice.html"]'),
        id="a path twice in no_column",
    ),
    pytest.param(
        k1_import_only(b'["src/shop/constants.py","src/shop/constants.py"]'),
        id="a path twice in import_only",
    ),
    pytest.param(
        k1_row(b'["src/shop/pricing.py","src/shop/pricing.py","src/shop/report.py"]'),
        id="a path twice in a row",
    ),
]


@pytest.mark.parametrize("line", REPEATED)
def test_a_list_with_a_repeat_is_not_a_record(line: bytes) -> None:
    assert records.decode(line) is None


# Records with a tab and with DEL in their path with no column, which encode
# writes as escapes.
TAB_RECORD = dataclasses.replace(K1_RECORD, no_column=("templates/a\tb.html",))
DEL_RECORD = dataclasses.replace(K1_RECORD, no_column=("templates/a\x7fb.html",))

# Lines that json.loads reads into a record's keys and values, all of the right
# type and allowed, but that are not byte for byte what encode writes for them:
# only Rule 7's last check, encode of the record that decode rebuilds equal to
# the line, finds them. K4's line saved as UTF-16 with no byte order mark has
# only ASCII bytes; whole, json.loads reads those bytes as UTF-16 and gives
# K4's keys and values, while it cannot read their text (checked on
# 2026-10-24).
WRITTEN_OTHERWISE = [
    pytest.param(k4_with(b'"pr":7', b'"pr": 7'), id="a space after a colon"),
    pytest.param(k4_with(b',"pr":7', b', "pr":7'), id="a space after a comma"),
    pytest.param(K4_LINE.removesuffix(b"\n") + b" \n", id="a space before the newline"),
    pytest.param(b" " + K4_LINE, id="a space before the line"),
    pytest.param(
        replaced(H_AS_GIVEN_LINE, E_ACUTE_ESCAPE, u_escape(b"00E9")),
        id="an escape with upper case hex digits",
    ),
    pytest.param(
        k4_with(b'"head":"c', b'"head":"' + u_escape(b"0063")),
        id="a letter written as an escape",
    ),
    pytest.param(
        k1_with(b'"templates/invoice.html"', b'"templates\\/invoice.html"'),
        id="a slash written as an escape",
    ),
    pytest.param(
        replaced(records.encode(TAB_RECORD), b"\\t", u_escape(b"0009")),
        id="a tab written with four hex digits, not as its short escape",
    ),
    pytest.param(
        replaced(records.encode(DEL_RECORD), u_escape(b"007f"), b"\x7f"),
        id="DEL written as itself",
    ),
    pytest.param(
        k1_with(b'"selected_ms":0', b'"selected_ms":-0'),
        id="minus zero, which json.loads reads as the int 0",
    ),
    pytest.param(
        k4_with(b'"input":"coverage"}', b'"input":"coverage","pr":7}'),
        id="pr twice, which json.loads keeps once, in its first place",
    ),
    pytest.param(
        k4_with(b'"pr":7', b'"' + u_escape(b"0070") + b'r":7'),
        id="a key with a letter written as an escape",
    ),
    pytest.param(
        K4_LINE.decode("ascii").encode("utf-16-be"), id="K4 saved as UTF-16-BE"
    ),
    pytest.param(
        K4_LINE.decode("ascii").encode("utf-16-le"), id="K4 saved as UTF-16-LE, whole"
    ),
]


@pytest.mark.parametrize("line", WRITTEN_OTHERWISE)
def test_a_line_that_encode_would_write_otherwise_is_not_a_record(
    line: bytes,
) -> None:
    assert records.decode(line) is None


# Records. Each line below is one that encode writes, and decode gives back the
# very record that encode wrote it for.

# Every rejection of the [core] examples, each a reason and its input.
REJECTIONS = [
    pytest.param("coverage-not-ancestor", "coverage", id="K4"),
    pytest.param("missing-history", "checkout", id="K5"),
    pytest.param("unsafe-xml", "junit", id="K6 junit"),
    pytest.param("unsafe-xml", "rerun", id="K6 rerun"),
    pytest.param("unusable-input", "checkout", id="K8 checkout"),
    pytest.param("unusable-input", "head", id="K8 head"),
    pytest.param("unusable-input", "base", id="K8 base"),
    pytest.param("unusable-input", "coverage", id="K8 K14 coverage"),
    pytest.param("unusable-input", "junit", id="K8 junit"),
    pytest.param("unusable-input", "rerun", id="K8 rerun"),
    pytest.param("unusable-input", "floor", id="K8 floor"),
    pytest.param("collection-error", "junit", id="K9"),
    pytest.param("no-shared-lines", "coverage", id="K12"),
]


@pytest.mark.parametrize(("reason", "input_name"), REJECTIONS)
def test_every_rejection_of_the_core_examples_is_a_record(
    reason: str, input_name: str
) -> None:
    record = records.RejectedRecord(key=KEY, pr=7, reason=reason, input_name=input_name)
    line = records.encode(record)

    assert records.decode(line) == record


# A caught run of pull request 12, as tests/test_records.py has it, whose
# figures all differ, so that no field can stand in for another.
CAUGHT_RECORD = records.EvaluatedRecord(
    key=records.RunKey(head=OTHER_HEAD, junit_sha256=OTHER_JUNIT_SHA256),
    pr=12,
    verdict="caught",
    merge_base=MERGE_BASE,
    coverage_commit=M,
    selected_ms=6300,
    full_ms=12300,
    tests=5,
    unmeasured=2,
    tests_with_row=4,
    tests_with_row_not_in_run=1,
    floor_matched=False,
    rerun_given=False,
    not_reproduced=(),
    failed_left_out=(
        selection.Test(
            pair=("tests.api.test_orders", "test_create"),
            node_id="tests/api/test_orders.py::test_create",
            row=frozenset({"src/shop/orders.py"}),
        ),
    ),
    no_column=("tests/test_tax.py",),
    import_only=(),
)

# Selection 4's run, in which no test failed: a diff that modifies uv.lock
# selects every test through the floor.
FLOOR_RECORD = dataclasses.replace(
    K1_RECORD,
    verdict="green",
    selected_ms=12000,
    floor_matched=True,
    failed_left_out=(),
    no_column=("uv.lock",),
)

EVALUATED = [
    pytest.param(K2_RECORD, id="K2, green with a failure not reproduced"),
    pytest.param(CAUGHT_RECORD, id="a caught run whose figures all differ"),
    pytest.param(FLOOR_RECORD, id="a green run that the floor matched"),
]


@pytest.mark.parametrize("record", EVALUATED)
def test_each_verdict_of_an_evaluated_run_is_a_record(
    record: records.EvaluatedRecord,
) -> None:
    line = records.encode(record)

    assert records.decode(line) == record


def h_as_given(head: str) -> records.RejectedRecord:
    """The rejected record of a run whose H, given as head, names no commit."""
    return dataclasses.replace(
        H_AS_GIVEN_RECORD, key=records.RunKey(head=head, junit_sha256=JUNIT_SHA256)
    )


def with_no_column(path: str) -> records.EvaluatedRecord:
    """K1's record, with this path as its only one with no column."""
    return dataclasses.replace(K1_RECORD, no_column=(path,))


def with_import_only(path: str) -> records.EvaluatedRecord:
    """K1's record, with this path as its only import-only one."""
    return dataclasses.replace(K1_RECORD, import_only=(path,))


def with_render_row(path: str) -> records.EvaluatedRecord:
    """K1's record, with test_render left out with this path as its row."""
    render = selection.Test(
        pair=RENDER_PAIR, node_id=TEST_RENDER, row=frozenset({path})
    )
    return dataclasses.replace(K1_RECORD, failed_left_out=(render,))


def with_left_out(pair: tuple[str, str], node_id: str) -> records.EvaluatedRecord:
    """K1's record, with this test left out in place of test_render, its row
    being src/shop/tax.py alone."""
    test = selection.Test(
        pair=pair, node_id=node_id, row=frozenset({"src/shop/tax.py"})
    )
    return dataclasses.replace(K1_RECORD, failed_left_out=(test,))


def with_not_reproduced(pair: tuple[str, str]) -> records.EvaluatedRecord:
    """K1's record, with this pair as its only failure not reproduced."""
    return dataclasses.replace(K1_RECORD, not_reproduced=(pair,))


# Every printable ASCII character, from space to ~, but the quotation mark and
# the backslash, which have escapes of their own.
PRINTABLE_ASCII = "".join(
    chr(code) for code in range(0x20, 0x7F) if chr(code) not in {'"', "\\"}
)

# Records with characters that a record escapes, in each kind of string where
# an input can put them: H as given, a path, a pair and a node id. The
# characters are those of tests/test_records.py.
WITH_ESCAPES = [
    pytest.param(H_AS_GIVEN_RECORD, id="H as given with an e with an acute accent"),
    pytest.param(h_as_given('origin/say "hi"'), id="H as given with quotation marks"),
    pytest.param(h_as_given("origin\\main"), id="H as given with a backslash"),
    pytest.param(
        h_as_given("origin/caf" + chr(0xDCE9)),
        id="H as given with the lone surrogate that os.fsdecode gives for a byte",
    ),
    pytest.param(TAB_RECORD, id="a tab"),
    pytest.param(DEL_RECORD, id="DEL"),
    pytest.param(with_no_column("docs/back\x08space.md"), id="a backspace"),
    pytest.param(with_no_column("templates/new\nline.html"), id="a newline"),
    pytest.param(
        with_no_column("docs/tab\x0bline.md"),
        id="a line tabulation, which has no short escape in JSON",
    ),
    pytest.param(
        with_no_column("templates/invoice\x1b.html"), id="an escape character"
    ),
    pytest.param(
        with_no_column("docs/line" + chr(0x2028) + "break.md"), id="a line separator"
    ),
    pytest.param(with_no_column("docs/" + chr(0xFFFF) + ".md"), id="U+FFFF"),
    pytest.param(
        with_no_column("docs/" + chr(0x10000) + ".md"),
        id="U+10000, written as a surrogate pair",
    ),
    pytest.param(with_no_column("docs/" + chr(0x10FFFF) + ".md"), id="U+10FFFF"),
    pytest.param(
        with_no_column("docs/" + PRINTABLE_ASCII),
        id="every other printable ASCII character, as itself",
    ),
    pytest.param(with_import_only("src/shop/form\x0cfeed.py"), id="a form feed"),
    pytest.param(
        with_import_only("src/shop/next\x85line.py"), id="a next line, a C1 control"
    ),
    pytest.param(with_import_only("src/shop/no\xa0break.py"), id="a no-break space"),
    pytest.param(
        with_import_only("src/shop/" + chr(0xFEFF) + "bom.py"), id="a byte order mark"
    ),
    pytest.param(with_render_row("src/shop/car\rriage.py"), id="a carriage return"),
    pytest.param(
        with_render_row("src/shop/tarifa a\xf1o.py"),
        id="Edge 5's path, a space and an n with a tilde",
    ),
    pytest.param(
        with_left_out(
            ("tests.test_greet", 'test_hello[say "hi"]'),
            'tests/test_greet.py::test_hello[say "hi"]',
        ),
        id="quotation marks in a parameter's id",
    ),
    pytest.param(
        with_left_out(
            ("tests.test_" + chr(0x20AC), "test_m"),
            "tests/test_" + chr(0x20AC) + ".py::test_m",
        ),
        id="a euro sign in a test file's name",
    ),
    pytest.param(
        with_not_reproduced(("tests.test_x", "test_m[caf\\xe9]")),
        id="a backslash, from a parameter's id that pytest escaped",
    ),
    pytest.param(
        with_not_reproduced(("tests.tab\tdir.test_x", "test_m")),
        id="a tab in a directory's name",
    ),
    pytest.param(
        with_not_reproduced(("tests.test_" + chr(0x1F600), "test_m")),
        id="U+1F600 in a module's name",
    ),
]


@pytest.mark.parametrize("record", WITH_ESCAPES)
def test_a_record_with_characters_that_it_escapes_is_a_record(
    record: records.Record,
) -> None:
    line = records.encode(record)

    assert records.decode(line) == record


# Two pairs that code point order and an order like it put the other way
# round: by its whole classname, the module's test comes first; joined to the
# name, or by node id, the class's would.
MODULE_PAIR = ("tests.test_x", "test_z")
CLASS_PAIR = ("tests.test_x.TestB", "test_c")

# Characters beyond ASCII. By code point, a fullwidth a, U+FF41, comes before
# U+1F600; in UTF-16, and escaped, U+1F600 starts with U+D83D and comes first.
FULLWIDTH_A = chr(0xFF41)
SMILEY = chr(0x1F600)

# Lists in code point order, as encode writes them, where an order like it
# would differ: by escaped text, in which an escape starts with a backslash; by
# UTF-16; by a pair joined into one string; or by node id.
IN_CODE_POINT_ORDER = [
    pytest.param(
        dataclasses.replace(K1_RECORD, not_reproduced=(MODULE_PAIR, CLASS_PAIR)),
        id="pairs by their whole classname, not joined to their name",
    ),
    pytest.param(
        dataclasses.replace(
            K1_RECORD,
            not_reproduced=(
                ("tests.test_report", "test_render[PDF]"),
                ("tests.test_report", "test_render[html]"),
            ),
        ),
        id="upper case before lower case",
    ),
    pytest.param(
        dataclasses.replace(
            K1_RECORD,
            failed_left_out=(
                selection.Test(
                    pair=MODULE_PAIR,
                    node_id="tests/test_x.py::test_z",
                    row=frozenset({"src/shop/tax.py"}),
                ),
                selection.Test(
                    pair=CLASS_PAIR,
                    node_id="tests/test_x.py::TestB::test_c",
                    row=frozenset({"src/shop/tax.py"}),
                ),
            ),
        ),
        id="failed tests left out by their pairs, not their node ids",
    ),
    pytest.param(
        dataclasses.replace(K1_RECORD, no_column=("docs/zebra.md", "docs/\xe9cole.md")),
        id="z before a letter beyond ASCII, whose escape comes before z",
    ),
    pytest.param(
        dataclasses.replace(
            K1_RECORD,
            import_only=("docs/" + FULLWIDTH_A + ".md", "docs/" + SMILEY + ".md"),
        ),
        id="U+FF41 before U+1F600, which UTF-16 puts first",
    ),
    pytest.param(
        dataclasses.replace(K1_RECORD, no_column=("docs/a\nb.md", "docs/a b.md")),
        id="a newline before a space, though its escape comes after it",
    ),
]


@pytest.mark.parametrize("record", IN_CODE_POINT_ORDER)
def test_lists_in_code_point_order_are_records(record: records.Record) -> None:
    line = records.encode(record)

    assert records.decode(line) == record


# Values at the edges of what each field allows.
AT_THE_EDGES = [
    pytest.param(dataclasses.replace(K4_RECORD, pr=1), id="pr 1, the smallest"),
    pytest.param(
        dataclasses.replace(K1_RECORD, full_ms=10**4299),
        id="a full_ms of 4300 digits, the most Python converts by default",
    ),
    pytest.param(
        dataclasses.replace(
            K1_RECORD, merge_base=SHA256_MERGE_BASE, coverage_commit=SHA256_M
        ),
        id="commit ids of 64 digits",
    ),
    pytest.param(
        records.RejectedRecord(
            key=records.RunKey(head=HEAD, junit_sha256=None),
            pr=7,
            reason="unusable-input",
            input_name="junit",
        ),
        id="no SHA-256, for a full-run JUnit file that is missing",
    ),
    pytest.param(h_as_given(""), id="H given as an empty string"),
    pytest.param(
        with_not_reproduced(("", "tests.v[1]/test_x.py::test_m")),
        id="an empty classname, as pytest writes for a [ before any ::",
    ),
    pytest.param(with_not_reproduced(("tests.test_x", "")), id="an empty name"),
    pytest.param(with_left_out(("tests.test_x", "test_m"), ""), id="an empty node id"),
    pytest.param(with_render_row(""), id="an empty path in a row"),
    pytest.param(with_no_column(""), id="an empty path with no column"),
    pytest.param(with_import_only(""), id="an empty import-only path"),
]


@pytest.mark.parametrize("record", AT_THE_EDGES)
def test_values_at_the_edges_of_what_a_field_allows_are_records(
    record: records.Record,
) -> None:
    line = records.encode(record)

    assert records.decode(line) == record


# K1's line, then K4's, with fields that do not agree with each other, and the
# record that each holds: Rule 7 does not check agreement between fields, so
# each is still a record, the SPEC's own example first.
NOT_AGREEING = [
    pytest.param(
        k1_failed_left_out(b"[]"),
        dataclasses.replace(K1_RECORD, failed_left_out=()),
        id="a missed record with an empty failed_left_out",
    ),
    pytest.param(
        k1_with(b'"verdict":"missed"', b'"verdict":"green"'),
        dataclasses.replace(K1_RECORD, verdict="green"),
        id="a green run with a failed test left out",
    ),
    pytest.param(
        k1_with(b'"unmeasured":0', b'"unmeasured":5'),
        dataclasses.replace(K1_RECORD, unmeasured=5),
        id="more unmeasured tests than tests",
    ),
    pytest.param(
        k1_with(b'"tests_with_row_not_in_run":0', b'"tests_with_row_not_in_run":5'),
        dataclasses.replace(K1_RECORD, tests_with_row_not_in_run=5),
        id="more tests with a row not in the run than tests with a row",
    ),
    pytest.param(
        k1_with(b'"selected_ms":0', b'"selected_ms":13000'),
        dataclasses.replace(K1_RECORD, selected_ms=13000),
        id="a selection longer than the full suite",
    ),
    pytest.param(
        k1_with(b'"floor_matched":false', b'"floor_matched":true'),
        dataclasses.replace(K1_RECORD, floor_matched=True),
        id="a floor match with nothing selected",
    ),
    pytest.param(
        k1_not_reproduced(b'[["tests.test_pricing","test_total"]]'),
        dataclasses.replace(K1_RECORD, not_reproduced=(TOTAL_PAIR,)),
        id="a failure not reproduced with no rerun file",
    ),
    pytest.param(
        replaced(
            k1_not_reproduced(b'[["tests.test_report","test_render"]]'),
            b'"rerun_given":false',
            b'"rerun_given":true',
        ),
        dataclasses.replace(K1_RECORD, rerun_given=True, not_reproduced=(RENDER_PAIR,)),
        id="a test both not reproduced and left out",
    ),
    pytest.param(
        k1_import_only(b'["templates/invoice.html"]'),
        dataclasses.replace(K1_RECORD, import_only=("templates/invoice.html",)),
        id="a path both with no column and import-only",
    ),
    pytest.param(
        k1_no_column(b'["src/shop/report.py"]'),
        dataclasses.replace(K1_RECORD, no_column=("src/shop/report.py",)),
        id="a path with no column in the row of a test left out",
    ),
    pytest.param(
        k1_with(NODE_ID_FIELD, string_field("node_id", TEST_VAT)),
        dataclasses.replace(
            K1_RECORD,
            failed_left_out=(dataclasses.replace(K1_TEST_RENDER, node_id=TEST_VAT),),
        ),
        id="a node id that does not turn into its pair",
    ),
    pytest.param(
        k1_with(SHA256_FIELD, b'"junit_sha256":null'),
        dataclasses.replace(
            K1_RECORD, key=records.RunKey(head=HEAD, junit_sha256=None)
        ),
        id="an evaluated run with no SHA-256",
    ),
    pytest.param(
        k4_with(
            REASON_FIELD + b"," + INPUT_FIELD,
            b'"reason":"missing-history","input":"junit"',
        ),
        dataclasses.replace(K4_RECORD, reason="missing-history", input_name="junit"),
        id="a reason with an input that the SPEC never gives it",
    ),
]


@pytest.mark.parametrize(("line", "record"), NOT_AGREEING)
def test_fields_that_do_not_agree_still_make_a_record(
    line: bytes, record: records.Record
) -> None:
    assert records.decode(line) == record
