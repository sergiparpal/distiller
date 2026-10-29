import hashlib
import sys
from dataclasses import dataclass

from distiller import coverage_at_m, floor, git, junit, messages, records, selection

# The evaluate command, as "How a run goes" in the SPEC tells it: the record
# file, read before any input; the run's key, from the full run's JUnit bytes
# and H; the warning for a run already recorded; the inputs, taken in the SPEC's
# problem order, where the first problem rejects the run; the evaluated record,
# built by the functions of the technical sheet's Interfaces and appended with
# nothing printed; the rejected record, appended unless the record file already
# holds it, and its message; and the exit code. Every text that it writes to
# stderr comes from messages.


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
    # file that is missing or cannot be read, which step 3 rejects where the
    # problem order puts it.
    full_run_data = junit.read_junit(args.junit)
    # Rule 2: H is resolved once, here, and every later git command names
    # commits by their full ids. resolve_commit gives None for an H that names
    # no commit, as any H does at a path with no git repository, which step 3
    # rejects.
    head_commit = git.resolve_commit(args.checkout, args.head)
    key = records.RunKey(
        head=_key_head(args.head, head_commit),
        junit_sha256=_sha256_of(full_run_data),
    )
    if records.has_evaluated(recorded, key):
        print(messages.already_recorded(key.head, key.junit_sha256), file=sys.stderr)
        return 0
    try:
        record = _evaluated_record(args, key, head_commit, full_run_data)
    except messages.Rejected as error:
        # Step 5, whether a check of step 3 or a reader raised it. The record
        # goes before the message: if the append fails, its OSError reaches
        # cli as any other failure, exit 1, and no message names the input.
        _append_rejection(args, recorded, key, error)
        print(messages.rejection(error), file=sys.stderr)
        return 3
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


def _key_head(head_as_given: str, head_commit: git.Commit | None) -> str:
    # The key's head: H's full commit id, or H as given if git finds no commit
    # by that name at the checkout's path, as at a path with no repository.
    if head_commit is None:
        return head_as_given
    return head_commit


def _sha256_of(full_run_data: bytes | None) -> str | None:
    # The key's junit_sha256, None if there is no full-run JUnit file or it
    # cannot be read. Hashing parses nothing (Rule 5).
    if full_run_data is None:
        return None
    return hashlib.sha256(full_run_data).hexdigest()


def _evaluated_record(
    args: RunArgs,
    key: records.RunKey,
    head_commit: git.Commit | None,
    full_run_data: bytes | None,
) -> records.EvaluatedRecord:  # raises Rejected
    # Step 3: the inputs in the SPEC's problem order, one call per check, each
    # giving a value or raising Rejected, so that the first problem decides the
    # record and no check, git command or read comes after it: the checkout, a
    # git checkout and then not shallow; H; the base branch; the coverage; the
    # full run's JUnit; the rerun file; and the floor configuration.
    _check_checkout(args.checkout)
    _check_not_shallow(args.checkout)
    head = _checked_head(head_commit, args.head)
    merge_base = _merge_base(args.checkout, args.base, head)
    # The coverage: M, resolved once (Rule 2), then the file, read in full,
    # then M's ancestry, then the shared lines.
    coverage_commit = _coverage_commit(args.checkout, args.coverage_commit)
    raw = coverage_at_m.read_coverage(args.coverage)
    _check_ancestry(args.checkout, coverage_commit, merge_base, args.coverage_commit)
    _check_shared_lines(raw, args.coverage)
    # The full run's JUnit: parsed, then checked for a collection error.
    full = _full_run(full_run_data, args.junit)
    _check_no_collection_error(full, args.junit)
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


def _check_checkout(checkout: str) -> None:  # raises Rejected
    # A path that is not inside a work tree: a directory with no repository,
    # a repository with no work tree, a path that does not exist or a file.
    if not git.is_checkout(checkout):
        raise _unusable(input_name="checkout", subject=checkout)


def _check_not_shallow(checkout: str) -> None:  # raises Rejected
    # A shallow checkout, as git rev-parse --is-shallow-repository reports it,
    # even one that has every commit the run names: a shallow clone usually
    # lacks M and the merge-base, so git cannot tell whether M is an ancestor.
    if git.is_shallow(checkout):
        raise messages.Rejected(
            reason="missing-history", input_name="checkout", subject=checkout
        )


def _checked_head(head_commit: git.Commit | None, head_as_given: str) -> git.Commit:
    # H, as step 2 resolved it: None if it names no commit.
    if head_commit is None:
        raise _unusable(input_name="head", subject=head_as_given)
    return head_commit


def _merge_base(checkout: str, base: str, head: git.Commit) -> git.Commit:
    # The base branch: B, the commit it stands for, resolved once (Rule 2), then
    # the merge-base of B and H, in that order, from their full commit ids:
    # with several best common ancestors, the order can change which one git
    # prints (note 63). A base that names no commit cannot be used, and
    # neither can one whose commit shares no history with H, so that the two
    # have no merge-base.
    base_commit = git.resolve_commit(checkout, base)
    if base_commit is None:
        raise _unusable(input_name="base", subject=base)
    merge_base = git.merge_base(checkout, base_commit, head)
    if merge_base is None:
        raise _unusable(input_name="base", subject=base)
    return merge_base


def _coverage_commit(checkout: str, coverage_commit: str) -> git.Commit:
    # M, resolved once (Rule 2), before the coverage file is read. An M that
    # names no commit makes the coverage unusable, and the message names M as
    # given, not the file.
    commit = git.resolve_commit(checkout, coverage_commit)
    if commit is None:
        raise _unusable(input_name="coverage", subject=coverage_commit)
    return commit


def _check_ancestry(
    checkout: str,
    coverage_commit: git.Commit,
    merge_base: git.Commit,
    coverage_commit_as_given: str,
) -> None:  # raises Rejected
    # M must be the merge-base or one of its ancestors. git compares the two by
    # their full commit ids (Rule 2), and the message names M as given.
    if not git.is_ancestor(checkout, coverage_commit, merge_base):
        raise messages.Rejected(
            reason="coverage-not-ancestor",
            input_name="coverage",
            subject=coverage_commit_as_given,
        )


def _check_shared_lines(
    raw: coverage_at_m.RawCoverage, path: str
) -> None:  # raises Rejected
    # Coverage in which no line was recorded for more than one test, as the
    # sysmon core leaves it: the data file does not say which core recorded
    # it. The message names the coverage file.
    if not raw.has_shared_line:
        raise messages.Rejected(
            reason="no-shared-lines", input_name="coverage", subject=path
        )


def _full_run(full_run_data: bytes | None, path: str) -> junit.JUnit:
    # The bytes that step 2 read, None if the file is missing or cannot be
    # read, parsed here: parse_junit raises Rejected for a file that declares
    # an entity, is not well-formed, has a test case that cannot be used or
    # holds pytest's internal error.
    if full_run_data is None:
        raise _unusable(input_name="junit", subject=path)
    return junit.parse_junit(full_run_data, "junit", path)


def _check_no_collection_error(full: junit.JUnit, path: str) -> None:  # raises Rejected
    # A full run's JUnit that holds a collection error: evaluated, the run would
    # always count as caught, since the error's own test case is selected as
    # unmeasured. A rerun file that holds one is used (note 39).
    if full.has_collection_error:
        raise messages.Rejected(
            reason="collection-error", input_name="junit", subject=path
        )


def _rerun(path: str | None) -> junit.JUnit | None:  # None: no rerun file given
    if path is None:
        return None
    # Rule 5, as for the full run's file: read once, into bytes, which are
    # parsed. read_junit gives None for a rerun file that is missing or cannot
    # be read.
    data = junit.read_junit(path)
    if data is None:
        raise _unusable(input_name="rerun", subject=path)
    return junit.parse_junit(data, "rerun", path)


def _unusable(input_name: str, subject: str) -> messages.Rejected:
    # An input that cannot be used. The message names subject, a path or a
    # name as given on the command line.
    return messages.Rejected(
        reason="unusable-input", input_name=input_name, subject=subject
    )


def _append_rejection(
    args: RunArgs,
    recorded: list[records.Record],
    key: records.RunKey,
    error: messages.Rejected,
) -> None:
    # The rejected record is appended unless the record file, as step 2 read
    # it, already holds one with the run's key, reason and input, whatever its
    # pr, which is not part of the key.
    if records.has_rejected(recorded, key, error.reason, error.input_name):
        return
    record = records.RejectedRecord(
        key=key, pr=args.pr, reason=error.reason, input_name=error.input_name
    )
    records.append_record(args.records, record)


def _unmeasured_count(tests: list[selection.Test]) -> int:
    # match_tests gives an unmeasured test no row, and no node id either.
    unmeasured = [test for test in tests if test.row is None]
    return len(unmeasured)
