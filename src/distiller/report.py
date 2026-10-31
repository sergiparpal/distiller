import math
from decimal import ROUND_HALF_UP, Decimal
from typing import cast

from distiller import records

# The report command, as far as task 16 goes: the record files, read in the
# order given, all of them before anything is written; each run's key counted
# once, however many lines or record files hold its record, with the rejected
# runs in no figure; and the report on stdout, one line for each of these: the
# miss rate, k missed PRs out of n PRs with a red run, with the red runs and the
# one-sided 95% Clopper-Pearson upper bound; the savings, with the sentence that
# they are an upper bound; and the sentence that the figures belong to the
# all-affected selector. Every percentage is computed with Decimal and rounded
# half up to one decimal (Rule 10). The report holds only fixed words and
# numbers, so it is ASCII: Clopper-Pearson is written with a hyphen.

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


def run(paths: list[str]) -> int:  # the report on stdout
    # Every record file is read, and every line of the report built, before
    # anything is written, so that a failure leaves stdout empty.
    recorded = _read_record_files(paths)
    runs = _evaluated_runs(recorded)
    lines = [
        _miss_rate_line(runs),
        _savings_line(runs),
        _FIGURES_BELONG_TO_THE_ALL_AFFECTED_SELECTOR,
    ]
    for line in lines:
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


def _read_record_files(paths: list[str]) -> list[records.Record]:
    # The record files in the order given, and each file's records in its
    # lines' order.
    recorded: list[records.Record] = []
    for path in paths:
        recorded.extend(_records_in(path))
    return recorded


def _records_in(path: str) -> list[records.Record]:
    # read_record_file raises NotARecord for a line that is not a record and
    # OSError for a file that exists but cannot be read, and gives None for a
    # path with no file. Task 17 names the file in a message of its own for
    # each; until then, both errors reach cli as any other failure, and cast
    # tells pyright that the records are there, and checks nothing at run
    # time: a None makes extend raise TypeError, which reaches cli too.
    return cast(list[records.Record], records.read_record_file(path))


def _evaluated_runs(recorded: list[records.Record]) -> list[records.EvaluatedRecord]:
    # Every figure counts each key once, even when its record is held by several
    # lines or record files: the records are grouped by key, and a set holds a
    # record once however many lines hold it. A rejected run counts in no
    # figure, so its record is left out here.
    records_by_key: dict[records.RunKey, set[records.EvaluatedRecord]] = {}
    for record in recorded:
        if isinstance(record, records.EvaluatedRecord):
            records_of_key = records_by_key.setdefault(record.key, set())
            records_of_key.add(record)
    return [_only_record(records_of_key) for records_of_key in records_by_key.values()]


def _only_record(
    records_of_key: set[records.EvaluatedRecord],
) -> records.EvaluatedRecord:
    # The one evaluated record of a key. Two that differ are a conflict, which
    # task 17 leaves out of every figure and lists with its record files. Until
    # then, unpacking a set of two or more records into one name raises
    # ValueError, which reaches cli as any other failure: no report then
    # depends on which of the two records came first.
    [record] = records_of_key
    return record


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
