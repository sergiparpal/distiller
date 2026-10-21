from dataclasses import dataclass

from distiller.coverage_at_m import NodeId
from distiller.git import RepoPath
from distiller.junit import Pair, Result

# Pure rules, with no I/O: node ids turned into the pairs that pytest writes in
# the JUnit, and the run's tests matched to the rows of the coverage at M.


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
