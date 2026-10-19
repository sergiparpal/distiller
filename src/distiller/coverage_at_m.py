import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

import coverage

from distiller import messages
from distiller.git import RepoPath

# Reads the coverage at M through coverage's public API, from a private copy of
# the file (D-002), and maps what it read to M's tree as rows and import-only
# files.

NodeId = str  # relative to pytest's rootdir

# What follows the last | of a test context.
_TEST_PHASES = frozenset({"setup", "run", "teardown"})


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
    # D-002: coverage writes to the file it reads, even when it is only asked
    # to read, so it reads a private copy and never the original. The
    # temporary directory, and the copy in it, are removed when the with block
    # ends, whether read_coverage returns or raises.
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / "coverage"
        _copy_original(path, copy)
        return _read_copy(copy, path)


def node_id_of(context: str) -> NodeId | None:  # None: not a test context
    # Split at the last |, since a node id can hold one, as in a parameter.
    if "|" not in context:
        return None
    node_id, phase = context.rsplit("|", 1)
    if phase not in _TEST_PHASES:
        return None
    return node_id


def build_matrix(raw: RawCoverage, tree: frozenset[RepoPath]) -> Matrix:
    rows = _rows(raw.nodes_by_file, tree)
    columns: set[RepoPath] = set()
    for row in rows.values():
        columns.update(row)
    import_only: set[RepoPath] = set()
    for recorded in raw.import_only_files:
        tree_path = _tree_path_of(recorded, tree)
        # A file outside the repository is not import-only, and neither is a
        # repository file that another of its recorded paths puts in a row.
        if tree_path is not None and tree_path not in columns:
            import_only.add(tree_path)
    return Matrix(rows=rows, import_only=frozenset(import_only))


def _copy_original(path: str, copy: Path) -> None:
    original = _read_original(path)
    if original is None:
        raise _unusable(path)
    # An error here, such as a full disk, is not the coverage file's: it
    # reaches cli as an unexpected failure.
    copy.write_bytes(original)


def _read_original(path: str) -> bytes | None:  # None: missing or cannot be read
    # Rule 3: the path must be a regular file before it is opened, since
    # opening a FIFO for reading waits until something opens it for writing.
    # is_file runs os.stat, which follows a symbolic link to what it points to.
    # This is the only place that opens the original, for reading only.
    try:
        if not Path(path).is_file():
            return None  # missing, or a directory, a FIFO or a device
        return Path(path).read_bytes()
    except OSError:
        return None  # the tool is not allowed to read it, or reading failed


def _read_copy(copy: Path, path: str) -> RawCoverage:
    data = coverage.CoverageData(basename=copy)
    try:
        return _read_data(data, path)
    except (coverage.CoverageException, sqlite3.Error):
        # Rule 3. coverage lets sqlite3's errors through when the copy already
        # holds a table named like one of its own, or when a query meets the
        # end of a file cut short. "from None" keeps a traceback from showing
        # the error, whose text can quote what the file holds.
        raise _unusable(path) from None
    finally:
        # coverage's connections to the copy, closed before it is removed.
        data.close()


def _read_data(data: coverage.CoverageData, path: str) -> RawCoverage:
    # Rule 3: read() before any query, since a file queried first loses its
    # contexts for good.
    data.read()
    measured_files = data.measured_files()
    if not measured_files:
        # Not a coverage data file. An empty file and an SQLite database of
        # something else read like this, once coverage has written its tables
        # into the copy.
        raise _unusable(path)
    nodes_by_file: dict[str, frozenset[NodeId]] = {}
    import_only_files: set[str] = set()
    has_shared_line = False
    for recorded in measured_files:
        # Rule 4: one query per measured file. Of its lines, only their node
        # ids are kept, and whether one of them has two node ids or more.
        contexts_by_line = data.contexts_by_lineno(recorded)
        node_ids = _node_ids_in_file(contexts_by_line)
        if node_ids:
            nodes_by_file[recorded] = node_ids
        elif contexts_by_line:
            import_only_files.add(recorded)  # lines, none in a test context
        # Once a file has a shared line, the other files' lines need no check.
        has_shared_line = has_shared_line or _has_shared_line(contexts_by_line)
    return RawCoverage(
        nodes_by_file=nodes_by_file,
        import_only_files=frozenset(import_only_files),
        has_shared_line=has_shared_line,
    )


def _node_ids_in_file(contexts_by_line: dict[int, list[str]]) -> frozenset[NodeId]:
    node_ids: set[NodeId] = set()
    for contexts in contexts_by_line.values():
        node_ids.update(_node_ids_of_line(contexts))
    return frozenset(node_ids)


def _has_shared_line(contexts_by_line: dict[int, list[str]]) -> bool:
    # A line recorded for two node ids or more. One test's setup, call and
    # teardown are one node id, and a context outside any test is none.
    return any(
        len(_node_ids_of_line(contexts)) > 1 for contexts in contexts_by_line.values()
    )


def _node_ids_of_line(contexts: list[str]) -> set[NodeId]:
    # The node ids of a line's test contexts; its other contexts add none.
    node_ids: set[NodeId] = set()
    for context in contexts:
        node_id = node_id_of(context)
        if node_id is not None:
            node_ids.add(node_id)
    return node_ids


def _rows(
    nodes_by_file: dict[str, frozenset[NodeId]], tree: frozenset[RepoPath]
) -> dict[NodeId, frozenset[RepoPath]]:
    rows: dict[NodeId, set[RepoPath]] = {}
    for recorded, node_ids in nodes_by_file.items():
        tree_path = _tree_path_of(recorded, tree)
        for node_id in node_ids:
            # Every node id gets a row, which stays empty if all its lines fall
            # in files outside the repository: those are in no row.
            if node_id not in rows:
                rows[node_id] = set()
            if tree_path is not None:
                rows[node_id].add(tree_path)
    return {node_id: frozenset(row) for node_id, row in rows.items()}


def _tree_path_of(recorded: str, tree: frozenset[RepoPath]) -> RepoPath | None:
    # The longest tree path that the recorded path equals or ends with right
    # after a /, compared case-sensitively. None: outside the repository.
    for candidate in _ends_after_a_slash(recorded):
        if candidate in tree:
            return candidate
    return None


def _ends_after_a_slash(recorded: str) -> list[str]:
    # The recorded path itself, then what follows each of its slashes, the
    # longest first: /work/src/tax.py gives /work/src/tax.py, work/src/tax.py,
    # src/tax.py and tax.py.
    segments = recorded.split("/")
    return ["/".join(segments[start:]) for start in range(len(segments))]


def _unusable(path: str) -> messages.Rejected:
    # The coverage file is missing, cannot be read or is not a coverage data
    # file. The rejection names it as given on the command line.
    return messages.Rejected(
        reason="unusable-input", input_name="coverage", subject=path
    )
