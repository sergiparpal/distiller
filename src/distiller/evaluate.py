import hashlib
import sys
from dataclasses import dataclass
from typing import cast

from distiller import coverage_at_m, floor, git, junit, messages, records, selection

# The evaluate command, as "How a run goes" in the SPEC tells it: the record
# file, read before any input; the run's key, from the full run's JUnit bytes
# and H; the warning for a run already recorded; the inputs, taken in the SPEC's
# problem order; the evaluated record, built by the functions of the technical
# sheet's Interfaces and appended with nothing printed; and the exit code.
# Every text that it writes to stderr comes from messages.


# One field per option of the evaluate command, as given, except that rootdir
# is normalized: "" is the repository root.
@dataclass(frozen=True)
class RunArgs:
    pr: int
    head: str
    base: str
    coverage: str
    coverage_commit: str
    junit: str
    rerun: str | None
    rootdir: str
    floor_config: str | None
    records: str
    checkout: str


def run(args: RunArgs) -> int:  # prints its message; returns the exit code
    # Step 2: the record file, before any input, so that a line that is not a
    # record stops the run whatever the inputs are. A record file that exists
    # but cannot be read raises OSError, which reaches cli as any other failure.
    try:
        recorded = _recorded_runs(args.records)
    except records.NotARecord as error:
        print(messages.not_a_record(error.path, error.line_number), file=sys.stderr)
        return 1
    # Rule 5: the full run's JUnit file is read once, into bytes, which give the
    # key's SHA-256 here and are parsed in step 3. read_junit gives None for a
    # file that is missing or cannot be read, which task 14 rejects, with a key
    # whose junit_sha256 is null: until then, cast tells pyright that the bytes
    # are there, and checks nothing at run time.
    full_run_data = cast(bytes, junit.read_junit(args.junit))
    # Rule 2: H is resolved once, here, and every git command after this one
    # gets its full commit id. resolve_commit gives None for an H that names no
    # commit, which task 14 rejects, with a key whose head is H as given: cast
    # as for the bytes.
    head = cast(git.Commit, git.resolve_commit(args.checkout, args.head))
    junit_sha256 = hashlib.sha256(full_run_data).hexdigest()
    key = records.RunKey(head=head, junit_sha256=junit_sha256)
    if records.has_evaluated(recorded, key):
        print(messages.already_recorded(key.head, key.junit_sha256), file=sys.stderr)
        return 0
    record = _evaluated_record(args, key, head, full_run_data)
    # An evaluated run prints nothing and exits with 0, whatever its verdict.
    records.append_record(args.records, record)
    return 0


def _recorded_runs(path: str) -> list[records.Record]:
    # Raises NotARecord, or OSError if the file exists but cannot be read. A
    # record file that does not exist is an empty one, which the append creates.
    recorded = records.read_record_file(path)
    if recorded is None:
        return []
    return recorded


def _evaluated_record(
    args: RunArgs, key: records.RunKey, head: git.Commit, full_run_data: bytes
) -> records.EvaluatedRecord:
    # Step 3: the inputs in the SPEC's problem order, one call each, which gives
    # a value: the checkout, H, the base branch, the coverage, the full run's
    # JUnit, the rerun file and the floor configuration. Tasks 14 and 15 add the
    # checks that reject a run, each where the order puts it: the checkout has
    # no call yet, and H was resolved in step 2. Until then, a Rejected that a
    # reader raises reaches cli as any other failure.
    merge_base = _merge_base(args.checkout, args.base, head)
    # The coverage: M, resolved once (Rule 2), then the file, read in full.
    # resolve_commit gives None for an M that names no commit, which task 14
    # rejects as an unusable coverage input: cast as for H.
    coverage_commit = cast(
        git.Commit, git.resolve_commit(args.checkout, args.coverage_commit)
    )
    raw = coverage_at_m.read_coverage(args.coverage)
    full = junit.parse_junit(full_run_data, "junit", args.junit)
    rerun = _rerun(args.rerun)
    patterns = floor.read_floor(args.floor_config)
    # Step 4: the diff, from the merge-base of B and H to H, never against M;
    # the coverage, mapped to M's tree; the run's tests, matched to their rows;
    # the selection, with the floor's hits; and the verdict.
    changed = git.changed_paths(args.checkout, merge_base, head)
    tree = git.tree_files(args.checkout, coverage_commit)
    matrix = coverage_at_m.build_matrix(raw, tree)
    tests = selection.match_tests(full.results, matrix.rows)
    hits = floor.floor_hits(patterns, changed)
    chosen = selection.select(tests, changed, hits, args.rootdir)
    judgement = selection.judge(full, rerun, tests, chosen)
    selected_ms, full_ms = selection.durations(full, chosen)
    tests_with_row, not_in_run = selection.row_counts(matrix.rows, full.results)
    return records.EvaluatedRecord(
        key=key,
        pr=args.pr,
        verdict=judgement.verdict,
        merge_base=merge_base,
        coverage_commit=coverage_commit,
        selected_ms=selected_ms,
        full_ms=full_ms,
        tests=len(tests),  # match_tests gives one Test for each pair in the run
        unmeasured=_unmeasured_count(tests),
        tests_with_row=tests_with_row,
        tests_with_row_not_in_run=not_in_run,
        floor_matched=len(hits) > 0,
        rerun_given=rerun is not None,
        # Rule 8: every list is sorted where it is built. not_reproduced is a
        # frozenset, so it is sorted here, by pair (note 40); judge, no_column
        # and import_only_paths give their lists already sorted.
        not_reproduced=tuple(sorted(judgement.not_reproduced)),
        failed_left_out=judgement.failed_left_out,
        no_column=tuple(selection.no_column(changed, matrix)),
        import_only=tuple(selection.import_only_paths(changed, matrix)),
    )


def _merge_base(checkout: str, base: str, head: git.Commit) -> git.Commit:
    # The base branch: B, the commit it stands for, resolved once (Rule 2), then
    # the merge-base of B and H, in that order, from their full commit ids:
    # with several best common ancestors, the order can change which one git
    # prints (note 63). Each is None only for a base that task 14 rejects: one
    # that names no commit, or whose commit shares no history with H. Until
    # then, cast tells pyright that each is a commit, and checks nothing at run
    # time.
    base_commit = cast(git.Commit, git.resolve_commit(checkout, base))
    return cast(git.Commit, git.merge_base(checkout, base_commit, head))


def _rerun(path: str | None) -> junit.JUnit | None:  # None: no rerun file given
    if path is None:
        return None
    # Rule 5, as for the full run's file: read once, into bytes, which are
    # parsed. read_junit gives None for a rerun file that is missing or cannot
    # be read, which task 14 rejects: until then, cast tells pyright that the
    # bytes are there, and checks nothing at run time.
    data = cast(bytes, junit.read_junit(path))
    return junit.parse_junit(data, "rerun", path)


def _unmeasured_count(tests: list[selection.Test]) -> int:
    # match_tests gives an unmeasured test no row, and no node id either.
    unmeasured = [test for test in tests if test.row is None]
    return len(unmeasured)
