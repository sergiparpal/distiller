import contextlib
import os
import signal
from collections.abc import Generator
from pathlib import Path
from types import FrameType

import pytest

from distiller import junit, messages

# Each test writes its own files in tmp_path, or hands parse_junit the bytes of
# one, and watches junit from outside: what read_junit and parse_junit return
# or raise, and what the file holds after.

# How long a call may run before fails_if_it_blocks stops it.
BLOCKING_SECONDS = 5

# Each JUnit input, with its path as a command line could give it. A rejection
# names that path exactly, ./ included.
INPUTS = [
    pytest.param("junit", "./ci/junit.xml", id="junit"),
    pytest.param("rerun", "./ci/rerun.xml", id="rerun"),
]

XML_DECLARATION = b'<?xml version="1.0" encoding="utf-8"?>'

# Children of a test case, with the messages pytest writes in them.
FAILURE = '<failure message="assert 2 == 3">assert 2 == 3</failure>'
SETUP_ERROR = '<error message="failed on setup with &quot;OSError&quot;">x</error>'
TEARDOWN_ERROR = (
    '<error message="failed on teardown with &quot;OSError&quot;">x</error>'
)
SKIPPED = '<skipped type="pytest.skip" message="not on CI">not on CI</skipped>'
EXPECTED_FAILURE = '<skipped type="pytest.xfail" message="a known bug" />'
COLLECTION_ERROR = '<error message="collection failure">ImportError</error>'
INTERNAL_ERROR = '<error message="internal error">Traceback</error>'

# A doctype that declares an entity, which nothing uses.
UNUSED_ENTITY = '<!DOCTYPE testsuites [<!ENTITY unused "never used">]>'


class BlockedError(BaseException):
    """A call was still running when the alarm went off.

    A BaseException, so that no `except Exception` in the code under test
    catches it.
    """


def case(classname: str, name: str, time: str, *children: str) -> str:
    """A testcase element with these attributes and children."""
    attributes = f'classname="{classname}" name="{name}" time="{time}"'
    inside = "".join(children)
    return f"<testcase {attributes}>{inside}</testcase>"


def junit_body(*testcases: str) -> bytes:
    """The testsuites element that pytest writes, around these test cases."""
    suite = (
        '<testsuite name="pytest" errors="0" failures="0" skipped="0" '
        f'tests="{len(testcases)}" time="12.345" '
        'timestamp="2026-10-10T12:00:00.000000+00:00" hostname="runner">'
    )
    cases = "".join(testcases)
    text = f'<testsuites name="pytest tests">{suite}{cases}</testsuite></testsuites>'
    return text.encode()


def junit_file(*testcases: str, doctype: str = "") -> bytes:
    """A JUnit file as pytest writes it, with a doctype if one is given."""
    return XML_DECLARATION + doctype.encode() + junit_body(*testcases)


def vat_with_output(output: str) -> str:
    """test_vat's test case, with captured output that can refer to an entity."""
    return case(
        "tests.test_tax", "test_vat", "1.000", f"<system-out>{output}</system-out>"
    )


def nested_expansions(levels: int) -> str:
    """Entities that each expand to ten of the one before, as in billion laughs.

    Kept small, so that a parser that expanded them all would still finish.
    """
    declarations = ['<!ENTITY lol0 "lol">']
    for level in range(1, levels + 1):
        ten_references = f"&lol{level - 1};" * 10
        declarations.append(f'<!ENTITY lol{level} "{ten_references}">')
    return "".join(declarations)


@contextlib.contextmanager
def fails_if_it_blocks() -> Generator[None]:
    """Stop with BlockedError a call that blocks, so that the test fails.

    Opening a FIFO for reading waits until something opens it for writing,
    which nothing does here: without the alarm, the test would hang.
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


def rejection(
    data: bytes, input_name: str, path: str
) -> tuple[str, str, str, int | None]:
    """The reason, input, subject and line number of what parse_junit raises."""
    with pytest.raises(messages.Rejected) as caught:
        junit.parse_junit(data, input_name, path)
    error = caught.value
    return error.reason, error.input_name, error.subject, error.line_number


# The fixture's tests as pytest writes them, and K1's full run, which is also
# K13's: test_render failed.
TEST_TOTAL = case("tests.test_pricing", "test_total", "2.000")
TEST_VAT = case("tests.test_tax", "test_vat", "1.000")
TEST_RENDER_FAILED = case("tests.test_report", "test_render", "5.000", FAILURE)
TEST_CREATE = case("tests.api.test_orders", "test_create", "4.000")
K1_JUNIT = junit_file(TEST_TOTAL, TEST_VAT, TEST_RENDER_FAILED, TEST_CREATE)
K1_RESULTS = {
    ("tests.test_pricing", "test_total"): junit.Result(
        failed=False, passed=True, time_ms=2000
    ),
    ("tests.test_tax", "test_vat"): junit.Result(
        failed=False, passed=True, time_ms=1000
    ),
    ("tests.test_report", "test_render"): junit.Result(
        failed=True, passed=False, time_ms=5000
    ),
    ("tests.api.test_orders", "test_create"): junit.Result(
        failed=False, passed=True, time_ms=4000
    ),
}

# The test case pytest writes for tests/test_report.py when it cannot collect
# it, as in K9.
REPORT_COLLECTION_ERROR = case("", "tests.test_report", "0.000", COLLECTION_ERROR)

# The test case pytest writes when it fails itself.
PYTEST_INTERNAL_ERROR = case("pytest", "internal", "0.000", INTERNAL_ERROR)

# Test cases that cannot be used, each for a reason of its own.
UNUSABLE_CASES = [
    pytest.param(
        '<testcase classname="tests.test_tax" name="test_vat" />', id="no time"
    ),
    pytest.param(PYTEST_INTERNAL_ERROR, id="pytest's internal error"),
]

# Each way a file can declare an entity, with the test cases that follow it.
# {target} stands for the URI of a FIFO in tmp_path: reading it would block.
ENTITY_DECLARATIONS = [
    pytest.param(UNUSED_ENTITY, (TEST_VAT,), id="an entity never used"),
    pytest.param(
        '<!DOCTYPE testsuites [<!ENTITY module "tests.test_tax">]>',
        (case("&module;", "test_vat", "1.000"),),
        id="an entity in an attribute",
    ),
    pytest.param(
        '<!DOCTYPE testsuites [<!ENTITY ext SYSTEM "{target}">]>',
        (TEST_VAT,),
        id="an external entity never used",
    ),
    pytest.param(
        '<!DOCTYPE testsuites [<!ENTITY ext SYSTEM "{target}">]>',
        (vat_with_output("&ext;"),),
        id="an external entity in a test's output",
    ),
    pytest.param(
        '<!DOCTYPE testsuites [<!ENTITY ext PUBLIC "-//Tests//EN" "{target}">]>',
        (vat_with_output("&ext;"),),
        id="a public external entity",
    ),
    pytest.param(
        '<!DOCTYPE testsuites [<!ENTITY % param "never used">]>',
        (TEST_VAT,),
        id="a parameter entity",
    ),
    pytest.param(
        '<!DOCTYPE testsuites [<!ENTITY % ext SYSTEM "{target}">%ext;]>',
        (TEST_VAT,),
        id="an external parameter entity",
    ),
    pytest.param(
        '<!DOCTYPE testsuites [<!NOTATION gif SYSTEM "image/gif">'
        '<!ENTITY logo SYSTEM "{target}" NDATA gif>]>',
        (TEST_VAT,),
        id="an unparsed entity",
    ),
    pytest.param(
        f"<!DOCTYPE testsuites [{nested_expansions(4)}]>",
        (vat_with_output("&lol4;"),),
        id="nested expansions, as in billion laughs",
    ),
]


# Reading


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(K1_JUNIT, id="K13's JUnit"),
        pytest.param(b"", id="empty"),
        pytest.param(b"\xef\xbb\xbfnot XML\r\n\xff\x00", id="bytes that are not XML"),
    ],
)
def test_reading_gives_the_files_bytes_as_they_are(data: bytes, tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.write_bytes(data)

    assert junit.read_junit(str(path)) == data


def test_a_file_that_may_only_be_read_is_read(tmp_path: Path) -> None:
    # Rule 3: the JUnit files are opened for reading only, which a read-only
    # file allows.
    path = tmp_path / "junit.xml"
    path.write_bytes(K1_JUNIT)
    path.chmod(0o444)

    assert junit.read_junit(str(path)) == K1_JUNIT


def test_a_missing_file_cannot_be_read(tmp_path: Path) -> None:
    assert junit.read_junit(str(tmp_path / "junit.xml")) is None


def test_a_directory_cannot_be_read(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    path.mkdir()

    assert junit.read_junit(str(path)) is None


def test_a_file_the_tool_is_not_allowed_to_read_cannot_be_read(
    tmp_path: Path,
) -> None:
    path = tmp_path / "junit.xml"
    path.write_bytes(K1_JUNIT)
    path.chmod(0)
    if os.access(path, os.R_OK):
        pytest.skip("this user reads a file whatever its mode, as root does")

    assert junit.read_junit(str(path)) is None


def test_a_fifo_cannot_be_read_and_reading_it_does_not_block(tmp_path: Path) -> None:
    path = tmp_path / "junit.xml"
    os.mkfifo(path)

    with fails_if_it_blocks():
        data = junit.read_junit(str(path))

    assert data is None


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(K1_JUNIT, id="K13"),
        pytest.param(junit_file(TEST_VAT, doctype=UNUSED_ENTITY), id="unsafe-xml"),
        pytest.param(K1_JUNIT[:100], id="not well-formed"),
    ],
)
def test_reading_and_parsing_leave_the_junit_file_byte_for_byte_as_it_was(
    data: bytes, tmp_path: Path
) -> None:
    path = tmp_path / "junit.xml"
    path.write_bytes(data)
    os.utime(path, ns=(0, 0))  # an old time, which any write would replace

    bytes_read = junit.read_junit(str(path))
    assert bytes_read is not None
    with contextlib.suppress(messages.Rejected):
        junit.parse_junit(bytes_read, "junit", str(path))

    assert path.read_bytes() == data
    assert path.stat().st_mtime_ns == 0


# Results by pair


def test_k1s_junit_gives_each_tests_result_under_its_pair() -> None:
    parsed = junit.parse_junit(K1_JUNIT, "junit", "./ci/junit.xml")

    assert parsed == junit.JUnit(results=K1_RESULTS, has_collection_error=False)


def test_a_pair_is_the_classname_and_the_name_as_the_file_holds_them() -> None:
    # The SPEC's example of the pair rule, a name with the characters that XML
    # escapes, and a classname with a letter that is not ASCII: n with a tilde.
    tarifa = "tests.test_tarifa_a" + chr(0xF1) + "o"
    data = junit_file(
        case("tests.test_tax.TestVat", "test_rate[es-0.21]", "0.100"),
        case("tests.test_odd", "test_odd[a&amp;b&lt;c&gt;&quot;d&quot;]", "0.100"),
        case(tarifa, "test_rate", "0.100"),
    )
    passed = junit.Result(failed=False, passed=True, time_ms=100)

    parsed = junit.parse_junit(data, "junit", "./ci/junit.xml")

    assert parsed.results == {
        ("tests.test_tax.TestVat", "test_rate[es-0.21]"): passed,
        ("tests.test_odd", 'test_odd[a&b<c>"d"]'): passed,
        (tarifa, "test_rate"): passed,
    }


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        pytest.param(
            (), junit.Result(failed=False, passed=True, time_ms=250), id="passed"
        ),
        pytest.param(
            (FAILURE,),
            junit.Result(failed=True, passed=False, time_ms=250),
            id="a failure",
        ),
        pytest.param(
            (SETUP_ERROR,),
            junit.Result(failed=True, passed=False, time_ms=250),
            id="an error in setup and no failure (Edge 14)",
        ),
        pytest.param(
            (TEARDOWN_ERROR,),
            junit.Result(failed=True, passed=False, time_ms=250),
            id="an error in teardown and no failure (Edge 14)",
        ),
        pytest.param(
            (SKIPPED,),
            junit.Result(failed=False, passed=False, time_ms=250),
            id="skipped",
        ),
        pytest.param(
            (EXPECTED_FAILURE,),
            junit.Result(failed=False, passed=False, time_ms=250),
            id="an expected failure, which pytest writes as skipped",
        ),
    ],
)
def test_a_failure_or_an_error_fails_a_test_and_a_skip_keeps_it_from_passing(
    children: tuple[str, ...], expected: junit.Result
) -> None:
    data = junit_file(case("tests.test_tax", "test_vat", "0.250", *children))

    parsed = junit.parse_junit(data, "rerun", "./ci/rerun.xml")

    assert parsed.results == {("tests.test_tax", "test_vat"): expected}


def shared_pair_case(time: str, *children: str) -> str:
    """A test case of tests/v1.2/test_x.py::test_m or tests/v1/2/test_x.py::test_m."""
    return case("tests.v1.2.test_x", "test_m", time, *children)


@pytest.mark.parametrize(
    ("testcases", "expected"),
    [
        pytest.param(
            (
                shared_pair_case("0.100", FAILURE),
                shared_pair_case("0.020", TEARDOWN_ERROR),
            ),
            junit.Result(failed=True, passed=False, time_ms=120),
            id="a failure in the call, then an error in the teardown",
        ),
        pytest.param(
            (
                shared_pair_case("1.000", FAILURE),
                shared_pair_case("1.000", FAILURE),
                shared_pair_case("1.000"),
            ),
            junit.Result(failed=True, passed=False, time_ms=3000),
            id="repeated attempts of one test",
        ),
        pytest.param(
            (shared_pair_case("0.250"), shared_pair_case("0.750", SETUP_ERROR)),
            junit.Result(failed=True, passed=False, time_ms=1000),
            id="two node ids with one pair",
        ),
        pytest.param(
            (shared_pair_case("0.100"), shared_pair_case("0.200")),
            junit.Result(failed=False, passed=True, time_ms=300),
            id="passed every time",
        ),
        pytest.param(
            (shared_pair_case("0.100"), shared_pair_case("0.000", SKIPPED)),
            junit.Result(failed=False, passed=False, time_ms=100),
            id="passed, then skipped",
        ),
    ],
)
def test_the_test_cases_that_share_a_pair_are_one_test(
    testcases: tuple[str, ...], expected: junit.Result
) -> None:
    data = junit_file(TEST_TOTAL, *testcases, TEST_CREATE)

    parsed = junit.parse_junit(data, "junit", "./ci/junit.xml")

    assert parsed.results == {
        ("tests.test_pricing", "test_total"): K1_RESULTS[
            ("tests.test_pricing", "test_total")
        ],
        ("tests.v1.2.test_x", "test_m"): expected,
        ("tests.api.test_orders", "test_create"): K1_RESULTS[
            ("tests.api.test_orders", "test_create")
        ],
    }


def test_properties_and_captured_output_are_not_results() -> None:
    data = junit_file(
        case(
            "tests.test_tax",
            "test_vat",
            "1.000",
            '<properties><property name="owner" value="billing" /></properties>',
            "<system-out>printed</system-out>",
            "<system-err>warned</system-err>",
        )
    )

    parsed = junit.parse_junit(data, "rerun", "./ci/rerun.xml")

    assert parsed.results == {
        ("tests.test_tax", "test_vat"): junit.Result(
            failed=False, passed=True, time_ms=1000
        )
    }


def test_a_junit_file_with_no_test_case_has_no_results() -> None:
    # What pytest writes when it collects no test.
    parsed = junit.parse_junit(junit_file(), "junit", "./ci/junit.xml")

    assert parsed == junit.JUnit(results={}, has_collection_error=False)


# Times


@pytest.mark.parametrize(
    ("time", "time_ms"),
    [
        pytest.param("2", 2000, id="digits alone"),
        pytest.param("0.123", 123, id="as pytest writes it"),
        pytest.param("1.5", 1500, id="one decimal"),
        pytest.param("00.250", 250, id="leading zeros"),
        pytest.param("0.000", 0, id="zero"),
        pytest.param("1.23456", 1235, id="more decimals, rounded up"),
        pytest.param("1.23449", 1234, id="more decimals, rounded down"),
        pytest.param("0.0005", 1, id="a half, rounded up"),
        pytest.param("0.0025", 3, id="a half, rounded up and not to even"),
        pytest.param("0.0004999", 0, id="just under a half"),
        pytest.param("0.9995", 1000, id="a half, rounded up to a whole second"),
        pytest.param("4.0005", 4001, id="a half that a float would round down"),
    ],
)
def test_a_time_is_rounded_to_the_nearest_millisecond_halves_up(
    time: str, time_ms: int
) -> None:
    data = junit_file(case("tests.test_tax", "test_vat", time))

    parsed = junit.parse_junit(data, "junit", "./ci/junit.xml")

    result = parsed.results[("tests.test_tax", "test_vat")]
    assert result.time_ms == time_ms
    assert type(result.time_ms) is int


@pytest.mark.parametrize(
    ("times", "time_ms"),
    [
        pytest.param(("0.0005", "0.0005"), 2, id="halves, each rounded up"),
        pytest.param(("0.0004", "0.0004", "0.0004"), 0, id="each rounded down"),
    ],
)
def test_each_test_cases_time_is_rounded_before_they_are_summed(
    times: tuple[str, ...], time_ms: int
) -> None:
    testcases = [case("tests.test_tax", "test_vat", time) for time in times]

    parsed = junit.parse_junit(junit_file(*testcases), "junit", "./ci/junit.xml")

    assert parsed.results == {
        ("tests.test_tax", "test_vat"): junit.Result(
            failed=False, passed=True, time_ms=time_ms
        )
    }


# Collection errors


@pytest.mark.parametrize(
    "testcases",
    [
        pytest.param(
            (REPORT_COLLECTION_ERROR,), id="only a collection error, as in K9"
        ),
        pytest.param(
            (TEST_TOTAL, TEST_VAT, REPORT_COLLECTION_ERROR, TEST_CREATE),
            id="among tests that ran",
        ),
    ],
)
def test_a_collection_error_is_recognized(testcases: tuple[str, ...]) -> None:
    parsed = junit.parse_junit(junit_file(*testcases), "junit", "./ci/junit.xml")

    assert parsed.has_collection_error is True


@pytest.mark.parametrize(
    "testcase_element",
    [
        pytest.param(
            case("tests", "test_report", "0.000", COLLECTION_ERROR), id="a classname"
        ),
        pytest.param(
            case("", "tests.test_report", "0.000", SETUP_ERROR), id="another message"
        ),
        pytest.param(
            case(
                "",
                "tests.test_report",
                "0.000",
                '<failure message="collection failure">x</failure>',
            ),
            id="a failure, not an error",
        ),
        pytest.param(
            case(
                "",
                "tests.test_report",
                "0.000",
                '<skipped message="collection skipped">x</skipped>',
            ),
            id="a module skipped at collection",
        ),
    ],
)
def test_only_an_error_of_collection_failure_with_no_classname_is_a_collection_error(
    testcase_element: str,
) -> None:
    data = junit_file(TEST_TOTAL, testcase_element)

    parsed = junit.parse_junit(data, "junit", "./ci/junit.xml")

    assert parsed.has_collection_error is False


# Test cases that cannot be used


@pytest.mark.parametrize(
    "testcase_element",
    [
        pytest.param('<testcase name="test_vat" time="1.000" />', id="no classname"),
        pytest.param(
            '<testcase classname="tests.test_tax" time="1.000" />', id="no name"
        ),
        pytest.param(
            '<testcase classname="tests.test_tax" name="test_vat" />', id="no time"
        ),
    ],
)
@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_k8_a_test_case_without_classname_name_or_time_cannot_be_used(
    testcase_element: str, input_name: str, path: str
) -> None:
    data = junit_file(TEST_TOTAL, testcase_element, TEST_CREATE)

    assert rejection(data, input_name, path) == (
        "unusable-input",
        input_name,
        path,
        None,
    )


# Digits of other scripts, which \d and Decimal take, written by code point:
# ARABIC-INDIC DIGIT ONE, FIVE and ZERO; FULLWIDTH DIGIT ONE, ZERO and FIVE;
# DEVANAGARI DIGIT ONE; and SUPERSCRIPT TWO, which str.isdigit takes.
ARABIC_INDIC_ONE_AND_A_HALF = chr(0x0661) + "." + chr(0x0665) + chr(0x0660) * 2
FULLWIDTH_ONE = chr(0xFF11) + "." + chr(0xFF10) * 3
DEVANAGARI_ONE = chr(0x0967)
SUPERSCRIPT_TWO = chr(0x00B2)

TIMES_THAT_CANNOT_BE_USED = [
    pytest.param("", id="empty"),
    pytest.param(".5", id="no digit before the point"),
    pytest.param("5.", id="no digit after the point"),
    pytest.param("1.2.3", id="two points"),
    pytest.param("-1.000", id="a minus sign"),
    pytest.param("+1.000", id="a plus sign"),
    pytest.param("1e3", id="an exponent"),
    pytest.param("inf", id="infinity"),
    pytest.param("NaN", id="not a number"),
    pytest.param("1,000", id="a comma"),
    pytest.param("1_000", id="an underscore"),
    pytest.param(" 1.000", id="a space before"),
    pytest.param("1.000 ", id="a space after"),
    pytest.param("1.000&#10;", id="a newline after"),
    pytest.param(ARABIC_INDIC_ONE_AND_A_HALF, id="Arabic-Indic digits"),
    pytest.param(FULLWIDTH_ONE, id="fullwidth digits"),
    pytest.param(DEVANAGARI_ONE, id="a Devanagari digit"),
    pytest.param("1." + chr(0xFF15), id="ASCII digits, then a fullwidth one"),
    pytest.param(SUPERSCRIPT_TWO, id="a superscript digit"),
]


@pytest.mark.parametrize("time", TIMES_THAT_CANNOT_BE_USED)
@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_k8_a_time_that_is_not_ascii_digits_with_an_optional_fraction_cannot_be_used(
    time: str, input_name: str, path: str
) -> None:
    data = junit_file(TEST_TOTAL, case("tests.test_tax", "test_vat", time), TEST_CREATE)

    assert rejection(data, input_name, path) == (
        "unusable-input",
        input_name,
        path,
        None,
    )


@pytest.mark.parametrize(
    "testcases",
    [
        pytest.param((PYTEST_INTERNAL_ERROR,), id="alone"),
        pytest.param(
            (TEST_TOTAL, TEST_VAT, PYTEST_INTERNAL_ERROR), id="after tests that ran"
        ),
    ],
)
@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_k8_a_file_that_holds_pytests_internal_error_cannot_be_used(
    testcases: tuple[str, ...], input_name: str, path: str
) -> None:
    data = junit_file(*testcases)

    assert rejection(data, input_name, path) == (
        "unusable-input",
        input_name,
        path,
        None,
    )


@pytest.mark.parametrize(
    "testcase_element",
    [
        pytest.param(
            case("pytest", "internal", "0.000", SETUP_ERROR), id="another message"
        ),
        pytest.param(
            case(
                "pytest",
                "internal",
                "0.000",
                '<failure message="internal error">x</failure>',
            ),
            id="a failure, not an error",
        ),
        pytest.param(
            case("tests.test_pytest", "internal", "0.000", INTERNAL_ERROR),
            id="another classname",
        ),
        pytest.param(
            case("pytest", "test_internal", "0.000", INTERNAL_ERROR), id="another name"
        ),
    ],
)
def test_a_test_case_that_only_looks_like_pytests_internal_error_is_a_failed_test(
    testcase_element: str,
) -> None:
    parsed = junit.parse_junit(junit_file(testcase_element), "junit", "./ci/junit.xml")

    assert list(parsed.results.values()) == [
        junit.Result(failed=True, passed=False, time_ms=0)
    ]


@pytest.mark.parametrize("unusable", UNUSABLE_CASES)
@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_a_test_case_that_cannot_be_used_comes_before_a_collection_error(
    unusable: str, input_name: str, path: str
) -> None:
    data = junit_file(REPORT_COLLECTION_ERROR, unusable)

    assert rejection(data, input_name, path) == (
        "unusable-input",
        input_name,
        path,
        None,
    )


# Unsafe XML and XML that is not well-formed


@pytest.mark.parametrize(("doctype", "testcases"), ENTITY_DECLARATIONS)
@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_k6_a_file_that_declares_an_entity_is_unsafe_and_nothing_it_names_is_read(
    doctype: str,
    testcases: tuple[str, ...],
    input_name: str,
    path: str,
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    os.mkfifo(target)
    data = junit_file(*testcases, doctype=doctype.format(target=target.as_uri()))

    with fails_if_it_blocks():
        found = rejection(data, input_name, path)

    assert found == ("unsafe-xml", input_name, path, None)


def test_a_doctype_that_declares_no_entity_is_not_unsafe() -> None:
    # Rule 5: DTDs are allowed, and only an entity declaration is unsafe.
    doctype = "<!DOCTYPE testsuites [<!-- no entity --><!ELEMENT testsuites ANY>]>"
    data = junit_file(
        TEST_TOTAL, TEST_VAT, TEST_RENDER_FAILED, TEST_CREATE, doctype=doctype
    )

    parsed = junit.parse_junit(data, "junit", "./ci/junit.xml")

    assert parsed == junit.JUnit(results=K1_RESULTS, has_collection_error=False)


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"not XML at all\n", id="text"),
        pytest.param(K1_JUNIT[: len(K1_JUNIT) // 2], id="cut short"),
        pytest.param(b"<testsuites><testsuite></testsuites>", id="mismatched tags"),
        pytest.param(b"<testsuites /><testsuites />", id="two root elements"),
        pytest.param(b'<testsuites name="\xff" />', id="a byte that is not UTF-8"),
        pytest.param(b"<testsuites>\x00</testsuites>", id="a NUL byte"),
        pytest.param(
            b'<testsuites name="&undeclared;" />', id="a reference to no entity"
        ),
    ],
)
@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_k8_a_file_that_is_not_well_formed_xml_cannot_be_used(
    data: bytes, input_name: str, path: str
) -> None:
    assert rejection(data, input_name, path) == (
        "unusable-input",
        input_name,
        path,
        None,
    )


@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_a_malformed_byte_before_an_entity_declaration_makes_the_file_unusable(
    input_name: str, path: str
) -> None:
    data = (
        XML_DECLARATION
        + b"<!-- \xff -->"
        + UNUSED_ENTITY.encode()
        + junit_body(TEST_VAT)
    )

    assert rejection(data, input_name, path) == (
        "unusable-input",
        input_name,
        path,
        None,
    )


@pytest.mark.parametrize(
    "malformed_body",
    [
        pytest.param(b"<testsuites><testsuite></testsuites>", id="mismatched tags"),
        pytest.param(b"<!-- \xff -->" + junit_body(TEST_VAT), id="a malformed byte"),
    ],
)
@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_an_entity_declaration_before_a_malformed_body_makes_the_file_unsafe(
    malformed_body: bytes, input_name: str, path: str
) -> None:
    data = XML_DECLARATION + UNUSED_ENTITY.encode() + malformed_body

    assert rejection(data, input_name, path) == ("unsafe-xml", input_name, path, None)


@pytest.mark.parametrize("unusable", UNUSABLE_CASES)
@pytest.mark.parametrize(("input_name", "path"), INPUTS)
def test_an_entity_declaration_comes_before_a_test_case_that_cannot_be_used(
    unusable: str, input_name: str, path: str
) -> None:
    data = junit_file(TEST_VAT, unusable, doctype=UNUSED_ENTITY)

    assert rejection(data, input_name, path) == ("unsafe-xml", input_name, path, None)
