from dataclasses import dataclass

from distiller.coverage_at_m import Matrix, NodeId
from distiller.git import RepoPath
from distiller.junit import JUnit, Pair, Result

# Pure rules, with no I/O: node ids turned into the pairs that pytest writes in
# the JUnit, the run's tests matched to the rows of the coverage at M, the
# tests that the all-affected selector picks, each with its reasons, and the
# run's verdict, whether it is green, caught or missed, with the failures that
# the rerun file discards and the failed tests that the selection leaves out.


@dataclass(frozen=True)
class Test:  # a test of the run, after matching
    pair: Pair
    node_id: NodeId | None  # None when unmeasured
    row: frozenset[RepoPath] | None  # None when unmeasured


@dataclass(frozen=True)
class Reason:
    rule: str  # "covers", "floor", "unmeasured", "own file" or "conftest"
    path: RepoPath | None  # None only for "unmeasured"
    pattern: str | None = None  # only for "floor"


Selection = dict[Pair, frozenset[Reason]]  # selected tests only, never an empty set


@dataclass(frozen=True)
class Judgement:
    verdict: str  # "green", "caught" or "missed"
    not_reproduced: frozenset[Pair]
    failed_left_out: tuple[Test, ...]  # all measured, so node_id and row are set


def pair_of(node_id: NodeId) -> Pair:
    # The SPEC's pair rule, the one pytest's mangle_test_address follows to
    # name a test in the JUnit. The parameters, from the first [ on, stay
    # whole, so a :: or a / in them splits nothing. partition gives "" for the
    # [ and for the parameters when the node id has none.
    before_parameters, open_bracket, parameters = node_id.partition("[")
    names = before_parameters.split("::")
    # The first name is the file's path, the last one the function, and any
    # in between are classes. A node id with no :: before its parameters has
    # a single name, both the first and the last: as in pytest, its classname
    # is then empty and its name the dotted path, so the tests/test_report.py
    # of a collection error gives an empty classname and tests.test_report.
    names[0] = _dotted_path(names[0])
    classname = ".".join(names[:-1])
    name = names[-1] + open_bracket + parameters
    return (classname, name)


def match_tests(
    results: dict[Pair, Result], rows: dict[NodeId, frozenset[RepoPath]]
) -> list[Test]:
    # One Test for each pair in the run, whatever its result, and none for a
    # node id whose pair is not in the run. The tests are sorted by pair, by
    # classname and then name, as records sort pairs, so that the list does
    # not depend on the order of the JUnit's test cases.
    node_ids_by_pair = _node_ids_by_pair(rows)
    return [
        _test_of(pair, node_ids_by_pair.get(pair, []), rows) for pair in sorted(results)
    ]


def select(
    tests: list[Test],
    changed: list[RepoPath],
    hits: list[tuple[str, RepoPath]],
    rootdir: str,
) -> Selection:
    # Every test in the run that at least one rule picks, with every reason it
    # carries. The rules look at a test's row and node id, never at its
    # result, so which tests failed and how long they took change nothing.
    changed_paths = frozenset(changed)
    floor_reasons = _floor_reasons(hits)
    selection: Selection = {}
    for test in tests:
        reasons = floor_reasons | _reasons_of(test, changed_paths, rootdir)
        # A test that no rule picks is left out, so no set of reasons is empty.
        if reasons:
            selection[test.pair] = reasons
    return selection


def judge(
    full: JUnit, rerun: JUnit | None, tests: list[Test], selection: Selection
) -> Judgement:
    # A run is red when at least one test has a failure or an error that the
    # rerun file does not discard. A discarded failure is marked not
    # reproduced and is not one of the run's failed tests: it neither makes
    # the run caught nor is listed as left out.
    failures = _failures(full)
    not_reproduced = _not_reproduced(failures, rerun)
    failed = failures - not_reproduced
    return Judgement(
        verdict=_verdict(failed, selection),
        not_reproduced=not_reproduced,
        failed_left_out=_failed_left_out(failed, tests, selection),
    )


def no_column(changed: list[RepoPath], matrix: Matrix) -> list[RepoPath]:
    raise NotImplementedError


def import_only_paths(changed: list[RepoPath], matrix: Matrix) -> list[RepoPath]:
    raise NotImplementedError


def row_counts(
    rows: dict[NodeId, frozenset[RepoPath]], results: dict[Pair, Result]
) -> tuple[int, int]:
    raise NotImplementedError


def durations(full: JUnit, selection: Selection) -> tuple[int, int]:
    raise NotImplementedError


def _dotted_path(path: str) -> str:
    # Each / turned into a . and the final .py dropped: tests/test_tax.py
    # gives tests.test_tax, while docs/tax.txt, a text file's doctest, gives
    # docs.tax.txt.
    return path.replace("/", ".").removesuffix(".py")


def _node_ids_by_pair(
    rows: dict[NodeId, frozenset[RepoPath]],
) -> dict[Pair, list[NodeId]]:
    # One direction only: each node id is turned into its pair, and a pair is
    # never turned back into a node id, since the rule loses information:
    # tests/v1.2/test_x.py::test_m and tests/v1/2/test_x.py::test_m have the
    # same pair. Every node id counts, one with an empty row too: Matrix.rows
    # keeps it because it still counts among the node ids of its pair.
    node_ids_by_pair: dict[Pair, list[NodeId]] = {}
    for node_id in rows:
        pair = pair_of(node_id)
        if pair not in node_ids_by_pair:
            node_ids_by_pair[pair] = []
        node_ids_by_pair[pair].append(node_id)
    return node_ids_by_pair


def _test_of(
    pair: Pair, node_ids: list[NodeId], rows: dict[NodeId, frozenset[RepoPath]]
) -> Test:
    # node_ids: those whose pair is the test's. The test is measured only when
    # there is exactly one and its row is not empty.
    if len(node_ids) != 1:
        # No node id has its pair, as for a new or a renamed test, or more
        # than one has, and the JUnit cannot tell them apart: unmeasured.
        return Test(pair=pair, node_id=None, row=None)
    node_id = node_ids[0]
    row = rows[node_id]
    if not row:
        # All of its node id's lines fell in files outside the repository, and
        # an empty row is no row: unmeasured.
        return Test(pair=pair, node_id=None, row=None)
    return Test(pair=pair, node_id=node_id, row=row)


def _floor_reasons(hits: list[tuple[str, RepoPath]]) -> frozenset[Reason]:
    # floor X (P) for each floor pattern X and changed path P that match,
    # which every test carries. A hit given twice, by a pattern written twice
    # or a default one written again in the configuration, is one reason.
    return frozenset(
        Reason(rule="floor", path=path, pattern=pattern) for pattern, path in hits
    )


def _reasons_of(test: Test, changed: frozenset[RepoPath], rootdir: str) -> set[Reason]:
    # The four rules besides the floor's, which look at the test itself:
    # unmeasured and covers at its row, own file and conftest at its node id.
    reasons: set[Reason] = set()
    if test.row is None:
        reasons.add(Reason(rule="unmeasured", path=None))
    else:
        reasons.update(_covers_reasons(test.row, changed))
    # An unmeasured test has no node id, since a pair is never turned back
    # into one, so own file and conftest never pick it.
    if test.node_id is not None:
        test_file = _file_in(test.node_id)
        reasons.update(_own_file_reasons(test_file, changed, rootdir))
        reasons.update(_conftest_reasons(test_file, changed, rootdir))
    return reasons


def _covers_reasons(
    row: frozenset[RepoPath], changed: frozenset[RepoPath]
) -> list[Reason]:
    # covers P for each changed path P in the test's row.
    return [Reason(rule="covers", path=path) for path in row & changed]


def _file_in(node_id: NodeId) -> str:
    # The file in a node id, what comes before its first ::, relative to
    # pytest's rootdir as the node id is: tests/test_x.py::test_m[a::b] gives
    # tests/test_x.py.
    return node_id.partition("::")[0]


def _own_file_reasons(
    test_file: str, changed: frozenset[RepoPath], rootdir: str
) -> list[Reason]:
    # own file P when P, the test's file, is a changed path.
    path = _from_repository_root(test_file, rootdir)
    if path not in changed:
        return []
    return [Reason(rule="own file", path=path)]


def _conftest_reasons(
    test_file: str, changed: frozenset[RepoPath], rootdir: str
) -> list[Reason]:
    # conftest P for each conftest.py that is a changed path, in the test
    # file's directory or in one above it, up to pytest's rootdir. Nothing
    # looks at the disk: a conftest.py counts only as a changed path.
    paths = [
        _from_repository_root(conftest, rootdir)
        for conftest in _conftests_up_to_rootdir(test_file)
    ]
    return [Reason(rule="conftest", path=path) for path in paths if path in changed]


def _conftests_up_to_rootdir(test_file: str) -> list[str]:
    # The conftest.py of each directory from pytest's rootdir down to the test
    # file's own, relative to the rootdir as the test file is:
    # tests/api/test_orders.py gives conftest.py, tests/conftest.py and
    # tests/api/conftest.py.
    directories = test_file.split("/")[:-1]  # the file's own name left out
    conftests = ["conftest.py"]  # the rootdir's
    directory = ""
    for name in directories:
        directory += name + "/"
        conftests.append(directory + "conftest.py")
    return conftests


def _from_repository_root(path: str, rootdir: str) -> RepoPath:
    # path: relative to pytest's rootdir, as node ids are. The rootdir is ""
    # for the repository root, and has no empty or . segment, as cli leaves it.
    if rootdir == "":
        return path
    return rootdir + "/" + path


def _failures(full: JUnit) -> frozenset[Pair]:
    # The tests with a failure or an error in the full run. A skipped test did
    # not fail, so a run whose only results that are not passes are skips has
    # no failure.
    return frozenset(pair for pair, result in full.results.items() if result.failed)


def _not_reproduced(failures: frozenset[Pair], rerun: JUnit | None) -> frozenset[Pair]:
    # The failures that the rerun file discards. Only a pass there discards
    # one, so with no rerun file none is discarded. Only the full run's
    # failures are looked up in it, so the result there of a test that did not
    # fail in the full run is ignored.
    if rerun is None:
        return frozenset()
    return frozenset(pair for pair in failures if _passed_in(rerun, pair))


def _passed_in(rerun: JUnit, pair: Pair) -> bool:
    # A test passes in the rerun file only if none of its test cases there has
    # a failure, an error or a skipped, which is what Result.passed says. A
    # test that failed again, was skipped or is missing from the file, as the
    # tests of a file that pytest could not collect are, did not pass.
    result = rerun.results.get(pair)
    return result is not None and result.passed


def _verdict(failed: frozenset[Pair], selection: Selection) -> str:
    # A run with no failed test is green. A red one is caught when the
    # selection holds at least one of its failed tests, whatever the rule that
    # picked it, and missed otherwise.
    if not failed:
        return "green"
    if any(pair in selection for pair in failed):
        return "caught"
    return "missed"


def _failed_left_out(
    failed: frozenset[Pair], tests: list[Test], selection: Selection
) -> tuple[Test, ...]:
    # The failed tests that the selection does not hold, whether or not the
    # run was caught, as their Tests, which hold the node id and the row that
    # a record lists; match_tests gives a Test for every pair in the run.
    # Rule 8: sorted where they are built, by pair, classname and then name
    # by code point, whatever the order of the tests.
    tests_by_pair = {test.pair: test for test in tests}
    return tuple(
        tests_by_pair[pair] for pair in sorted(failed) if pair not in selection
    )
