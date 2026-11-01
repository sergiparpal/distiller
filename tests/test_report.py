import dataclasses
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from distiller import cli, records, report, selection

# Each test writes record files in tmp_path, its working directory, runs the
# report on them and looks for words in what it writes on stdout, or on stderr
# for a record file that the report cannot use; the tests of
# clopper_pearson_upper call it alone. The report's tests call report.run, so
# that an exception it raises reaches the test, and so that a check that some
# words are absent, or that nothing is on stdout, cannot pass on a report that
# failed: cli would turn the exception into exit 1 with nothing on stdout. Only
# the tests of the command's exit codes and streams go through cli.main, and
# the test of Invariants 1 runs python -m distiller, as the CI step does.
#
# Every line of a record file is what records.encode writes for a record built
# as a literal, and write_record_file checks that records.decode gives that
# record back, so that each line is a record as Rule 7 defines it. Only the
# tests of a line that is not a record write one that is not.
#
# The report's layout is not fixed (open question 4): each test looks for the
# words of one figure or sentence, taken from the examples. Where the SPEC
# leaves the report open, these tests follow the answers given in task 16's
# tests phase, 2026-10-31. One form for each figure, whichever example shows
# it: "<k> missed PR[s] out of <n> PR[s] with a red run", "one-sided 95%
# Clopper-Pearson upper bound of <b>%", "<r> red run[s]" and "savings of <s>%",
# each in the singular only for 1. Clopper-Pearson is written with a hyphen, so
# that the whole report is ASCII. With a zero denominator the report says so,
# "with no bound" for the miss rate and "no savings figure" for the savings.
# The miss rate is shown as k out of n and its bound, never as a percentage.
# clopper_pearson_upper is within 1e-9 of the proportion it should give.
#
# Where the SPEC leaves the rest of the report open, these tests follow the
# answers given in task 17's tests phase, 2026-11-01. One form for each entry
# of the two lists that task 17 adds. A count of rejected runs, for each pair
# of reason and input: "<n> run[s] rejected for <reason> with <input>", in the
# singular only for 1; with none, "no rejected run", Report 13's words. A
# conflict: "conflict: <key> in <record files>", the key as its records' lines
# write it, "head":...,"junit_sha256":..., escapes included, and the record
# files as a JSON list of strings, sorted, each once, as a record writes a list
# of paths; with none, "no conflict". A conflict names every record file in
# which its key appears, one that holds only a rejected record of that key
# included, and a record file given twice once, comparing paths as given,
# which no test pins. Two evaluated records with one key differ when any of
# their fields does, pr included. The record files here have ASCII names, with
# nothing to escape: the escape of a path is task 18's. A head that its record
# has to escape is this task's, since the SPEC's sentence on escaping names
# pairs, node ids and paths, not the key. The order of the list of failed
# tests left out is task 18's.
#
# Where the SPEC leaves the rest of the report open, these tests follow the
# answers given in task 18's tests phase, 2026-11-01. One form for each figure,
# in the singular only for 1. The floor and no-column rates always show their
# counts, as Report 5 and 6 do: "floor rate of <p>%: <k> PR[s] out of <n>" and
# "no-column rate of <p>%: <k> PR[s] out of <n>". The shares: "<p>% of tests
# treated as unmeasured" and "<p>% of the tests with a row were not in their
# run". With a zero denominator each of the four is 0 out of 0, as the miss
# rate is: "floor rate: 0 PRs out of 0", "no-column rate: 0 PRs out of 0", "0
# out of 0 tests treated as unmeasured" and "0 out of 0 tests with a row were
# not in their run". Saying "no floor rate" could be read as a floor that never
# matched, and with few PRs a reader needs to see how many each rate comes
# from. The reruns: "the failures of <r> red run[s] were not confirmed by a
# rerun" and "<f> failures were discarded as not reproduced", "1 failure was"
# for 1, then "order-dependent failures can hide in that count", without the
# SPEC's section number, whose sign is not ASCII. A failure discarded counts in
# its run, so a pair discarded in two runs counts twice. The list of failed
# tests left out names each run by its key, written as a conflict's, and by its
# pull request, "PR <n>": a pull request can have several runs, and it holds the
# diff's paths, which a record does not. Next to them go the run's "paths with
# no column <list>" and "import-only paths <list>", each a JSON list of strings
# that is empty for none, and each failed test as its record's line writes it
# in failed_left_out, with "its row has none of the diff's paths, and no other
# rule picked it". With no entry, "no failed test left out". A run that left
# out no failed test shows none of its paths, so Report 16's run is K1's, and a
# conflict's failed tests left out are not listed, since a conflict counts in
# no figure. Within a run, a record's line holds the failed tests by pair and
# each list of paths by path, so no record file can give them in another order:
# those tests tell the order that the report keeps from the orders that another
# comparison would give. The escape tests put a newline, an escape character
# and an n with a tilde in each field that the report writes: the first two are
# ASCII, so only the n can show a report that is not.

# The fixture's merge-base and M, as tests/test_records.py writes them.
MERGE_BASE = "9d1e3f5a7b2c4d6e8f0a1b3c5d7e9f2a4b6c8d0e"
M = "e2b4d6f8a0c1e3b5d7f9a2c4e6b8d0f1a3c5e7b9"

# test_render, failed and left out of the selection, as in K1's record.
K1_TEST_RENDER = selection.Test(
    pair=("tests.test_report", "test_render"),
    node_id="tests/test_report.py::test_render",
    row=frozenset({"src/shop/pricing.py", "src/shop/report.py"}),
)

# How far clopper_pearson_upper may be from the proportion it should give.
TOLERANCE = 1e-9


# Records

# Each run is named by a number, r1, r2 and so on, as in the examples. Its key
# is that number written in hex digits: 40 for its head, as a full commit id,
# and 64 for its JUnit file's SHA-256, so that each run has a key of its own.


def commit_id(run: int) -> str:
    """Run r<run>'s head: its number in 40 lowercase hex digits."""
    return f"{run:040x}"


def junit_sha256(run: int) -> str:
    """Run r<run>'s JUnit file's SHA-256: its number in 64 lowercase hex digits."""
    return f"{run:064x}"


def key_of(run: int) -> records.RunKey:
    return records.RunKey(head=commit_id(run), junit_sha256=junit_sha256(run))


def evaluated(
    run: int, pr: int, verdict: str, *, selected_ms: int = 0, full_ms: int = 12000
) -> records.EvaluatedRecord:
    """Run r<run>'s evaluated record, for pull request pr.

    K1's record with another key, pr, verdict and durations: by default the
    fixture's 12.0 s suite with nothing selected, as in K1. A missed run left
    test_render out, as K1's did, and a green or caught run no failed test, so
    that each record agrees with itself, although the SPEC does not ask it to.
    """
    failed_left_out = (K1_TEST_RENDER,) if verdict == "missed" else ()
    return records.EvaluatedRecord(
        key=key_of(run),
        pr=pr,
        verdict=verdict,
        merge_base=MERGE_BASE,
        coverage_commit=M,
        selected_ms=selected_ms,
        full_ms=full_ms,
        tests=4,
        unmeasured=0,
        tests_with_row=4,
        tests_with_row_not_in_run=0,
        floor_matched=False,
        rerun_given=False,
        not_reproduced=(),
        failed_left_out=failed_left_out,
        no_column=("templates/invoice.html",),
        import_only=(),
    )


def rejected(run: int, pr: int, reason: str, input_name: str) -> records.RejectedRecord:
    """Run r<run>'s rejected record, for pull request pr."""
    return records.RejectedRecord(
        key=key_of(run), pr=pr, reason=reason, input_name=input_name
    )


def write_record_file(path: Path, recorded: list[records.Record]) -> None:
    """Write one line for each record, in this order.

    Each line is what encode writes, and decode must give the record back:
    a line that is not a record would stop the report, which is not what these
    tests look at.
    """
    lines: list[bytes] = []
    for record in recorded:
        line = records.encode(record)
        assert records.decode(line) == record, f"not a record: {line!r}"
        lines.append(line)
    path.write_bytes(b"".join(lines))


def write_record_files(
    record_files: list[list[records.Record]], directory: Path
) -> list[str]:
    """Write each list as a record file in directory, the working directory,
    and return their paths, in this order, as a command line gives them."""
    paths: list[str] = []
    for number, recorded in enumerate(record_files, start=1):
        name = f"records-{number}.jsonl"
        write_record_file(directory / name, recorded)
        paths.append(name)
    return paths


def report_of(
    record_files: list[list[records.Record]],
    directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> str:
    """What report.run writes on stdout for these record files."""
    report.run(write_record_files(record_files, directory))
    return capsys.readouterr().out


def shows(text: str, words: str) -> bool:
    """Whether text holds words, with no letter or digit right before or after
    them: "4 red runs" is not in "14 red runs", nor "1 red run" in "1 red runs".

    (?<!...) and (?!...) look at the character before and after the words
    without taking it into the match, and also hold at the start and the end
    of the text.
    """
    no_letter_or_digit_before = r"(?<![0-9A-Za-z])"
    no_letter_or_digit_after = r"(?![0-9A-Za-z])"
    pattern = no_letter_or_digit_before + re.escape(words) + no_letter_or_digit_after
    return re.search(pattern, text) is not None


def comes_before(text: str, first: str, second: str) -> bool:
    """Whether text shows both words, first before second."""
    both_shown = shows(text, first) and shows(text, second)
    return both_shown and text.index(first) < text.index(second)


def numbers_in(message: str) -> list[int]:
    """Every run of ASCII digits in the message, as a number, as
    tests/test_messages.py reads them."""
    return [int(digits) for digits in re.findall(r"[0-9]+", message)]


@pytest.fixture
def working_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """tmp_path, as the working directory, where the record files go."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


# The examples' recorded runs

# Report 1: r1 (green) and r2 (caught) of PR 1, r3 (missed) and r4 (caught) of
# PR 2, r5 (green) of PR 3 and r6 (caught) of PR 4.
R3_MISSED = evaluated(3, 2, "missed")
REPORT_1: list[records.Record] = [
    evaluated(1, 1, "green"),
    evaluated(2, 1, "caught"),
    R3_MISSED,
    evaluated(4, 2, "caught"),
    evaluated(5, 3, "green"),
    evaluated(6, 4, "caught"),
]

# Report 2: 30 PRs with a red run and none missed, one caught run each.
REPORT_2: list[records.Record] = [evaluated(pr, pr, "caught") for pr in range(1, 31)]

# Report 3: recorded runs that are all green.
REPORT_3: list[records.Record] = [
    evaluated(1, 1, "green"),
    evaluated(2, 2, "green"),
    evaluated(3, 3, "green"),
]

# Report 4: two runs of the 12.0 s suite, r1, which selected 3.0 s, and r2,
# where the floor selected all 12.0 s.
R1_SELECTED_3_S = evaluated(1, 1, "green", selected_ms=3000)
R2_FLOOR_SELECTED_ALL = dataclasses.replace(
    evaluated(2, 2, "green", selected_ms=12000), floor_matched=True
)
REPORT_4: list[records.Record] = [R1_SELECTED_3_S, R2_FLOOR_SELECTED_ALL]

# Rejected runs, of PR 3, whose only evaluated run in Report 1 is green, and of
# PR 5, which has no evaluated run. No evaluated run has their keys.
REJECTED_OF_PR_3 = rejected(8, 3, "unusable-input", "coverage")
REJECTED_OF_PR_5 = rejected(9, 5, "missing-history", "checkout")

# A single caught run, of PR 1: 0 missed PRs out of 1, and 1 red run.
ONE_CAUGHT_RUN: list[records.Record] = [evaluated(1, 1, "caught")]

# Report 13: r1 of PR 1, first rejected because its coverage file was missing,
# and then evaluated as caught.
R1_REJECTED_FOR_ITS_COVERAGE = rejected(1, 1, "unusable-input", "coverage")
R1_CAUGHT = evaluated(1, 1, "caught")
REPORT_13: list[records.Record] = [R1_REJECTED_FOR_ITS_COVERAGE, R1_CAUGHT]

# Report 15: r1 (caught) of PR 1 and r2 (missed) of PR 2 in one record file,
# and in a second one r2, with the same key, caught, because it was evaluated
# against coverage from another commit. The example gives no durations: r1
# selected 3.0 s, test_total and test_vat, as for a diff of src/shop/tax.py,
# and the caught r2 test_render's 5.0 s, so that r2 would show in the savings.
OTHER_M = "b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1"
R1_CAUGHT_SELECTED_3_S = evaluated(1, 1, "caught", selected_ms=3000)
R2_MISSED = evaluated(2, 2, "missed")
R2_CAUGHT_AGAINST_OTHER_COVERAGE = dataclasses.replace(
    evaluated(2, 2, "caught", selected_ms=5000), coverage_commit=OTHER_M
)
REPORT_15: list[list[records.Record]] = [
    [R1_CAUGHT_SELECTED_3_S, R2_MISSED],
    [R2_CAUGHT_AGAINST_OTHER_COVERAGE],
]

# The figures' words, in the form these tests take for every example.
REPORT_1_MISS_RATE = "1 missed PR out of 3 PRs with a red run"
REPORT_1_RED_RUNS = "4 red runs"
REPORT_4_SAVINGS = "savings of 37.5%"
NO_SAVINGS_FIGURE = "no savings figure"

# The words that show a figure as a percentage, which a zero denominator never
# gives.
A_BOUND = "Clopper-Pearson upper bound of"
A_SAVINGS_FIGURE = "savings of"

# The report's sentences.
SAVINGS_ARE_AN_UPPER_BOUND = (
    "this is an upper bound, because fixed per-run costs such as start-up and "
    "collection are not in the JUnit times"
)
FIGURES_BELONG_TO_THE_ALL_AFFECTED_SELECTOR = (
    "figures belong to the all-affected selector, which picks every test that "
    "any rule picks over these rows; a selector that picks only some of them, "
    "such as a set cover over the same rows, misses at least as often"
)

# Report 13's and Report 15's miss rate.
REPORT_13_AND_15_MISS_RATE = "0 missed PRs out of 1 PR with a red run"

# What the lists of rejected runs and of conflicts say with no entry.
NO_REJECTED_RUN = "no rejected run"
NO_CONFLICT = "no conflict"


# The recorded runs of Report 5 to 12 and 16

# evaluated's runs change only templates/invoice.html, as K1's does: a path with
# no column, and no floor match. The runs below change other paths.


def floor_matched_run(run: int, pr: int) -> records.EvaluatedRecord:
    """Run r<run>'s green record, for pull request pr, whose diff changes
    uv.lock: a path with no column that matches the floor, which selected the
    whole 12.0 s suite."""
    return dataclasses.replace(
        evaluated(run, pr, "green", selected_ms=12000),
        floor_matched=True,
        no_column=("uv.lock",),
    )


def tax_only_run(run: int, pr: int) -> records.EvaluatedRecord:
    """Run r<run>'s green record, for pull request pr, whose diff changes only
    src/shop/tax.py, a column: test_total and test_vat, 3.0 s, are selected,
    and no changed path lacks a column."""
    return dataclasses.replace(
        evaluated(run, pr, "green", selected_ms=3000), no_column=()
    )


def with_tests(
    record: records.EvaluatedRecord,
    *,
    tests: int,
    unmeasured: int,
    tests_with_row: int,
    not_in_run: int,
) -> records.EvaluatedRecord:
    """record with these counts: the run's tests and how many of them are
    unmeasured, and the tests with a row in its coverage and how many of those
    are not in the run."""
    return dataclasses.replace(
        record,
        tests=tests,
        unmeasured=unmeasured,
        tests_with_row=tests_with_row,
        tests_with_row_not_in_run=not_in_run,
    )


def given_a_rerun(
    record: records.EvaluatedRecord, *not_reproduced: tuple[str, str]
) -> records.EvaluatedRecord:
    """record, given a rerun file in which these of its failed tests passed,
    in pair order, as its line holds them."""
    return dataclasses.replace(record, rerun_given=True, not_reproduced=not_reproduced)


# Report 5: all 3 runs of PR 1 matched the floor, and the single runs of PRs 2,
# 3 and 4 did not.
REPORT_5: list[records.Record] = [
    floor_matched_run(1, 1),
    floor_matched_run(2, 1),
    floor_matched_run(3, 1),
    evaluated(4, 2, "green"),
    evaluated(5, 3, "green"),
    evaluated(6, 4, "green"),
]

# Report 6: the run of PR 1 changed only templates/invoice.html, the run of PR 2
# templates/invoice.html and uv.lock, which matched the floor, and the runs of
# PRs 3 and 4 only src/shop/tax.py.
REPORT_6: list[records.Record] = [
    evaluated(1, 1, "green"),
    dataclasses.replace(
        floor_matched_run(2, 2), no_column=("templates/invoice.html", "uv.lock")
    ),
    tax_only_run(3, 3),
    tax_only_run(4, 4),
]

# Report 7: two runs of four tests each, one of which had one unmeasured test,
# test_create, added after M, so that the coverage of that run has three tests
# with a row.
REPORT_7: list[records.Record] = [
    with_tests(
        evaluated(1, 1, "green"),
        tests=4,
        unmeasured=1,
        tests_with_row=3,
        not_in_run=0,
    ),
    with_tests(
        evaluated(2, 2, "green"),
        tests=4,
        unmeasured=0,
        tests_with_row=4,
        not_in_run=0,
    ),
]

# Report 8: two runs, each evaluated against coverage in which four tests have a
# row, where one of those four, test_vat, is not in the second run: deleted at
# H, as in Edge 7, so that the second run has three tests.
REPORT_8: list[records.Record] = [
    with_tests(
        evaluated(1, 1, "green"),
        tests=4,
        unmeasured=0,
        tests_with_row=4,
        not_in_run=0,
    ),
    with_tests(
        evaluated(2, 2, "green"),
        tests=3,
        unmeasured=0,
        tests_with_row=4,
        not_in_run=1,
    ),
]

# Report 9: a missed run whose diff changes only templates/invoice.html and in
# which test_render failed: K1's record, with r1's key.
K1_RUN = evaluated(1, 7, "missed")


def missed_run_with(
    key: records.RunKey, *left_out: selection.Test
) -> records.EvaluatedRecord:
    """K1's run with this key, which left out these failed tests, in pair
    order, as its line holds them."""
    return dataclasses.replace(K1_RUN, key=key, failed_left_out=left_out)


# Report 10: a caught run in which test_render also failed without being
# selected, as in Verdict 3: its diff changes src/shop/tax.py, and test_vat and
# test_render failed.
REPORT_10_RUN = dataclasses.replace(
    tax_only_run(2, 8), verdict="caught", failed_left_out=(K1_TEST_RENDER,)
)

# Report 11: 5 red runs, 2 of them, r1 and r2, without a rerun file.
REPORT_11: list[records.Record] = [
    evaluated(1, 1, "caught"),
    evaluated(2, 2, "missed"),
    given_a_rerun(evaluated(3, 3, "caught")),
    given_a_rerun(evaluated(4, 4, "caught")),
    given_a_rerun(evaluated(5, 5, "missed")),
]

# Report 12: 3 failed tests passed in their rerun files: test_render in r1,
# green, as in K2, and test_total and test_vat in r2, which another failure made
# caught.
RENDER_PAIR = ("tests.test_report", "test_render")
TOTAL_PAIR = ("tests.test_pricing", "test_total")
VAT_PAIR = ("tests.test_tax", "test_vat")
REPORT_12: list[records.Record] = [
    given_a_rerun(evaluated(1, 1, "green"), RENDER_PAIR),
    given_a_rerun(evaluated(2, 2, "caught"), TOTAL_PAIR, VAT_PAIR),
]

# Report 16: a run in which a changed path with no column has a newline and an
# escape character in its name. The report shows a run's paths only next to the
# failed tests that it left out, so the run is K1's.
REPORT_16_RUN = dataclasses.replace(K1_RUN, no_column=("templates/new\nline\x1b.html",))

# The words of Report 5 to 12, in the form that every test of these figures,
# this list and these sentences takes.
REPORT_5_FLOOR_RATE = "floor rate of 25%: 1 PR out of 4"
REPORT_6_NO_COLUMN_RATE = "no-column rate of 25%: 1 PR out of 4"
REPORT_7_UNMEASURED_SHARE = "12.5% of tests treated as unmeasured"
REPORT_8_NOT_IN_RUN_SHARE = "12.5% of the tests with a row were not in their run"
REPORT_11_NOT_CONFIRMED = "the failures of 2 red runs were not confirmed by a rerun"
REPORT_12_DISCARDED = "3 failures were discarded as not reproduced"
ORDER_DEPENDENT_FAILURES = "order-dependent failures can hide in that count"
WHY_IT_WAS_LEFT_OUT = (
    "its row has none of the diff's paths, and no other rule picked it"
)
NO_FAILED_TEST_LEFT_OUT = "no failed test left out"

# A rate or a share with a zero denominator: 0 out of 0, as the miss rate.
FLOOR_RATE_0_OUT_OF_0 = "floor rate: 0 PRs out of 0"
NO_COLUMN_RATE_0_OUT_OF_0 = "no-column rate: 0 PRs out of 0"
UNMEASURED_0_OUT_OF_0 = "0 out of 0 tests treated as unmeasured"
NOT_IN_RUN_0_OUT_OF_0 = "0 out of 0 tests with a row were not in their run"

# The words that show a rate or a share as a percentage, which a zero
# denominator never gives.
A_FLOOR_RATE = "floor rate of"
A_NO_COLUMN_RATE = "no-column rate of"
AN_UNMEASURED_SHARE = "% of tests treated as unmeasured"
A_NOT_IN_RUN_SHARE = "% of the tests with a row were not in their run"

# The report writes pairs, node ids and paths as JSON strings, as a record's
# line does. These helpers write those with nothing to escape.


def json_string(text: str) -> str:
    """text as a JSON string, for text with nothing to escape."""
    return '"' + text + '"'


def json_list(items: list[str]) -> str:
    """A JSON list of these items, each already written as JSON."""
    return "[" + ",".join(items) + "]"


def left_out_entry(test: selection.Test) -> str:
    """A failed test left out, as its record's line writes it in
    failed_left_out: its pair, its node id and its row, sorted by path."""
    assert test.node_id is not None
    assert test.row is not None
    pair = json_list([json_string(name) for name in test.pair])
    node_id = json_string(test.node_id)
    row = json_list([json_string(path) for path in sorted(test.row)])
    return '{"pair":' + pair + ',"node_id":' + node_id + ',"row":' + row + "}"


def paths_with_no_column(written: str) -> str:
    """The words that show a run's paths with no column, written as a JSON
    list, next to the failed tests that it left out."""
    return "paths with no column " + written


def import_only_paths(written: str) -> str:
    """The words that show a run's import-only paths, written as a JSON list,
    next to the failed tests that it left out."""
    return "import-only paths " + written


# test_render, left out in Report 9 and 10, as K1's line writes it.
K1_LEFT_OUT_ENTRY = (
    '{"pair":["tests.test_report","test_render"],'
    '"node_id":"tests/test_report.py::test_render",'
    '"row":["src/shop/pricing.py","src/shop/report.py"]}'
)

# A backslash. Every escape made of a backslash, u and four hex digits is built
# from it: typed in one piece in a Write or Edit call, such an escape lands in
# the file as the character it stands for (CLAUDE.md).
BACKSLASH = "\\"


def u_escape(hex_digits: str) -> str:
    """How a JSON string writes a character outside printable ASCII that has no
    short escape: a backslash, u and these four hex digits."""
    return BACKSLASH + "u" + hex_digits


# A conflict's words


def key_as_its_line_writes_it(record: records.Record) -> str:
    """The key of record as the record's line writes it,
    "head":...,"junit_sha256":..., escapes included: what comes between the
    line's "format" and its "pr"."""
    line = records.encode(record).decode("ascii")
    before_the_key = '{"format":1,'
    assert line.startswith(before_the_key)
    return line[len(before_the_key) : line.index(',"pr":')]


def conflict(record: records.Record, record_files: list[str]) -> str:
    """The words that list the key of record as a conflict, with these record
    files in this order. Their names are ASCII, with nothing to escape."""
    key = key_as_its_line_writes_it(record)
    names = ",".join(f'"{name}"' for name in record_files)
    return f"conflict: {key} in [{names}]"


def conflicting_records(key: records.RunKey) -> list[records.Record]:
    """Two evaluated records with this key that differ, as r2's do in Report
    15: missed, and caught against coverage from another commit."""
    return [
        dataclasses.replace(R2_MISSED, key=key),
        dataclasses.replace(R2_CAUGHT_AGAINST_OTHER_COVERAGE, key=key),
    ]


# The examples


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(REPORT_1_MISS_RATE, id="the miss rate"),
        pytest.param(
            "one-sided 95% Clopper-Pearson upper bound of 86.5%", id="the bound"
        ),
        pytest.param(REPORT_1_RED_RUNS, id="the red runs"),
    ],
)
def test_report_1_shows(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([REPORT_1], working_directory, capsys), words)


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(REPORT_1_MISS_RATE, id="the miss rate"),
        pytest.param(REPORT_1_RED_RUNS, id="the red runs"),
    ],
)
def test_report_1_split_over_two_record_files_shows_the_same_figures(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # r1 to r3 in the first file and r4 to r6 in the second: a report that
    # read only the first file would show 1 missed PR out of 2 and 2 red runs.
    record_files = [REPORT_1[:3], REPORT_1[3:]]

    assert shows(report_of(record_files, working_directory, capsys), words)


@pytest.mark.parametrize(
    "words",
    [
        pytest.param("0 missed PRs out of 30 PRs with a red run", id="the miss rate"),
        # 9.503%: rounding the bound up would give 9.6%.
        pytest.param(
            "one-sided 95% Clopper-Pearson upper bound of 9.5%", id="the bound"
        ),
    ],
)
def test_report_2_shows(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([REPORT_2], working_directory, capsys), words)


@pytest.mark.parametrize(
    "words",
    [
        pytest.param("0 missed PRs out of 0 PRs with a red run", id="the miss rate"),
        pytest.param("with no bound", id="no bound"),
    ],
)
def test_report_3_shows(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([REPORT_3], working_directory, capsys), words)


def test_report_4_shows_savings_of_37_5_percent(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1 - (3.0 s + 12.0 s) / (12.0 s + 12.0 s).
    assert shows(report_of([REPORT_4], working_directory, capsys), REPORT_4_SAVINGS)


def test_report_14_counts_r1_once_in_two_record_files(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Counting r1 twice would give 1 - 18.0 s / 36.0 s, 50%.
    record_files: list[list[records.Record]] = [REPORT_4, [R1_SELECTED_3_S]]

    assert shows(report_of(record_files, working_directory, capsys), REPORT_4_SAVINGS)


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(NO_REJECTED_RUN, id="no rejected run"),
        pytest.param(REPORT_13_AND_15_MISS_RATE, id="the miss rate"),
    ],
)
def test_report_13_shows(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([REPORT_13], working_directory, capsys), words)


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(REPORT_13_AND_15_MISS_RATE, id="the miss rate"),
        # Counting r2 would give 2 red runs.
        pytest.param("1 red run", id="the red runs"),
        # 1 - 3.0 s / 12.0 s. With the missed r2, 87.5%; with the caught r2,
        # 66.7%; with both, 77.8%.
        pytest.param("savings of 75%", id="the savings"),
        pytest.param(
            conflict(R2_MISSED, ["records-1.jsonl", "records-2.jsonl"]),
            id="r2's key as a conflict, with both record files",
        ),
    ],
)
def test_report_15_shows(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of(REPORT_15, working_directory, capsys), words)


def test_report_5_shows_a_floor_rate_of_25_percent(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1 PR out of 4, not 3 runs out of 6.
    assert shows(report_of([REPORT_5], working_directory, capsys), REPORT_5_FLOOR_RATE)


def test_report_6_shows_a_no_column_rate_of_25_percent(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # PR 2's paths with no column came with a floor match: counted, they would
    # give 2 PRs out of 4.
    assert shows(
        report_of([REPORT_6], working_directory, capsys), REPORT_6_NO_COLUMN_RATE
    )


def test_report_7_shows_12_5_percent_of_tests_treated_as_unmeasured(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1 out of 8 tests. Divided by the tests with a row, 1 out of 7, 14.3%.
    assert shows(
        report_of([REPORT_7], working_directory, capsys), REPORT_7_UNMEASURED_SHARE
    )


def test_report_8_shows_12_5_percent_of_the_tests_with_a_row_not_in_their_run(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1 out of 8 tests with a row. Divided by the runs' tests, 1 out of 7,
    # 14.3%.
    assert shows(
        report_of([REPORT_8], working_directory, capsys), REPORT_8_NOT_IN_RUN_SHARE
    )


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(K1_LEFT_OUT_ENTRY, id="test_render, as its record writes it"),
        pytest.param(WHY_IT_WAS_LEFT_OUT, id="why it was left out"),
        pytest.param(
            paths_with_no_column('["templates/invoice.html"]'),
            id="its run's paths with no column",
        ),
        pytest.param(import_only_paths("[]"), id="its run's import-only paths, none"),
        pytest.param(key_as_its_line_writes_it(K1_RUN), id="its run's key"),
        pytest.param("PR 7", id="its run's pull request"),
    ],
)
def test_report_9_lists_test_render_with_why_it_was_left_out(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([[K1_RUN]], working_directory, capsys), words)


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(K1_LEFT_OUT_ENTRY, id="test_render, as its record writes it"),
        pytest.param(WHY_IT_WAS_LEFT_OUT, id="why it was left out"),
        pytest.param(
            paths_with_no_column("[]"), id="its run's paths with no column, none"
        ),
        pytest.param(import_only_paths("[]"), id="its run's import-only paths, none"),
        pytest.param(key_as_its_line_writes_it(REPORT_10_RUN), id="its run's key"),
        pytest.param("PR 8", id="its run's pull request"),
    ],
)
def test_report_10_lists_a_caught_runs_failed_test_left_out_the_same_way(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([[REPORT_10_RUN]], working_directory, capsys), words)


def test_report_11_says_the_failures_of_2_red_runs_were_not_confirmed(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(
        report_of([REPORT_11], working_directory, capsys), REPORT_11_NOT_CONFIRMED
    )


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(REPORT_12_DISCARDED, id="the failures discarded"),
        pytest.param(ORDER_DEPENDENT_FAILURES, id="what can hide in that count"),
    ],
)
def test_report_12_says_3_failures_were_discarded_as_not_reproduced(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([REPORT_12], working_directory, capsys), words)


def test_report_16_writes_a_newline_and_an_escape_character_escaped(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The JSON list of the run's paths with no column: the newline as a
    # backslash and n, and the escape character as a backslash, u and 001b.
    written = '["templates/new' + BACKSLASH + "nline" + u_escape("001b") + '.html"]'

    assert shows(
        report_of([[REPORT_16_RUN]], working_directory, capsys),
        paths_with_no_column(written),
    )


# Report 17 is the first of the problems under "A record file that the report
# cannot use".


# Each key once


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(
            [[*REPORT_1, R3_MISSED]],
            REPORT_1_RED_RUNS,
            id="a red run's line twice in one file",
        ),
        pytest.param(
            [REPORT_1, [R3_MISSED]],
            REPORT_1_RED_RUNS,
            id="a red run's record in two files",
        ),
        pytest.param(
            [[R1_SELECTED_3_S, R1_SELECTED_3_S, R2_FLOOR_SELECTED_ALL]],
            REPORT_4_SAVINGS,
            id="a run's line twice in one file, in the savings",
        ),
    ],
)
def test_each_key_counts_once(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


# r7, a caught run of PR 2 whose key shares one half with r3's.
R7_WITH_R3S_HEAD = dataclasses.replace(
    evaluated(7, 2, "caught"),
    key=records.RunKey(head=commit_id(3), junit_sha256=junit_sha256(7)),
)
R7_WITH_R3S_JUNIT = dataclasses.replace(
    evaluated(7, 2, "caught"),
    key=records.RunKey(head=commit_id(7), junit_sha256=junit_sha256(3)),
)


@pytest.mark.parametrize(
    "r7",
    [
        pytest.param(R7_WITH_R3S_HEAD, id="r3's head, another JUnit file"),
        pytest.param(R7_WITH_R3S_JUNIT, id="r3's JUnit file, another head"),
    ],
)
def test_a_key_is_its_head_and_its_junit_sha256_together(
    r7: records.EvaluatedRecord,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Two keys that share one half are two runs, both red.
    record_files: list[list[records.Record]] = [[*REPORT_1, r7]]

    assert shows(report_of(record_files, working_directory, capsys), "5 red runs")


# Evaluated runs only


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        # A rejected run counted as red would give 5 PRs with a red run.
        pytest.param(
            [[*REPORT_1, REJECTED_OF_PR_3, REJECTED_OF_PR_5]],
            REPORT_1_MISS_RATE,
            id="the miss rate",
        ),
        pytest.param(
            [[*REPORT_1, REJECTED_OF_PR_3, REJECTED_OF_PR_5]],
            REPORT_1_RED_RUNS,
            id="the red runs",
        ),
        pytest.param(
            [[*REPORT_4, REJECTED_OF_PR_3]], REPORT_4_SAVINGS, id="the savings"
        ),
    ],
)
def test_rejected_runs_count_in_no_figure(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


# The miss rate and the savings


def test_the_miss_rate_counts_pull_requests_not_runs(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Report 1 has a single missed run, so it cannot tell missed PRs from
    # missed runs: here PR 1 has two.
    recorded: list[records.Record] = [
        evaluated(1, 1, "missed"),
        evaluated(2, 1, "missed"),
        evaluated(3, 2, "caught"),
    ]

    assert shows(
        report_of([recorded], working_directory, capsys),
        "1 missed PR out of 2 PRs with a red run",
    )


@pytest.mark.parametrize(
    "words",
    [
        # Report 13's and Report 15's words.
        pytest.param(
            "0 missed PRs out of 1 PR with a red run", id="1 PR with a red run"
        ),
        pytest.param("1 red run", id="1 red run"),
    ],
)
def test_one_pr_and_one_red_run_are_written_in_the_singular(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([ONE_CAUGHT_RUN], working_directory, capsys), words)


def test_savings_sum_every_evaluated_run_green_and_red(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 1 - 15.0 s / 36.0 s. The green run alone would give 75%, and the red
    # runs alone 50%.
    recorded: list[records.Record] = [
        evaluated(1, 1, "green", selected_ms=3000),
        evaluated(2, 2, "caught", selected_ms=12000),
        evaluated(3, 3, "missed"),
    ]

    assert shows(report_of([recorded], working_directory, capsys), "savings of 58.3%")


# Zero denominators

# With no pull request with a red run, the miss rate is 0 out of 0 with no
# bound (Report 3). With no evaluated run, or a total full-suite time of zero,
# there is no savings figure.
NO_EVALUATED_RUN_ONLY_REJECTED: list[list[records.Record]] = [
    [REJECTED_OF_PR_3, REJECTED_OF_PR_5]
]
NO_EVALUATED_RUN_AN_EMPTY_FILE: list[list[records.Record]] = [[]]
NO_FULL_SUITE_TIME: list[list[records.Record]] = [
    [
        evaluated(1, 1, "green", full_ms=0),
        evaluated(2, 2, "green", full_ms=0),
    ]
]


@pytest.mark.parametrize(
    "record_files",
    [
        pytest.param(NO_EVALUATED_RUN_ONLY_REJECTED, id="only rejected runs"),
        pytest.param(NO_EVALUATED_RUN_AN_EMPTY_FILE, id="an empty record file"),
        pytest.param(NO_FULL_SUITE_TIME, id="a total full-suite time of zero"),
    ],
)
def test_with_no_savings_figure_the_report_says_so(
    record_files: list[list[records.Record]],
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), NO_SAVINGS_FIGURE)


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param([REPORT_3], A_BOUND, id="no PR with a red run, no bound"),
        pytest.param(
            NO_EVALUATED_RUN_ONLY_REJECTED,
            A_SAVINGS_FIGURE,
            id="only rejected runs, no savings",
        ),
        pytest.param(
            NO_EVALUATED_RUN_AN_EMPTY_FILE,
            A_SAVINGS_FIGURE,
            id="an empty record file, no savings",
        ),
        pytest.param(
            NO_FULL_SUITE_TIME,
            A_SAVINGS_FIGURE,
            id="a total full-suite time of zero, no savings",
        ),
    ],
)
def test_a_zero_denominator_gives_no_percentage(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Each case has its twin among the words that must be there, in
    # test_report_3_shows and test_with_no_savings_figure_the_report_says_so.
    assert words not in report_of(record_files, working_directory, capsys)


# The report's sentences


def test_the_savings_are_said_to_be_an_upper_bound(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(
        report_of([REPORT_4], working_directory, capsys), SAVINGS_ARE_AN_UPPER_BOUND
    )


def test_the_figures_are_said_to_belong_to_the_all_affected_selector(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(
        report_of([REPORT_1], working_directory, capsys),
        FIGURES_BELONG_TO_THE_ALL_AFFECTED_SELECTOR,
    )


# Percentages, as Rule 10 writes them


def one_run(selected_ms: int, full_ms: int) -> list[list[records.Record]]:
    """One record file with one green run of PR 1, with these durations."""
    return [[evaluated(1, 1, "green", selected_ms=selected_ms, full_ms=full_ms)]]


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(one_run(9000, 12000), "savings of 25%", id="no trailing .0"),
        # 6.25%: f"{6.25:.1f}" takes the tie to the even digit, 6.2.
        pytest.param(
            one_run(15000, 16000), "savings of 6.3%", id="a tie rounds half up"
        ),
        pytest.param(
            one_run(4000, 12000), "savings of 66.7%", id="rounded, not cut, to 0.1"
        ),
        # 0.25%: through a float, 1 - 39900 / 40000 is just under 0.0025, which
        # would give 0.2%.
        pytest.param(one_run(39900, 40000), "savings of 0.3%", id="from the integers"),
        # 28.75%: through a float, both (80000 - 57000) / 80000 * 100 and
        # (1 - 57000 / 80000) * 100 are 28.749999999999996, which would give
        # 28.7%.
        pytest.param(
            one_run(57000, 80000),
            "savings of 28.8%",
            id="from the integers, whichever float route",
        ),
        # The bound for 0 out of 1, 0.95.
        pytest.param(
            [ONE_CAUGHT_RUN],
            "one-sided 95% Clopper-Pearson upper bound of 95%",
            id="a bound with no trailing .0",
        ),
    ],
)
def test_percentages_are_written_as_rule_10_says(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


# Rejected runs

# REJECTED_OF_PR_3 is r8, rejected because its coverage file was missing. r10
# is another run rejected for the same reason and input, and r8 is rejected
# again, for its JUnit file, once its coverage file is there.
R10_REJECTED_FOR_ITS_COVERAGE = rejected(10, 6, "unusable-input", "coverage")
R8_REJECTED_FOR_ITS_JUNIT = rejected(8, 3, "unsafe-xml", "junit")
ONE_RUN_REJECTED_FOR_ITS_COVERAGE = "1 run rejected for unusable-input with coverage"
TWO_RUNS_REJECTED_FOR_THEIR_COVERAGE = (
    "2 runs rejected for unusable-input with coverage"
)

# A rejected record with the key of r2's conflict (Report 15).
R2_REJECTED_FOR_ITS_COVERAGE = rejected(2, 2, "unusable-input", "coverage")


@pytest.mark.parametrize(
    "record_files",
    [
        pytest.param(
            [list(reversed(REPORT_13))], id="Report 13's lines in the other order"
        ),
        pytest.param(
            [[R1_CAUGHT], [R1_REJECTED_FOR_ITS_COVERAGE]],
            id="evaluated in one record file and rejected in another",
        ),
        pytest.param(
            [
                [R2_REJECTED_FOR_ITS_COVERAGE, R2_MISSED],
                [R2_CAUGHT_AGAINST_OTHER_COVERAGE],
            ],
            id="the key of a conflict",
        ),
    ],
)
def test_a_key_that_an_evaluated_record_has_is_never_counted_as_rejected(
    record_files: list[list[records.Record]],
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), NO_REJECTED_RUN)


# Rejected runs whose key shares one half with r3's, of PR 2: r3's head with no
# JUnit file's SHA-256, as a run whose JUnit file was missing and that was then
# evaluated with it, and another head, r7's, with r3's JUnit file.
R3S_HEAD_REJECTED_WITH_NO_JUNIT = dataclasses.replace(
    rejected(3, 2, "unusable-input", "junit"),
    key=records.RunKey(head=commit_id(3), junit_sha256=None),
)
R7_REJECTED_WITH_R3S_JUNIT = dataclasses.replace(
    rejected(7, 2, "unusable-input", "junit"),
    key=records.RunKey(head=commit_id(7), junit_sha256=junit_sha256(3)),
)


@pytest.mark.parametrize(
    "rejected_run",
    [
        pytest.param(
            R3S_HEAD_REJECTED_WITH_NO_JUNIT, id="r3's head, with no JUnit file"
        ),
        pytest.param(R7_REJECTED_WITH_R3S_JUNIT, id="r3's JUnit file, another head"),
    ],
)
def test_a_rejected_key_that_shares_one_half_with_an_evaluated_key_is_counted(
    rejected_run: records.RejectedRecord,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A key is its head and its junit_sha256 together, as for the figures in
    # test_a_key_is_its_head_and_its_junit_sha256_together: no evaluated
    # record has this one.
    record_files: list[list[records.Record]] = [[*REPORT_1, rejected_run]]

    assert shows(
        report_of(record_files, working_directory, capsys),
        "1 run rejected for unusable-input with junit",
    )


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(
            [[REJECTED_OF_PR_3, REJECTED_OF_PR_3]],
            ONE_RUN_REJECTED_FOR_ITS_COVERAGE,
            id="its line twice in one record file",
        ),
        pytest.param(
            [[REJECTED_OF_PR_3], [REJECTED_OF_PR_3]],
            ONE_RUN_REJECTED_FOR_ITS_COVERAGE,
            id="its record in two record files",
        ),
        # pr is not part of the key.
        pytest.param(
            [[REJECTED_OF_PR_3, dataclasses.replace(REJECTED_OF_PR_3, pr=4)]],
            ONE_RUN_REJECTED_FOR_ITS_COVERAGE,
            id="its key with another pr",
        ),
        pytest.param(
            [[REJECTED_OF_PR_3, R10_REJECTED_FOR_ITS_COVERAGE]],
            TWO_RUNS_REJECTED_FOR_THEIR_COVERAGE,
            id="two keys",
        ),
    ],
)
def test_rejected_runs_count_each_key_once_under_its_reason_and_input(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


@pytest.mark.parametrize(
    "words",
    [
        # Counted only under its first pair in sort order, unsafe-xml and
        # junit, r8 would leave 1 run here.
        pytest.param(TWO_RUNS_REJECTED_FOR_THEIR_COVERAGE, id="its first reason"),
        # Counted only under the pair of its first record, r8 would leave none
        # here.
        pytest.param(
            "1 run rejected for unsafe-xml with junit", id="its second reason"
        ),
    ],
)
def test_a_key_rejected_for_two_reasons_counts_under_each(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Question 9: the counts add up to 3, for 2 keys rejected.
    recorded: list[records.Record] = [
        REJECTED_OF_PR_3,
        R8_REJECTED_FOR_ITS_JUNIT,
        R10_REJECTED_FOR_ITS_COVERAGE,
    ]

    assert shows(report_of([recorded], working_directory, capsys), words)


# Conflicts

# A key whose head its record has to escape, with a newline and an escape
# character, as Report 16's path has.
KEY_WITH_A_HEAD_TO_ESCAPE = records.RunKey(
    head="pr-7\n\x1b[31m", junit_sha256=junit_sha256(2)
)
CONFLICT_WITH_A_HEAD_TO_ESCAPE = conflicting_records(KEY_WITH_A_HEAD_TO_ESCAPE)


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(
            [[R2_MISSED, R2_CAUGHT_AGAINST_OTHER_COVERAGE]],
            conflict(R2_MISSED, ["records-1.jsonl"]),
            id="both in one record file, named once",
        ),
        pytest.param(
            [[R2_MISSED], [R2_CAUGHT_AGAINST_OTHER_COVERAGE], [R2_MISSED]],
            conflict(
                R2_MISSED, ["records-1.jsonl", "records-2.jsonl", "records-3.jsonl"]
            ),
            id="in three record files, two with the same record",
        ),
        pytest.param(
            [
                [R2_MISSED],
                [R2_CAUGHT_AGAINST_OTHER_COVERAGE],
                [R2_REJECTED_FOR_ITS_COVERAGE],
            ],
            conflict(
                R2_MISSED, ["records-1.jsonl", "records-2.jsonl", "records-3.jsonl"]
            ),
            id="and in a record file with only a rejected record of its key",
        ),
        # The miss rate counts pull requests, so a key recorded for two cannot
        # be counted.
        pytest.param(
            [[R2_MISSED, dataclasses.replace(R2_MISSED, pr=12)]],
            conflict(R2_MISSED, ["records-1.jsonl"]),
            id="two records that differ only in their pr",
        ),
        # Task 18's tests look at a key only in the list of failed tests left out.
        pytest.param(
            [CONFLICT_WITH_A_HEAD_TO_ESCAPE],
            conflict(CONFLICT_WITH_A_HEAD_TO_ESCAPE[0], ["records-1.jsonl"]),
            id="a head that its record escapes, written as the record writes it",
        ),
    ],
)
def test_two_evaluated_records_with_one_key_that_differ_are_a_conflict(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


# Lists with no entry


@pytest.mark.parametrize(
    "words",
    [
        pytest.param(NO_CONFLICT, id="no conflict"),
        pytest.param(NO_REJECTED_RUN, id="no rejected run"),
    ],
)
def test_an_empty_list_says_so(
    words: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert shows(report_of([REPORT_1], working_directory, capsys), words)


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(REPORT_15, NO_CONFLICT, id="a conflict"),
        pytest.param([[REJECTED_OF_PR_5]], NO_REJECTED_RUN, id="a rejected run"),
    ],
)
def test_a_list_with_an_entry_does_not_say_it_has_none(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Each case has its twin in test_an_empty_list_says_so.
    assert words not in report_of(record_files, working_directory, capsys)


# The order of the lists

# Keys that share their head or their JUnit file's SHA-256 with another one.
R1_HEAD_WITH_NO_SHA256 = records.RunKey(head=commit_id(1), junit_sha256=None)
R1_HEAD_WITH_R3_SHA256 = records.RunKey(head=commit_id(1), junit_sha256=junit_sha256(3))
R1_HEAD_WITH_R5_SHA256 = records.RunKey(head=commit_id(1), junit_sha256=junit_sha256(5))
R2_HEAD_WITH_R3_SHA256 = records.RunKey(head=commit_id(2), junit_sha256=junit_sha256(3))


@pytest.mark.parametrize(
    ("first", "second"),
    [
        # Sorted by junit_sha256 first, the second would come first.
        pytest.param(
            R1_HEAD_WITH_R5_SHA256,
            R2_HEAD_WITH_R3_SHA256,
            id="by head, whatever the junit_sha256",
        ),
        pytest.param(
            R1_HEAD_WITH_R3_SHA256, R1_HEAD_WITH_R5_SHA256, id="then by junit_sha256"
        ),
        # Sorted as the text null, it would come after the hex digits.
        pytest.param(R1_HEAD_WITH_NO_SHA256, R1_HEAD_WITH_R3_SHA256, id="null first"),
    ],
)
def test_conflicts_are_sorted_by_key(
    first: records.RunKey,
    second: records.RunKey,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The record file holds the second conflict's records first.
    first_conflict = conflicting_records(first)
    second_conflict = conflicting_records(second)
    text = report_of([[*second_conflict, *first_conflict]], working_directory, capsys)

    assert comes_before(
        text,
        conflict(first_conflict[0], ["records-1.jsonl"]),
        conflict(second_conflict[0], ["records-1.jsonl"]),
    )


def test_a_conflicts_record_files_are_sorted_by_path(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # By code point, capital letters come before small ones: B, C and then a,
    # an order that neither the one given, nor its reverse, nor one that
    # ignores case gives.
    write_record_file(working_directory / "C.jsonl", [R2_MISSED])
    write_record_file(working_directory / "a.jsonl", [R2_CAUGHT_AGAINST_OTHER_COVERAGE])
    write_record_file(working_directory / "B.jsonl", [R2_MISSED])

    report.run(["C.jsonl", "a.jsonl", "B.jsonl"])

    assert shows(
        capsys.readouterr().out,
        conflict(R2_MISSED, ["B.jsonl", "C.jsonl", "a.jsonl"]),
    )


@pytest.mark.parametrize(
    ("recorded", "first", "second"),
    [
        # Given in the order that sorting by input, or by count from more to
        # fewer, would give.
        pytest.param(
            [
                rejected(8, 3, "missing-history", "checkout"),
                rejected(9, 4, "missing-history", "checkout"),
                rejected(10, 5, "coverage-not-ancestor", "coverage"),
            ],
            "1 run rejected for coverage-not-ancestor with coverage",
            "2 runs rejected for missing-history with checkout",
            id="by reason",
        ),
        pytest.param(
            [
                rejected(8, 3, "unsafe-xml", "rerun"),
                rejected(9, 4, "unsafe-xml", "junit"),
            ],
            "1 run rejected for unsafe-xml with junit",
            "1 run rejected for unsafe-xml with rerun",
            id="then by input",
        ),
    ],
)
def test_rejected_counts_are_sorted_by_reason_then_input(
    recorded: list[records.Record],
    first: str,
    second: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    text = report_of([recorded], working_directory, capsys)

    assert comes_before(text, first, second)


# The floor and no-column rates


def test_the_no_column_rate_counts_pull_requests_not_runs(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Report 6 has a single run for each PR. Here all 3 runs of PR 1 changed
    # only templates/invoice.html, and the single runs of PRs 2, 3 and 4 only
    # src/shop/tax.py: counting runs would give 3 out of 6.
    recorded: list[records.Record] = [
        evaluated(1, 1, "green"),
        evaluated(2, 1, "green"),
        evaluated(3, 1, "green"),
        tax_only_run(4, 2),
        tax_only_run(5, 3),
        tax_only_run(6, 4),
    ]

    assert shows(
        report_of([recorded], working_directory, capsys), REPORT_6_NO_COLUMN_RATE
    )


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        # Only the first of PR 1's three runs matched the floor: asked of every
        # run, the rate would give 0 PRs, and counting runs 1 out of 6.
        pytest.param(
            [
                [
                    floor_matched_run(1, 1),
                    evaluated(2, 1, "green"),
                    evaluated(3, 1, "green"),
                    evaluated(4, 2, "green"),
                    evaluated(5, 3, "green"),
                    evaluated(6, 4, "green"),
                ]
            ],
            REPORT_5_FLOOR_RATE,
            id="the floor rate",
        ),
        # Only the first of PR 1's three runs had a path with no column and no
        # floor match: the second had no path with no column, and the third a
        # floor match.
        pytest.param(
            [
                [
                    evaluated(1, 1, "green"),
                    tax_only_run(2, 1),
                    floor_matched_run(3, 1),
                    tax_only_run(4, 2),
                    tax_only_run(5, 3),
                    tax_only_run(6, 4),
                ]
            ],
            REPORT_6_NO_COLUMN_RATE,
            id="the no-column rate",
        ),
    ],
)
def test_a_pr_counts_in_a_rate_when_one_of_its_runs_does(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


def test_the_no_column_rate_asks_for_both_conditions_in_one_run(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # PR 1's first run had a path with no column but a floor match, and its
    # second run neither: taken over the PR's runs together, PR 1 would count
    # too, 2 PRs out of 2.
    recorded: list[records.Record] = [
        floor_matched_run(1, 1),
        tax_only_run(2, 1),
        evaluated(3, 2, "green"),
    ]

    assert shows(
        report_of([recorded], working_directory, capsys),
        "no-column rate of 50%: 1 PR out of 2",
    )


def test_an_import_only_path_is_not_a_path_with_no_column(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Report 6 and the run of PR 5, which changed only src/shop/constants.py,
    # an import-only path, as in Selection 15. Taken as a path with no column,
    # it would give 2 PRs out of 5.
    import_only_run = dataclasses.replace(
        evaluated(5, 5, "green"),
        no_column=(),
        import_only=("src/shop/constants.py",),
    )

    assert shows(
        report_of([[*REPORT_6, import_only_run]], working_directory, capsys),
        "no-column rate of 20%: 1 PR out of 5",
    )


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(
            [
                [
                    floor_matched_run(1, 1),
                    floor_matched_run(2, 2),
                    evaluated(3, 3, "green"),
                    evaluated(4, 4, "green"),
                ]
            ],
            "floor rate of 50%: 2 PRs out of 4",
            id="the floor rate",
        ),
        pytest.param(
            [
                [
                    evaluated(1, 1, "green"),
                    evaluated(2, 2, "green"),
                    tax_only_run(3, 3),
                    tax_only_run(4, 4),
                ]
            ],
            "no-column rate of 50%: 2 PRs out of 4",
            id="the no-column rate",
        ),
    ],
)
def test_a_rates_prs_are_in_the_plural_but_for_1(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Report 5 and 6 show 1 PR, in the singular.
    assert shows(report_of(record_files, working_directory, capsys), words)


# The unmeasured and not-in-run shares


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        # 1 out of 10 tests: the mean of the two runs' shares, 25% and 0%,
        # would give 12.5%, and counting runs 1 out of 2.
        pytest.param(
            [
                [
                    with_tests(
                        evaluated(1, 1, "green"),
                        tests=4,
                        unmeasured=1,
                        tests_with_row=3,
                        not_in_run=0,
                    ),
                    with_tests(
                        evaluated(2, 2, "green"),
                        tests=6,
                        unmeasured=0,
                        tests_with_row=6,
                        not_in_run=0,
                    ),
                ]
            ],
            "10% of tests treated as unmeasured",
            id="the unmeasured share",
        ),
        # 1 out of 10 tests with a row: the mean of the two runs' shares, 0%
        # and 16.7%, would give 8.3%, and counting runs 1 out of 2.
        pytest.param(
            [
                [
                    with_tests(
                        evaluated(1, 1, "green"),
                        tests=4,
                        unmeasured=0,
                        tests_with_row=4,
                        not_in_run=0,
                    ),
                    with_tests(
                        evaluated(2, 2, "green"),
                        tests=5,
                        unmeasured=0,
                        tests_with_row=6,
                        not_in_run=1,
                    ),
                ]
            ],
            "10% of the tests with a row were not in their run",
            id="the not-in-run share",
        ),
    ],
)
def test_a_share_counts_tests_not_runs(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


# Reruns


def test_a_green_run_has_no_failure_for_a_rerun_to_confirm(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Report 11 and two green runs without a rerun file: counted, they would
    # give 4.
    recorded: list[records.Record] = [
        *REPORT_11,
        evaluated(6, 6, "green"),
        evaluated(7, 7, "green"),
    ]

    assert shows(
        report_of([recorded], working_directory, capsys), REPORT_11_NOT_CONFIRMED
    )


def test_a_failure_discarded_counts_in_each_run(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # test_render passed in the rerun files of two runs: counting each pair
    # once would give 1.
    recorded: list[records.Record] = [
        given_a_rerun(evaluated(1, 1, "green"), RENDER_PAIR),
        given_a_rerun(evaluated(2, 2, "green"), RENDER_PAIR),
    ]

    assert shows(
        report_of([recorded], working_directory, capsys),
        "2 failures were discarded as not reproduced",
    )


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(
            [ONE_CAUGHT_RUN],
            "the failures of 1 red run were not confirmed by a rerun",
            id="1 red run",
        ),
        pytest.param(
            [REPORT_3],
            "the failures of 0 red runs were not confirmed by a rerun",
            id="0 red runs",
        ),
        pytest.param(
            [[given_a_rerun(evaluated(1, 1, "green"), RENDER_PAIR)]],
            "1 failure was discarded as not reproduced",
            id="1 failure",
        ),
        pytest.param(
            [REPORT_1], "0 failures were discarded as not reproduced", id="0 failures"
        ),
    ],
)
def test_the_rerun_counts_are_in_the_singular_for_1_and_shown_with_0(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


@pytest.mark.parametrize(
    "record_files",
    [
        pytest.param([REPORT_11], id="Report 11"),
        pytest.param(
            [[*REPORT_11, REPORT_11[2]]], id="a confirmed red run's line twice"
        ),
        pytest.param([[*REPORT_11, REJECTED_OF_PR_5]], id="and a rejected run"),
    ],
)
def test_the_miss_rate_still_shows_its_red_runs_next_to_the_reruns(
    record_files: list[list[records.Record]],
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The sentence on reruns holds "<n> red run[s]", which task 16's tests
    # look for in the miss rate: in their reports no red run has a rerun file,
    # so the sentence holds their number too. Here it holds 2, so only the
    # miss rate can show 5.
    assert shows(report_of(record_files, working_directory, capsys), "5 red runs")


# Each key once, evaluated runs only and no conflict, in the new figures. In the
# two rates, a key whose record is there twice is still one PR, so no rate can
# count it twice: the rates count PRs.


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        # Counted twice, the run with an unmeasured test would give 2 out of 12.
        pytest.param(
            [[*REPORT_7, REPORT_7[0]]],
            REPORT_7_UNMEASURED_SHARE,
            id="unmeasured, a line twice",
        ),
        pytest.param(
            [REPORT_7, [REPORT_7[0]]],
            REPORT_7_UNMEASURED_SHARE,
            id="unmeasured, in two files",
        ),
        # Counted twice, the run without test_vat would give 2 out of 12.
        pytest.param(
            [[*REPORT_8, REPORT_8[1]]],
            REPORT_8_NOT_IN_RUN_SHARE,
            id="not in their run, a line twice",
        ),
        pytest.param(
            [REPORT_8, [REPORT_8[1]]],
            REPORT_8_NOT_IN_RUN_SHARE,
            id="not in their run, in two files",
        ),
        # Counted twice, r1 would give 3.
        pytest.param(
            [[*REPORT_11, REPORT_11[0]]],
            REPORT_11_NOT_CONFIRMED,
            id="not confirmed, a line twice",
        ),
        pytest.param(
            [REPORT_11, [REPORT_11[0]]],
            REPORT_11_NOT_CONFIRMED,
            id="not confirmed, in two files",
        ),
        # Counted twice, r2 would give 5.
        pytest.param(
            [[*REPORT_12, REPORT_12[1]]],
            REPORT_12_DISCARDED,
            id="discarded, a line twice",
        ),
        pytest.param(
            [REPORT_12, [REPORT_12[1]]],
            REPORT_12_DISCARDED,
            id="discarded, in two files",
        ),
    ],
)
def test_each_key_counts_once_in_the_shares_and_the_rerun_counts(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        # PR 5 has only a rejected run: taken as an evaluated PR, it would give
        # 1 PR out of 5.
        pytest.param(
            [[*REPORT_5, REJECTED_OF_PR_5]], REPORT_5_FLOOR_RATE, id="the floor rate"
        ),
        pytest.param(
            [[*REPORT_6, REJECTED_OF_PR_5]],
            REPORT_6_NO_COLUMN_RATE,
            id="the no-column rate",
        ),
        # A rejected record holds no tests and no rerun file, so a report that
        # counted one could only fail on it.
        pytest.param(
            [[*REPORT_7, REJECTED_OF_PR_5]],
            REPORT_7_UNMEASURED_SHARE,
            id="the unmeasured share",
        ),
        pytest.param(
            [[*REPORT_8, REJECTED_OF_PR_5]],
            REPORT_8_NOT_IN_RUN_SHARE,
            id="the not-in-run share",
        ),
        # Taken as red, a rejected run would give 3.
        pytest.param(
            [[*REPORT_11, REJECTED_OF_PR_5]],
            REPORT_11_NOT_CONFIRMED,
            id="the red runs not confirmed",
        ),
        pytest.param(
            [[*REPORT_12, REJECTED_OF_PR_5]],
            REPORT_12_DISCARDED,
            id="the failures discarded",
        ),
    ],
)
def test_rejected_runs_count_in_no_new_figure(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


def conflict_of(record: records.EvaluatedRecord) -> list[records.Record]:
    """Two evaluated records with the key of record that differ: record, and
    record evaluated against coverage from another commit, as r2 in Report
    15."""
    return [record, dataclasses.replace(record, coverage_commit=OTHER_M)]


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        # Counted, the conflict of PR 5 would give 2 PRs out of 5.
        pytest.param(
            [[*REPORT_5, *conflict_of(floor_matched_run(20, 5))]],
            REPORT_5_FLOOR_RATE,
            id="the floor rate",
        ),
        pytest.param(
            [[*REPORT_6, *conflict_of(evaluated(20, 5, "green"))]],
            REPORT_6_NO_COLUMN_RATE,
            id="the no-column rate",
        ),
        # Counted, either of its records would give 5 out of 12.
        pytest.param(
            [
                [
                    *REPORT_7,
                    *conflict_of(
                        with_tests(
                            evaluated(20, 5, "green"),
                            tests=4,
                            unmeasured=4,
                            tests_with_row=0,
                            not_in_run=0,
                        )
                    ),
                ]
            ],
            REPORT_7_UNMEASURED_SHARE,
            id="the unmeasured share",
        ),
        pytest.param(
            [
                [
                    *REPORT_8,
                    *conflict_of(
                        with_tests(
                            evaluated(20, 5, "green"),
                            tests=0,
                            unmeasured=0,
                            tests_with_row=4,
                            not_in_run=4,
                        )
                    ),
                ]
            ],
            REPORT_8_NOT_IN_RUN_SHARE,
            id="the not-in-run share",
        ),
        # Counted, either of its records would give 3.
        pytest.param(
            [[*REPORT_11, *conflict_of(evaluated(20, 5, "caught"))]],
            REPORT_11_NOT_CONFIRMED,
            id="the red runs not confirmed",
        ),
        # Counted, either of its records would give 4.
        pytest.param(
            [
                [
                    *REPORT_12,
                    *conflict_of(given_a_rerun(evaluated(20, 5, "green"), RENDER_PAIR)),
                ]
            ],
            REPORT_12_DISCARDED,
            id="the failures discarded",
        ),
    ],
)
def test_conflicts_count_in_no_new_figure(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


# The new figures with a zero denominator

# Record files with no evaluated run that the figures count.
NO_RUN_TO_COUNT = [
    pytest.param(NO_EVALUATED_RUN_ONLY_REJECTED, id="only rejected runs"),
    pytest.param(NO_EVALUATED_RUN_AN_EMPTY_FILE, id="an empty record file"),
    pytest.param(
        [[R2_MISSED], [R2_CAUGHT_AGAINST_OTHER_COVERAGE]], id="only a conflict"
    ),
]


@pytest.mark.parametrize("record_files", NO_RUN_TO_COUNT)
@pytest.mark.parametrize(
    "words",
    [
        pytest.param(FLOOR_RATE_0_OUT_OF_0, id="the floor rate"),
        pytest.param(NO_COLUMN_RATE_0_OUT_OF_0, id="the no-column rate"),
        pytest.param(UNMEASURED_0_OUT_OF_0, id="the unmeasured share"),
        pytest.param(NOT_IN_RUN_0_OUT_OF_0, id="the not-in-run share"),
    ],
)
def test_with_no_run_to_count_each_rate_and_share_is_0_out_of_0(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


@pytest.mark.parametrize("record_files", NO_RUN_TO_COUNT)
@pytest.mark.parametrize(
    "words",
    [
        pytest.param(A_FLOOR_RATE, id="the floor rate"),
        pytest.param(A_NO_COLUMN_RATE, id="the no-column rate"),
        pytest.param(AN_UNMEASURED_SHARE, id="the unmeasured share"),
        pytest.param(A_NOT_IN_RUN_SHARE, id="the not-in-run share"),
    ],
)
def test_with_no_run_to_count_no_rate_or_share_is_a_percentage(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Each case has its twin in
    # test_with_no_run_to_count_each_rate_and_share_is_0_out_of_0.
    assert words not in report_of(record_files, working_directory, capsys)


# Two green runs whose JUnit files held no test, as a file that is not a JUnit
# file gives (Rule 5's known limits): every test with a row is not in its run.
NO_TEST: list[list[records.Record]] = [
    [
        with_tests(
            evaluated(1, 1, "green"),
            tests=0,
            unmeasured=0,
            tests_with_row=4,
            not_in_run=4,
        ),
        with_tests(
            evaluated(2, 2, "green"),
            tests=0,
            unmeasured=0,
            tests_with_row=4,
            not_in_run=4,
        ),
    ]
]

# Two runs evaluated against coverage in which no test has a row: every test
# is unmeasured.
NO_TEST_WITH_A_ROW: list[list[records.Record]] = [
    [
        with_tests(
            evaluated(1, 1, "green"),
            tests=4,
            unmeasured=4,
            tests_with_row=0,
            not_in_run=0,
        ),
        with_tests(
            evaluated(2, 2, "green"),
            tests=4,
            unmeasured=4,
            tests_with_row=0,
            not_in_run=0,
        ),
    ]
]


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(NO_TEST, UNMEASURED_0_OUT_OF_0, id="no test in the runs"),
        pytest.param(
            NO_TEST_WITH_A_ROW, NOT_IN_RUN_0_OUT_OF_0, id="no test with a row"
        ),
    ],
)
def test_a_share_with_no_test_to_count_is_0_out_of_0(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(NO_TEST, AN_UNMEASURED_SHARE, id="no test in the runs"),
        pytest.param(NO_TEST_WITH_A_ROW, A_NOT_IN_RUN_SHARE, id="no test with a row"),
    ],
)
def test_a_share_with_no_test_to_count_is_not_a_percentage(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Each case has its twin in test_a_share_with_no_test_to_count_is_0_out_of_0.
    assert words not in report_of(record_files, working_directory, capsys)


# The new percentages, as Rule 10 writes them

# PRs 2 to 16, one run each, that changed only src/shop/tax.py. With PR 1, 1 PR
# out of 16 is 6.25%: Rule 10 rounds the tie half up, to 6.3%, while a float
# formatted with one decimal takes it to the even digit, 6.2%.
PRS_2_TO_16_TAX_ONLY: list[records.Record] = [
    tax_only_run(pr, pr) for pr in range(2, 17)
]


@pytest.mark.parametrize(
    ("record_files", "words"),
    [
        pytest.param(
            [[floor_matched_run(1, 1), *PRS_2_TO_16_TAX_ONLY]],
            "floor rate of 6.3%: 1 PR out of 16",
            id="the floor rate",
        ),
        pytest.param(
            [[evaluated(1, 1, "green"), *PRS_2_TO_16_TAX_ONLY]],
            "no-column rate of 6.3%: 1 PR out of 16",
            id="the no-column rate",
        ),
        pytest.param(
            [
                [
                    with_tests(
                        evaluated(1, 1, "green"),
                        tests=16,
                        unmeasured=1,
                        tests_with_row=15,
                        not_in_run=0,
                    )
                ]
            ],
            "6.3% of tests treated as unmeasured",
            id="the unmeasured share",
        ),
        pytest.param(
            [
                [
                    with_tests(
                        evaluated(1, 1, "green"),
                        tests=15,
                        unmeasured=0,
                        tests_with_row=16,
                        not_in_run=1,
                    )
                ]
            ],
            "6.3% of the tests with a row were not in their run",
            id="the not-in-run share",
        ),
    ],
)
def test_a_tie_in_a_new_percentage_rounds_half_up(
    record_files: list[list[records.Record]],
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of(record_files, working_directory, capsys), words)


# The failed tests left out


@pytest.mark.parametrize(
    "record_files",
    [
        pytest.param([REPORT_3], id="only green runs"),
        pytest.param([ONE_CAUGHT_RUN], id="a caught run that left none out"),
        pytest.param(NO_EVALUATED_RUN_AN_EMPTY_FILE, id="no run"),
    ],
)
def test_an_empty_list_of_failed_tests_left_out_says_so(
    record_files: list[list[records.Record]],
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(
        report_of(record_files, working_directory, capsys), NO_FAILED_TEST_LEFT_OUT
    )


def test_a_list_of_failed_tests_left_out_with_an_entry_does_not_say_it_has_none(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Its twins are in test_an_empty_list_of_failed_tests_left_out_says_so.
    text = report_of([[K1_RUN]], working_directory, capsys)

    assert NO_FAILED_TEST_LEFT_OUT not in text


def test_a_runs_import_only_paths_are_shown_next_to_its_failed_tests_left_out(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Report 9's run has none; this one has src/shop/constants.py, as in
    # Selection 15.
    run = dataclasses.replace(K1_RUN, import_only=("src/shop/constants.py",))

    assert shows(
        report_of([[run]], working_directory, capsys),
        import_only_paths('["src/shop/constants.py"]'),
    )


@pytest.mark.parametrize(
    "path",
    [
        pytest.param("docs/guide.md", id="a path with no column"),
        pytest.param("src/shop/constants.py", id="an import-only path"),
    ],
)
def test_a_run_that_left_out_no_failed_test_shows_none_of_its_paths(
    path: str, working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # K1's run shows its own paths. Next to it, a green run whose diff changed
    # docs/guide.md and src/shop/constants.py.
    green_run = dataclasses.replace(
        evaluated(2, 8, "green"),
        no_column=("docs/guide.md",),
        import_only=("src/shop/constants.py",),
    )
    text = report_of([[K1_RUN, green_run]], working_directory, capsys)

    assert path not in text


@pytest.mark.parametrize(
    ("record_files", "times"),
    [
        pytest.param([[K1_RUN, K1_RUN]], 1, id="its run's line twice"),
        pytest.param([[K1_RUN], [K1_RUN]], 1, id="its run in two record files"),
        pytest.param(
            [[R1_REJECTED_FOR_ITS_COVERAGE, K1_RUN]], 1, id="its run's key rejected"
        ),
        # A conflict counts in no figure, so its failed tests left out are not
        # listed either.
        pytest.param(
            [[K1_RUN, *conflict_of(evaluated(20, 5, "missed"))]],
            1,
            id="and a conflict that left it out",
        ),
        pytest.param(
            [[K1_RUN, evaluated(2, 8, "missed")]], 2, id="left out by two runs"
        ),
    ],
)
def test_a_failed_test_left_out_is_listed_once_for_each_run_that_counts(
    record_files: list[list[records.Record]],
    times: int,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    text = report_of(record_files, working_directory, capsys)

    assert text.count(K1_LEFT_OUT_ENTRY) == times


# The order of the failed tests left out

# Two failed tests left out: by pair, test_create's comes first.
LEFT_OUT_CREATE = selection.Test(
    pair=("tests.api.test_orders", "test_create"),
    node_id="tests/api/test_orders.py::test_create",
    row=frozenset({"src/shop/orders.py"}),
)
LEFT_OUT_VAT = selection.Test(
    pair=("tests.test_tax", "test_vat"),
    node_id="tests/test_tax.py::test_vat",
    row=frozenset({"src/shop/tax.py"}),
)

# Keys whose heads differ in a letter beyond ASCII. By code point, z (U+007A)
# comes before the n with a tilde (U+00F1); escaped, the n starts with a
# backslash, U+005C, which comes before z.
TARIFA_AZUL = records.RunKey(head="tarifa azul", junit_sha256=junit_sha256(1))
TARIFA_ANO = records.RunKey(head="tarifa a\xf1o", junit_sha256=junit_sha256(1))


@pytest.mark.parametrize(
    ("first", "second"),
    [
        # Sorted by junit_sha256 first, the second would come first.
        pytest.param(
            R1_HEAD_WITH_R5_SHA256,
            R2_HEAD_WITH_R3_SHA256,
            id="by head, whatever the junit_sha256",
        ),
        pytest.param(
            R1_HEAD_WITH_R3_SHA256, R1_HEAD_WITH_R5_SHA256, id="then by junit_sha256"
        ),
        # Sorted as the text null, it would come after the hex digits.
        pytest.param(R1_HEAD_WITH_NO_SHA256, R1_HEAD_WITH_R3_SHA256, id="null first"),
        pytest.param(TARIFA_AZUL, TARIFA_ANO, id="by code point, not as escaped"),
    ],
)
def test_the_failed_tests_left_out_are_sorted_by_their_runs_key(
    first: records.RunKey,
    second: records.RunKey,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The run with the first key left out test_vat, whose pair comes second,
    # and its line comes second: neither the order of the lines nor that of
    # the pairs is the order of the keys.
    first_run = missed_run_with(first, LEFT_OUT_VAT)
    second_run = missed_run_with(second, LEFT_OUT_CREATE)
    text = report_of([[second_run, first_run]], working_directory, capsys)

    assert comes_before(
        text, left_out_entry(LEFT_OUT_VAT), left_out_entry(LEFT_OUT_CREATE)
    )


def pieces_of(run: records.EvaluatedRecord) -> list[str]:
    """The words that show a run in the list of failed tests left out: its key,
    its pull request, its paths with no column and each failed test that it
    left out. For a run whose paths have nothing to escape."""
    no_column = json_list([json_string(path) for path in run.no_column])
    left_out = [left_out_entry(test) for test in run.failed_left_out]
    return [
        key_as_its_line_writes_it(run),
        f"PR {run.pr}",
        paths_with_no_column(no_column),
        *left_out,
    ]


def all_come_before(text: str, firsts: list[str], seconds: list[str]) -> bool:
    """Whether text shows all these words, and each of firsts, wherever it is,
    comes before each of seconds, wherever it is."""
    every_one_shown = all(shows(text, words) for words in [*firsts, *seconds])
    if not every_one_shown:
        return False
    last_of_firsts = max(text.rindex(words) for words in firsts)
    first_of_seconds = min(text.index(words) for words in seconds)
    return last_of_firsts < first_of_seconds


def test_each_run_in_the_list_shows_its_own_key_pr_paths_and_test(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The run with the smaller key is of PR 31 and left out test_vat, and its
    # line comes second: sorted by pull request, by the order of the lines or
    # by pair, the other run would come first. In the other tests with several
    # runs in the list, every run is of PR 7: this one also tells a report that
    # shows each run with its own key, pull request and paths from one that
    # shows the first run's for both.
    first_run = dataclasses.replace(
        missed_run_with(R1_HEAD_WITH_R3_SHA256, LEFT_OUT_VAT),
        pr=31,
        no_column=("docs/a.md",),
    )
    second_run = dataclasses.replace(
        missed_run_with(R2_HEAD_WITH_R3_SHA256, LEFT_OUT_CREATE),
        pr=13,
        no_column=("docs/b.md",),
    )
    text = report_of([[second_run, first_run]], working_directory, capsys)

    assert all_come_before(text, pieces_of(first_run), pieces_of(second_run))


# A test in a class and a test of its module, as in tests/test_records.py: by
# the whole classname, the module's comes first; by node id, by name, or by the
# classname joined to the name, as tests.test_x.TestB.test_c, the class's would.
LEFT_OUT_OF_THE_MODULE = selection.Test(
    pair=("tests.test_x", "test_z"),
    node_id="tests/test_x.py::test_z",
    row=frozenset({"src/shop/tax.py"}),
)
LEFT_OUT_IN_A_CLASS = selection.Test(
    pair=("tests.test_x.TestB", "test_c"),
    node_id="tests/test_x.py::TestB::test_c",
    row=frozenset({"src/shop/tax.py"}),
)

# Tests in directories whose names differ in a letter beyond ASCII, in code
# point order: escaped, the second would come first.
LEFT_OUT_IN_TARIFA_AZUL = selection.Test(
    pair=("tests.tarifa azul.test_x", "test_m"),
    node_id="tests/tarifa azul/test_x.py::test_m",
    row=frozenset({"src/shop/tax.py"}),
)
LEFT_OUT_IN_TARIFA_ANO = selection.Test(
    pair=("tests.tarifa a\xf1o.test_x", "test_m"),
    node_id="tests/tarifa a\xf1o/test_x.py::test_m",
    row=frozenset({"src/shop/tax.py"}),
)


@pytest.mark.parametrize(
    ("left_out", "first", "second"),
    [
        pytest.param(
            (LEFT_OUT_OF_THE_MODULE, LEFT_OUT_IN_A_CLASS),
            '["tests.test_x","test_z"]',
            '["tests.test_x.TestB","test_c"]',
            id="by the whole classname",
        ),
        pytest.param(
            (LEFT_OUT_IN_TARIFA_AZUL, LEFT_OUT_IN_TARIFA_ANO),
            '["tests.tarifa azul.test_x","test_m"]',
            '["tests.tarifa a' + u_escape("00f1") + 'o.test_x","test_m"]',
            id="by code point, not as escaped",
        ),
    ],
)
def test_a_runs_failed_tests_left_out_are_sorted_by_pair(
    left_out: tuple[selection.Test, ...],
    first: str,
    second: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Each test is shown by its pair. A record's line holds them by pair
    # already, so no record file can give them in another order: the report
    # keeps that order, and sorts them by nothing else.
    run = missed_run_with(K1_RUN.key, *left_out)
    text = report_of([[run]], working_directory, capsys)

    assert comes_before(text, first, second)


# Paths whose names differ in a letter beyond ASCII, in code point order, and
# the JSON list of them: escaped, the second would come first.
AZUL_THEN_ANO = ("src/shop/tarifa azul.py", "src/shop/tarifa a\xf1o.py")
AZUL_THEN_ANO_WRITTEN = (
    '["src/shop/tarifa azul.py","src/shop/tarifa a' + u_escape("00f1") + 'o.py"]'
)


@pytest.mark.parametrize(
    ("run", "words"),
    [
        pytest.param(
            missed_run_with(
                K1_RUN.key,
                dataclasses.replace(K1_TEST_RENDER, row=frozenset(AZUL_THEN_ANO)),
            ),
            '"row":' + AZUL_THEN_ANO_WRITTEN,
            id="a failed test's row",
        ),
        pytest.param(
            dataclasses.replace(K1_RUN, no_column=AZUL_THEN_ANO),
            paths_with_no_column(AZUL_THEN_ANO_WRITTEN),
            id="its run's paths with no column",
        ),
        pytest.param(
            dataclasses.replace(K1_RUN, import_only=AZUL_THEN_ANO),
            import_only_paths(AZUL_THEN_ANO_WRITTEN),
            id="its run's import-only paths",
        ),
    ],
)
def test_a_runs_paths_are_sorted_by_code_point(
    run: records.EvaluatedRecord,
    words: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A record's line holds each list of paths by path already, as it holds
    # the failed tests left out by pair.
    assert shows(report_of([[run]], working_directory, capsys), words)


# Escapes

# Characters that the report writes escaped: a newline, an escape character
# that starts a terminal colour code, and an n with a tilde. The first two are
# ASCII, so only the n can show a report that is not ASCII.
TO_ESCAPE = "\n\x1b[31m\xf1"
# How a JSON string writes them, as a record's line does: the newline as its
# short escape, the other two as a backslash, u and four hex digits.
TO_ESCAPE_WRITTEN = BACKSLASH + "n" + u_escape("001b") + "[31m" + u_escape("00f1")


def is_printable_ascii_with_line_ends(text: str) -> bool:
    """Whether text holds only printable ASCII, from space to ~, and the
    newlines that end its lines: no other control character, and nothing
    beyond ASCII."""
    return all(" " <= character <= "~" or character == "\n" for character in text)


# K1's run with the characters in one of the fields that the list of failed
# tests left out writes.
WITH_A_CLASSNAME_TO_ESCAPE = missed_run_with(
    K1_RUN.key,
    dataclasses.replace(
        K1_TEST_RENDER, pair=("tests.test_report" + TO_ESCAPE, "test_render")
    ),
)
WITH_A_NAME_TO_ESCAPE = missed_run_with(
    K1_RUN.key,
    dataclasses.replace(
        K1_TEST_RENDER, pair=("tests.test_report", "test_render" + TO_ESCAPE)
    ),
)
WITH_A_NODE_ID_TO_ESCAPE = missed_run_with(
    K1_RUN.key,
    dataclasses.replace(
        K1_TEST_RENDER, node_id="tests/test_report.py::test_render" + TO_ESCAPE
    ),
)
WITH_A_ROW_TO_ESCAPE = missed_run_with(
    K1_RUN.key,
    dataclasses.replace(
        K1_TEST_RENDER,
        row=frozenset({"src/shop/pricing.py", "src/shop/report.py" + TO_ESCAPE}),
    ),
)
WITH_NO_COLUMN_TO_ESCAPE = dataclasses.replace(
    K1_RUN, no_column=("templates/invoice.html" + TO_ESCAPE,)
)
WITH_IMPORT_ONLY_TO_ESCAPE = dataclasses.replace(
    K1_RUN, import_only=("src/shop/constants.py" + TO_ESCAPE,)
)
WITH_A_HEAD_TO_ESCAPE = dataclasses.replace(
    K1_RUN,
    key=records.RunKey(head="pr-7" + TO_ESCAPE, junit_sha256=junit_sha256(1)),
)


@pytest.mark.parametrize(
    ("run", "written"),
    [
        pytest.param(
            WITH_A_CLASSNAME_TO_ESCAPE,
            '"tests.test_report' + TO_ESCAPE_WRITTEN + '"',
            id="a classname",
        ),
        pytest.param(
            WITH_A_NAME_TO_ESCAPE, '"test_render' + TO_ESCAPE_WRITTEN + '"', id="a name"
        ),
        pytest.param(
            WITH_A_NODE_ID_TO_ESCAPE,
            '"tests/test_report.py::test_render' + TO_ESCAPE_WRITTEN + '"',
            id="a node id",
        ),
        pytest.param(
            WITH_A_ROW_TO_ESCAPE,
            '"src/shop/report.py' + TO_ESCAPE_WRITTEN + '"',
            id="a path in a row",
        ),
        pytest.param(
            WITH_NO_COLUMN_TO_ESCAPE,
            '"templates/invoice.html' + TO_ESCAPE_WRITTEN + '"',
            id="a path with no column",
        ),
        pytest.param(
            WITH_IMPORT_ONLY_TO_ESCAPE,
            '"src/shop/constants.py' + TO_ESCAPE_WRITTEN + '"',
            id="an import-only path",
        ),
        pytest.param(
            WITH_A_HEAD_TO_ESCAPE, '"pr-7' + TO_ESCAPE_WRITTEN + '"', id="a head"
        ),
    ],
)
def test_each_field_of_the_list_is_written_as_a_json_string(
    run: records.EvaluatedRecord,
    written: str,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert shows(report_of([[run]], working_directory, capsys), written)


@pytest.mark.parametrize(
    "run",
    [
        pytest.param(WITH_A_CLASSNAME_TO_ESCAPE, id="a classname"),
        pytest.param(WITH_A_NAME_TO_ESCAPE, id="a name"),
        pytest.param(WITH_A_NODE_ID_TO_ESCAPE, id="a node id"),
        pytest.param(WITH_A_ROW_TO_ESCAPE, id="a path in a row"),
        pytest.param(WITH_NO_COLUMN_TO_ESCAPE, id="a path with no column"),
        pytest.param(WITH_IMPORT_ONLY_TO_ESCAPE, id="an import-only path"),
        pytest.param(WITH_A_HEAD_TO_ESCAPE, id="a head"),
        pytest.param(REPORT_16_RUN, id="Report 16's path with no column"),
    ],
)
def test_with_characters_to_escape_in_the_list_the_report_is_printable_ascii(
    run: records.EvaluatedRecord,
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Each case has its twin in
    # test_each_field_of_the_list_is_written_as_a_json_string, or, for Report
    # 16, in test_report_16_writes_a_newline_and_an_escape_character_escaped.
    assert is_printable_ascii_with_line_ends(
        report_of([[run]], working_directory, capsys)
    )


# A record file whose name holds the characters, with one of the records of
# r2's conflict.
RECORD_FILE_TO_ESCAPE = "records" + TO_ESCAPE + ".jsonl"


def report_of_a_conflict_in_a_record_file_to_escape(
    directory: Path, capsys: pytest.CaptureFixture[str]
) -> str:
    """What report.run writes for r2's conflict, with its records in
    RECORD_FILE_TO_ESCAPE and in records.jsonl."""
    write_record_file(directory / RECORD_FILE_TO_ESCAPE, [R2_MISSED])
    write_record_file(directory / "records.jsonl", [R2_CAUGHT_AGAINST_OTHER_COVERAGE])
    report.run([RECORD_FILE_TO_ESCAPE, "records.jsonl"])
    return capsys.readouterr().out


def test_a_conflicts_record_file_is_written_as_a_json_string(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = report_of_a_conflict_in_a_record_file_to_escape(working_directory, capsys)

    assert shows(text, '"records' + TO_ESCAPE_WRITTEN + '.jsonl"')


def test_with_a_record_file_to_escape_the_report_is_printable_ascii(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = report_of_a_conflict_in_a_record_file_to_escape(working_directory, capsys)

    assert is_printable_ascii_with_line_ends(text)


# A record file that the report cannot use

# The record files, as a command line gives them: no digit in their names, so
# that the only number in a message about a line is that line's.
FIRST = "./first.jsonl"
SECOND = "./second.jsonl"

# K15's text, in a line of a record file that is not a record: no message may
# quote it.
CANARY = "canary"


def nothing_at(_path: Path) -> None:
    """Put nothing at the path: the record file does not exist."""


def a_directory_at(path: Path) -> None:
    path.mkdir()


def a_file_the_tool_may_not_read_at(path: Path) -> None:
    write_record_file(path, REPORT_1)
    path.chmod(0)
    if os.access(path, os.R_OK):
        pytest.skip("this user reads a file whatever its mode, as root does")


def a_line_that_is_not_a_record_at(path: Path) -> None:
    """Two records, and then line 3, which is not a record and holds canary,
    as K15's line 2 does."""
    lines = [
        records.encode(REJECTED_OF_PR_3),
        records.encode(REJECTED_OF_PR_5),
        CANARY.encode("ascii") + b"\n",
    ]
    path.write_bytes(b"".join(lines))


PROBLEMS = [
    pytest.param(nothing_at, id="Report 17, a record file that does not exist"),
    pytest.param(a_directory_at, id="a directory"),
    pytest.param(a_file_the_tool_may_not_read_at, id="a file the tool may not read"),
    pytest.param(a_line_that_is_not_a_record_at, id="a line that is not a record"),
]


def with_a_problem_in_second(
    problem: Callable[[Path], None], directory: Path
) -> list[str]:
    """Report 1's records in FIRST and the problem in SECOND, and their paths in
    that order, as a command line gives them. A report that wrote before it had
    read every record file would write Report 1's figures."""
    write_record_file(directory / FIRST, REPORT_1)
    problem(directory / SECOND)
    return [FIRST, SECOND]


@pytest.mark.parametrize("problem", PROBLEMS)
def test_a_problem_with_a_record_file_writes_nothing_on_stdout(
    problem: Callable[[Path], None],
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report.run(with_a_problem_in_second(problem, working_directory))

    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("problem", PROBLEMS)
def test_a_problem_with_a_record_file_names_that_file(
    problem: Callable[[Path], None],
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # As given, ./ included. A record file that does not exist, taken as
    # empty, would give a report and no message.
    report.run(with_a_problem_in_second(problem, working_directory))

    assert SECOND in capsys.readouterr().err


def test_a_line_that_is_not_a_record_is_named_by_its_number(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Line 3 of SECOND: not 2, SECOND's place on the command line, nor 9, a
    # count that went on from FIRST's 6 lines.
    report.run(
        with_a_problem_in_second(a_line_that_is_not_a_record_at, working_directory)
    )

    assert 3 in numbers_in(capsys.readouterr().err)


def test_a_line_that_is_not_a_record_is_not_quoted(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report.run(
        with_a_problem_in_second(a_line_that_is_not_a_record_at, working_directory)
    )

    output = capsys.readouterr()
    assert CANARY not in output.out + output.err


@pytest.mark.parametrize(
    ("first_problem", "second_problem"),
    [
        pytest.param(
            nothing_at,
            a_line_that_is_not_a_record_at,
            id="a file that does not exist, then a line that is not a record",
        ),
        # A report that looked for every record file before it read any would
        # name SECOND.
        pytest.param(
            a_line_that_is_not_a_record_at,
            nothing_at,
            id="a line that is not a record, then a file that does not exist",
        ),
    ],
)
def test_the_first_problem_in_the_order_of_the_files_decides(
    first_problem: Callable[[Path], None],
    second_problem: Callable[[Path], None],
    working_directory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_problem(working_directory / FIRST)
    second_problem(working_directory / SECOND)

    report.run([FIRST, SECOND])

    error = capsys.readouterr().err
    assert (FIRST in error, SECOND in error) == (True, False)


# Invariants 1

# The tool's code, which the test of Invariants 1 runs as the CI step does.
SRC = Path(__file__).resolve().parent.parent / "src"

# Invariants 1's recorded runs, in two record files: r1 in both; the conflicts
# of r2 and r10, each with one record in each file; and rejected runs under
# three pairs of reason and input, r9 under two of them.
R10_CONFLICT = conflicting_records(key_of(10))
INVARIANTS_1_A: list[records.Record] = [
    R1_CAUGHT_SELECTED_3_S,
    R2_MISSED,
    REJECTED_OF_PR_3,
    evaluated(3, 3, "green"),
    R10_CONFLICT[0],
    REJECTED_OF_PR_5,
]
INVARIANTS_1_B: list[records.Record] = [
    R2_CAUGHT_AGAINST_OTHER_COVERAGE,
    rejected(9, 5, "unsafe-xml", "junit"),
    R10_CONFLICT[1],
    rejected(11, 6, "unusable-input", "coverage"),
    R1_CAUGHT_SELECTED_3_S,
]


def report_through_python_m(paths: list[str], hash_seed: str, directory: Path) -> bytes:
    """What python -P -m distiller report writes on stdout for these record
    files, run in a process of its own with this PYTHONHASHSEED.

    The seed sets the hashes of strings, and so the order of a set of them,
    which two reports in one process would share (TASKS.md, on task 13's test
    of Invariants 1). check=True raises if the report fails, so that two
    reports that failed, with nothing on stdout, are not taken as equal.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-P", "-m", "distiller", "report", *paths],
        cwd=directory,
        env={**os.environ, "PYTHONPATH": str(SRC), "PYTHONHASHSEED": hash_seed},
        capture_output=True,
        check=True,
    )
    return result.stdout


def test_invariants_1_two_reports_are_byte_identical_in_any_order_of_files_and_lines(
    working_directory: Path,
) -> None:
    write_record_file(working_directory / "a.jsonl", INVARIANTS_1_A)
    write_record_file(working_directory / "b.jsonl", INVARIANTS_1_B)
    first = report_through_python_m(["a.jsonl", "b.jsonl"], "0", working_directory)

    # The same records, the record files in the other order and their lines
    # reversed.
    write_record_file(working_directory / "a.jsonl", list(reversed(INVARIANTS_1_A)))
    write_record_file(working_directory / "b.jsonl", list(reversed(INVARIANTS_1_B)))
    second = report_through_python_m(["b.jsonl", "a.jsonl"], "1", working_directory)

    assert first == second


# Invariants 1 for the list of failed tests left out: runs under keys that share
# their head, one with a null junit_sha256; runs that left out two tests, or
# whose paths go beyond ASCII; runs of the rates, the shares and the reruns; and
# a conflict with a record in each file.
INVARIANTS_1_CONFLICT = conflict_of(evaluated(20, 9, "missed"))
INVARIANTS_1_LEFT_OUT_A: list[records.Record] = [
    missed_run_with(R1_HEAD_WITH_R3_SHA256, LEFT_OUT_CREATE),
    floor_matched_run(11, 11),
    dataclasses.replace(
        missed_run_with(R1_HEAD_WITH_R5_SHA256, LEFT_OUT_VAT), no_column=AZUL_THEN_ANO
    ),
    with_tests(
        evaluated(12, 12, "caught"),
        tests=4,
        unmeasured=1,
        tests_with_row=3,
        not_in_run=0,
    ),
    missed_run_with(
        R2_HEAD_WITH_R3_SHA256, LEFT_OUT_OF_THE_MODULE, LEFT_OUT_IN_A_CLASS
    ),
    INVARIANTS_1_CONFLICT[0],
]
INVARIANTS_1_LEFT_OUT_B: list[records.Record] = [
    missed_run_with(R1_HEAD_WITH_NO_SHA256, LEFT_OUT_VAT),
    given_a_rerun(evaluated(13, 13, "green"), RENDER_PAIR),
    INVARIANTS_1_CONFLICT[1],
    tax_only_run(14, 14),
    missed_run_with(R1_HEAD_WITH_R3_SHA256, LEFT_OUT_CREATE),
]


def test_invariants_1_holds_for_the_failed_tests_left_out(
    working_directory: Path,
) -> None:
    write_record_file(working_directory / "a.jsonl", INVARIANTS_1_LEFT_OUT_A)
    write_record_file(working_directory / "b.jsonl", INVARIANTS_1_LEFT_OUT_B)
    first = report_through_python_m(["a.jsonl", "b.jsonl"], "0", working_directory)

    # The same records, the record files in the other order and their lines
    # reversed.
    write_record_file(
        working_directory / "a.jsonl", list(reversed(INVARIANTS_1_LEFT_OUT_A))
    )
    write_record_file(
        working_directory / "b.jsonl", list(reversed(INVARIANTS_1_LEFT_OUT_B))
    )
    second = report_through_python_m(["b.jsonl", "a.jsonl"], "1", working_directory)

    assert first == second


# The command, through cli


def test_the_report_command_exits_with_0(working_directory: Path) -> None:
    paths = write_record_files([REPORT_1], working_directory)

    assert cli.main(["report", *paths]) == 0


def test_the_report_goes_to_stdout_and_nothing_to_stderr(
    working_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = write_record_files([REPORT_1], working_directory)

    cli.main(["report", *paths])

    output = capsys.readouterr()
    assert (shows(output.out, REPORT_1_MISS_RATE), output.err) == (True, "")


@pytest.mark.parametrize("problem", PROBLEMS)
def test_a_problem_with_a_record_file_exits_with_1(
    problem: Callable[[Path], None], working_directory: Path
) -> None:
    paths = with_a_problem_in_second(problem, working_directory)

    assert cli.main(["report", *paths]) == 1


@pytest.mark.parametrize(
    "record_files",
    [
        pytest.param(REPORT_15, id="a conflict"),
        pytest.param([[REJECTED_OF_PR_5]], id="a rejected run"),
    ],
)
def test_a_report_with_a_conflict_or_a_rejected_run_exits_with_0(
    record_files: list[list[records.Record]], working_directory: Path
) -> None:
    # Never with 3, evaluate's code for a rejected run.
    paths = write_record_files(record_files, working_directory)

    assert cli.main(["report", *paths]) == 0


# clopper_pearson_upper

# The one-sided 95% upper bound for k missed PRs out of n is the proportion p
# at which k or fewer out of n have a probability of 5%. No test searches for
# it: each compares the bound with what that definition gives in closed form,
# or puts the bound back into the definition.


def test_with_no_pr_with_a_red_run_there_is_no_bound() -> None:
    assert report.clopper_pearson_upper(0, 0) is None


# The n of the SPEC: 0 out of 3 gives 63.2% and 0 out of 29 9.8% (Checked), and
# 0 out of 30 9.503% (open question 3).
@pytest.mark.parametrize("n", [1, 3, 29, 30])
def test_with_no_missed_pr_the_bound_is_1_minus_the_nth_root_of_5_percent(
    n: int,
) -> None:
    # 0 out of n has a probability of (1 - p) ** n.
    expected = 1 - 0.05 ** (1 / n)

    assert report.clopper_pearson_upper(0, n) == pytest.approx(expected, abs=TOLERANCE)


@pytest.mark.parametrize("n", [1, 3, 30])
def test_with_every_pr_missed_the_bound_is_1(n: int) -> None:
    # n or fewer out of n has a probability of 1, whatever p is.
    assert report.clopper_pearson_upper(n, n) == pytest.approx(1, abs=TOLERANCE)


# n = 2000 is past the n of about 1,030 from which math.comb(n, i) * p**i
# overflows (Checked).
@pytest.mark.parametrize("n", [2, 3, 2000])
def test_with_all_prs_but_one_missed_the_bound_is_the_nth_root_of_95_percent(
    n: int,
) -> None:
    # n - 1 or fewer out of n has a probability of 1 - p ** n.
    expected = 0.95 ** (1 / n)

    assert report.clopper_pearson_upper(n - 1, n) == pytest.approx(
        expected, abs=TOLERANCE
    )


def test_report_1s_bound_leaves_5_percent_to_1_or_fewer_missed_prs_out_of_3() -> None:
    # Report 1's test shows that it is the root between 0 and 1: 86.5%.
    bound = report.clopper_pearson_upper(1, 3)
    assert bound is not None

    none_or_one_out_of_3 = (1 - bound) ** 3 + 3 * bound * (1 - bound) ** 2

    assert none_or_one_out_of_3 == pytest.approx(0.05, abs=TOLERANCE)
