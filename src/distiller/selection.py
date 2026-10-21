from dataclasses import dataclass

from distiller.coverage_at_m import NodeId
from distiller.git import RepoPath
from distiller.junit import Pair, Result


@dataclass(frozen=True)
class Test:  # a test of the run, after matching
    pair: Pair
    node_id: NodeId | None  # None when unmeasured
    row: frozenset[RepoPath] | None


def pair_of(node_id: NodeId) -> Pair:
    raise NotImplementedError


def match_tests(
    results: dict[Pair, Result], rows: dict[NodeId, frozenset[RepoPath]]
) -> list[Test]:
    raise NotImplementedError
