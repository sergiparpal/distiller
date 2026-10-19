from dataclasses import dataclass

from distiller.git import RepoPath

NodeId = str  # relative to pytest's rootdir


@dataclass(frozen=True)
class RawCoverage:  # as coverage's API gives it
    # recorded path -> node ids with a line in it
    nodes_by_file: dict[str, frozenset[NodeId]]
    # recorded paths with lines, none in a test context
    import_only_files: frozenset[str]
    # a line recorded for two node ids or more
    has_shared_line: bool


@dataclass(frozen=True)
class Matrix:  # mapped to M's tree
    # every node id in a test context, empty rows too
    rows: dict[NodeId, frozenset[RepoPath]]
    import_only: frozenset[RepoPath]


def read_coverage(path: str) -> RawCoverage:  # raises Rejected
    raise NotImplementedError


def node_id_of(context: str) -> NodeId | None:  # None: not a test context
    raise NotImplementedError


def build_matrix(raw: RawCoverage, tree: frozenset[RepoPath]) -> Matrix:
    raise NotImplementedError
