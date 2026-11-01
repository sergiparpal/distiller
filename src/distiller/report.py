import json
import math
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from distiller import messages, records, selection

# The report command. The record files are read in the order given, all of
# them before anything is written, and the first one that does not exist,
# cannot be read or holds a line that is not a record stops the report: one
# line on stderr that names it, nothing on stdout and exit 1. Each run's key is
# counted once, however many lines or record files hold its record. A key
# whose evaluated records differ is a conflict, and neither a conflict nor a
# rejected run counts in any figure or in the list of failed tests left out.
# The report on stdout has one line for each of these: the miss rate, k missed
# PRs out of n PRs with a red run, with the red runs and the one-sided 95%
# Clopper-Pearson upper bound; the savings, with the sentence that they are an
# upper bound; the sentence that these two figures belong to the all-affected
# selector; the floor and no-column rates, each k PRs out of the n evaluated
# PRs; the unmeasured and not-in-run shares, of the tests summed over the runs;
# and the reruns: the red runs whose failures no rerun confirmed, and the
# failures discarded as not reproduced. Then come three lists, each under a
# heading and saying so when it has no entry: the failed tests left out of a
# selection, under the run that left them out, with its key, its pull request,
# its paths with no column and its import-only paths; the conflicts, each key
# with the record files that hold it; and the rejected runs, counted under
# each reason and input for the keys that no evaluated record has. A figure
# whose denominator is zero is never a percentage, and every percentage is
# computed with Decimal and rounded half up to one decimal (Rule 10). Every
# list is sorted where it is built, by code point (Rule 8), so that the report
# depends neither on the order of the record files and of their lines nor on a
# set's. Keys, record files, pairs, node ids and paths are written with the
# json.dumps of records.encode, escapes included, and the rest is fixed words,
# numbers and the reasons and inputs that a record allows, so the report is
# ASCII: Clopper-Pearson is written with a hyphen, and Report 12's sentence
# without the SPEC's section number.

# An evaluated run is red when it is caught or missed, and green otherwise.
_RED_VERDICTS = ("caught", "missed")

# Rule 10: a percentage keeps one decimal at most.
_ONE_DECIMAL = Decimal("0.1")

# The one-sided 95% upper bound leaves 5% to k or fewer missed PRs out of n.
_TAIL = 0.05

# How many times the bisection halves [0, 1]. After 50 halvings the interval is
# 2**-50 wide, about 9e-16, and every middle point on the way is a float
# strictly between 0 and 1, where the logarithms of p and of 1 - p are defined.
_HALVINGS = 50

_SAVINGS_ARE_AN_UPPER_BOUND = (
    "this is an upper bound, because fixed per-run costs such as start-up and "
    "collection are not in the JUnit times"
)
_FIGURES_BELONG_TO_THE_ALL_AFFECTED_SELECTOR = (
    "These figures belong to the all-affected selector, which picks every test "
    "that any rule picks over these rows; a selector that picks only some of "
    "them, such as a set cover over the same rows, misses at least as often."
)

# Report 12's sentence on what the failures discarded can hide, without the
# SPEC's section number, whose sign is not ASCII.
_ORDER_DEPENDENT_FAILURES_CAN_HIDE = "order-dependent failures can hide in that count"

# Why a failed test was left out, which holds for every one of them, since a
# test that any rule picks is selected (open question 5).
_WHY_IT_WAS_LEFT_OUT = (
    "its row has none of the diff's paths, and no other rule picked it"
)

# The heading of each list, and the words that say it has no entry, Report
# 13's "no rejected run" among them.
_LEFT_OUT_HEADING = (
    "Failed tests left out of a selection, by run, whether or not the run was caught:"
)
_NO_FAILED_TEST_LEFT_OUT = "no failed test left out"
_CONFLICTS_HEADING = (
    "Conflicts, keys whose evaluated records differ, left out of every figure:"
)
_NO_CONFLICT = "no conflict"
_REJECTED_RUNS_HEADING = (
    "Rejected runs, left out of every figure, each counted under every reason "
    "and input it was rejected for:"
)
_NO_REJECTED_RUN = "no rejected run"

# Each line of a list goes after two spaces, and in the list of failed tests
# left out, the lines under a run after two more.
_INDENT = "  "


# A line of a record file: its record, and the path of the file that holds it,
# as given on the command line. A line held twice gives two equal ones.
@dataclass(frozen=True)
class _RecordLine:
    record: records.Record
    path: str


def run(paths: list[str]) -> int:  # the report on stdout
    # The paragraph after "How a run goes": the record files are read in the
    # order given, all of them before anything is written, and the first
    # problem stops the report with exit 1, before the files after it are
    # read. Unlike evaluate, the report never takes a record file that does
    # not exist as empty: a mistyped path would drop its runs without a
    # warning.
    record_lines: list[_RecordLine] = []
    for path in paths:
        try:
            lines_of_file = _records_in(path)
        except records.NotARecord as error:
            print(messages.not_a_record(error.path, error.line_number), file=sys.stderr)
            return 1
        if lines_of_file is None:
            print(messages.unreadable_record_file(path), file=sys.stderr)
            return 1
        record_lines.extend(lines_of_file)
    # Every line of the report is built before the first is written, so that
    # an error while building it leaves stdout empty too.
    for line in _report_lines(record_lines):
        print(line)
    return 0


def clopper_pearson_upper(k: int, n: int) -> float | None:
    # A proportion from 0 to 1; None when n is 0. The one-sided 95% upper bound
    # for k missed PRs out of n is the proportion p at which k or fewer out of n
    # have a probability of 5%. For k below n, that probability falls as p
    # grows, from 1 at p = 0 to 0 at p = 1, so bisection finds p: each halving
    # keeps the half of the interval in which the probability crosses 5%.
    if n == 0:
        return None  # no PR with a red run: 0 out of 0, with no bound
    if k == n:
        return 1.0  # k or fewer out of n is certain, whatever p is
    low = 0.0  # the probability is above 5% here
    high = 1.0  # and 5% or less here
    for _ in range(_HALVINGS):
        middle = (low + high) / 2
        if _probability_of_k_or_fewer(k, n, middle) > _TAIL:
            low = middle
        else:
            high = middle
    # The last interval's upper end, where the probability is 5% or less: the
    # bound errs upward, by 2**-50 at most, but for the rounding errors of the
    # floats that compute the probability (note 72).
    return high


def _records_in(path: str) -> list[_RecordLine] | None:
    # None: the record file does not exist or cannot be read. read_record_file
    # gives None for a path with no file and raises OSError for a file that
    # exists but cannot be read, such as a directory, a FIFO or a file that
    # the tool may not read; the report's message is the same for both.
    # NotARecord, for a line that is not a record, goes through to run. Each
    # record keeps the path of its file, which a conflict names.
    try:
        recorded = records.read_record_file(path)
    except OSError:
        return None
    if recorded is None:
        return None
    return [_RecordLine(record=record, path=path) for record in recorded]


def _report_lines(record_lines: list[_RecordLine]) -> list[str]:
    # The miss rate and the savings, over the runs that count, and the
    # sentence on the selector that they belong to; then the rates, the shares
    # and the reruns, over the same runs, none of which depends on which tests
    # the selector picks; then the three lists: the failed tests that those
    # runs left out, and what no figure counts, the conflicts and the rejected
    # runs.
    evaluated = _evaluated_records_by_key(record_lines)
    runs, conflicts = _runs_and_conflicts(evaluated)
    return [
        _miss_rate_line(runs),
        _savings_line(runs),
        _FIGURES_BELONG_TO_THE_ALL_AFFECTED_SELECTOR,
        _rates_line(runs),
        _shares_line(runs),
        _reruns_line(runs),
        *_left_out_lines(runs),
        *_conflict_lines(conflicts, _record_files_by_key(record_lines)),
        *_rejected_run_lines(_rejected_counts(record_lines, evaluated)),
    ]


def _evaluated_records_by_key(
    record_lines: list[_RecordLine],
) -> dict[records.RunKey, set[records.EvaluatedRecord]]:
    # Each key that an evaluated record has, with its evaluated records, each
    # once however many lines or record files hold it: a set holds equal
    # records once, and two records are equal only if every field is, pr
    # included. A rejected record adds nothing here.
    records_by_key: dict[records.RunKey, set[records.EvaluatedRecord]] = {}
    for record_line in record_lines:
        record = record_line.record
        if isinstance(record, records.EvaluatedRecord):
            records_of_key = records_by_key.setdefault(record.key, set())
            records_of_key.add(record)
    return records_by_key


def _runs_and_conflicts(
    evaluated: dict[records.RunKey, set[records.EvaluatedRecord]],
) -> tuple[list[records.EvaluatedRecord], list[records.RunKey]]:
    # The runs that the figures count, one for each key with a single
    # evaluated record, and the conflicts, the keys with more, both in key
    # order: the order of the conflicts' list, and of the runs in the list of
    # failed tests left out.
    runs: list[records.EvaluatedRecord] = []
    conflicts: list[records.RunKey] = []
    for key in sorted(evaluated, key=_key_order):
        record = _only_record(evaluated[key])
        if record is None:
            conflicts.append(key)
        else:
            runs.append(record)
    return runs, conflicts


def _only_record(
    records_of_key: set[records.EvaluatedRecord],
) -> records.EvaluatedRecord | None:  # None: a conflict
    # The one evaluated record of a key. Two or more that differ are a
    # conflict, which no figure counts: choosing one of them would make the
    # report depend on the order of the files, or on which one a set gives
    # first.
    if len(records_of_key) > 1:
        return None
    [record] = records_of_key
    return record


def _key_order(key: records.RunKey) -> tuple[str, int, str]:
    # The SPEC's order of runs: by head and then by junit_sha256, with null
    # first, each string by code point, which is Python's order for str. After
    # the head comes 0 for a null junit_sha256 and 1 for a SHA-256, so that
    # null comes first, and then the SHA-256 itself, which orders the others.
    if key.junit_sha256 is None:
        return (key.head, 0, "")
    return (key.head, 1, key.junit_sha256)


def _miss_rate_line(runs: list[records.EvaluatedRecord]) -> str:
    # The miss rate counts pull requests: n, the PRs with at least one red run,
    # and k, those of them with at least one missed run. It is written as k out
    # of n and its bound, never as a percentage of its own, and next to it how
    # many red runs those PRs had.
    red_runs = [run for run in runs if run.verdict in _RED_VERDICTS]
    red_prs = {run.pr for run in red_runs}  # n is how many
    missed_prs = {run.pr for run in red_runs if run.verdict == "missed"}  # k
    bound = clopper_pearson_upper(len(missed_prs), len(red_prs))
    missed_words = _count(len(missed_prs), "missed PR")
    red_pr_words = _count(len(red_prs), "PR")
    red_run_words = _count(len(red_runs), "red run")
    return (
        f"Miss rate: {missed_words} out of {red_pr_words} with a red run "
        f"({red_run_words}), {_bound_words(bound)}."
    )


def _bound_words(bound: float | None) -> str:
    # None when no PR has a red run: the miss rate is then 0 out of 0, and a
    # zero denominator gives no percentage.
    if bound is None:
        return "with no bound"
    return (
        f"with a one-sided 95% Clopper-Pearson upper bound of {_bound_percent(bound)}"
    )


def _savings_line(runs: list[records.EvaluatedRecord]) -> str:
    # Savings are 1 - the selected duration over the full-suite duration, each
    # summed over every evaluated run, green and red, in whole milliseconds.
    selected_ms = sum(run.selected_ms for run in runs)
    full_ms = sum(run.full_ms for run in runs)
    if full_ms == 0:
        # No evaluated run, or none with a full-suite time above 0: a zero
        # denominator gives no percentage.
        return (
            "Test time: no savings figure, since no evaluated run has a "
            "full-suite time above zero."
        )
    # Rule 10: computed with Decimal from the integers it divides, never
    # through a float. As a percentage, 1 - selected / full is
    # 100 * (full - selected) / full, so the only step that is not exact is
    # Decimal's division, which keeps 28 significant digits: enough to round
    # exactly any savings from 0 to 100% of a total under 10**25 ms (note 73).
    savings = Decimal(100 * (full_ms - selected_ms)) / Decimal(full_ms)
    return (
        f"Test time: savings of {_percent_text(savings)} of the full suite's "
        f"time; {_SAVINGS_ARE_AN_UPPER_BOUND}."
    )


def _rates_line(runs: list[records.EvaluatedRecord]) -> str:
    # The floor and no-column rates count pull requests: k out of n, where n
    # is the evaluated PRs, those with at least one run that counts, and k
    # those of them with at least one run that the rate looks for, however
    # many of their other runs it does not look for.
    evaluated_prs = {run.pr for run in runs}
    floor_prs = {run.pr for run in runs if run.floor_matched}
    no_column_prs = {run.pr for run in runs if _counts_in_the_no_column_rate(run)}
    floor_rate = _rate_words("floor rate", len(floor_prs), len(evaluated_prs))
    no_column_rate = _rate_words(
        "no-column rate", len(no_column_prs), len(evaluated_prs)
    )
    return f"Evaluated PRs: {floor_rate}; {no_column_rate}."


def _counts_in_the_no_column_rate(run: records.EvaluatedRecord) -> bool:
    # A run in which a changed path had no column and no changed path matched
    # the floor: only in such a run could file tracing change the selection.
    # An import-only path is not a path with no column.
    return len(run.no_column) > 0 and not run.floor_matched


def _rate_words(name: str, prs: int, evaluated_prs: int) -> str:
    # "<name> of <p>%: <k> PR[s] out of <n>", always with the PRs that the rate
    # comes from, since with few PRs a percentage says little. With no
    # evaluated PR, a zero denominator, "<name>: 0 PRs out of 0", with no
    # percentage, as the miss rate is then 0 out of 0.
    counts = f"{_count(prs, 'PR')} out of {evaluated_prs}"
    if evaluated_prs == 0:
        return f"{name}: {counts}"
    return f"{name} of {_percent_of(prs, evaluated_prs)}: {counts}"


def _shares_line(runs: list[records.EvaluatedRecord]) -> str:
    # Two shares of tests, each summed over the runs that count, so that every
    # test weighs the same, whatever the size of its run: the tests treated as
    # unmeasured, out of the runs' tests, and the tests with a row in the
    # coverage at M that were not in their run, out of the tests with a row.
    tests = sum(run.tests for run in runs)
    unmeasured = sum(run.unmeasured for run in runs)
    tests_with_row = sum(run.tests_with_row for run in runs)
    not_in_run = sum(run.tests_with_row_not_in_run for run in runs)
    unmeasured_share = _unmeasured_share_words(unmeasured, tests)
    not_in_run_share = _not_in_run_share_words(not_in_run, tests_with_row)
    return f"Tests: {unmeasured_share}; {not_in_run_share}."


def _unmeasured_share_words(unmeasured: int, tests: int) -> str:
    # "<p>% of tests treated as unmeasured", or, with no test in the runs, a
    # zero denominator, "<k> out of 0 tests treated as unmeasured", with no
    # percentage.
    if tests == 0:
        return f"{unmeasured} out of {tests} tests treated as unmeasured"
    return f"{_percent_of(unmeasured, tests)} of tests treated as unmeasured"


def _not_in_run_share_words(not_in_run: int, tests_with_row: int) -> str:
    # "<p>% of the tests with a row were not in their run", or, with no test
    # with a row, a zero denominator, "<k> out of 0 tests with a row were not
    # in their run", with no percentage.
    if tests_with_row == 0:
        return (
            f"{not_in_run} out of {tests_with_row} tests with a row were not in "
            "their run"
        )
    share = _percent_of(not_in_run, tests_with_row)
    return f"{share} of the tests with a row were not in their run"


def _reruns_line(runs: list[records.EvaluatedRecord]) -> str:
    # How far a rerun checked the red runs' failures: the red runs given no
    # rerun file, whose failures no rerun confirmed, and the failures that a
    # rerun file discarded as not reproduced, counted in each run, so that a
    # pair discarded in two runs counts twice. The miss rate's line keeps its
    # own count, of every red run.
    red_runs_with_no_rerun = [
        run for run in runs if run.verdict in _RED_VERDICTS and not run.rerun_given
    ]
    not_confirmed = _count(len(red_runs_with_no_rerun), "red run")
    discarded = sum(len(run.not_reproduced) for run in runs)
    return (
        f"Reruns: the failures of {not_confirmed} were not confirmed by a "
        f"rerun; {_discarded_words(discarded)}: "
        f"{_ORDER_DEPENDENT_FAILURES_CAN_HIDE}."
    )


def _discarded_words(discarded: int) -> str:
    # "<f> failures were discarded as not reproduced", in the singular only
    # for 1.
    if discarded == 1:
        return "1 failure was discarded as not reproduced"
    return f"{discarded} failures were discarded as not reproduced"


def _left_out_lines(runs: list[records.EvaluatedRecord]) -> list[str]:
    # The failed tests left out of a selection under their heading, each
    # under the run that left it out, whether or not that run was caught, and
    # the runs in key order, as _runs_and_conflicts gives them. A run that
    # left out no failed test is not listed, nor are its paths; and a
    # conflict's records are not among the runs, so their failed tests are
    # not listed either, as they count in no figure.
    lines: list[str] = []
    for run in runs:
        if len(run.failed_left_out) > 0:
            lines.extend(_run_lines(run))
    return _list_lines(_LEFT_OUT_HEADING, lines, _NO_FAILED_TEST_LEFT_OUT)


def _run_lines(run: records.EvaluatedRecord) -> list[str]:
    # A run in the list: "run <key> of PR <n>", its key as a conflict writes
    # it and its pull request, which holds the diff's paths that a record
    # does not; then, one level further in, its paths with no column and its
    # import-only paths, each a JSON list of strings sorted by code point,
    # empty for none, and each failed test that it left out, with why it was
    # left out, sorted by pair, by classname and then name, as tuples
    # compare. A record's line holds each of them sorted already: sorting
    # them here keeps the report's order from depending on what a record
    # holds.
    tests = sorted(run.failed_left_out, key=lambda test: test.pair)
    test_lines = [
        f"{_INDENT}{_left_out_text(test)}: {_WHY_IT_WAS_LEFT_OUT}" for test in tests
    ]
    return [
        f"run {_key_text(run.key)} of PR {run.pr}",
        f"{_INDENT}paths with no column {_json_text(sorted(run.no_column))}",
        f"{_INDENT}import-only paths {_json_text(sorted(run.import_only))}",
        *test_lines,
    ]


def _left_out_text(test: selection.Test) -> str:
    # A failed test left out, as its record's line writes it in
    # failed_left_out: an object with pair, node_id and row, in that order,
    # its row sorted by code point, since a frozenset keeps no order. A record
    # holds only measured failed tests left out, as decode checks, so the row
    # is set (Data model): cast tells pyright so, and checks nothing at run
    # time, as in records.encode.
    row = cast(frozenset[str], test.row)
    entry: dict[str, object] = {
        "pair": test.pair,
        "node_id": test.node_id,
        "row": sorted(row),
    }
    return _json_text(entry)


def _conflict_lines(
    conflicts: list[records.RunKey], record_files: dict[records.RunKey, set[str]]
) -> list[str]:
    # The conflicts under their heading, in key order, as _runs_and_conflicts
    # gives them, each with the record files that hold a record of its key.
    entries = [_conflict_entry(key, record_files[key]) for key in conflicts]
    return _list_lines(_CONFLICTS_HEADING, entries, _NO_CONFLICT)


def _conflict_entry(key: records.RunKey, paths: set[str]) -> str:
    # "conflict: <key> in <record files>": the key as its records' lines write
    # it, and the record files as a JSON list of strings, as a record writes a
    # list of paths, sorted by code point, each once. Paths compare as given,
    # so a file given twice is named once, while ./a.jsonl and a.jsonl would
    # be two names.
    return f"conflict: {_key_text(key)} in {_json_text(sorted(paths))}"


def _key_text(key: records.RunKey) -> str:
    # The key as its records' lines write it, "head":...,"junit_sha256":...,
    # each value with the json.dumps of records.encode, so with the same
    # escapes, and null for a junit_sha256 of None.
    head = _json_text(key.head)
    junit_sha256 = _json_text(key.junit_sha256)
    return f'"head":{head},"junit_sha256":{junit_sha256}'


def _json_text(value: str | list[str] | dict[str, object] | None) -> str:
    # Rule 7: the json.dumps that records.encode writes a line with, with no
    # spaces between tokens and the default ensure_ascii, which writes every
    # character outside printable ASCII as an escape: a control character in
    # a key, a pair, a node id or a path never reaches the terminal or a log
    # unescaped. A failed test left out comes as a dict, which json.dumps
    # writes as an object, in the dict's order, and its pair, a tuple, as a
    # list, as in a record's line.
    return json.dumps(value, separators=(",", ":"))


def _record_files_by_key(
    record_lines: list[_RecordLine],
) -> dict[records.RunKey, set[str]]:
    # The record files that hold a record of each key, evaluated or rejected,
    # each path once.
    files_by_key: dict[records.RunKey, set[str]] = {}
    for record_line in record_lines:
        files_of_key = files_by_key.setdefault(record_line.record.key, set())
        files_of_key.add(record_line.path)
    return files_by_key


def _rejected_run_lines(counts: dict[tuple[str, str], int]) -> list[str]:
    # The counts of rejected runs under their heading, sorted by reason and
    # then input, as pairs of strings compare.
    entries = [_rejected_entry(pair, counts[pair]) for pair in sorted(counts)]
    return _list_lines(_REJECTED_RUNS_HEADING, entries, _NO_REJECTED_RUN)


def _rejected_entry(pair: tuple[str, str], number: int) -> str:
    # "<n> run[s] rejected for <reason> with <input>", in the singular only
    # for 1. decode allows only the SPEC's reasons and inputs, which are
    # ASCII words with nothing to escape.
    reason, input_name = pair
    return f"{_count(number, 'run')} rejected for {reason} with {input_name}"


def _rejected_counts(
    record_lines: list[_RecordLine],
    evaluated: dict[records.RunKey, set[records.EvaluatedRecord]],
) -> dict[tuple[str, str], int]:
    # How many keys are counted under each pair of reason and input. A key
    # that an evaluated record has, a conflict's included, is never counted as
    # rejected. Any other key counts once under each pair that its rejected
    # records give, so the counts can add up to more than the number of keys
    # rejected (open question 9).
    counts: dict[tuple[str, str], int] = {}
    for key, pairs in _rejections_by_key(record_lines).items():
        if key in evaluated:
            continue
        for pair in pairs:
            counts[pair] = counts.get(pair, 0) + 1
    return counts


def _rejections_by_key(
    record_lines: list[_RecordLine],
) -> dict[records.RunKey, set[tuple[str, str]]]:
    # The pairs of reason and input that each key's rejected records give,
    # each pair once, whatever the records' pr, which is not part of the key,
    # and however many lines or record files hold them.
    pairs_by_key: dict[records.RunKey, set[tuple[str, str]]] = {}
    for record_line in record_lines:
        record = record_line.record
        if isinstance(record, records.RejectedRecord):
            pairs_of_key = pairs_by_key.setdefault(record.key, set())
            pairs_of_key.add((record.reason, record.input_name))
    return pairs_by_key


def _list_lines(heading: str, entries: list[str], when_empty: str) -> list[str]:
    # A list under its heading, each of the lines that its entries give after
    # two spaces, or a single line with the words that say it has no entry. A
    # run in the list of failed tests left out gives several lines.
    if not entries:
        return [heading, _INDENT + when_empty]
    indented = [_INDENT + entry for entry in entries]
    return [heading, *indented]


def _percent_of(part: int, whole: int) -> str:
    # Rule 10: part out of whole as a percentage, computed with Decimal from
    # the two integers, never through a float, and written as every other
    # percentage. whole is above 0, since a zero denominator gives no
    # percentage. Decimal's division keeps 28 significant digits, as for the
    # savings (note 73).
    return _percent_text(Decimal(100 * part) / Decimal(whole))


def _bound_percent(bound: float) -> str:
    # Rule 10: the float from clopper_pearson_upper turned into Decimal
    # exactly, as Decimal(float) does, multiplied by 100 and rounded like every
    # other percentage. Never formatted from the float with f"{x:.1f}", which
    # takes a tie to the even digit.
    return _percent_text(Decimal(bound) * 100)


def _percent_text(percent: Decimal) -> str:
    # Rule 10: rounded with quantize to one decimal, halves up, as Rule 5
    # rounds JUnit times, and then a trailing .0 dropped: 25% and 37.5%.
    # quantize leaves exactly one decimal, which str writes as plain digits,
    # with a minus sign for the negative savings of records whose fields
    # disagree (note 69).
    rounded = percent.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)
    return str(rounded).removesuffix(".0") + "%"


def _count(number: int, noun: str) -> str:
    # A number and its noun, in the singular only for 1: "1 PR" and "0 PRs".
    if number == 1:
        return f"1 {noun}"
    return f"{number} {noun}s"


def _probability_of_k_or_fewer(k: int, n: int, p: float) -> float:
    # The probability of k or fewer out of n, each with probability p, for a p
    # strictly between 0 and 1: the sum, for i from 0 to k, of
    # math.comb(n, i) * p**i * (1 - p)**(n - i). Each term is computed from its
    # logarithm, with math.lgamma: math.comb(n, i) * p**i overflows a float
    # from about n = 1,030 (Checked), while its logarithm stays small. A term
    # too small for a float comes out as 0.0.
    log_p = math.log(p)
    # math.log1p(-p) is the logarithm of 1 - p, without rounding 1 - p first.
    log_one_minus_p = math.log1p(-p)
    total = 0.0
    for i in range(k + 1):
        log_term = _log_comb(n, i) + i * log_p + (n - i) * log_one_minus_p
        total += math.exp(log_term)
    return total


def _log_comb(n: int, i: int) -> float:
    # The logarithm of math.comb(n, i), which is n! / (i! * (n - i)!), from
    # math.lgamma: lgamma(m + 1) is the logarithm of m!.
    return math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
