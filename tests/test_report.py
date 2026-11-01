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
        # No test of task 18 looks at how the report writes a key.
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
