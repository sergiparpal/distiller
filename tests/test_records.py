import dataclasses

import pytest

from distiller import records, selection

# Each test hands encode a record, built as a literal, and compares the whole
# line it returns, byte for byte, with the line that the SPEC's sentence on
# records gives for that record. The record classes are tested only through
# encode. encode writes what a record holds (Rule 7), so most tests change one
# list of K1's record and keep its other values, even where they would not
# agree with that list.

# The fixture's commit ids and its JUnit file's SHA-256: <H>, <M> and <sha> as
# tests/test_messages.py writes them, so that K4's line is the first line of
# its K15 record file, and <merge-base>, which differs from <M>.
HEAD = "c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4"
MERGE_BASE = "9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e"
M = "e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9"
JUNIT_SHA256 = "5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a"
KEY = records.RunKey(head=HEAD, junit_sha256=JUNIT_SHA256)

# Another run's key, as tests/test_messages.py writes it.
OTHER_HEAD = "0a9b8c7d6e5f40312a3b4c5d6e7f8091a2b3c4d5"
OTHER_JUNIT_SHA256 = "f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d2c3b4a5968778695a4b3c2d1e0f"

# Three of the fixture's tests and test_rate, another test in tests/test_tax.py,
# by node id and by the pair that pytest writes for each in the JUnit.
TEST_TOTAL = "tests/test_pricing.py::test_total"
TEST_VAT = "tests/test_tax.py::test_vat"
TEST_RATE = "tests/test_tax.py::test_rate"
TEST_RENDER = "tests/test_report.py::test_render"
TOTAL_PAIR = ("tests.test_pricing", "test_total")
VAT_PAIR = ("tests.test_tax", "test_vat")
RATE_PAIR = ("tests.test_tax", "test_rate")
RENDER_PAIR = ("tests.test_report", "test_render")

# A backslash. Every escape made of a backslash, u and four hex digits is built
# from it: typed in one piece in a Write or Edit call, such an escape lands in
# the file as the character it stands for (CLAUDE.md).
BACKSLASH = b"\\"


def u_escape(hex_digits: bytes) -> bytes:
    """How a record writes a character outside printable ASCII that has no
    short escape: a backslash, u and these four hex digits."""
    return BACKSLASH + b"u" + hex_digits


# K1 and K2, with the values that the SPEC gives them

# test_render, failed and left out, its row in the order of the fixture's
# table, which a frozenset does not keep.
K1_TEST_RENDER = selection.Test(
    pair=("tests.test_report", "test_render"),
    node_id="tests/test_report.py::test_render",
    row=frozenset({"src/shop/report.py", "src/shop/pricing.py"}),
)

# K1's record: a diff that modifies only templates/invoice.html, a full run in
# which test_render failed, and no rerun file.
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

# K1's line, with the values above for <H>, <sha>, <merge-base> and <M>.
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


def test_k1_a_missed_run_is_written_as_exactly_its_line() -> None:
    # Every key of an evaluated record in its order, a pair as a list of two
    # strings, test_render's entry with pair, node_id and row in that order,
    # its row sorted, ASCII with no spaces and a newline at the end. The line
    # is fixed, so no time or environment value can be in it (Rule 8).
    assert records.encode(K1_RECORD) == K1_LINE


# K2's record: test_render failed in the full run and passed in the rerun
# file. K2 names no diff, so its other values are K1's, whose diff modifies
# only templates/invoice.html.
K2_RECORD = records.EvaluatedRecord(
    key=KEY,
    pr=7,
    verdict="green",
    merge_base=MERGE_BASE,
    coverage_commit=M,
    selected_ms=0,
    full_ms=12000,
    tests=4,
    unmeasured=0,
    tests_with_row=4,
    tests_with_row_not_in_run=0,
    floor_matched=False,
    rerun_given=True,
    not_reproduced=(("tests.test_report", "test_render"),),
    failed_left_out=(),
    no_column=("templates/invoice.html",),
    import_only=(),
)

# K2's line: its verdict green, rerun_given true, test_render's pair not
# reproduced and no failed test left out, among K1's other values.
K2_LINE = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
    b'"junit_sha256":'
    b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
    b'"pr":7,"verdict":"green",'
    b'"merge_base":"9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e",'
    b'"coverage_commit":"e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9",'
    b'"selected_ms":0,"full_ms":12000,'
    b'"tests":4,"unmeasured":0,"tests_with_row":4,"tests_with_row_not_in_run":0,'
    b'"floor_matched":false,"rerun_given":true,'
    b'"not_reproduced":[["tests.test_report","test_render"]],'
    b'"failed_left_out":[],'
    b'"no_column":["templates/invoice.html"],'
    b'"import_only":[]}\n'
)


def test_k2_a_failure_not_reproduced_is_written_with_k2s_values() -> None:
    assert records.encode(K2_RECORD) == K2_LINE


# Other evaluated runs, so that each field shows what it holds

# A caught run of pull request 12, another run, whose figures all differ, so
# that no field can stand in for another: test_vat was renamed at H to
# test_vat_rate and test_rounding was added, both unmeasured, and a diff that
# modifies src/shop/report.py and tests/test_tax.py selects test_render and
# those two. test_rounding and test_create failed, so the run is caught and
# test_create is left out.
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
CAUGHT_LINE = (
    b'{"format":1,"head":"0a9b8c7d6e5f40312a3b4c5d6e7f8091a2b3c4d5",'
    b'"junit_sha256":'
    b'"f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d2c3b4a5968778695a4b3c2d1e0f",'
    b'"pr":12,"verdict":"caught",'
    b'"merge_base":"9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e",'
    b'"coverage_commit":"e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9",'
    b'"selected_ms":6300,"full_ms":12300,'
    b'"tests":5,"unmeasured":2,"tests_with_row":4,"tests_with_row_not_in_run":1,'
    b'"floor_matched":false,"rerun_given":false,'
    b'"not_reproduced":[],'
    b'"failed_left_out":[{"pair":["tests.api.test_orders","test_create"],'
    b'"node_id":"tests/api/test_orders.py::test_create",'
    b'"row":["src/shop/orders.py"]}],'
    b'"no_column":["tests/test_tax.py"],'
    b'"import_only":[]}\n'
)


def test_each_figure_of_a_caught_run_is_written_in_its_place() -> None:
    assert records.encode(CAUGHT_RECORD) == CAUGHT_LINE


# Selection 4's run, in which no test failed: a diff that modifies uv.lock
# selects every test through the floor.
FLOOR_RECORD = records.EvaluatedRecord(
    key=KEY,
    pr=7,
    verdict="green",
    merge_base=MERGE_BASE,
    coverage_commit=M,
    selected_ms=12000,
    full_ms=12000,
    tests=4,
    unmeasured=0,
    tests_with_row=4,
    tests_with_row_not_in_run=0,
    floor_matched=True,
    rerun_given=False,
    not_reproduced=(),
    failed_left_out=(),
    no_column=("uv.lock",),
    import_only=(),
)
FLOOR_LINE = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
    b'"junit_sha256":'
    b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
    b'"pr":7,"verdict":"green",'
    b'"merge_base":"9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e",'
    b'"coverage_commit":"e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9",'
    b'"selected_ms":12000,"full_ms":12000,'
    b'"tests":4,"unmeasured":0,"tests_with_row":4,"tests_with_row_not_in_run":0,'
    b'"floor_matched":true,"rerun_given":false,'
    b'"not_reproduced":[],"failed_left_out":[],'
    b'"no_column":["uv.lock"],"import_only":[]}\n'
)


def test_a_floor_match_is_written_as_true() -> None:
    assert records.encode(FLOOR_RECORD) == FLOOR_LINE


# Rejected runs

# K4's record and line: coverage recorded at a commit that is neither the
# merge-base nor one of its ancestors.
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


def test_k4_coverage_that_is_not_an_ancestor_is_written_as_exactly_its_line() -> None:
    # Every key of a rejected record in its order: verdict rejected, which no
    # field holds, and the input under the key input.
    assert records.encode(K4_RECORD) == K4_LINE


# Every rejected record of the fixture's run starts as K4's does, up to its
# reason.
FIXTURE_REJECTED_UP_TO_THE_REASON = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
    b'"junit_sha256":'
    b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
    b'"pr":7,"verdict":"rejected","reason":"'
)

# The other [core] examples' rejections, each a reason and its input.
REJECTIONS = [
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
def test_a_rejected_record_is_written_with_its_reason_and_input(
    reason: str, input_name: str
) -> None:
    record = records.RejectedRecord(key=KEY, pr=7, reason=reason, input_name=input_name)

    line = records.encode(record)

    assert line == (
        FIXTURE_REJECTED_UP_TO_THE_REASON
        + reason.encode("ascii")
        + b'","input":"'
        + input_name.encode("ascii")
        + b'"}\n'
    )


def test_a_missing_junit_files_sha256_is_written_as_null() -> None:
    # K8 for a full-run JUnit file that does not exist, in pull request 12:
    # the key has no SHA-256.
    record = records.RejectedRecord(
        key=records.RunKey(head=HEAD, junit_sha256=None),
        pr=12,
        reason="unusable-input",
        input_name="junit",
    )

    line = records.encode(record)

    assert line == (
        b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
        b'"junit_sha256":null,"pr":12,"verdict":"rejected",'
        b'"reason":"unusable-input","input":"junit"}\n'
    )


def test_an_h_that_names_no_commit_is_written_as_given() -> None:
    # K8 for an H that names no commit, given as a branch name with an e with
    # an acute accent: the key holds H as given, and the line escapes it.
    record = records.RejectedRecord(
        key=records.RunKey(head="origin/caf\xe9", junit_sha256=JUNIT_SHA256),
        pr=7,
        reason="unusable-input",
        input_name="head",
    )

    line = records.encode(record)

    assert line == (
        b'{"format":1,"head":"origin/caf'
        + u_escape(b"00e9")
        + (
            b'","junit_sha256":'
            b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
            b'"pr":7,"verdict":"rejected","reason":"unusable-input","input":"head"}\n'
        )
    )


# K1's record and line with one list changed

# K1's line up to its lists, which the tests below fill in.
K1_UP_TO_THE_LISTS = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4",'
    b'"junit_sha256":'
    b'"5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a",'
    b'"pr":7,"verdict":"missed",'
    b'"merge_base":"9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e",'
    b'"coverage_commit":"e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9",'
    b'"selected_ms":0,"full_ms":12000,'
    b'"tests":4,"unmeasured":0,"tests_with_row":4,"tests_with_row_not_in_run":0,'
    b'"floor_matched":false,"rerun_given":false,'
)

# test_render's entry in K1's failed_left_out, up to its row, and all of it.
RENDER_UP_TO_ITS_ROW = (
    b'{"pair":["tests.test_report","test_render"],'
    b'"node_id":"tests/test_report.py::test_render","row":'
)
K1_FAILED_LEFT_OUT = (
    b"[" + RENDER_UP_TO_ITS_ROW + b'["src/shop/pricing.py","src/shop/report.py"]}]'
)


def k1_line_with(
    *,
    not_reproduced: bytes = b"[]",
    failed_left_out: bytes = K1_FAILED_LEFT_OUT,
    no_column: bytes = b'["templates/invoice.html"]',
    import_only: bytes = b"[]",
) -> bytes:
    """K1's line, with these lists, written as JSON, in place of its own."""
    return (
        K1_UP_TO_THE_LISTS
        + b'"not_reproduced":'
        + not_reproduced
        + b',"failed_left_out":'
        + failed_left_out
        + b',"no_column":'
        + no_column
        + b',"import_only":'
        + import_only
        + b"}\n"
    )


def with_render_row(row: frozenset[str]) -> records.EvaluatedRecord:
    """K1's record, with test_render left out with this row."""
    render = selection.Test(pair=RENDER_PAIR, node_id=TEST_RENDER, row=row)
    return dataclasses.replace(K1_RECORD, failed_left_out=(render,))


def line_with_render_row(row: bytes) -> bytes:
    """K1's line, with test_render left out with this row, written as JSON."""
    return k1_line_with(failed_left_out=b"[" + RENDER_UP_TO_ITS_ROW + row + b"}]")


def left_out(pair: tuple[str, str], node_id: str) -> selection.Test:
    """A failed test left out, as judge gives it, whose row is src/shop/tax.py
    alone: the row decides no order."""
    return selection.Test(
        pair=pair, node_id=node_id, row=frozenset({"src/shop/tax.py"})
    )


def entry(pair: bytes, node_id: bytes) -> bytes:
    """The entry in failed_left_out of a test that left_out gives, from its pair
    and node id written as JSON."""
    return (
        b'{"pair":' + pair + b',"node_id":' + node_id + b',"row":["src/shop/tax.py"]}'
    )


def json_list(*items: bytes) -> bytes:
    """A JSON list of these items, each already written as JSON."""
    return b"[" + b",".join(items) + b"]"


# Escapes. Each test puts characters in one field, where an input can put them:
# in a path, in a pair or a node id, or in H as given.

# Every printable ASCII character, from space to ~, but the quotation mark and
# the backslash, which have escapes of their own.
PRINTABLE_ASCII = "".join(
    chr(code) for code in range(0x20, 0x7F) if chr(code) not in {'"', "\\"}
)

# Characters in a changed path with no column, and how the line writes the path.
IN_A_PATH_WITH_NO_COLUMN = [
    pytest.param("docs/back\x08space.md", b"docs/back\\bspace.md", id="a backspace"),
    pytest.param(
        "templates/new\nline.html",
        b"templates/new\\nline.html",
        id="a newline, as in Report 16",
    ),
    pytest.param(
        "docs/tab\x0bline.md",
        b"docs/tab" + u_escape(b"000b") + b"line.md",
        id="a line tabulation, which has a short escape in C but not in JSON",
    ),
    pytest.param(
        "templates/invoice\x1b.html",
        b"templates/invoice" + u_escape(b"001b") + b".html",
        id="an escape character, as in Report 16",
    ),
    pytest.param(
        "docs/line" + chr(0x2028) + "break.md",
        b"docs/line" + u_escape(b"2028") + b"break.md",
        id="a line separator",
    ),
    pytest.param(
        "docs/" + chr(0xFFFF) + ".md",
        b"docs/" + u_escape(b"ffff") + b".md",
        id="U+FFFF, the last code point written with one escape",
    ),
    pytest.param(
        "docs/" + chr(0x10000) + ".md",
        b"docs/" + u_escape(b"d800") + u_escape(b"dc00") + b".md",
        id="U+10000, the first code point written as a surrogate pair",
    ),
    pytest.param(
        "docs/" + chr(0x10FFFF) + ".md",
        b"docs/" + u_escape(b"dbff") + u_escape(b"dfff") + b".md",
        id="U+10FFFF, the last code point",
    ),
    pytest.param(
        "docs/" + PRINTABLE_ASCII,
        b"docs/" + PRINTABLE_ASCII.encode("ascii"),
        id="every other printable ASCII character, as itself",
    ),
    pytest.param(
        "src/shop/caf" + chr(0xDCE9) + ".py",
        b"src/shop/caf" + u_escape(b"dce9") + b".py",
        id="a lone surrogate, which os.fsdecode gives for a byte that is not UTF-8",
    ),
]


@pytest.mark.parametrize(("path", "written"), IN_A_PATH_WITH_NO_COLUMN)
def test_a_path_with_no_column_is_written_with_the_specs_escapes(
    path: str, written: bytes
) -> None:
    record = dataclasses.replace(K1_RECORD, no_column=(path,))

    line = records.encode(record)

    assert line == k1_line_with(no_column=b'["' + written + b'"]')


# Characters in an import-only path, and how the line writes the path.
IN_AN_IMPORT_ONLY_PATH = [
    pytest.param(
        "src/shop/form\x0cfeed.py", b"src/shop/form\\ffeed.py", id="a form feed"
    ),
    pytest.param(
        "src/shop/unit\x1fseparator.py",
        b"src/shop/unit" + u_escape(b"001f") + b"separator.py",
        id="a unit separator, the last C0 control",
    ),
    pytest.param(
        "src/shop/next\x85line.py",
        b"src/shop/next" + u_escape(b"0085") + b"line.py",
        id="a next line, a C1 control",
    ),
    pytest.param(
        "src/shop/no\xa0break.py",
        b"src/shop/no" + u_escape(b"00a0") + b"break.py",
        id="a no-break space",
    ),
    pytest.param(
        "src/shop/" + chr(0xFEFF) + "bom.py",
        b"src/shop/" + u_escape(b"feff") + b"bom.py",
        id="a byte order mark",
    ),
]


@pytest.mark.parametrize(("path", "written"), IN_AN_IMPORT_ONLY_PATH)
def test_an_import_only_path_is_written_with_the_specs_escapes(
    path: str, written: bytes
) -> None:
    record = dataclasses.replace(K1_RECORD, import_only=(path,))

    line = records.encode(record)

    assert line == k1_line_with(import_only=b'["' + written + b'"]')


# Characters in a path of a failed test's row, and how the line writes the path.
IN_A_ROW = [
    pytest.param(
        "src/shop/car\rriage.py",
        b"src/shop/car\\rriage.py",
        id="a carriage return",
    ),
    pytest.param(
        "src/shop/del\x7f.py",
        b"src/shop/del" + u_escape(b"007f") + b".py",
        id="DEL, right after ~",
    ),
    pytest.param(
        "src/shop/tarifa a\xf1o.py",
        b"src/shop/tarifa a" + u_escape(b"00f1") + b"o.py",
        id="Edge 5's path, a space as itself and an n with a tilde",
    ),
]


@pytest.mark.parametrize(("path", "written"), IN_A_ROW)
def test_a_path_in_a_row_is_written_with_the_specs_escapes(
    path: str, written: bytes
) -> None:
    line = records.encode(with_render_row(frozenset({path})))

    assert line == line_with_render_row(b'["' + written + b'"]')


# Failed tests left out whose pair and node id hold characters, and their
# entries in failed_left_out.
IN_A_LEFT_OUT_TEST = [
    pytest.param(
        left_out(
            ("tests.test_greet", 'test_hello[say "hi"]'),
            'tests/test_greet.py::test_hello[say "hi"]',
        ),
        entry(
            b'["tests.test_greet","test_hello[say \\"hi\\"]"]',
            b'"tests/test_greet.py::test_hello[say \\"hi\\"]"',
        ),
        id="quotation marks in a parameter's id",
    ),
    pytest.param(
        left_out(
            ("tests.test_" + chr(0x20AC), "test_m"),
            "tests/test_" + chr(0x20AC) + ".py::test_m",
        ),
        entry(
            b'["tests.test_' + u_escape(b"20ac") + b'","test_m"]',
            b'"tests/test_' + u_escape(b"20ac") + b'.py::test_m"',
        ),
        id="a euro sign in a test file's name",
    ),
]


@pytest.mark.parametrize(("failed_test", "written"), IN_A_LEFT_OUT_TEST)
def test_a_left_out_tests_pair_and_node_id_are_written_with_the_specs_escapes(
    failed_test: selection.Test, written: bytes
) -> None:
    record = dataclasses.replace(K1_RECORD, failed_left_out=(failed_test,))

    line = records.encode(record)

    assert line == k1_line_with(failed_left_out=json_list(written))


# Pairs not reproduced that hold characters, and how the line writes them.
IN_A_PAIR_NOT_REPRODUCED = [
    pytest.param(
        ("tests.test_x", "test_m[caf\\xe9]"),
        b'["tests.test_x","test_m[caf\\\\xe9]"]',
        id="a backslash, from a parameter's id that pytest escaped",
    ),
    pytest.param(
        ("tests.tab\tdir.test_x", "test_m"),
        b'["tests.tab\\tdir.test_x","test_m"]',
        id="a tab in a directory's name",
    ),
    pytest.param(
        ("tests.test_" + chr(0x1F600), "test_m"),
        b'["tests.test_' + u_escape(b"d83d") + u_escape(b"de00") + b'","test_m"]',
        id="U+1F600 in a module's name, as a surrogate pair",
    ),
]


@pytest.mark.parametrize(("pair", "written"), IN_A_PAIR_NOT_REPRODUCED)
def test_a_pair_not_reproduced_is_written_with_the_specs_escapes(
    pair: tuple[str, str], written: bytes
) -> None:
    record = dataclasses.replace(K1_RECORD, not_reproduced=(pair,))

    line = records.encode(record)

    assert line == k1_line_with(not_reproduced=b"[" + written + b"]")


# Sorting. encode sorts every list it writes, by code point, whatever the order
# it gets them in, so these tests hand it each list out of order. Each case
# tells code point order from an order like it: the escaped text's, in which an
# escape starts with a backslash, U+005C; UTF-16's, in which every character
# beyond U+FFFF comes before U+E000 to U+FFFF; or a pair's joined into one
# string.

# A test in a class and a test of its module. By its whole classname, the
# module's comes first; joined to its name, as tests.test_x.TestB.test_c, with
# ::, / or nothing between them, or by its node id, the class's would.
CLASS_PAIR = ("tests.test_x.TestB", "test_c")
MODULE_PAIR = ("tests.test_x", "test_z")
TEST_IN_A_CLASS = "tests/test_x.py::TestB::test_c"
TEST_OF_THE_MODULE = "tests/test_x.py::test_z"

# Directory names that differ in a letter beyond ASCII. By code point, z
# (U+007A) comes before the n with a tilde (U+00F1); escaped, the n's escape
# starts with a backslash, which comes before z.
ANO = "tarifa a\xf1o"
AZUL = "tarifa azul"

# Characters beyond ASCII. By code point, a fullwidth a (U+FF41) comes before
# U+1F600; in UTF-16, and escaped, U+1F600 starts with U+D83D and comes first.
FULLWIDTH_A = chr(0xFF41)
SMILEY = chr(0x1F600)

# Pairs in the order encode gets them, and the list that the line holds: sorted
# by classname and then name.
PAIR_ORDERS = [
    pytest.param(
        (RENDER_PAIR, TOTAL_PAIR),
        b'[["tests.test_pricing","test_total"],["tests.test_report","test_render"]]',
        id="by classname before name",
    ),
    pytest.param(
        (VAT_PAIR, RATE_PAIR),
        b'[["tests.test_tax","test_rate"],["tests.test_tax","test_vat"]]',
        id="by name within a classname",
    ),
    pytest.param(
        (CLASS_PAIR, MODULE_PAIR),
        b'[["tests.test_x","test_z"],["tests.test_x.TestB","test_c"]]',
        id="by the whole classname, not joined to the name",
    ),
    pytest.param(
        (
            ("tests." + ANO + ".test_x", "test_m"),
            ("tests." + AZUL + ".test_x", "test_m"),
        ),
        b'[["tests.tarifa azul.test_x","test_m"],["tests.tarifa a'
        + u_escape(b"00f1")
        + b'o.test_x","test_m"]]',
        id="by code point, not by the escaped text",
    ),
    pytest.param(
        (("tests.test_" + SMILEY, "test_m"), ("tests.test_" + FULLWIDTH_A, "test_m")),
        b'[["tests.test_'
        + u_escape(b"ff41")
        + b'","test_m"],["tests.test_'
        + u_escape(b"d83d")
        + u_escape(b"de00")
        + b'","test_m"]]',
        id="by code point, not by UTF-16",
    ),
    pytest.param(
        (
            ("tests.test_report", "test_render[html]"),
            ("tests.test_report", "test_render[PDF]"),
        ),
        b'[["tests.test_report","test_render[PDF]"],'
        b'["tests.test_report","test_render[html]"]]',
        id="upper case before lower case",
    ),
]


@pytest.mark.parametrize(("pairs", "written"), PAIR_ORDERS)
def test_not_reproduced_is_sorted_by_classname_then_name_by_code_point(
    pairs: tuple[tuple[str, str], ...], written: bytes
) -> None:
    record = dataclasses.replace(K1_RECORD, not_reproduced=pairs)

    line = records.encode(record)

    assert line == k1_line_with(not_reproduced=written)


# Failed tests left out in the order encode gets them, and the list that the
# line holds: sorted by their pairs.
LEFT_OUT_ORDERS = [
    pytest.param(
        (left_out(RENDER_PAIR, TEST_RENDER), left_out(TOTAL_PAIR, TEST_TOTAL)),
        json_list(
            entry(
                b'["tests.test_pricing","test_total"]',
                b'"tests/test_pricing.py::test_total"',
            ),
            entry(
                b'["tests.test_report","test_render"]',
                b'"tests/test_report.py::test_render"',
            ),
        ),
        id="by classname before name",
    ),
    pytest.param(
        (left_out(VAT_PAIR, TEST_VAT), left_out(RATE_PAIR, TEST_RATE)),
        json_list(
            entry(b'["tests.test_tax","test_rate"]', b'"tests/test_tax.py::test_rate"'),
            entry(b'["tests.test_tax","test_vat"]', b'"tests/test_tax.py::test_vat"'),
        ),
        id="by name within a classname",
    ),
    pytest.param(
        (
            left_out(CLASS_PAIR, TEST_IN_A_CLASS),
            left_out(MODULE_PAIR, TEST_OF_THE_MODULE),
        ),
        json_list(
            entry(b'["tests.test_x","test_z"]', b'"tests/test_x.py::test_z"'),
            entry(
                b'["tests.test_x.TestB","test_c"]',
                b'"tests/test_x.py::TestB::test_c"',
            ),
        ),
        id="by the whole classname, not joined to the name or by node id",
    ),
    pytest.param(
        (
            left_out(
                ("tests." + ANO + ".test_x", "test_m"),
                "tests/" + ANO + "/test_x.py::test_m",
            ),
            left_out(
                ("tests." + AZUL + ".test_x", "test_m"),
                "tests/" + AZUL + "/test_x.py::test_m",
            ),
        ),
        json_list(
            entry(
                b'["tests.tarifa azul.test_x","test_m"]',
                b'"tests/tarifa azul/test_x.py::test_m"',
            ),
            entry(
                b'["tests.tarifa a' + u_escape(b"00f1") + b'o.test_x","test_m"]',
                b'"tests/tarifa a' + u_escape(b"00f1") + b'o/test_x.py::test_m"',
            ),
        ),
        id="by code point, not by the escaped text",
    ),
    pytest.param(
        (
            left_out(
                ("tests.test_" + SMILEY, "test_m"),
                "tests/test_" + SMILEY + ".py::test_m",
            ),
            left_out(
                ("tests.test_" + FULLWIDTH_A, "test_m"),
                "tests/test_" + FULLWIDTH_A + ".py::test_m",
            ),
        ),
        json_list(
            entry(
                b'["tests.test_' + u_escape(b"ff41") + b'","test_m"]',
                b'"tests/test_' + u_escape(b"ff41") + b'.py::test_m"',
            ),
            entry(
                b'["tests.test_'
                + u_escape(b"d83d")
                + u_escape(b"de00")
                + b'","test_m"]',
                b'"tests/test_'
                + u_escape(b"d83d")
                + u_escape(b"de00")
                + b'.py::test_m"',
            ),
        ),
        id="by code point, not by UTF-16",
    ),
    pytest.param(
        (
            left_out(
                ("tests.test_report", "test_render[html]"),
                "tests/test_report.py::test_render[html]",
            ),
            left_out(
                ("tests.test_report", "test_render[PDF]"),
                "tests/test_report.py::test_render[PDF]",
            ),
        ),
        json_list(
            entry(
                b'["tests.test_report","test_render[PDF]"]',
                b'"tests/test_report.py::test_render[PDF]"',
            ),
            entry(
                b'["tests.test_report","test_render[html]"]',
                b'"tests/test_report.py::test_render[html]"',
            ),
        ),
        id="upper case before lower case",
    ),
]


@pytest.mark.parametrize(("failed_tests", "written"), LEFT_OUT_ORDERS)
def test_failed_left_out_is_sorted_by_its_pairs_by_code_point(
    failed_tests: tuple[selection.Test, ...], written: bytes
) -> None:
    record = dataclasses.replace(K1_RECORD, failed_left_out=failed_tests)

    line = records.encode(record)

    assert line == k1_line_with(failed_left_out=written)


# Paths in the order encode gets them, and the list that the line holds.
PATH_ORDERS = [
    pytest.param(
        ("docs/guide.md", "README.md"),
        b'["README.md","docs/guide.md"]',
        id="upper case before lower case",
    ),
    pytest.param(
        ("docs/\xe9cole.md", "docs/zebra.md"),
        b'["docs/zebra.md","docs/' + u_escape(b"00e9") + b'cole.md"]',
        id="z before a letter beyond ASCII, whose escape comes before z",
    ),
    pytest.param(
        ("docs/a b.md", "docs/a\nb.md"),
        b'["docs/a\\nb.md","docs/a b.md"]',
        id="a newline before a space, though its escape comes after it",
    ),
    pytest.param(
        ("docs/" + SMILEY + ".md", "docs/" + FULLWIDTH_A + ".md"),
        b'["docs/'
        + u_escape(b"ff41")
        + b'.md","docs/'
        + u_escape(b"d83d")
        + u_escape(b"de00")
        + b'.md"]',
        id="U+FF41 before U+1F600, which UTF-16 puts first",
    ),
]


@pytest.mark.parametrize(("paths", "written"), PATH_ORDERS)
def test_the_paths_with_no_column_are_sorted_by_code_point(
    paths: tuple[str, ...], written: bytes
) -> None:
    record = dataclasses.replace(K1_RECORD, no_column=paths)

    line = records.encode(record)

    assert line == k1_line_with(no_column=written)


@pytest.mark.parametrize(("paths", "written"), PATH_ORDERS)
def test_the_import_only_paths_are_sorted_by_code_point(
    paths: tuple[str, ...], written: bytes
) -> None:
    record = dataclasses.replace(K1_RECORD, import_only=paths)

    line = records.encode(record)

    assert line == k1_line_with(import_only=written)


@pytest.mark.parametrize(("paths", "written"), PATH_ORDERS)
def test_the_paths_of_a_row_are_sorted_by_code_point(
    paths: tuple[str, ...], written: bytes
) -> None:
    # A row is a frozenset, which keeps no order of its own.
    line = records.encode(with_render_row(frozenset(paths)))

    assert line == line_with_render_row(written)


def test_a_row_is_sorted_whatever_order_its_frozenset_keeps() -> None:
    # A frozenset of strings keeps them in the order of their hashes, which
    # changes from one process to the next. Twelve files come out of it in
    # their sorted order by chance once in 12! runs, so an encode that does not
    # sort a row fails here every time, in practice: no set order reaches an
    # output (Rule 8). By code point, C comes before _, which comes before c.
    row = frozenset(
        {
            "src/utils/money.py",
            "src/shop/tax.py",
            "src/api/routes.py",
            "src/shop/__init__.py",
            "src/shop/report.py",
            "src/shop/cart.py",
            "src/utils/dates.py",
            "src/shop/Currency.py",
            "src/shop/pricing.py",
            "src/api/auth.py",
            "src/shop/orders.py",
            "src/shop/db.py",
        }
    )

    line = records.encode(with_render_row(row))

    assert line == line_with_render_row(
        b'["src/api/auth.py","src/api/routes.py","src/shop/Currency.py",'
        b'"src/shop/__init__.py","src/shop/cart.py","src/shop/db.py",'
        b'"src/shop/orders.py","src/shop/pricing.py","src/shop/report.py",'
        b'"src/shop/tax.py","src/utils/dates.py","src/utils/money.py"]'
    )
