import json
from dataclasses import dataclass
from typing import cast

from distiller.git import Commit, RepoPath
from distiller.junit import Pair
from distiller.selection import Test

# The records that the tool appends to the record file, an evaluated run's and
# a rejected run's, both with the run's key, and the line that encode writes
# for each: ASCII JSON with no spaces between tokens, its keys in the SPEC's
# order, every list sorted by code point, and a newline at the end.


@dataclass(frozen=True)
class RunKey:
    head: str  # H's full commit id, or H as given
    junit_sha256: str | None


@dataclass(frozen=True)
class RejectedRecord:
    key: RunKey
    pr: int
    reason: str
    input_name: str


@dataclass(frozen=True)
class EvaluatedRecord:
    key: RunKey
    pr: int
    verdict: str
    merge_base: Commit
    coverage_commit: Commit
    selected_ms: int
    full_ms: int
    tests: int
    unmeasured: int
    tests_with_row: int
    tests_with_row_not_in_run: int
    floor_matched: bool
    rerun_given: bool
    not_reproduced: tuple[Pair, ...]
    failed_left_out: tuple[Test, ...]
    no_column: tuple[RepoPath, ...]
    import_only: tuple[RepoPath, ...]


Record = EvaluatedRecord | RejectedRecord


def encode(record: Record) -> bytes:
    # Rule 7: a dict in the SPEC's key order, which json.dumps keeps, written
    # with no spaces between tokens and a newline at the end. The default
    # ensure_ascii writes the SPEC's escapes, so the line is ASCII: a character
    # outside printable ASCII with no short escape becomes a backslash, u and
    # four lowercase hex digits, one beyond U+FFFF a surrogate pair, and a lone
    # surrogate from os.fsdecode a single escape. encode checks nothing, not
    # even whether the fields agree: it writes what the record holds, with its
    # lists sorted.
    if isinstance(record, EvaluatedRecord):
        fields = _evaluated_fields(record)
    else:
        fields = _rejected_fields(record)
    line = json.dumps(fields, separators=(",", ":")) + "\n"
    return line.encode("ascii")


def _evaluated_fields(record: EvaluatedRecord) -> dict[str, object]:
    # The first keys, then an evaluated run's own, in the SPEC's order, every
    # list sorted by code point whatever order the record holds it in (Rule 8).
    # json.dumps writes a tuple as a list, so a pair is a list of two strings,
    # and pairs compare as tuples do, by classname and then name.
    return _first_fields(record.key, record.pr, record.verdict) | {
        "merge_base": record.merge_base,
        "coverage_commit": record.coverage_commit,
        "selected_ms": record.selected_ms,
        "full_ms": record.full_ms,
        "tests": record.tests,
        "unmeasured": record.unmeasured,
        "tests_with_row": record.tests_with_row,
        "tests_with_row_not_in_run": record.tests_with_row_not_in_run,
        "floor_matched": record.floor_matched,
        "rerun_given": record.rerun_given,
        "not_reproduced": sorted(record.not_reproduced),
        "failed_left_out": _left_out_entries(record.failed_left_out),
        "no_column": sorted(record.no_column),
        "import_only": sorted(record.import_only),
    }


def _rejected_fields(record: RejectedRecord) -> dict[str, object]:
    # The first keys, with the verdict rejected, which no field holds, then the
    # reason and the input, whose key is input.
    return _first_fields(record.key, record.pr, "rejected") | {
        "reason": record.reason,
        "input": record.input_name,
    }


def _first_fields(key: RunKey, pr: int, verdict: str) -> dict[str, object]:
    # The keys that every record starts with, in the SPEC's order. The record
    # format version is always 1, since no record class holds it (open
    # question 2), and a junit_sha256 of None is written as null.
    return {
        "format": 1,
        "head": key.head,
        "junit_sha256": key.junit_sha256,
        "pr": pr,
        "verdict": verdict,
    }


def _left_out_entries(tests: tuple[Test, ...]) -> list[dict[str, object]]:
    # The failed tests left out, sorted by their pairs, since a Test has no
    # order of its own. sorted is stable, so two tests with one pair, which
    # Judgement never gives, would keep the record's order.
    in_pair_order = sorted(tests, key=lambda test: test.pair)
    return [_left_out_entry(test) for test in in_pair_order]


def _left_out_entry(test: Test) -> dict[str, object]:
    # A failed test left out, as an object with pair, node_id and row, in that
    # order, its row sorted by code point: a frozenset keeps no order. The
    # failed tests that Judgement leaves out are all measured, so the row is
    # set (Data model): cast tells pyright so, and checks nothing at run time.
    row = cast(frozenset[RepoPath], test.row)
    return {"pair": test.pair, "node_id": test.node_id, "row": sorted(row)}
