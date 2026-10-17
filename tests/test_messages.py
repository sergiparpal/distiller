import re
from pathlib import Path

import pytest

from distiller import messages

# K15's text: a line of the record file holds it, and no message may.
CANARY = "canary"

# The fixture's commit ids and its JUnit file's SHA-256: <H>, <M> and <sha>.
HEAD = "c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4"
M = "e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9"
JUNIT_SHA256 = "5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a"

# Another run's key, so that the warning cannot be written for one key alone.
OTHER_HEAD = "0a9b8c7d6e5f40312a3b4c5d6e7f8091a2b3c4d5"
OTHER_JUNIT_SHA256 = "f0e1d2c3b4a5968778695a4b3c2d1e0ff0e1d2c3b4a5968778695a4b3c2d1e0f"

# Inputs as a command line could give them. A message names each one exactly
# so, ./ included: never resolved, normalized or made absolute.
CHECKOUT = "./pilot"
HEAD_AS_GIVEN = "no-such-head"
BASE = "origin/main"
COVERAGE = "./ci/m.coverage"
M_AS_GIVEN = "no-such-commit"
JUNIT = "./ci/junit.xml"
RERUN = "./ci/rerun.xml"
FLOOR_CONFIG = "./ci/floor.txt"
RECORDS = "./ci/records.jsonl"

# Each rejection, its input, and the path or name that its message names: the
# input's, or M's when M is what failed.
REJECTIONS = [
    pytest.param("unusable-input", "checkout", CHECKOUT, id="K8 checkout"),
    pytest.param("unusable-input", "head", HEAD_AS_GIVEN, id="K8 head"),
    pytest.param("unusable-input", "base", BASE, id="K8 base"),
    pytest.param("unusable-input", "coverage", COVERAGE, id="K8 K10 K14 coverage"),
    pytest.param("unusable-input", "coverage", M_AS_GIVEN, id="K8 M names no commit"),
    pytest.param("unusable-input", "junit", JUNIT, id="K8 junit"),
    pytest.param("unusable-input", "rerun", RERUN, id="K8 rerun"),
    pytest.param("unusable-input", "floor", FLOOR_CONFIG, id="K8 floor"),
    pytest.param("coverage-not-ancestor", "coverage", M, id="K4 M"),
    pytest.param("missing-history", "checkout", CHECKOUT, id="K5 checkout"),
    pytest.param("unsafe-xml", "junit", JUNIT, id="K6 junit"),
    pytest.param("unsafe-xml", "rerun", RERUN, id="K6 rerun"),
    pytest.param("no-shared-lines", "coverage", COVERAGE, id="no-shared-lines"),
    pytest.param("collection-error", "junit", JUNIT, id="K9 junit"),
]

# The rejections that come from a library's error about a file, whose text can
# quote what the file holds: defusedxml's names an entity and its system id.
FILE_REJECTIONS = [
    pytest.param("unsafe-xml", "junit", JUNIT, id="K6 junit"),
    pytest.param("unsafe-xml", "rerun", RERUN, id="K6 rerun"),
    pytest.param("unusable-input", "junit", JUNIT, id="K8 junit"),
    pytest.param("unusable-input", "coverage", COVERAGE, id="K8 K14 coverage"),
    pytest.param("unusable-input", "floor", FLOOR_CONFIG, id="K8 floor"),
]

# K15's record file: K4's line, with HEAD for <H> and JUNIT_SHA256 for <sha>,
# then a line that is not a record.
K15_RECORD_FILE = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4","junit_sha256":"'
    b'5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a","pr":7,'
    b'"verdict":"rejected","reason":"coverage-not-ancestor","input":"coverage"}\n'
    b"canary\n"
)


class LibraryError(Exception):
    pass


def numbers_in(message: str) -> list[int]:
    # Every run of ASCII digits in the message, as a number.
    return [int(digits) for digits in re.findall(r"[0-9]+", message)]


def test_a_rejected_keeps_its_reason_input_and_subject() -> None:
    error = messages.Rejected("unsafe-xml", "rerun", RERUN)

    assert error.reason == "unsafe-xml"
    assert error.input_name == "rerun"
    assert error.subject == RERUN
    assert error.line_number is None


def test_a_rejected_for_an_invalid_floor_pattern_keeps_its_line_number() -> None:
    error = messages.Rejected("unusable-input", "floor", FLOOR_CONFIG, 3)

    assert error.line_number == 3


@pytest.mark.parametrize(("reason", "input_name", "subject"), REJECTIONS)
def test_a_rejection_names_its_input_as_given(
    reason: str, input_name: str, subject: str
) -> None:
    message = messages.rejection(messages.Rejected(reason, input_name, subject))

    assert subject in message


@pytest.mark.parametrize(("reason", "input_name", "subject"), FILE_REJECTIONS)
def test_a_rejection_quotes_nothing_from_the_error_behind_it(
    reason: str, input_name: str, subject: str
) -> None:
    error = messages.Rejected(reason, input_name, subject)
    error.__cause__ = LibraryError(CANARY)  # what `raise error from cause` sets

    message = messages.rejection(error)

    assert subject in message
    assert CANARY not in message


@pytest.mark.parametrize("line_number", [3, 12])
def test_an_invalid_floor_pattern_is_named_by_its_file_and_line_number(
    line_number: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The configuration exists, and its line at line_number holds a pattern
    # that is not valid, since ? is no wildcard: named, never quoted.
    monkeypatch.chdir(tmp_path)
    comments = "# a comment\n" * (line_number - 1)
    (tmp_path / "floor.txt").write_text(f"{comments}{CANARY}/?.csv\n", encoding="utf-8")
    error = messages.Rejected("unusable-input", "floor", "floor.txt", line_number)

    message = messages.rejection(error)

    assert "floor.txt" in message
    assert line_number in numbers_in(message)
    assert CANARY not in message


def test_the_no_shared_lines_message_says_how_m_must_be_recorded() -> None:
    error = messages.Rejected("no-shared-lines", "coverage", COVERAGE)

    message = messages.rejection(error)

    assert "--cov-context=test" in message
    assert "COVERAGE_CORE=ctrace" in message
    assert "share no code" in message


@pytest.mark.parametrize(
    ("head", "junit_sha256"),
    [
        pytest.param(HEAD, JUNIT_SHA256, id="K3"),
        pytest.param(OTHER_HEAD, OTHER_JUNIT_SHA256, id="another key"),
    ],
)
def test_the_already_recorded_warning_names_the_key(
    head: str, junit_sha256: str
) -> None:
    message = messages.already_recorded(head, junit_sha256)

    assert head in message
    assert junit_sha256 in message


def test_the_already_recorded_warning_names_a_missing_junit_sha256_as_null() -> None:
    # decode checks no agreement between fields, so an evaluated record can
    # hold "junit_sha256":null; the warning names the key as the record does.
    message = messages.already_recorded(HEAD, None)

    assert HEAD in message
    assert "null" in message


def test_k15s_message_names_the_record_file_and_line_2_without_quoting_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "records.jsonl").write_bytes(K15_RECORD_FILE)

    message = messages.not_a_record("records.jsonl", 2)

    assert "records.jsonl" in message
    assert 2 in numbers_in(message)
    assert CANARY not in message


def test_a_line_that_is_not_a_record_is_named_by_its_file_and_number() -> None:
    message = messages.not_a_record(RECORDS, 15)

    assert RECORDS in message
    assert 15 in numbers_in(message)


@pytest.mark.parametrize("path", [RECORDS, "missing.jsonl"])
def test_a_record_file_the_report_cannot_read_is_named_by_its_path(path: str) -> None:
    message = messages.unreadable_record_file(path)

    assert path in message
