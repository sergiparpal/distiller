import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.etree.ElementTree import Element

from defusedxml import EntitiesForbidden, ExternalReferenceForbidden
from defusedxml.ElementTree import ParseError, fromstring

from distiller import messages

# Reads a JUnit file into bytes, opening it for reading only, and parses those
# bytes into results by pair with defusedxml, which resolves and expands no
# entity.

Pair = tuple[str, str]  # (classname, name)


@dataclass(frozen=True)
class Result:  # one pair in one JUnit file, its test cases merged
    failed: bool  # a case has a failure or an error
    passed: bool  # no case has a failure, an error or a skipped
    time_ms: int  # the cases' times, each rounded half up, summed


@dataclass(frozen=True)
class JUnit:
    results: dict[Pair, Result]
    has_collection_error: bool


# A time as pytest writes it: ASCII digits, then optionally a point and more
# ASCII digits. [0-9] and not \d, which also takes the digits of other scripts.
_TIME_PATTERN = re.compile(r"[0-9]+(\.[0-9]+)?")


def read_junit(path: str) -> bytes | None:  # None: missing or cannot be read
    # Rule 3: the path must be a regular file before it is opened, since
    # opening a FIFO for reading waits until something opens it for writing.
    # is_file runs os.stat, which follows a symbolic link to what it points to.
    try:
        if not Path(path).is_file():
            return None  # missing, or a directory, a FIFO or a device
        return Path(path).read_bytes()  # opened for reading only
    except OSError:
        return None  # the tool is not allowed to read it, or reading failed


def parse_junit(data: bytes, input_name: str, path: str) -> JUnit:  # raises Rejected
    root = _parse_xml(data, input_name, path)
    results: dict[Pair, Result] = {}
    has_collection_error = False
    # Every testcase element is a test case, wherever it is in the file.
    for testcase in root.iter("testcase"):
        pair = _pair_of(testcase)
        time_ms = _time_ms_of(testcase)
        if pair is None or time_ms is None or _is_internal_error(testcase):
            raise messages.Rejected(
                reason="unusable-input", input_name=input_name, subject=path
            )
        result = _result_of(testcase, time_ms)
        # The test cases that share a pair are one test.
        if pair in results:
            result = _merged(results[pair], result)
        results[pair] = result
        if _is_collection_error(testcase):
            has_collection_error = True
    return JUnit(results=results, has_collection_error=has_collection_error)


def _parse_xml(data: bytes, input_name: str, path: str) -> Element:
    # Rule 5: defusedxml at its defaults, with entities and external references
    # forbidden and DTDs allowed. The parser stops at the first problem it
    # meets, and that one decides: an entity declaration, even of an entity
    # that is never used, is unsafe-xml, and XML that is not well-formed is
    # unusable-input. "from None" keeps a traceback from showing the parser's
    # error, whose text can quote the file, such as an entity's name.
    try:
        return fromstring(data)
    except (EntitiesForbidden, ExternalReferenceForbidden):
        raise messages.Rejected(
            reason="unsafe-xml", input_name=input_name, subject=path
        ) from None
    except ParseError:
        raise messages.Rejected(
            reason="unusable-input", input_name=input_name, subject=path
        ) from None


def _pair_of(testcase: Element) -> Pair | None:  # None: an attribute is missing
    classname = testcase.get("classname")
    name = testcase.get("name")
    if classname is None or name is None:
        return None
    return (classname, name)


def _time_ms_of(testcase: Element) -> int | None:  # None: it cannot be used
    time = testcase.get("time")
    if time is None or _TIME_PATTERN.fullmatch(time) is None:
        return None
    # Rule 5: through Decimal, never through a float, in which 4.0005 is a
    # little under 4.0005 and would round down.
    seconds = Decimal(time).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return int(seconds * 1000)


def _result_of(testcase: Element, time_ms: int) -> Result:
    # pytest writes failure, error and skipped as children of the testcase
    # element, and an expected failure as skipped too.
    failed = _has_child(testcase, "failure") or _has_child(testcase, "error")
    skipped = _has_child(testcase, "skipped")
    return Result(failed=failed, passed=not failed and not skipped, time_ms=time_ms)


def _merged(earlier: Result, later: Result) -> Result:
    # Failed if any of the test cases failed, passed only if all of them
    # passed, and the sum of their times.
    return Result(
        failed=earlier.failed or later.failed,
        passed=earlier.passed and later.passed,
        time_ms=earlier.time_ms + later.time_ms,
    )


def _is_collection_error(testcase: Element) -> bool:
    # What pytest writes for a file that it could not collect.
    return testcase.get("classname") == "" and _has_error_with_message(
        testcase, "collection failure"
    )


def _is_internal_error(testcase: Element) -> bool:
    # What pytest writes when it fails itself.
    return (
        testcase.get("classname") == "pytest"
        and testcase.get("name") == "internal"
        and _has_error_with_message(testcase, "internal error")
    )


def _has_child(testcase: Element, tag: str) -> bool:
    return any(child.tag == tag for child in testcase)


def _has_error_with_message(testcase: Element, message: str) -> bool:
    return any(
        child.tag == "error" and child.get("message") == message for child in testcase
    )
