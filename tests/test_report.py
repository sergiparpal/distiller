import dataclasses
import re
from pathlib import Path

import pytest

from distiller import cli, records, report, selection

# Each test writes record files in tmp_path, its working directory, runs the
# report on them and looks for words in what it writes on stdout; the tests of
# clopper_pearson_upper call it alone. The report's tests call report.run, so
# that an exception it raises reaches the test, and so that a check that some
# words are absent cannot pass on a report that failed: cli would turn the
# exception into exit 1 with nothing on stdout. Only the tests of the command's
# exit code and streams go through cli.main.
#
# Every line of a record file is what records.encode writes for a record built
# as a literal, and write_record_file checks that records.decode gives that
# record back, so that each line is a record as Rule 7 defines it.
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
