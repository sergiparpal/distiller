# Tasks

- In the tests phase nothing stops the agent from creating the files that implement freezes (pytest.ini, ruff.toml, .gitattributes and the rest of `FROZEN_AT_ROOT` and `FROZEN_ANYWHERE` in `.claude/hooks/phase.py`); one that enters the tests commit becomes implement's reference.
- `.git/info/` can be written from the agent's Bash, and git does not track it: `.git/info/attributes` outranks every `.gitattributes`, and `.git/info/exclude` hides untracked files from `scripts/check_characters.py`. Proposed, for the user: `"Edit(/.git/info/**)"` among the deny rules of `.claude/settings.json`. With the rules for .venv, .git/hooks and .git/config, the Bash sandbox made those read-only; the same is expected for .git/info [VERIFY].
- `clean_environment` in the Stop hook drops `GIT_CONFIG_KEY_n`, whose names hold KEY, but keeps `GIT_CONFIG_COUNT`, so git fails inside Stop's bwrap wherever that variable is set. The Bash sandbox sets it, which is why the implement-phase Stop tests fail there.

## Slice 1

Seventeen tasks, each one cycle: a tests session, which cannot read `src/`, then an implement session, with the tests frozen. Task 18 is outside the cycle. The tasks go bottom up through the imports that the technical sheet's signatures and types imply (each type lives in the module that creates it): `messages` and `git` import no module of the package; `junit`, `coverage_at_m` and `floor` use `Rejected` and `RepoPath`; `selection` uses their types; `records` uses `Pair` and `Test`; `evaluate` and `report` sit on top. Each task, once done, leaves main green and depends on no later task.

A module that does not exist yet gets its stubs from the agent, in the tests phase, with its import-linter contract. A signature missing from a module that exists is the user's to write before the tests phase. With `fail_under = 100`, a stub that no test runs turns main red, so `selection` and `records` are split into three tasks each: the first creates the module with its own stubs only.

How to read the fields:
- **Closes**: the behaviour that the task's tests pin down.
- **Covers**: the [core] examples (K, from the technical sheet's table), the other examples and the rules of Slice 1's prose. Other examples are named by their section and position: Selection 1-16, Verdict 1-5, Report 1-17, Invariants 1-4 and Edge 1-22, in the order of `docs/SPEC.md`. Prose rules are named by the term or the paragraph they belong to. **Constrained by** lists the K examples whose "then" holds a text, a value or a line that the task produces: its tests use those exact values.
- **Modules**: from D-001.
- **Stubs**: exact signatures, from the technical sheet, and who writes them.
- **Contract**: the import-linter contract that the task adds or changes, in `pyproject.toml`.
- **Rewrites**: the existing tests that the task replaces.

### 1. Messages
- **Closes**: every text that the tool writes to stderr, apart from argparse's usage errors and the unexpected-failure line, which exists.
- **Covers**: prose, "Warnings and error messages go to stderr...": the inputs named by path and commits as given, nothing a file holds quoted; a rejection's message names its input, or M for `coverage-not-ancestor` and for an M that names no commit; the `no-shared-lines` text; an invalid floor pattern's message names the configuration file and the line number; the already-recorded warning names the key as the record holds it. Technical sheet, Rule 6. A `Rejected`'s `subject` and `line_number`, as the sentence after Interfaces defines them.
- **Constrained by**: K3 (the warning names the key), K4 (names M), K5 (names the checkout), K6 (names the file, quotes nothing), K8 (names the input that failed), K9 (names the JUnit file), K10 and K14 (name the coverage file), K12 (says that the coverage at M must be recorded with `--cov-context=test` and `COVERAGE_CORE=ctrace`, or that the suite's tests share no code), K15 (names the record file and line 2; `canary` appears nowhere).
- **Modules**: `messages`.
- **Stubs**, by the user, before the phase:
  ```python
  class Rejected(Exception):
      def __init__(self, reason: str, input_name: str, subject: str,
                   line_number: int | None = None) -> None: ...
  def rejection(error: Rejected) -> str: ...
  def already_recorded(head: str, junit_sha256: str | None) -> str: ...
  def not_a_record(path: str, line_number: int) -> str: ...
  def unreadable_record_file(path: str) -> str: ...
  ```
- **Contract**: none; "messages imports no other module of the package" exists.

### 2. Git queries
- **Closes**: the seven read-only git queries that the tool runs on the checkout, and that the tool opens no network connection.
- **Covers**: prose, "The changed paths are...": `--no-renames` lists a renamed file under both names, a deleted file under its old name, and `-z` leaves non-ASCII, quoted and control characters unquoted; the merge-base is the one `git merge-base` prints when there are several. Prose, Selection term: "A renamed path counts under both of its names, a deleted one under its old name", as far as the listing goes. Prose, "Apart from appending...": git runs only commands that read. Constraints, Agent safety: "Slice 1 opens no network connection". Deployment: a base given as `origin/<branch>` resolves. Technical sheet, Rule 2 (each name resolved as a commit, option-like names such as `--all` name no commit, paths decoded from `-z` output, git's output never reaches the tool's stderr, only the commands under "Checked" run) and "Checked" for git 2.43 (`--is-inside-work-tree` outside a repository, shallow and full clones, no common history, A is its own ancestor, `diff` from a subdirectory with `diff.relative=true` and with `color.ui=always`, `.git/index` left unchanged, `ls-tree` from a subdirectory). Edge 5.
- **No network**: tests that every git command the module runs is one of the local subcommands under "Checked" (`rev-parse`, `merge-base`, `diff`, `ls-tree`), and the contract below.
- **Modules**: `git`.
- **Stubs**, by the agent, in the tests phase (new module):
  ```python
  Commit = str
  RepoPath = str
  def is_checkout(checkout: str) -> bool: ...
  def is_shallow(checkout: str) -> bool: ...
  def resolve_commit(checkout: str, name: str) -> Commit | None: ...
  def merge_base(checkout: str, a: Commit, b: Commit) -> Commit | None: ...
  def is_ancestor(checkout: str, ancestor: Commit, descendant: Commit) -> bool: ...
  def changed_paths(checkout: str, old: Commit, new: Commit) -> list[RepoPath]: ...
  def tree_files(checkout: str, commit: Commit) -> frozenset[RepoPath]: ...
  ```
- **Contract**, by the agent: "only git imports subprocess" becomes a protected contract, as the comment above it in `pyproject.toml` says. A new forbidden contract: no module of `distiller` imports the standard library's network modules (`socket`, `ssl`, `http`, `urllib`, `ftplib`, `smtplib`, `poplib`, `imaplib`, `xmlrpc`, `socketserver`) [VERIFY: that import-linter follows no import inside an external package, so that `coverage` or `defusedxml` importing one of these does not break the contract].

### 3. Reading and parsing JUnit
- **Closes**: reading a JUnit file into bytes, and parsing it into its results by pair, with the rejections that come from its content.
- **Covers**: prose, JUnit term: the test cases of one file that share a pair are one test, failed if any of them has a `failure` or an `error`, with the sum of their times. Prose, "A run is red...": a test passes in the rerun file only if none of its test cases there has a `failure`, an `error` or a `skipped` (`Result.passed`). Prose, "A collection error is...": how a collection error is recognized (`has_collection_error`). Prose, "A test case cannot be used if...": the missing attributes, the `time` format, pytest's internal error, each `unusable-input` with the input given. Prose, the rejection reasons: `unsafe-xml` for a file that declares an entity, even one it never uses, with nothing resolved or expanded; a file that is not well-formed XML is `unusable-input`; within one file, `unsafe-xml` or not well-formed, whichever the parser meets first. Prose, "An input file that exists but is not a regular file...", for the JUnit files: `read_junit` gives `None`, and a FIFO does not block. Prose, "Each test case's JUnit time is rounded to the nearest whole millisecond, halves up, before any sum". Technical sheet, Rule 5 (a `time` in another script's digits cannot be used) and Rule 3 (opened for reading only). Edge 14.
- **Constrained by**: K6 (`unsafe-xml`, with `junit` or `rerun`), K8 (`unusable-input`, with `junit` or `rerun`), K9 (a test case with an empty `classname` and an `error` whose message is `collection failure`).
- **Modules**: `junit`.
- **Stubs**, by the agent, in the tests phase (new module):
  ```python
  Pair = tuple[str, str]
  @dataclass(frozen=True)
  class Result:
      failed: bool
      passed: bool
      time_ms: int
  @dataclass(frozen=True)
  class JUnit:
      results: dict[Pair, Result]
      has_collection_error: bool
  def read_junit(path: str) -> bytes | None: ...
  def parse_junit(data: bytes, input_name: str, path: str) -> JUnit: ...  # raises Rejected
  ```
- **Contract**, by the agent: "only junit imports defusedxml" becomes a protected contract.

### 4. Reading the coverage at M and building the matrix
- **Closes**: reading the coverage file without changing it, and mapping it to M's tree as rows and import-only files.
- **Covers**: prose, "A test context is...": split at the last `|`, and any other context is outside any test. Prose, "A test's row is...": setup, call and teardown all count, and files outside the repository are in no row; a node id whose recorded lines all fall outside the repository keeps an empty row in `Matrix.rows`. Prose, "A coverage file is a coverage data file only if..." and "A measured file in which no line was recorded is in no row and is not import-only". Prose, "A file recorded in the coverage maps to the longest path...". Prose, "A file whose lines were all recorded outside any test... is import-only". Prose, Inputs, the per-test coverage: a line recorded for two node ids or more (`has_shared_line`). Prose, "An input file that exists but is not a regular file...", for the coverage file. Technical sheet, Rule 3 for the coverage file and Rule 4; D-002: the coverage file is left byte for byte as it was, an empty one and a foreign SQLite database included. Edge 4.
- **Constrained by**: K8 and K14 (`unusable-input`, with `coverage`), K14 (an empty file stays 0 bytes long), K13 (the coverage file is left byte for byte as it was).
- **Modules**: `coverage_at_m`.
- **Stubs**, by the agent, in the tests phase (new module):
  ```python
  NodeId = str
  @dataclass(frozen=True)
  class RawCoverage:
      nodes_by_file: dict[str, frozenset[NodeId]]
      import_only_files: frozenset[str]
      has_shared_line: bool
  @dataclass(frozen=True)
  class Matrix:
      rows: dict[NodeId, frozenset[RepoPath]]
      import_only: frozenset[RepoPath]
  def read_coverage(path: str) -> RawCoverage: ...  # raises Rejected
  def node_id_of(context: str) -> NodeId | None: ...
  def build_matrix(raw: RawCoverage, tree: frozenset[RepoPath]) -> Matrix: ...
  ```
- **Contract**, by the agent: "only coverage_at_m imports coverage" becomes a protected contract.

### 5. The floor
- **Closes**: reading the floor configuration, the default patterns, pattern validity and matching.
- **Covers**: prose, Inputs, the floor configuration: blank lines, lines that start with `#`, spaces at either end, UTF-8 with a byte order mark and `\r\n` endings, a file that is not valid UTF-8. Prose, "The floor is the default patterns...", and "A configuration adds patterns and never removes them". Prose, "Floor patterns have their own syntax...": segment matching, `**`, `*`, the invalid patterns, and its examples (`**/uv.lock`, `config/**`, `**/requirements*.txt`). Prose, the rejection reasons: `floor` for a configuration that cannot be read or has an invalid pattern, with the pattern's line number. Prose, "An input file that exists but is not a regular file...", for the floor configuration. Technical sheet, Rule 9 (lines split on newline only). Edge 21, Edge 22.
- **Constrained by**: K8 (`unusable-input`, with `floor`).
- **Modules**: `floor`.
- **Stubs**, by the agent, in the tests phase (new module):
  ```python
  DEFAULT_PATTERNS: tuple[str, ...]
  def read_floor(path: str | None) -> tuple[str, ...]: ...  # the defaults, then the file's; raises Rejected
  def matches(pattern: str, path: RepoPath) -> bool: ...
  def floor_hits(patterns: tuple[str, ...], changed: list[RepoPath]) -> list[tuple[str, RepoPath]]: ...
  ```
- **Contract**: none; Imports sets none for `floor`.

### 6. Matching tests to rows
- **Closes**: turning node ids into pairs and matching the run's tests to their rows.
- **Covers**: prose, JUnit term: the pair rule, with its example (`tests.test_tax.TestVat`, `test_rate[es-0.21]`). Prose, "Each node id in the test contexts is turned into its pair...": one direction only, and two node ids with one pair make that pair's test unmeasured, `tests/v1.2/test_x.py::test_m` and `tests/v1/2/test_x.py::test_m` among them. Prose, "An unmeasured test is...". Prose, "A test's row is...": an empty row is no row, but its node id still counts among its pair's node ids (the sentence after the Data model).
- **Modules**: `selection`.
- **Stubs**, by the agent, in the tests phase (new module):
  ```python
  @dataclass(frozen=True)
  class Test:
      pair: Pair
      node_id: NodeId | None
      row: frozenset[RepoPath] | None
  def pair_of(node_id: NodeId) -> Pair: ...
  def match_tests(results: dict[Pair, Result], rows: dict[NodeId, frozenset[RepoPath]]) -> list[Test]: ...
  ```
- **Contract**: none.

### 7. Selection rules
- **Closes**: which tests the all-affected selector picks, and with which reasons.
- **Covers**: Selection 1-12. Invariants 2, 3 and 4. Prose, "The selection is every test in the run that at least one rule picks...": the five rules, `conftest` up to pytest's rootdir, and an unmeasured test picked only by `unmeasured` or a floor reason. Prose, Inputs, pytest's rootdir: node ids relative to it, `own file` and `conftest` resolved through it. Edge 1, 3, 10, 11, 12, 13 and 20.
- **Modules**: `selection`.
- **Stubs**, by the user, before the phase:
  ```python
  @dataclass(frozen=True)
  class Reason:
      rule: str
      path: RepoPath | None
      pattern: str | None = None
  Selection = dict[Pair, frozenset[Reason]]
  def select(tests: list[Test], changed: list[RepoPath],
             hits: list[tuple[str, RepoPath]], rootdir: str) -> Selection: ...
  ```
- **Contract**: none.

### 8. Verdict
- **Closes**: whether a run is green, caught or missed, which failures are not reproduced, and which failed tests were left out.
- **Covers**: Verdict 1-5. Prose, "A run is red when...": only a pass in the rerun file discards a failure, the test is then marked not reproduced; caught, missed and green. Edge 2, 15, 16, 17, 18 (its first clause; that the rerun file is still rejected is task 13's) and 19.
- **Modules**: `selection`.
- **Stubs**, by the user, before the phase:
  ```python
  @dataclass(frozen=True)
  class Judgement:
      verdict: str
      not_reproduced: frozenset[Pair]
      failed_left_out: tuple[Test, ...]
  def judge(full: JUnit, rerun: JUnit | None, tests: list[Test], selection: Selection) -> Judgement: ...
  ```
- **Contract**: none.

### 9. Encoding records
- **Closes**: the record types and the exact bytes of a record line.
- **Covers**: prose, "A record is one line...": ASCII JSON with no spaces, the escapes, the keys and their order for evaluated and rejected records, the sorting of lists of pairs, of `failed_left_out` and of lists of paths by code point, a pair as a list of two strings. Technical sheet, Rule 7 (`encode`) and Rule 8 (sorted, no time or environment value).
- **Constrained by**: K1 (its whole line), K2 (`"verdict":"green"`, `"rerun_given":true`, `"not_reproduced":[["tests.test_report","test_render"]]`, `"failed_left_out":[]`), K4 (its whole line), K5 (`missing-history`, `checkout`), K6 (`unsafe-xml`, `junit` or `rerun`), K8 and K14 (`unusable-input` and each input), K9 (`collection-error`, `junit`), K12 (`no-shared-lines`, `coverage`).
- **Modules**: `records`.
- **Stubs**, by the agent, in the tests phase (new module). `RunKey` and `RejectedRecord` are written out in the Data model. `EvaluatedRecord` is described there in prose; each field below comes from the sentence quoted next to it:

  | Field | Type | Data model sentence |
  |---|---|---|
  | `key` | `RunKey` | "with `key: RunKey` in place of `head` and `junit_sha256`" |
  | `pr` | `int` | "`pr`, the durations and the counts are `int`" |
  | `verdict` | `str` | "`verdict` is `str`" |
  | `merge_base` | `Commit` | "`merge_base` and `coverage_commit` are `Commit`" |
  | `coverage_commit` | `Commit` | same sentence |
  | `selected_ms` | `int` | "`pr`, the durations and the counts are `int`" |
  | `full_ms` | `int` | same sentence |
  | `tests` | `int` | same sentence |
  | `unmeasured` | `int` | same sentence |
  | `tests_with_row` | `int` | same sentence |
  | `tests_with_row_not_in_run` | `int` | same sentence |
  | `floor_matched` | `bool` | "`floor_matched` and `rerun_given` `bool`" |
  | `rerun_given` | `bool` | same sentence |
  | `not_reproduced` | `tuple[Pair, ...]` | "`not_reproduced` a `tuple[Pair, ...]`" |
  | `failed_left_out` | `tuple[Test, ...]` | "`failed_left_out` a `tuple[Test, ...]`" |
  | `no_column` | `tuple[RepoPath, ...]` | "`no_column` and `import_only` `tuple[RepoPath, ...]`" |
  | `import_only` | `tuple[RepoPath, ...]` | same sentence |

  The order is "the record's fields in the SPEC's order", that of the prose's "A record is one line...", with `key` where `head` and `junit_sha256` are. Whether `format` is a field is open question 2.
  ```python
  @dataclass(frozen=True)
  class RunKey:
      head: str
      junit_sha256: str | None
  @dataclass(frozen=True)
  class RejectedRecord:
      key: RunKey
      pr: int
      reason: str
      input_name: str
  @dataclass(frozen=True)
  class EvaluatedRecord: ...  # the fields above, in that order
  Record = EvaluatedRecord | RejectedRecord
  def encode(record: Record) -> bytes: ...
  ```
- **Contract**: none.

### 10. Telling a record from a line that is not one
- **Closes**: which lines of a record file are records.
- **Covers**: prose, "A line of a record file is a record only if it is byte for byte what the tool would write...": an empty line, a carriage return, a missing newline, another format; shape only, no agreement between fields. Technical sheet, Rule 7 (`decode`: ASCII, keys and order, exact types, so `true` is not `1`, allowed values, lists sorted with no repeats, `encode` of the result equal to the line).
- **Constrained by**: K1 and K4 (their lines are records, and decode to the values they show), K15 (a line holding `canary` is not a record).
- **Modules**: `records`.
- **Stubs**, by the user, before the phase:
  ```python
  def decode(line: bytes) -> Record | None: ...
  ```
- **Contract**: none.

### 11. The record file
- **Closes**: reading the record file, looking up a key, and appending a line.
- **Covers**: prose, "Before evaluating a run, the tool reads the record file; if it does not exist, the tool treats it as empty and creates it when it appends", as far as reading, the lookups and the append go. Prose, "`pr` is not part of it: a rejected record already there with the same key, reason and input stops the append, whatever its `pr`" (`has_rejected`). Prose, "The record file is not one of these inputs: if it exists but cannot be read, that is any other failure" (`read_record_file` raises `OSError`). Prose, a line that is not a record named by its line number. Technical sheet, Rule 3 for the record file (a FIFO does not block) and Rule 8 (one write of the whole line, to a file opened for appending, created if missing).
- **Constrained by**: K3 (an evaluated record with the key is found), K10 (a rejected record with the same key, reason and input is found), K11 (an evaluated record is appended after the rejected one), K13 (the file is created and holds that one line), K15 (line 2 is reported, the file is left as it was).
- **Modules**: `records`.
- **Stubs**, by the user, before the phase:
  ```python
  class NotARecord(Exception):
      def __init__(self, path: str, line_number: int) -> None: ...
  def read_record_file(path: str) -> list[Record] | None: ...
  def has_evaluated(records: list[Record], key: RunKey) -> bool: ...
  def has_rejected(records: list[Record], key: RunKey, reason: str, input_name: str) -> bool: ...
  def append_record(path: str, record: Record) -> None: ...
  ```
- **Contract**: none.

### 12. Evaluating a run end to end
- **Closes**: `python -m distiller evaluate` on valid inputs: the record file, the key, the evaluated record, the warning for a run already recorded, and the exit codes 0 and 1.
- **Covers**: K1, K2, K3, K7, K13, K15. Selection 13-16. Invariants 1, its first half (two evaluations, byte-identical record files). Edge 6, 7, 8 and 9. Prose, Inputs, the base branch: the diff is `merge-base..H`, never against M. Prose, "A column is a file in at least one row... A changed path that is neither a column nor import-only has no column" (`no_column`, `import_only`). Prose, "Every count and every list of the run's tests takes each pair once". Prose, "A node id with a row is in the run when its pair is in the run's JUnit" (`tests_with_row`, `tests_with_row_not_in_run`). Prose, "`full_ms` is the sum over every test case of the full run's JUnit and `selected_ms` over those of the selected tests; neither uses a `testsuite` element's `time`". Prose, "Before evaluating a run...": the record file read first, a missing one taken as empty and created, a line that is not a record (nothing appended, exit 1), a run already recorded (nothing appended, a warning, exit 0), an evaluated run appended with exit 0 whatever the verdict. Command line, the exit codes 0 and 1 of `evaluate`. Technical sheet, "How a run goes", steps 1, 2, 4 and 6.
- **Modules**: `evaluate`, through `cli` and `__main__`.
- **Stubs**: none; `evaluate.run` and `RunArgs` exist.
- **Rewrites**: `tests/test_main.py::test_python_m_distiller_exits_with_what_main_returns`, and the `evaluate` case of `tests/test_cli.py::test_the_commands_are_not_implemented_yet`, which the walking skeleton marked for the evaluate tasks.

### 13. Rejecting unusable inputs
- **Closes**: `unusable-input` for every input, the rejected record, its deduplication and exit code 3.
- **Covers**: K8, K10, K11, K14. Prose, the reasons: `unusable-input` with `checkout`, `head`, `base` (no commit, or no common history with H), `coverage` (a file that is missing, cannot be read or is not a coverage data file, or an M that names no commit), `junit`, `rerun` and `floor`. Prose, "An input file that exists but is not a regular file... counts like a missing one", end to end. Prose, "A record is one line...": `head` is H as given when it names no commit, and `junit_sha256` is `null` when there is no such file or it cannot be read. Prose, "If it rejects the run instead, it appends its record unless one with the same key, reason and input is already there, and exits with 3". Prose, "Apart from appending to the record file, the tool never writes to its inputs... whatever the outcome". Edge 18, its second clause (a rerun file with a test case that cannot be used is rejected even when that test did not fail in the full run). Command line, exit 3 of `evaluate`. Technical sheet, "How a run goes", step 5.
- **Modules**: `evaluate`.
- **Stubs**: none.

### 14. The other rejections and the problem order
- **Closes**: `coverage-not-ancestor`, `missing-history`, `unsafe-xml`, `no-shared-lines` and `collection-error` end to end, and which problem decides a run that has several.
- **Covers**: K4, K5, K6, K9, K12. Prose, Inputs, the per-test coverage: M must be the merge-base or one of its ancestors, and coverage with no line recorded for more than one test is `no-shared-lines`. Prose, the reasons: `coverage-not-ancestor`, `missing-history` (as `git rev-parse --is-shallow-repository` reports), `unsafe-xml` with `junit` or `rerun`, `no-shared-lines`, `collection-error`. Prose, "A collection error is...": a full-run JUnit that holds one is rejected. Prose, "When a run has more than one problem, the first in this order decides its record". Technical sheet, "How a run goes", step 3.
- **Modules**: `evaluate`.
- **Stubs**: none.

### 15. Report: miss rate, bound and savings
- **Closes**: the report's main figures over one or more record files, each key counted once.
- **Covers**: Report 1, 2, 3, 4 and 14. Prose, "The miss rate counts pull requests and looks only at evaluated runs". Prose, "Savings are 1 - the selected duration over the full-suite duration...", with the sentence that they are an upper bound (Report 4). Prose, the report: "Every figure in it counts each key once, even when the key appears in several record files"; a figure whose denominator is zero is never a percentage; the sentence that the figures belong to the all-affected selector.
- **Modules**: `report`, through `cli`.
- **Stubs**, by the user, before the phase:
  ```python
  def clopper_pearson_upper(k: int, n: int) -> float | None: ...  # None when n is 0
  ```
- **Rewrites**: the `report` case of `tests/test_cli.py::test_the_commands_are_not_implemented_yet`, which leaves the test with no case, so the test goes.
- **Open questions it needs**: 3 and 4.

### 16. Report: errors, conflicts, rejected runs and order
- **Closes**: what the report does with missing files, lines that are not records, conflicting keys and rejected runs, and that its output does not depend on the order of its inputs.
- **Covers**: Report 13, 15 and 17. Invariants 1, its second half (two reports, byte-identical, whatever the order of the files and of their lines). Prose, the report: a line that is not a record (nothing produced, file and line named, exit 1); every record file must exist and be readable (nothing on stdout, the file named, exit 1), never taken as empty; two evaluated records with one key that differ form a conflict, left out of every figure and listed with its record files; rejected runs shown by reason and input, counting only keys that no evaluated record has. Prose, "The report depends on neither the order of the record files nor that of their lines...": the sort orders. Command line, the exit codes of `report`. Technical sheet, the paragraph after "How a run goes" (all files read before anything is written).
- **Modules**: `report`.
- **Stubs**: none.
- **Open questions it needs**: 4.

### 17. Report: rates, shares, failed tests left out and escaping
- **Closes**: the floor and no-column rates, the unmeasured and not-in-run shares, the list of failed tests left out, the rerun counts, and escaping in the report.
- **Covers**: Report 5-12 and 16. Prose, "The floor rate counts pull requests...". Prose, "The no-column rate counts pull requests...". Prose, the report: "writes every pair, node id and path as a JSON string, the way the records hold it".
- **Modules**: `report`.
- **Stubs**: none.
- **Open questions it needs**: 3, 4 and 5.

### 18. Connect the step to the pilot's CI (outside the cycle)
- **Closes**: the Kill signal's "Slice 1 runs end to end in its CI" on sergiparpal/adaptive-policy-compilation. Work in the pilot's repository, not a tests and implement cycle here.
- **Depends on**: tasks 1-17 merged, and the external requirements below.
- **Checklist**, from Constraints and Deployment unless noted [VERIFY: the pilot's repository has not been read]:
  - [ ] The pilot's CI runs its suite with pytest instead of unittest, before anything else on this list.
  - [ ] The pull request's full run writes its JUnit in a single pytest invocation, without `--junit-prefix`.
  - [ ] A separate job on the base branch records the coverage at M at least once a day, with pytest-cov `--cov-context=test` and `COVERAGE_CORE=ctrace`, and keeps the data file with M.
  - [ ] Each run is given the newest recorded M that is the merge-base or one of its ancestors; choosing M stays outside the tool.
  - [ ] The checkout is a full clone, not a partial one, with `fetch-depth: 0`.
  - [ ] H is `github.sha`, the merge commit on `pull_request`, and the base is `origin/<branch>`.
  - [ ] The step runs after the tests with `if: always()` and `continue-on-error: true`.
  - [ ] The step runs `python -P -m distiller` from a checkout of this repository at a fixed commit, with `PYTHONPATH` set to its `src`, Python 3.12 or later, `defusedxml`, and the same version of `coverage` as the job that records M.
  - [ ] Optionally, a rerun of only the failed tests writes the rerun file.
  - [ ] Each CI job writes its own record file; decide where record files are kept between jobs so that the report can read them all (the SPEC does not say).
  - [ ] Measure on the pilot the limits under Constraints, Performance: one run with 10,000 tests and 2,000 files under 60 s and 1 GB on a standard hosted runner, and a report over 1,000 recorded runs under 10 s.
  - [ ] In the first week, check the records by hand against the CI's list of pull request runs.

### Coverage
Each line has the one task that covers it. "Constrains" lists the earlier tasks whose tests use the K example's exact values.

| Item | Task | Constrains |
|---|---|---|
| K1 | 12 | 9, 10 |
| K2 | 12 | 9 |
| K3 | 12 | 1, 11 |
| K4 | 14 | 1, 9, 10 |
| K5 | 14 | 1, 9 |
| K6 | 14 | 1, 3, 9 |
| K7 | 12 | |
| K8 | 13 | 1, 3, 4, 5, 9 |
| K9 | 14 | 1, 3, 9 |
| K10 | 13 | 1, 11 |
| K11 | 13 | 11 |
| K12 | 14 | 1, 9 |
| K13 | 12 | 4, 11 |
| K14 | 13 | 1, 4, 9 |
| K15 | 12 | 1, 10, 11 |
| Selection 1-12 | 7 | |
| Selection 13-16 | 12 | |
| Verdict 1-5 | 8 | |
| Report 1-4, 14 | 15 | |
| Report 5-12, 16 | 17 | |
| Report 13, 15, 17 | 16 | |
| Invariants 1, first half | 12 | |
| Invariants 1, second half | 16 | |
| Invariants 2-4 | 7 | |
| Edge 1, 3, 10, 11, 12, 13, 20 | 7 | |
| Edge 2, 15, 16, 17, 19 | 8 | |
| Edge 4 | 4 | |
| Edge 5 | 2 | |
| Edge 6, 7, 8, 9 | 12 | |
| Edge 14 | 3 | |
| Edge 18, first clause | 8 | |
| Edge 18, second clause | 13 | |
| Edge 21, 22 | 5 | |
| Inputs: PR number required, `--pr` digits above 0 | walking skeleton, `tests/test_cli.py` | |
| Inputs: diff is `merge-base..H`, never against M | 12 | |
| Inputs: M is the merge-base or an ancestor | 14 | |
| Inputs: `no-shared-lines` for coverage with no shared line | 14 | |
| Inputs: rootdir, node ids and `own file`/`conftest` through it | 7 | |
| Inputs: floor configuration file format | 5 | |
| Inputs: record file path on the command line | walking skeleton | |
| Term: changed paths (`--no-renames`, `-z`, renames, deletions) | 2 | |
| Term: merge-base chosen by `git merge-base` | 2 | |
| Term: test context | 4 | |
| Term: row (setup, run, teardown; outside the repository) | 4 | |
| Term: empty row is no row | 6 | |
| Term: coverage data file; measured file with no line | 4 | |
| Term: path mapping to M's tree | 4 | |
| Term: column, import-only, no column | 12 | |
| Term: pair rule (`mangle_test_address`) | 6 | |
| Term: lookup by pair, one direction; shared pairs unmeasured | 6 | |
| Term: test cases with one pair merged in one file | 3 | |
| Term: counts and lists take each pair once | 12 | |
| Term: unmeasured test | 6 | |
| Term: floor, default patterns, configuration only adds | 5 | |
| Term: floor pattern syntax and validity | 5 | |
| Term: selection rules and reasons | 7 | |
| Term: red, caught, missed, green; rerun discards | 8 | |
| Term: pass in the rerun file | 3 | |
| Term: collection error recognized | 3 | |
| Term: collection error rejected | 14 | |
| Term: test case that cannot be used; pytest's internal error | 3 | |
| Term: record encoding, keys, order, escapes, sorting | 9 | |
| Term: run key; `head` as given; `junit_sha256` null | 13 | |
| Term: rejected record deduplicated whatever its `pr` | 11 | |
| Term: node id with a row in the run when its pair is | 12 | |
| Rejections: `unusable-input` and its inputs | 13 | |
| Rejections: the other five reasons | 14 | |
| Non-regular or unreadable input file: JUnit | 3 | |
| Non-regular or unreadable input file: coverage | 4 | |
| Non-regular or unreadable input file: floor | 5 | |
| Non-regular or unreadable input file: end to end | 13 | |
| Record file that exists but cannot be read | 11 | |
| Problem order | 14 | |
| Messages: what they name, never quoting a file | 1 | |
| Other failures: one line naming the class, exit 1 | walking skeleton, `tests/test_cli.py` | |
| Record file: read first, created, not a record, already recorded, exit 0 | 12 | |
| Rejected run: appended unless already there, exit 3 | 13 | |
| Usage errors: exit 2, no abbreviation, `--rootdir` rules and normalization | walking skeleton, `tests/test_cli.py` | |
| Inputs never written, whatever the outcome | 13 | |
| git runs only commands that read; no network connection | 2 | |
| Line of a record file is a record only if... | 10 | |
| Miss rate | 15 | |
| Savings | 15 | |
| JUnit time rounded half up per test case | 3 | |
| `full_ms` and `selected_ms` | 12 | |
| Floor rate | 17 | |
| No-column rate | 17 | |
| Report: not a record, missing or unreadable files | 16 | |
| Report: each key once | 15 | |
| Report: conflicts | 16 | |
| Report: rejected runs by reason and input | 16 | |
| Report: zero denominators; all-affected sentence | 15 | |
| Report: pairs, node ids and paths as JSON strings | 17 | |
| Report: order of its lists | 16 | |

Not covered by any task:
- Constraints, Performance (60 s and 1 GB for one run, 10 s for a report): measured in task 18, not tested. The SPEC already marks reading the rows at that size [VERIFY].
- "The report covers one repository and is never given record files from several": a precondition on its use, with no behaviour to test.
- Deployment: tested by no task; it is task 18's checklist.
- "Checked and [VERIFY]": a repository with "dubious ownership", defusedxml on Python 3.14, and which coverage versions write schema 7.

### Open questions
Each one is to be decided before the task that needs it.

1. **A home for `no_column`, `import_only`, `tests_with_row`, `tests_with_row_not_in_run`, `selected_ms` and `full_ms`.** Interfaces gives them no function, so as it stands they belong to `evaluate` and are tested only end to end, in task 12.
   - Proposal: four pure functions in `selection`, which already imports the types they take, in a task of their own between 8 and 9, with stubs by the user:
     ```python
     def no_column(changed: list[RepoPath], matrix: Matrix) -> list[RepoPath]: ...         # sorted
     def import_only_paths(changed: list[RepoPath], matrix: Matrix) -> list[RepoPath]: ...  # sorted
     def row_counts(rows: dict[NodeId, frozenset[RepoPath]],
                    results: dict[Pair, Result]) -> tuple[int, int]: ...  # tests_with_row, not in the run
     def durations(full: JUnit, selection: Selection) -> tuple[int, int]: ...  # selected_ms, full_ms
     ```
     They would cover Selection 13 (its no-column clause), 14 and 15, Edge 6, 7, 8 and 9, and the terms on columns, rows in the run and durations, with literals; task 12 would keep Selection 16, K1, K2, K3, K7, K13, K15 and Invariants 1. This changes the technical sheet's Interfaces, which is the user's to edit.
   - Alternative: they stay in `evaluate`. Task 12 then holds six K examples, four Selection examples, four Edge cases and every count of the record, with a git repository, a coverage file and JUnit files for each: too much for one session. It would split into 12a, the evaluated record (K1, K2, K7, Selection 13-16, Edge 6-9, Invariants 1 first half), and 12b, the record file (K3, K13, K15). 12b's tests may already pass after 12a, since appending to a missing file creates it.
2. **Is `format` a field of `EvaluatedRecord`?** Data model: "`EvaluatedRecord` (`records.py`) has the record's fields in the SPEC's order, with `key: RunKey` in place of `head` and `junit_sha256`". Readings: (a) `format` is a field, since it is one of the record's fields; (b) it is not, since its value is always 1 and `RejectedRecord`, written out, has no `format` and no `verdict`. Task 9's stubs need the answer.
3. **How percentages are written in the report.** Report 1: "a one-sided 95% Clopper-Pearson upper bound of 86.5%"; Report 2: "an upper bound of 9.5%"; Report 4: "savings of 37.5%"; Report 5: "a floor rate of 25%"; Report 7: "12.5% of tests treated as unmeasured". Readings: (a) one decimal, with `25.0%`; (b) at most one decimal, so `25%` and `37.5%`; (c) another precision, with the examples rounded. And how the bound is rounded to that precision: (a) half up; (b) up, since it is an upper bound; (c) half to even.
4. **The report's layout.** The SPEC says what the report "shows", "lists" and "says", but not its layout or wording. Readings: (a) the tests check only that each figure, list and sentence appears, and every report task adds to the text without breaking the earlier ones; (b) a layout is fixed in the SPEC before task 15, and the tests compare whole outputs.
5. **Report 9, the reason a failed test was left out.** Report 9: "it lists test_render with the reason it was left out (its row, `src/shop/pricing.py` and `src/shop/report.py`, has none of the diff's paths, and no other rule picked it), next to the diff's paths with no column (`templates/invoice.html`) and the import-only ones (none)". A record holds the test's `row`, `no_column` and `import_only`, but not the diff's paths. Readings: (a) the report shows the row and a fixed sentence that no rule picked the test; (b) the report shows the diff's paths, which needs a new record field and so a change to record format 1.
6. **Spaces and comments in the floor configuration.** Inputs: "Blank lines and lines that start with `#` are ignored, and spaces at either end of a line are not part of its pattern." Readings for "spaces": (a) U+0020 only; (b) any whitespace, tabs included. Readings for "start with `#`": (a) the line's first character, so `  # x` is the pattern `# x`; (b) after dropping the spaces, so `  # x` is a comment. And "blank lines": (a) empty only; (b) spaces only too. Task 5 needs the answers.
