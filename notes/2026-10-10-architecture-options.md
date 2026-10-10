# Architecture options for Slice 1

Phase 2, step 1. Read: `docs/SPEC.md`, whole; for context, the notes in `notes/` and `docs/C6-destilador-revisada.md`. No code was written and `docs/SPEC.md` was not edited.

**[VERIFY]** marks an API or behaviour of coverage, pytest or git (and of defusedxml, which the SPEC also relies on) that I have not checked. Every other claim about those tools was checked in one of two ways, listed in §6: *read* in the installed source of coverage 7.16.2, pytest 9.1.1 and defusedxml 0.7.1, the spike's versions, found in the local uv cache; or *run* with git 2.43.0 on this repository, read-only commands only.

The three options implement the same behaviour: none drops or adds anything the SPEC says. They differ in how the modules are cut, where the problem order lives, and how the [core] examples can be tested.

The twelve [core] examples, numbered in the SPEC's order and used throughout:

| # | Given | "then", in short |
|---|---|---|
| K1 | missed run, no rerun file | exactly the SPEC's line is appended |
| K2 | test_render passes in the rerun file | `green`, `rerun_given` true, `not_reproduced` and an empty `failed_left_out` |
| K3 | run already recorded | file unchanged, a warning naming the key, exit 0 |
| K4 | coverage at a commit that is not an ancestor | the exact rejected line, a message naming M, exit 3 |
| K5 | shallow checkout | `missing-history` and `checkout`, a message naming the checkout, exit 3 |
| K6 | JUnit or rerun file declaring an entity | no entity resolved, `unsafe-xml`, a message naming the file and quoting nothing, exit 3 |
| K7 | valid inputs | exit 0 whatever the verdict |
| K8 | an input the evaluation cannot use | `unusable-input` and that input, a message naming it, exit 3 |
| K9 | collection error | `collection-error` and `junit`, a message naming the JUnit file, exit 3 |
| K10 | the K8 run again, same inputs | file unchanged, the message names the coverage file again, exit 3 |
| K11 | the K8 run again, with its coverage | evaluated, appended after the rejected record, exit 0 |
| K12 | no line shared by two tests | `no-shared-lines` and `coverage`, the `ctrace` advice, exit 3 |

## 0. What the three options share

### 0.1 Command line

The same in A, B and C.

```
python -m distiller evaluate --pr N --head REV --base REV
    --coverage PATH --coverage-commit REV --junit PATH [--rerun PATH]
    [--rootdir DIR] [--floor-config PATH] --records PATH [--checkout DIR]

python -m distiller report RECORD_FILE [RECORD_FILE ...]
```

| Option | Meaning |
|---|---|
| `--pr N` | the pull request's number: ASCII digits, above 0 |
| `--head REV` | H as given; on `pull_request`, `$GITHUB_SHA` |
| `--base REV` | the base branch or a commit. A bare `main` resolves only through `refs/heads/main`, `refs/remotes/main` and `refs/remotes/main/HEAD` (*man gitrevisions*), so a checkout that has the base only as `origin/main` needs `origin/main` or the base commit |
| `--coverage PATH` | the coverage data file recorded at M |
| `--coverage-commit REV` | M as given |
| `--junit PATH` | the full run's JUnit XML |
| `--rerun PATH` | the rerun file, if any |
| `--rootdir DIR` | pytest's rootdir, relative to the repository root; default the root. Absolute or with `..`: usage error |
| `--floor-config PATH` | the floor configuration, if any |
| `--records PATH` | the record file, read first and appended to last |
| `--checkout DIR` | the git checkout; default `.` |

Exit codes. `evaluate`: 0 when the run is evaluated, whatever the verdict, or already recorded; 3 when it is rejected; 2 for a usage error; 1 when the record file holds a line that is not a record, and for any other failure. `report`: writes the report to stdout and exits 0; 1 for a line that is not a record or any other failure; 2 for a usage error.

A missing argument is a usage error and appends nothing; a missing file is a rejection. argparse runs with `allow_abbrev=False`, so `--cov` is never taken for `--coverage`. Choosing M, "the newest recorded M that is the merge-base or one of its ancestors", stays outside the tool, as the SPEC has it: it is an input.

Packaging is open. `python -m distiller` from a pinned checkout of this repository needs nothing more; installing the tool as a package needs a build backend, which Constraints does not list.

### 0.2 Data model

Frozen dataclasses, the only decorator in the code: no metaclasses, registries, `getattr` dispatch or dynamic imports. Python names use `input_name` where the record's key is `input`, so as not to shadow the builtin.

```python
Pair = tuple[str, str]  # (classname, name), as the JUnit names a test
NodeId = str            # "tests/test_tax.py::test_vat", relative to pytest's rootdir
RepoPath = str          # "src/shop/tax.py": "/"-separated, from the repository root
Commit = str            # a full commit id

@dataclass(frozen=True)
class RunArgs:          # the evaluate command's inputs, as given
    pr: int
    head: str
    base: str
    coverage: str
    coverage_commit: str
    junit: str
    rerun: str | None
    rootdir: str        # "" for the repository root
    floor_config: str | None
    records: str
    checkout: str

@dataclass(frozen=True)
class RunKey:
    head: str                      # H's full commit id, or H as given
    junit_sha256: str | None

@dataclass(frozen=True)
class Result:                      # one pair in one JUnit file, its cases merged
    failed: bool                   # some case has a failure or an error
    passed: bool                   # no case has a failure, an error or a skip
    time_ms: int                   # sum of the cases' times, each rounded half up

@dataclass(frozen=True)
class JUnit:
    results: dict[Pair, Result]
    has_collection_error: bool

@dataclass(frozen=True)
class RawCoverage:                 # the coverage at M as the API gives it
    nodes_by_file: dict[str, frozenset[NodeId]]  # recorded path -> node ids with a line in it
    import_only_files: frozenset[str]            # recorded paths with lines, none in a test
    has_shared_line: bool                        # some line recorded for two node ids or more

@dataclass(frozen=True)
class Matrix:                      # the coverage at M, mapped to M's tree
    rows: dict[NodeId, frozenset[RepoPath]]
    import_only: frozenset[RepoPath]

@dataclass(frozen=True)
class Test:                        # a test of the run, after matching
    pair: Pair
    node_id: NodeId | None         # None when unmeasured
    row: frozenset[RepoPath] | None

@dataclass(frozen=True)
class Reason:
    rule: str                      # "covers", "floor", "unmeasured", "own file" or "conftest"
    path: RepoPath | None          # None only for "unmeasured"
    pattern: str | None = None     # only for "floor"

Selection = dict[Pair, frozenset[Reason]]  # selected tests only, never an empty set

@dataclass(frozen=True)
class Judgement:
    verdict: str                   # "green", "caught" or "missed"
    not_reproduced: frozenset[Pair]
    failed_left_out: tuple[Test, ...]  # all measured, so node_id and row are set

@dataclass(frozen=True)
class Rejection:
    reason: str
    input_name: str
    message: str                   # paths and names as given; nothing read from a file

@dataclass(frozen=True)
class EvaluatedRecord:             # the SPEC's fields, in its order
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

@dataclass(frozen=True)
class RejectedRecord:
    key: RunKey
    pr: int
    reason: str
    input_name: str

Record = EvaluatedRecord | RejectedRecord
```

### 0.3 Rules that hold in every option

These follow from the SPEC or from what the libraries do, so no option gets to choose them.

1. **Dependencies.** One module imports `coverage` and one imports `defusedxml`. git runs only through `subprocess.run` with an argument list, never a shell. Everything else is the standard library.
2. **Git names.** H, the base and M are each resolved once with `git rev-parse --verify --quiet --end-of-options NAME^{commit}`. Every other git command gets full commit ids only, so nothing given on the command line reaches git where it could be read as an option. Paths come from `-z` output, decoded with `os.fsdecode`, Python's own decoding for file names. The commands are listed in §6; all of them are read-only.
3. **The coverage reader never touches its input.** `CoverageData` writes to its file in two cases (read). `measured_contexts()`, `contexts_by_lineno()`, `lines()`, `arcs()` and `set_query_context(s)()` start with `_start_using()`, which deletes the data file with `os.remove` unless `read()` ran first on an existing file, and the next connection then creates a new, empty one at the same path. And `read()` on an SQLite file with no `coverage_schema` table writes coverage's schema into it. So the reader (a) rejects a path that is not a regular file; (b) rejects a file whose first 16 bytes are not SQLite's header, which catches the 0-byte file that coverage would otherwise initialise [VERIFY: that SQLite opens a 0-byte file as an empty database]; (c) copies the file into a temporary directory and reads the copy, which costs a copy of M's file; (d) calls `read()` before any query; (e) turns any `coverage.CoverageException`, the public base class, into `unusable-input`.
4. **Rows from the public API.** One `contexts_by_lineno(f)` per measured file. Each context is split at its last `|`; per recorded file, the reader keeps the node ids with a line in it, and a line with two node ids or more sets `has_shared_line`. This is the only step whose time and memory at 10,000 tests and 2,000 files are unknown [VERIFY], and it sits behind one function in every option, so changing how it reads changes nothing else. If it misses the limit, batching contexts with `set_query_contexts()` bounds memory but not time [VERIFY].
5. **JUnit.** The file is read once into bytes: the same bytes give `junit_sha256` and are parsed, and hashing parses nothing. Parsing uses `defusedxml.ElementTree.fromstring` at its defaults: entities and external references forbidden, DOCTYPE allowed, since the SPEC rejects entity declarations, not DTDs. `EntitiesForbidden` and `ExternalReferenceForbidden` become `unsafe-xml`; `ParseError` becomes `unusable-input`. Each `time` goes through `Decimal(text).quantize(Decimal("0.001"), ROUND_HALF_UP)`, never through a float.
6. **Messages.** Built from the command line's values and fixed text only, never from an exception's text: coverage's `DataError` carries the schema version it read from the file, and defusedxml's exceptions carry the entity's name and system id (read). An unexpected exception is caught at the top, printed as one fixed line naming its class, and exits 1.
7. **Records.** `encode` builds a dict in the SPEC's key order and writes `json.dumps(obj, separators=(",", ":"))` followed by `\n`; its default `ensure_ascii` gives exactly the SPEC's escapes (run: DEL as `\u007f`, lowercase hex, surrogate pairs). `decode` checks that the line is ASCII, parses it, checks keys, their order and exact types (`type(x) is int`, so that `true` does not pass for `1`), rebuilds the record and requires `encode(record) == line`. That round trip is what makes "byte for byte what the tool would write for some run" checkable.
8. **Determinism.** Every list that reaches a record or the report is sorted where it is built; no set order, clock or environment value reaches the output. The append is one write of the whole line, to a file opened for appending, created if missing.

## 1. Option A: straight line, the simplest that meets the spec

One module per input, each reading and interpreting its input and raising `Rejected` when it cannot use it. `evaluate.py` calls them in the SPEC's problem order, one statement per check, then computes the record with small pure functions. The types of §0.2 live next to the function that creates them; there is no `model.py`.

| Module | Does | Tier | [core] "then"s it produces |
|---|---|---|---|
| `__main__.py` | calls `cli.main` | periphery | none |
| `cli.py` | arguments; both commands; append and exit decisions; stderr; the catch-all | core | K1–K12 |
| `git.py` | the seven git queries | core | K1–K6, K8–K12 |
| `coverage_at_m.py` | reads the coverage at M and maps it to M's tree; the only `coverage` import | core | K1, K8, K10–K12 |
| `junit.py` | parses a JUnit or rerun file; the only `defusedxml` import | core | K1, K2, K6, K8, K9, K11 |
| `floor.py` | the patterns and their matching | core | K1, K8, K11 |
| `evaluate.py` | run key; problem order; matching, selection, verdict, record fields | core | K1–K6, K8–K12 |
| `records.py` | encode, decode, read the record file, append | core | K1–K6, K8–K12 |
| `report.py` | dedupe, figures, bound, text | medium | none |

```python
# records.py
class Rejected(Exception):
    def __init__(self, reason: str, input_name: str, message: str) -> None: ...
class NotARecord(Exception):
    def __init__(self, path: str, line_number: int) -> None: ...
def encode(record: Record) -> bytes: ...
def decode(line: bytes) -> Record | None: ...              # None: not a record
def read_record_file(path: str) -> list[Record]: ...        # [] if missing; raises NotARecord
def has_evaluated(records: list[Record], key: RunKey) -> bool: ...
def has_rejected(records: list[Record], key: RunKey, reason: str, input_name: str) -> bool: ...
def append_record(path: str, record: Record) -> None: ...

# git.py: each runs `git -C checkout ...`
def is_checkout(checkout: str) -> bool: ...
def is_shallow(checkout: str) -> bool: ...                 # "true" on a shallow clone [VERIFY]
def resolve_commit(checkout: str, name: str) -> Commit | None: ...
def merge_base(checkout: str, a: Commit, b: Commit) -> Commit | None: ...  # None: no common history [VERIFY]
def is_ancestor(checkout: str, ancestor: Commit, descendant: Commit) -> bool: ...
def changed_paths(checkout: str, old: Commit, new: Commit) -> list[RepoPath]: ...
def tree_files(checkout: str, commit: Commit) -> frozenset[RepoPath]: ...

# coverage_at_m.py
def read_coverage(path: str) -> RawCoverage: ...           # raises Rejected("unusable-input", "coverage", ...)
def node_id_of(context: str) -> NodeId | None: ...
def build_matrix(raw: RawCoverage, tree: frozenset[RepoPath]) -> Matrix: ...

# junit.py
def parse_junit(data: bytes, path: str, input_name: str) -> JUnit: ...  # raises Rejected("unsafe-xml" or "unusable-input", ...)

# floor.py
DEFAULT_PATTERNS: tuple[str, ...]
def read_floor(path: str | None) -> tuple[str, ...]: ...   # defaults, then the file's; raises Rejected(..., "floor", ...)
def matches(pattern: str, path: RepoPath) -> bool: ...
def floor_hits(patterns: tuple[str, ...], changed: list[RepoPath]) -> list[tuple[str, RepoPath]]: ...

# evaluate.py
def run_key(args: RunArgs, junit_bytes: bytes | None) -> RunKey: ...
def evaluate(args: RunArgs, key: RunKey, junit_bytes: bytes | None) -> EvaluatedRecord: ...  # raises Rejected
def pair_of(node_id: NodeId) -> Pair: ...
def match_tests(results: dict[Pair, Result], rows: dict[NodeId, frozenset[RepoPath]]) -> list[Test]: ...
def select(tests: list[Test], changed: list[RepoPath],
           hits: list[tuple[str, RepoPath]], rootdir: str) -> Selection: ...
def judge(full: JUnit, rerun: JUnit | None, tests: list[Test], selection: Selection) -> Judgement: ...

# report.py
def report(paths: list[str]) -> str: ...                   # raises NotARecord
def clopper_pearson_upper(k: int, n: int) -> float | None: ...  # None when n is 0

# cli.py
def main(argv: list[str] | None = None) -> int: ...
```

How a run goes:

1. `cli.main` parses the arguments (usage error: exit 2) and reads the record file (`NotARecord`: a message naming the file and the line number, exit 1).
2. It reads the JUnit file's bytes, if the file exists, and gets the key from `evaluate.run_key`. If an evaluated record has that key, it warns, naming the key, and exits 0.
3. `evaluate.evaluate` runs the checks in the SPEC's order: not a checkout, then shallow; H; the base, then the merge-base; M; the coverage file, read in full; ancestry; shared lines; the JUnit file (missing; unsafe or malformed, whichever the parser meets first; collection error); the rerun file; the floor configuration. Each check is one call that returns a value or raises `Rejected`.
4. It then takes the diff and M's tree, builds the matrix, matches the tests, selects, judges and returns the record.
5. `cli.main` appends it and exits 0. On `Rejected`, it appends the rejected record unless `has_rejected` finds it there, prints the message and exits 3.

The coverage file is read in full before the ancestry check, in all three options: the order puts "unusable" before `coverage-not-ancestor`, and a file can turn out unusable halfway through its read. A run rejected for ancestry pays for that read.

Why nothing simpler: folding the readers into `evaluate.py`, or everything into one file, would put the coverage, defusedxml and git calls next to the selection rules. No rule could then be tested without a repository, and the two imports that carry the SPEC's dependency and safety rules would no longer sit in one module each.

Cost:

- **Testing.** Easy: `pair_of`, `matches`, `select`, `judge`, `encode` and `decode` are pure, so the Selection, Verdict and Invariant examples are tests over literals. Hard: everything that crosses `evaluate()`, which is every [core] example and the problem order with its combinations, needs a git repository, a coverage file and a JUnit file in `tmp_path`, run through `cli.main`. The coverage file can be written with `CoverageData.set_context()` and `add_lines()` (read). A failing [core] test points at the whole pipeline.
- **Understanding.** Easy: `evaluate()` reads like the SPEC's list of problems; nine files and no layers. Hard: four modules (`evaluate`, `coverage_at_m`, `junit`, `floor`) choose reasons, inputs and messages, so "quotes nothing" has to be reviewed in four places.
- **Changing.** Easy: a new rejection is one `raise` where the problem is found. Hard: a change to a selection rule edits the file that also holds the problem order and the record; renaming a reason or an input touches every reader; later slices (the solver, file tracing) grow `evaluate.py`.

## 2. Option B: load, then compute

The modules that touch the outside world form a shell: `cli`, `git`, `coverage_io`, `load` and `record_file`. `load.load_run` walks the problem order with early returns and gives back either a `RunInputs`, with every input checked and parsed, or a `Rejection` value. Below it, pure modules (no file, no subprocess, no coverage) turn a `RunInputs` into an `EvaluatedRecord` and its bytes; they never import the shell. Readers raise their own small exceptions, and only `load.py` knows the reason and input vocabulary and writes rejection messages.

| Module | Does | Tier | [core] "then"s it produces |
|---|---|---|---|
| `__main__.py` | calls `cli.main` | periphery | none |
| `model.py` | the types of §0.2 and `RunInputs`; no code | periphery | none |
| `cli.py` | arguments; runs the steps; append and exit; stderr; the catch-all | core | K1–K12 |
| `git.py` | as in A | core | K1–K6, K8–K12 |
| `coverage_io.py` | reads the coverage at M into `RawCoverage`; the only `coverage` import | core | K1, K8, K10–K12 |
| `load.py` | run key; problem order; reasons, inputs, messages; `RunInputs` | core | K1–K6, K8–K12 |
| `record_file.py` | reads the record file; appends a line | core | K1–K6, K8–K12 |
| `junit.py` | pure: bytes to `JUnit`; the only `defusedxml` import | core | K1, K2, K6, K8, K9, K11 |
| `floor.py` | pure: text to patterns; matching | core | K1, K8, K11 |
| `matrix.py` | pure: `RawCoverage` and M's tree to `Matrix` | core | K1, K11 |
| `selection.py` | pure: node id to pair; matching; selection with reasons | core | K1, K11 |
| `verdict.py` | pure: red, caught, missed; not reproduced; left out | core | K1, K2, K11 |
| `compute.py` | pure: `RunInputs` to `EvaluatedRecord` | core | K1, K2, K11 |
| `record.py` | pure: encode, decode, `has_evaluated`, `has_rejected` | core | K1–K6, K8–K12 |
| `report.py` | pure: records to summary to text; the bound | medium | none |

```python
# model.py, besides §0.2
@dataclass(frozen=True)
class RunInputs:                   # everything the evaluation needs, already checked
    pr: int
    key: RunKey
    merge_base: Commit
    coverage_commit: Commit
    changed: tuple[RepoPath, ...]
    tree: frozenset[RepoPath]      # M's tree
    coverage: RawCoverage
    full: JUnit
    rerun: JUnit | None
    floor: tuple[str, ...]         # defaults, then the configuration's
    rootdir: str

# shell
# git.py: as in option A
# coverage_io.py
class UnusableCoverage(Exception): ...
def read_raw_coverage(path: str) -> RawCoverage: ...       # raises UnusableCoverage
# record_file.py
class NotARecord(Exception):
    def __init__(self, path: str, line_number: int) -> None: ...
def read_record_file(path: str) -> list[Record]: ...        # [] if missing; raises NotARecord
def append_line(path: str, line: bytes) -> None: ...
# load.py
def run_key(args: RunArgs) -> tuple[RunKey, bytes | None]: ...   # the key, and the JUnit bytes if any
def load_run(args: RunArgs, key: RunKey, junit_bytes: bytes | None) -> RunInputs | Rejection: ...

# pure core
# junit.py
class UnsafeXml(Exception): ...
class MalformedXml(Exception): ...
def parse_junit(data: bytes) -> JUnit: ...                 # raises UnsafeXml or MalformedXml
# floor.py
class InvalidPattern(Exception):
    def __init__(self, line_number: int) -> None: ...
DEFAULT_PATTERNS: tuple[str, ...]
def parse_floor_config(text: str) -> tuple[str, ...]: ...  # raises InvalidPattern
def matches(pattern: str, path: RepoPath) -> bool: ...
def floor_hits(patterns: tuple[str, ...], changed: tuple[RepoPath, ...]) -> list[tuple[str, RepoPath]]: ...
# matrix.py
def node_id_of(context: str) -> NodeId | None: ...
def build_matrix(raw: RawCoverage, tree: frozenset[RepoPath]) -> Matrix: ...
# selection.py
def pair_of(node_id: NodeId) -> Pair: ...
def match_tests(results: dict[Pair, Result], rows: dict[NodeId, frozenset[RepoPath]]) -> list[Test]: ...
def select(tests: list[Test], changed: tuple[RepoPath, ...],
           hits: list[tuple[str, RepoPath]], rootdir: str) -> Selection: ...
# verdict.py
def judge(full: JUnit, rerun: JUnit | None, tests: list[Test], selection: Selection) -> Judgement: ...
# compute.py
def evaluate(inputs: RunInputs) -> EvaluatedRecord: ...
# record.py
def encode(record: Record) -> bytes: ...
def decode(line: bytes) -> Record | None: ...
def has_evaluated(records: list[Record], key: RunKey) -> bool: ...
def has_rejected(records: list[Record], key: RunKey, reason: str, input_name: str) -> bool: ...
# report.py
@dataclass(frozen=True)
class Summary:                     # each figure with its numerator and denominator
    missed_prs: int
    red_prs: int
    red_runs: int
    selected_ms: int
    full_ms: int
    floor_prs: int
    no_column_prs: int
    evaluated_prs: int
    unmeasured: int
    tests: int
    with_row_not_in_run: int
    with_row: int
    red_runs_without_rerun: int
    not_reproduced: int
    left_out: tuple[EvaluatedRecord, ...]               # runs with failed tests left out, by key
    conflicts: tuple[tuple[RunKey, tuple[str, ...]], ...]  # key, record files
    rejected: tuple[tuple[str, str, int], ...]          # reason, input, keys
def summarize(entries: list[tuple[str, Record]]) -> Summary: ...   # (record file, record)
def render(summary: Summary) -> str: ...
def clopper_pearson_upper(k: int, n: int) -> float | None: ...

# cli.py
def main(argv: list[str] | None = None) -> int: ...
```

`coverage_io` imports `node_id_of` from `matrix`: the shell may import the core, never the other way round.

How a run goes:

1. `cli.main` parses the arguments and reads the record file, as in A.
2. `load.run_key` resolves H and hashes the JUnit bytes. If an evaluated record has the key, `cli` warns and exits 0.
3. `load.load_run` checks the inputs in the SPEC's order, one small function per input (`check_checkout`, `check_head`, `check_base`, `check_coverage`, `check_junit`, `check_rerun`, `check_floor`), each returning a value or a `Rejection`, and stops at the first problem.
4. A `Rejection` goes back to `cli`, which appends the rejected record unless `has_rejected` finds it there, prints the message and exits 3.
5. Otherwise `compute.evaluate(inputs)`, which is pure, gives the record; `cli` appends `record.encode(...)` and exits 0.

Cost:

- **Testing.** Easy: every Selection, Verdict, Invariant and Report example, and the exact bytes of K1 and K2, are pure tests that build a `RunInputs` from literals. The rejection examples (K4–K6, K8–K10, K12) test `load_run` against a real git repository, coverage file and XML file, which is where the behaviours of §0.3 live. Hard: the problem order still needs one repository state per problem, as in A, and K1 depends on both halves, so it needs a pure test and an end-to-end one.
- **Understanding.** Easy: one rule, only five modules do I/O; `load_run` is the SPEC's list of problems from top to bottom; reasons, inputs and every message are in one file. Hard: fifteen files, and `RunInputs` is a wide bundle to learn.
- **Changing.** Easy: selection and verdict changes stay in pure modules with fast tests; a new rejection is one early return. Hard: a new input touches `RunArgs`, `load_run`, `RunInputs` and `cli`; later slices that read new inputs grow `load.py`.

## 3. Option C: ports and adapters

`app.py` holds each command whole, from the record-file decisions through the problem order to the computation, and reaches git, files and coverage only through a `Workspace` interface. Production passes a `GitWorkspace`; tests pass an in-memory `FakeWorkspace`. `app` returns what to do as an `Outcome`, and `cli` does it. The pure modules are B's.

| Module | Does | Tier | [core] "then"s it produces |
|---|---|---|---|
| `__main__.py` | calls `cli.main` | periphery | none |
| `model.py` | §0.2, `RunInputs` and `Outcome`; no code | periphery | none |
| `ports.py` | the `Workspace` interface; no code | periphery | none |
| `cli.py` | arguments; reads the record file; performs the `Outcome` | core | K1–K12 |
| `workspace.py` | `GitWorkspace`: git, file reads, the coverage API | core | K1–K6, K8–K12 |
| `app.py` | both commands, with no I/O but through the workspace | core | K1–K12 |
| `junit`, `floor`, `matrix`, `selection`, `verdict`, `record`, `report` | as in B | as in B | as in B |
| `tests/fake_workspace.py` | test code, no tier | none | a fake that lies can hide a [core] defect |

```python
# ports.py: a typing.Protocol, or a plain base class whose methods
# raise NotImplementedError if the Protocol is one concept too many
class Workspace(Protocol):
    def is_checkout(self) -> bool: ...
    def is_shallow(self) -> bool: ...
    def resolve_commit(self, name: str) -> Commit | None: ...
    def merge_base(self, a: Commit, b: Commit) -> Commit | None: ...
    def is_ancestor(self, ancestor: Commit, descendant: Commit) -> bool: ...
    def changed_paths(self, old: Commit, new: Commit) -> list[RepoPath]: ...
    def tree_files(self, commit: Commit) -> frozenset[RepoPath]: ...
    def read_bytes(self, path: str) -> bytes | None: ...     # None: no such file
    def read_text(self, path: str) -> str | None: ...        # None: cannot be read
    def read_coverage(self, path: str) -> RawCoverage: ...   # raises UnusableCoverage

# model.py, besides §0.2 and RunInputs
@dataclass(frozen=True)
class Outcome:
    append: bytes | None
    stdout: str
    stderr: tuple[str, ...]
    exit_code: int

# app.py
def evaluate_command(args: RunArgs, record_file: bytes | None, ws: Workspace) -> Outcome: ...
def report_command(record_files: list[tuple[str, bytes]]) -> Outcome: ...

# workspace.py
class GitWorkspace:                # has every method of Workspace
    def __init__(self, checkout: str) -> None: ...

# cli.py
def main(argv: list[str] | None = None) -> int: ...
```

How a run goes:

1. `cli.main` parses the arguments, reads the record file's bytes (`None` if it does not exist) and builds a `GitWorkspace`.
2. `app.evaluate_command` decodes the record file, computes the key through the workspace, checks for an evaluated record, walks the problem order, computes and encodes the record, and returns an `Outcome`: the line to append, if any, the messages and the exit code.
3. `cli.main` appends `outcome.append`, prints `outcome.stderr` and returns `outcome.exit_code`.

Cost:

- **Testing.** Easy: nearly every [core] example, including the append decisions, exit codes, messages and combinations of problems, runs in memory in milliseconds with a `FakeWorkspace`; the real defusedxml still runs, because parsing is pure. Hard: keeping the fake honest. The traps found for this note (§0.3 and §6: coverage deleting or initialising its file, `ls-tree` without `--full-tree`, `rev-parse`'s exit codes) all live in `GitWorkspace`, which in-memory tests never run. It needs its own tests against real repositories, plus contract tests that run one list of scenarios against both workspaces.
- **Understanding.** Easy: `app.py` shows a whole command with no I/O detail. Hard: one more concept; a reader has to know that `ws.merge_base` is git in production and a dict in tests; thirteen files plus the fake.
- **Changing.** Easy: replacing git or the coverage reader means a new workspace class. Hard: every new query changes the port, the real workspace and the fake.

## 4. Side by side

| | A | B | C |
|---|---|---|---|
| Modules | 9 | 15 | 13, plus a test fake |
| Where the problem order lives | `evaluate.evaluate`, in statement order | `load.load_run`, early returns | `app.evaluate_command`, through the port |
| Who writes reasons, inputs and messages | four modules | `load` | `app` |
| `coverage` and `defusedxml` imported in | `coverage_at_m`, `junit` | `coverage_io`, `junit` | `workspace`, `junit` |
| K1 and K2, the record lines | end to end only | pure, plus one end to end | in memory, plus adapter tests |
| Rejection examples | end to end | `load_run` on real inputs | in memory; the real behaviour in adapter tests |
| Main cost | core logic and I/O share modules | more files; a wide `RunInputs` | a fake to keep honest |

## 5. Risk tiers and the [core] cross-reference

### 5.1 How the tiers come out

The rule: a module is core if it produces the "then" of a [core] example, medium if it is logic whose mistakes can be corrected without loss, periphery if it is glue.

All twelve [core] examples are in "Records, rejections and CI signal", and their "then"s are of five kinds: the bytes of a record line, whether a line is appended, the exit code, what a message must name or must not quote, and that no XML entity is resolved. Applied to them, the rule makes almost the whole evaluation core, in every option. The reason is in the SPEC. The record is the only thing stored; it is computed from inputs the tool does not keep; and once a key has an evaluated record, a corrected tool cannot replace it: the same key with other content, in another record file, becomes a conflict that the report leaves out of every figure. So every module whose output reaches a record field is core, git, the floor and the selection included.

Only the report is medium: records are kept, so a wrong figure is fixed by fixing the report and running it again. Periphery is what produces nothing: `__main__.py`, `model.py` and `ports.py`.

Two finer points. The selection's reasons are in no record, so a wrong reason label alone would be medium; `selection` is core because which tests it picks reaches `selected_ms`, the verdict and `failed_left_out`. And `cli` is core in every option because it performs the append and the exit, even in C, where `app` decides them.

### 5.2 From each [core] "then" to the modules that produce it

Every record line carries `head`, so git and the module that computes the key are in every row that appends one.

| # | A | B | C |
|---|---|---|---|
| K1 | `evaluate`, `junit`, `coverage_at_m`, `floor`, `git`, `records`, `cli` | `compute`, `selection`, `verdict`, `matrix`, `record`, `junit`, `floor`, `load`, `git`, `coverage_io`, `record_file`, `cli` | `app`, `selection`, `verdict`, `matrix`, `record`, `junit`, `floor`, `workspace`, `cli` |
| K2 | `junit`, `evaluate`, `git`, `records`, `cli` | `junit`, `verdict`, `compute`, `record`, `load`, `git`, `record_file`, `cli` | `junit`, `verdict`, `record`, `app`, `workspace`, `cli` |
| K3 | `records`, `evaluate`, `git`, `cli` | `record`, `record_file`, `load`, `git`, `cli` | `record`, `app`, `workspace`, `cli` |
| K4 | `git`, `evaluate`, `records`, `cli` | `git`, `load`, `record`, `record_file`, `cli` | `workspace`, `app`, `record`, `cli` |
| K5 | `git`, `evaluate`, `records`, `cli` | `git`, `load`, `record`, `record_file`, `cli` | `workspace`, `app`, `record`, `cli` |
| K6 | `junit`, `evaluate`, `git`, `records`, `cli` | `junit`, `load`, `git`, `record`, `record_file`, `cli` | `junit`, `app`, `workspace`, `record`, `cli` |
| K7 | `cli` | `cli` | `app`, `cli` |
| K8 | `git`, `coverage_at_m`, `junit`, `floor`, `evaluate`, `records`, `cli` | `git`, `coverage_io`, `junit`, `floor`, `load`, `record`, `record_file`, `cli` | `workspace`, `junit`, `floor`, `app`, `record`, `cli` |
| K9 | `junit`, `evaluate`, `git`, `records`, `cli` | `junit`, `load`, `git`, `record`, `record_file`, `cli` | `junit`, `app`, `workspace`, `record`, `cli` |
| K10 | `records`, `coverage_at_m`, `evaluate`, `git`, `cli` | `record`, `record_file`, `coverage_io`, `load`, `git`, `cli` | `record`, `app`, `workspace`, `cli` |
| K11 | `records`, `cli` and K1's modules | `record`, `record_file`, `cli` and K1's modules | `record`, `app`, `cli` and K1's modules |
| K12 | `coverage_at_m`, `evaluate`, `git`, `records`, `cli` | `coverage_io`, `load`, `git`, `record`, `record_file`, `cli` | `workspace`, `app`, `record`, `cli` |

The other direction is the last column of each option's module table. The two agree: every module rated core produces at least one [core] "then", and the only modules that produce none are the report and the periphery.

### 5.3 From the modules to irreversible effects that no [core] example observes

| Effect | Module in A / B / C | Observed by |
|---|---|---|
| Appending a record line | `records` / `record_file` / `cli` | K1, K2, K4–K6, K8, K9, K11, K12; not appending: K3, K10 |
| Leaving XML entities unresolved, so no file or URL is read | `junit` | K6 |
| Writing to the coverage input | `coverage_at_m` / `coverage_io` / `workspace` | none |
| Text in the CI log | `cli`, and whoever builds the messages | in part |
| A network connection opened by git | `git` / `git` / `workspace` | none |
| Creating the record file; a torn append | `records` / `record_file` / `cli` | none |

The unobserved ones, each with a candidate example. A module with such an effect means a missing example; the values of [core] examples are yours, so these are proposals, not decisions.

1. **Writing to the coverage input.** coverage's API deletes or rewrites the file it is given in the two cases of §0.3, rule 3 (read). The deleting case would also empty the rows, so K1's test would catch it. The writing case would not: an empty file, or an SQLite file of something else, would be initialised in place and then rejected as `no-shared-lines` instead of `unusable-input`, with the input changed. Candidate: *Given a coverage file that is empty, when the run is evaluated, then it is rejected with `unusable-input` and `coverage`, and the coverage file is left byte for byte as it was.* Rule 3's private copy adds an effect of its own: a temporary file the size of M's, removed at exit and left behind only if the process is killed.
2. **Text in the CI log.** stderr goes to the job's log, which stays and, on a public repository, is public. K3–K6, K8–K10 and K12 fix what their messages must name; only K6 fixes that a message quotes nothing, and only for an unsafe XML file. No example observes the messages that end in exit 1: a record file with a line that is not a record, and any unexpected failure, whose default traceback would print the exception's text, which for both libraries can hold data read from the file (§0.3, rule 6). Candidate: *Given an input that makes the evaluation fail in a way the rejection list does not name, when the run is evaluated, then nothing is appended, the tool exits with 1, and its message quotes nothing from any file.*
3. **A network connection opened by git.** Constraints says Slice 1 opens none. In a partial clone, git fetches missing objects from the remote when a command needs them [VERIFY for `diff`, `ls-tree` and `merge-base`], and git 2.43 has no switch to forbid it: `git --no-lazy-fetch` is an unknown option (run). A full clone, which is what the Deployment's `fetch-depth: 0` asks for, has nothing to fetch; the risk is a checkout step that also asks for a partial clone. Candidate: a line in Deployment saying the checkout is not a partial clone, or a rejection when it is.
4. **Creating the record file, and a torn append.** No example has a record file that does not exist yet: the fixture's is "empty". Creating it is low risk. A torn append, from a killed runner or a full disk, leaves a line without its newline, which by the SPEC's own rule makes that record file, and every report that reads it, fail with exit 1: loud, not wrong. Rule 8's single write keeps it unlikely.

## 6. What was checked, and what is [VERIFY]

| API or behaviour | Used by | Status |
|---|---|---|
| **coverage 7.16.2** | | |
| `CoverageData(basename=path)`; `read()` does nothing when the file is missing | coverage reader | read |
| `measured_contexts()`, `contexts_by_lineno()`, `lines()`, `arcs()`, `set_query_context(s)()` erase the file unless `read()` marked it used, then a new file is created at the path | coverage reader | read |
| `read()` writes coverage's schema into an SQLite file without a `coverage_schema` table | coverage reader | read |
| SQLite opens a 0-byte file as an empty database, so `read()` writes into it | coverage reader | [VERIFY] |
| A non-SQLite file, or another schema version, raises `DataError`; `SCHEMA_VERSION = 7` | coverage reader | read |
| Which coverage versions write schema 7, so that the recording job and the evaluating one can differ | Deployment | [VERIFY] |
| `measured_files() -> set[str]`, which may list a file with no lines | coverage reader | read |
| `measured_contexts() -> set[str]`; `contexts_by_lineno(filename) -> dict[int, list[str]]`, `{}` for an unknown file, built from arcs under branch coverage | coverage reader | read; both also used on real pytest-cov data in the spike |
| `set_query_contexts(contexts)`: regexes matched with `re.search` per context | batching fallback | read; its speed [VERIFY] |
| `coverage.CoverageException` exported at the top level; `DataError` its subclass in `coverage.exceptions` | coverage reader | read; whether `coverage.exceptions` is documented public [VERIFY], which catching `CoverageException` sidesteps |
| `set_context()`, `add_lines()`; `write()` is a no-op without a suffix | test fixtures | read |
| Time and memory of one `contexts_by_lineno()` per file at 10,000 tests and 2,000 files | coverage reader | [VERIFY]: the SPEC's open question "Weight of M" |
| **pytest 9.1.1** | | |
| `_pytest.junitxml.mangle_test_address(address: str) -> list[str]` | `pair_of`, and a test comparing the two | read; private, so its behaviour after 9.1.1 [VERIFY] on each upgrade |
| `classname` is `".".join(names[:-1])`, after `--junit-prefix`; `name` is `bin_xml_escape(names[-1])`; `time` is always written as `f"{duration:.3f}"` | JUnit parser | read |
| A collection error is `<error message="collection failure">` | JUnit parser | read; also a FACT in the spike |
| An internal error is `<testcase classname="pytest" name="internal">` with `<error message="internal error">` | JUnit parser | read; see §7 |
| Fixtures `tmp_path`, `capsys`, `capfd`, `monkeypatch` | tests | read |
| **git 2.43.0** | | |
| `git -C DIR rev-parse --is-inside-work-tree`: `true`; outside a repository, exit 128 | `is_checkout` | run |
| `git rev-parse --is-shallow-repository`: `false` here | `is_shallow` | run; `true` on a shallow clone only from the man page, [VERIFY] |
| `git rev-parse --verify --quiet --end-of-options NAME^{commit}`: the full id; exit 1 for an unknown name, a tree or an option-like name such as `--all` | `resolve_commit` | run |
| `git merge-base A B`: one commit | `merge_base` | run; with no common history [VERIFY] (expected: exit 1, nothing printed); with several best common ancestors "it is unspecified which best one is output" (man page) |
| `git merge-base --is-ancestor A B`: 0 when A is an ancestor or equal, 1 when not, 128 for an unknown name | `is_ancestor` | run |
| `git diff --name-only --no-renames --no-relative -z A B`: NUL-terminated paths from the root, also from a subdirectory with `diff.relative=true`; no colour codes even with `color.ui=always`; `.git/index` unchanged | `changed_paths` | run. Renames under both names and unquoted non-ASCII paths: checked with git 2.43 according to the SPEC, not re-run here |
| `git ls-tree -r --name-only -z --full-tree C`: every path from the root. Without `--full-tree`, run from a subdirectory, it lists only that subdirectory, relative to it | `tree_files` | run |
| `git --no-lazy-fetch`: unknown option | §5.3 | run |
| Whether `diff`, `ls-tree` and `merge-base` fetch missing objects in a partial clone | §5.3 | [VERIFY] |
| A repository owned by another user ("dubious ownership") makes every command fail, which the tool would report as "not a git checkout" | `is_checkout` | [VERIFY] |
| A bare branch name resolves through `refs/heads/`, `refs/remotes/<name>` and `refs/remotes/<name>/HEAD` only | `--base` | man gitrevisions |
| **defusedxml 0.7.1** | | |
| `defusedxml.ElementTree.fromstring(text, forbid_dtd=False, forbid_entities=True, forbid_external=True)` | JUnit parser | read |
| An entity declaration raises `EntitiesForbidden` from expat's declaration handler; an external reference, `ExternalReferenceForbidden`; malformed XML, `xml.etree.ElementTree.ParseError` | JUnit parser | read |
| A malformed byte before the declaration raises `ParseError` first, as "whichever the parser meets first" needs | JUnit parser | [VERIFY] |
| The exceptions' `str()` holds the entity's name and system id | messages | read |
| Whether expat calls the external-reference handler for an external DTD subset (`<!DOCTYPE x SYSTEM "...">`) | JUnit parser | [VERIFY] |
| 0.7.1 on Python 3.13 and 3.14 | deployment | [VERIFY] |
| **Standard library** | | |
| `json.dumps` escapes match the SPEC | `encode` | run |
| A Clopper–Pearson upper bound by bisection on the binomial CDF gives 86.5% for 1 of 3, 9.5% for 0 of 30, 63.2% for 0 of 3 and 9.8% for 0 of 29; computed as `math.comb(n, i) * p**i`, it overflows from about n = 1,030, so the report works in logarithms (`math.lgamma`) | `report` | run |

## 7. SPEC gaps met while designing

Each one is left open; the module that would carry the answer is in brackets, with B's names.

1. Two node ids with one pair: when that pair is in the run, does each node id count among `tests_with_row_not_in_run`? (`selection`)
2. A node id whose lines all fall outside the repository has an empty row: is that "a row" for `tests_with_row` and `unmeasured`? (`matrix`, `selection`)
3. A file that `measured_files()` lists with no recorded line (read): import-only, or no column? (`matrix`)
4. A `testcase` without `classname` or `name`, or whose `time` is missing or not a number: `unusable-input`, 0 ms, or a test? pytest always writes all three (read); other writers may not. (`junit`)
5. pytest's internal-error test case (read) would count as an unmeasured failed test and make the run caught: the distortion the SPEC rejects for collection errors. (`junit`, `load`)
6. A pass in the rerun file: does a skip there count as one? (`verdict`)
7. How deep "what the tool would write for some run" goes. Shape, types, enumerations and canonical bytes, surely; cross-field rules, such as a `missed` record with an empty `failed_left_out` or `selected_ms` above `full_ms`, are open. (`record.decode`)
8. Deployment: how the CI step gets the tool, and pinning coverage versions with the same data schema in the job that records M and in the one that evaluates. (§0.1, §6)

## 8. Recommendation

Opinion: B. It puts every computation that reaches a record in pure modules tested with literals, the exact bytes of K1 and K2 included, and keeps the problem order in one function tested against the real git, coverage and defusedxml, which is where the traps found for this note live. A is cheaper to write, but it spreads reasons, inputs and messages over four modules and tests the record only end to end. C buys fast in-memory tests of the [core] examples at the price of a fake that must mimic exactly the behaviours most likely to be wrong.

Whichever is chosen, build the coverage reader first and time it on the pilot's M. Its interface, a path in and a `RawCoverage` out, is the same in the three options, and it is the one module whose feasibility under the 60 s and 1 GB limit is still open.
