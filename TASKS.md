# Tasks

- In the tests phase nothing stops the agent from creating the files that implement freezes (pytest.ini, ruff.toml, .gitattributes and the rest of `FROZEN_AT_ROOT` and `FROZEN_ANYWHERE` in `.claude/hooks/phase.py`); one that enters the tests commit becomes implement's reference.
- `.git/info/` could be written from the agent's Bash, and git does not track it: `.git/info/attributes` outranks every `.gitattributes`, and `.git/info/exclude` hides untracked files from `scripts/check_characters.py`. Done in fbb10d9: `"Edit(/.git/info/**)"` is among the deny rules of `.claude/settings.json`. With the rules for .venv, .git/hooks and .git/config, the Bash sandbox made those read-only; the same is expected for .git/info [VERIFY].
- `clean_environment` in the Stop hook drops `GIT_CONFIG_KEY_n`, whose names hold KEY, but keeps `GIT_CONFIG_COUNT`, so git fails inside Stop's bwrap wherever that variable is set. The Bash sandbox sets it, which is why the implement-phase Stop tests fail there.
- `rev-parse --verify --quiet --end-of-options NAME^{commit}` exits with 128, not 1, for some names that name no commit, such as `HEAD@{99}` with a shorter reflog (run with git 2.43.0, 2026-10-18); the SPEC's "Checked" lists only 1. `git.resolve_commit` gives `None` for any failure, and no test pins the 128 case.
- No test pins what `is_shallow`, `merge_base`, `is_ancestor`, `changed_paths` and `tree_files` do when git fails with an exit code that is not one of their answers, such as 128 for an unknown commit id (run with git 2.43.0, 2026-10-18): they raise `CalledProcessError`, through `check_returncode`, rather than answer, so a failed `diff` never becomes an empty diff.
- `junit.read_junit` gives `None` for any `OSError` from `Path.is_file`, which runs `os.stat`, or from `read_bytes`, not only in the four cases its tests pin: a missing file, a directory, a file with mode 0 and a FIFO. `os.stat` follows symbolic links, so a link to a regular file is read, while a dangling link, a loop of links, a link to a FIFO or to a directory, a regular file used as a directory, a character device and a file in a directory the tool may not search all give `None` (run with Python 3.12.3, 2026-10-18). No test pins links. A path swapped for a FIFO between that `os.stat` and the `open` would still block: Rule 3 checks before it opens.
- `junit.parse_junit` takes every `testcase` element as a test case, at any depth and under any root, so a well-formed file with none, such as `<html><body/></html>`, gives no results and is not rejected; and it looks for `failure`, `error` and `skipped` only among a test case's own children, so a `failure` inside its `properties` fails nothing (run with defusedxml 0.7.1 on Python 3.12.3, 2026-10-18). pytest 9.1.1's `to_xml` writes them as the test case's children, under `testsuites` and `testsuite`. No test pins either.
- A collection error's test case is also among `parse_junit`'s results, as a failed test under its pair, (`""`, `tests.test_report`) for K9's (run with Python 3.12.3, 2026-10-18). No test pins whether it is there: a full-run JUnit that holds one is rejected anyway, and in a rerun file a failed test discards no failure.
- A `time` that matches Rule 5's pattern but rounds to 10^25 s or more makes `Decimal.quantize` raise `decimal.InvalidOperation`, since the default context keeps 28 digits: `9999999999999999999999999.9994` gives 9999999999999999999999999999 ms, and `9999999999999999999999999.9995` raises (run with Python 3.12.3, 2026-10-18). That is no `Rejected`, so the run ends as an unexpected failure, exit 1 with no record, although by the SPEC the test case can be used. No test pins it.
- `parse_junit` turns only Rule 5's three exceptions into rejections, and raises each `from None`, so that no traceback shows the parser's error, whose text can quote the file. An XML declaration naming an encoding that Python lacks makes `fromstring` raise `LookupError`, and one naming a multi-byte encoding that expat lacks, such as `shift_jis`, `ValueError`, both from pyexpat's handler for unknown encodings (run with defusedxml 0.7.1 on Python 3.12.3, 2026-10-18). Neither is a `Rejected`, so the run ends as an unexpected failure, exit 1 with no record. Whether such a file is "not well-formed XML", and so `unusable-input`, is the SPEC's to say; no test pins it.
- A file whose internal subset refers to an undeclared parameter entity before it declares an entity, as `<!DOCTYPE testsuites [%pe;<!ENTITY unused "never used">]>` does, is not `unsafe-xml`: without `standalone="yes"`, expat skips the entity declarations after such a reference, defusedxml is never told of them and raises nothing, and the file parses (run with defusedxml 0.7.1 on Python 3.12.3, 2026-10-18). Nothing is resolved or expanded: a reference to that entity in content raises `ParseError`, so `unusable-input`, and one in an attribute is dropped, so `classname="&module;"` reads as `""`. There the SPEC's "declares an entity, even one it never uses" and Rule 5's defaults disagree; no test pins it.
- coverage joins a static context, such as `[run] context = ci`, to pytest-cov's test contexts as `ci|<node id>|run` [VERIFY], and splitting at the last `|` then gives `ci|<node id>`, a node id that matches no JUnit pair, so every test would count as unmeasured. Deployment does not forbid a static context; task 19's checklist could require recording M without one. Found in task 4's tests phase, 2026-10-19; no test pins it.
- The SPEC does not say whether `|run`, a context whose node id is empty, is a test context; the rule gives `""` as its node id. pytest never writes an empty node id. No test pins it. `node_id_of` follows the rule (2026-10-19).
- The Data model does not say whether `RawCoverage.nodes_by_file` lists a recorded file in which no node id has a line, with an empty set; task 4's tests accept both. `read_coverage` leaves such a file out, so every file it lists has a node id (2026-10-19).
- import-linter does not look inside external packages, so the network contract cannot see that coverage 7.16.2's `sqldata.py` imports `socket`; it calls only `gethostname()`, for data file suffixes, which the reader does not use [VERIFY].
- `read_coverage` makes D-002's copy by reading the original's bytes and writing them to a file in a `tempfile.TemporaryDirectory`, which goes, copy and all, when the reader returns or raises. Only that read opens the original; coverage gets only the copy's path, and the whole file is in memory while it is copied. An `OSError` from `Path.is_file`, which runs `os.stat`, or from reading the original is `unusable-input`, as in `junit.read_junit`: a symbolic link to a regular file is read, and a dangling link, or a link to a FIFO or to a directory, is rejected without blocking. An `OSError` from creating the directory or writing the copy, such as a full disk, is not the coverage file's and is not converted, so the run ends as an unexpected failure, exit 1 with no record (run with Python 3.12.3, 2026-10-19). No test pins links or a copy that cannot be written.
- `read_coverage` turns into `unusable-input` only Rule 3's `coverage.CoverageException` and `sqlite3.Error`, raised by `read()` or by any query: a copy cut only a little short passes `read()` and raises `sqlite3.DatabaseError` from `contexts_by_lineno`, which coverage does not wrap, while the tests' copy, cut at half, raises `DataError` from `read()` (run with coverage 7.16.2 and SQLite 3.45.1 on Python 3.12.3, 2026-10-19). An SQLite file with coverage's tables and values that coverage does not expect makes it raise other errors: `ValueError` from `read()` for a `has_arcs` in `meta` that is not a number, `AssertionError` from `read()` for two `has_arcs` rows in a `meta` table without its unique key, and `TypeError` from `contexts_by_lineno` for `numbits` that are not a blob or an arc's `fromno` that is text (same run). None is a `Rejected`, so the run ends as an unexpected failure, exit 1 with no record. Whether such a file is "not a coverage data file", and so `unusable-input`, is the SPEC's to say; no test pins it, nor the `sqlite3.Error` from a query.
- With several invalid patterns, the SPEC does not say which line the floor configuration's rejection names. A file saved as UTF-16 without a byte order mark, with only ASCII, has a NUL, and so an invalid pattern, in every line that is not a comment; with UTF-16LE, a first line that is a comment stays one, since its `#` comes before its NUL. Found in task 5's tests phase, 2026-10-20; no test pins it. `read_floor` names the first, since it stops at the first invalid pattern: line 2 for UTF-16LE whose first line is a comment (run with Python 3.12.3, 2026-10-20).
- A NUL in a comment line makes nothing invalid, since a comment is not a pattern, but no test pins it: an implementation that rejected any NUL in the floor configuration would pass task 5's tests. `read_floor` checks a line's validity only once the line is a pattern, so a comment that holds a NUL is ignored like any other (run with Python 3.12.3, 2026-10-20).
- The SPEC does not say whether the floor configuration may be a symbolic link, as it does not for the JUnit and coverage files; no test pins it. `read_floor` reads the file as `junit.read_junit` does: `Path.is_file`, which runs `os.stat` and follows symbolic links, then `read_bytes`, which opens it for reading only, and an `OSError` from either is `unusable-input`. So a link to a regular file is read, while a dangling link, a loop of links, a link to a FIFO or to a directory, a regular file used as a directory, a character device and a file in a directory the tool may not search are `unusable-input`, with no line number, and none blocks (run with Python 3.12.3, 2026-10-20). A path swapped for a FIFO between that `os.stat` and the `open` would still block, as for the JUnit files.
- The SPEC does not fix the order of `DEFAULT_PATTERNS`; task 5's tests compare without order. `DEFAULT_PATTERNS` keeps the order in which the SPEC lists them (2026-10-20).
- The SPEC does not say what `matches` and `floor_hits` do with an invalid pattern; `read_floor` rejects one first, so `evaluate` never passes one. No test pins it. `matches` checks no validity and applies its rules to any pattern: `?`, `[` and `]` match themselves, a `**` inside a segment acts as one `*`, so `**.lock` matches `uv.lock` but not `a/uv.lock`, and an empty, `.` or `..` segment, or a NUL, matches no path that git lists (run with Python 3.12.3, 2026-10-20).
- `read_floor` keeps a pattern as many times as the configuration writes it, and a default pattern that the configuration writes again is there twice, among the defaults and among the file's; `floor_hits` then gives each of its pairs once for each time (run with Python 3.12.3, 2026-10-20). `floor_hits` gives its pairs pattern by pattern, in the order of the patterns it is given, and for each one the changed paths in their order. No test pins either; open question 8 asks which pairs a reason cites.
- `matches` tries, for each `*`, every number of characters it could take, and for each `**` that does not end the pattern, every number of segments, so its time grows as a power of the number of wildcards in one pattern. The default patterns, `data/**` and `db/*.sql` against 2,000 changed paths of six segments, none of which they match, take 0.05 s; against a name of 255 `a`, which it does not match, the segment `*a*a*b` takes 0.34 s and `*a*a*a*b` 22 s, and `**/**/**/**/x` against a path of 100 segments takes 1.1 s (run with Python 3.12.3, 2026-10-20). Decided, 2026-10-20: a known limit, with no cycle of its own. If a real configuration needs it, the linear algorithm stays an option: each piece between two `*`, and each run of segments between two `**`, taken as early as it can be, so that the time no longer grows as a power of the number of wildcards. It adds a branch, for a piece that is not there, that no test reaches, so it would need a tests phase first. No test pins the time.
- Tests use `selection.Test`, never `from distiller.selection import Test`: pytest tries to collect a class named `Test` in a test module, and with `filterwarnings = ["error"]` its `PytestCollectionWarning` interrupts the whole session, with no test run (pytest 9.1.1). Tasks 7 to 9 use `Test` too. Found in task 6's tests phase, 2026-10-21.
- pyright in strict mode rejected, as a `dict[Pair, Result]`, a dict of pair constants assigned to a variable with no annotation: five errors in task 6's tests phase, gone once the variable was annotated, as `K1_RESULTS` is. The tests of tasks 7 to 9 will have such dicts too.
- The SPEC's pair rule does not describe every node id, and no test of task 6 pins these. What pytest 9.1.1's `mangle_test_address` gives, checked by running it on 2026-10-21: with no `::` before the first `[`, the classname is empty, so a collection error's `tests/test_report.py` gives (`""`, `tests.test_report`) and `tests/v[1]/test_x.py::test_m` gives (`""`, `tests.v[1]/test_x.py::test_m`); a `::` in a directory, as in `tests/a::b/test_x.py::test_m`, gives (`tests.a.b/test_x.py`, `test_m`); and a `.py` followed by a newline at the end of the path is dropped too, the newline kept. `pair_of` takes `mangle_test_address`'s steps, so it gives those pairs for the first three, but it drops the final `.py` with `removesuffix`, as the pair rule says, and keeps a `.py` followed by a newline: such a node id's pair is not the one pytest writes, and its test would count as unmeasured, and so be selected (compared with pytest 9.1.1 on Python 3.12.3, 2026-10-21).
- In a test's `name`, pytest writes each character that XML does not allow, and DEL, as `#x` and its code (`bin_xml_escape`), which the pair rule does not do. By default pytest has already turned such characters in parametrize ids into backslash escapes, in the node id too, so none is left for `bin_xml_escape`; only with the ini option `disable_test_id_escaping_and_forfeit_all_rights_to_community_support` would such a test count as unmeasured, and so be selected. Checked by running pytest 9.1.1 on Python 3.13, 2026-10-21. `pair_of` follows the pair rule and escapes nothing (2026-10-21).
- A doctest's name is what follows the `::` of its node id, as `tax.txt` in `docs/tax.txt::tax.txt` and `shop.tax.vat` in `src/shop/tax.py::shop.tax.vat`, while the SPEC's pair rule speaks of the function with its parameters; task 6's tests pin what pytest writes.
- `match_tests` gives one `Test` for each pair in the run, whatever its result, a skipped test's included, and none for a node id whose pair is not in the run. The SPEC fixes no order for the list; task 6's tests compare in pair order. `match_tests` sorts its tests by pair, `classname` and then `name` by code point, as records sort pairs, so the list depends on which tests the run has and not on the order of the JUnit's test cases (run with Python 3.12.3, 2026-10-21).
- `make test-red` prints pytest's short summary trimmed to the terminal's width, and drops a failure's exception when a long test id leaves it no room (`_format_trimmed` in pytest 9.1.1's `terminal.py`), so a tests phase may not read there that its tests fail with `NotImplementedError`. Task 7's tests phase checked it with a temporary block that turned only `NotImplementedError` into a skip, and every new test was skipped. `-vv` would show the exception, but would also let the text of one raised in `src/` into the tests session. Found in task 7's tests phase, 2026-10-21.
- Invariant 2 is pinned in pieces: `match_tests` ignores the results (task 6) and `select` gets none (task 7). No task evaluates two runs that differ only in which tests failed and how long they took, and a record does not hold the selection, so an end-to-end test could not compare theirs.
- With a `::` in a directory, as in `tests/a::b/test_x.py::test_m` (task 6's note), the file in the node id, what comes before its first `::`, is `tests/a`: a change to the test's own file does not pick it, and the `conftest` rule starts at `tests/` and misses `tests/a::b/conftest.py`. No test pins it. `select` follows the SPEC's rule: with pytest's rootdir at the repository root, a diff that changes `tests/a::b/test_x.py` or `tests/a::b/conftest.py` leaves that test out, one that changes `tests/conftest.py` picks it with `conftest tests/conftest.py`, and one that changes a file named `tests/a`, if there is one, picks it with `own file tests/a` (run with Python 3.12.3, 2026-10-21).
- `match_tests` and `floor_hits` never give `select` a floor hit whose path is not a changed path, a `Test` with a node id and no row or a row and no node id, or two `Test`s with one pair. The SPEC does not say what `select` does with them, and no test pins it. `select` gives every test every floor hit it gets, so a hit whose path is not a changed path would break Invariant 4. It looks only at a test's row for `unmeasured` and `covers`, and only at its node id for `own file` and `conftest`: a test with a node id and no row gets `unmeasured`, and `own file` and `conftest` too when they pick it; one with a row and no node id is never `unmeasured`, and only `covers` and the floor pick it; and one with an empty row, which `match_tests` turns into `None`, is neither `unmeasured` nor picked by `covers`. Of two `Test`s with one pair, the later one that a rule picks replaces the earlier one's reasons, so their order changes the selection (run with Python 3.12.3, 2026-10-21).
- `select` gives the selected tests in the order of the tests it gets, which `match_tests` sorts by pair. The SPEC fixes no order for a `Selection`, a dict, and no test pins it, since dicts compare without order (run with Python 3.12.3, 2026-10-21).
- `judge` never gets a full run with a collection error, which is rejected first, a failed pair with no `Test` among the run's tests, a selected pair that is not in the run, or a `Result` both failed and passed. The SPEC does not say what `judge` does with them, and no test pins it. Found in task 8's tests phase, 2026-10-22. `judge` reads neither file's `has_collection_error`, so a full run that holds a collection error is judged by its results alone, and the error's own test case, failed, makes the run caught once `select` picks it as unmeasured, as the SPEC says. A failed pair with no `Test` is still one of the run's failed tests: if the selection holds it, it makes the run caught; if not, looking up its `Test` raises `KeyError`, so the run would end as an unexpected failure, exit 1 with no record, instead of with a `missed` record whose `failed_left_out` leaves it out. A selected pair that is not in the run changes nothing, since `judge` looks up only the failed pairs in the selection. Of a `Result`, `judge` reads only `failed` in the full run and only `passed` in the rerun file, so one both failed and passed is a failure in the full run and, in the rerun file, discards the failure. Nor does `judge` get two `Test`s with one pair, which `match_tests` never gives, or a failed unmeasured `Test` that the selection leaves out, since `select` picks every unmeasured test: of two `Test`s with one pair, the later one in the list gives `failed_left_out` its node id and row, and an unmeasured one is listed with neither (run with Python 3.12.3, 2026-10-23).
- The SPEC rejects a collection error only in the full run's JUnit, so a rerun file that holds one is used: the tests it could not collect are missing from it, so their failures stand (Edge 16), and the error's own test case, which did not fail in the full run, is ignored (Edge 18). Task 8's tests assume it, and task 15, the problem order, should keep it.
- `Judgement.not_reproduced` is a `frozenset`, so whoever builds a record's `not_reproduced` has to sort it by pair, as Rule 8 says. K2 has a single pair; task 10's tests check two or more, since `encode` sorts every list it writes, whatever order the record holds it in (decided in task 10's tests phase, 2026-10-24). Task 13's `evaluate` sorts it, with `sorted`, where it builds the record's tuple, and takes `failed_left_out`, `no_column` and `import_only` as `judge`, `no_column` and `import_only_paths` give them, already sorted (2026-10-25).
- No task pins a record's `tests` and `unmeasured` in Edge 6 and 7: no function of Interfaces gives them, and task 13's Covers has neither edge case; K1 pins only `"tests":4` and `"unmeasured":0`. Task 13, which builds the record, should pin them. Found in task 9's tests phase, 2026-10-23. Task 13's tests pin them: Edge 6 gives `"tests":4` and `"unmeasured":1`, Edge 7 gives 3 and 0 with test_vat deleted and 4 and 1 with it renamed, and all three give `"tests_with_row":4` and `"tests_with_row_not_in_run":1` (2026-10-25). `evaluate` counts as `tests` the `Test`s that `match_tests` gives, one for each pair of the full run, whatever its result, so a skipped test counts, as the SPEC's unmeasured share takes in skipped tests (Report 8), and as `unmeasured` those of them with no row: K1's run with test_vat skipped gave `"tests":4` and `"unmeasured":0`. No test has a skipped test end to end (run with Python 3.12.3, 2026-10-25).
- That `full_ms` ignores a `testsuite` element's `time` can be pinned only end to end, since `JUnit` does not hold that time: task 13's K1 JUnit file should give its `testsuite` a time other than 12.0 s, so that `"full_ms":12000` pins it. Task 13's K1 JUnit file gives its `testsuite` a time of 12.871 s, and K1's line pins `"full_ms":12000` (2026-10-25).
- `no_column`, `import_only_paths`, `row_counts` and `durations` never get a changed path listed twice, a selected pair that is not in the full run, or a path that is both in a row and import-only. The SPEC does not say what they do with them, and no test pins it. `no_column` and `import_only_paths` take the changed paths as a set, as `select` does, so a path listed twice is listed once: a list with a repeat would make the record's line one that `decode` rejects (Rule 7). `durations` looks up only the full run's tests in the selection, so a selected pair that is not in the full run adds nothing to `selected_ms`, which never exceeds `full_ms`. `import_only_paths` lists every changed path that the matrix has as import-only, and `no_column` none that is in a row, so a path both in a row and import-only is listed as import-only and not as having no column (run with Python 3.12.3, 2026-10-24).
- `encode` never gets a list that repeats an element (a pair, a path or two tests with one pair), a test in `failed_left_out` with no node id or no row, which `Judgement` rules out, a `verdict`, `reason` or `input_name` outside the allowed values, or a negative number. The SPEC does not say what it does with them, and no test pins it; a repeat, or a value outside the allowed ones, would give a line that `decode` rejects (Rule 7). Found in task 10's tests phase, 2026-10-24. `encode` checks none of them and writes what the record holds, its lists sorted: a repeated pair or path is written each time, next to its twin, and two tests with one pair keep the record's order, since `sorted` is stable and compares only their pairs; a value outside the allowed ones, such as an evaluated record whose `verdict` is `rejected`, and a negative number, as in `"pr":-1`, are written as they are; a test with no node id gets `"node_id":null`; and one with no row makes `sorted` raise `TypeError`, since `cast` only tells pyright that the row is set and checks nothing, so the run would end as an unexpected failure, exit 1 with no record. Nor does `encode` get an evaluated record whose key has no SHA-256, since an evaluated run's JUnit file was read; every record's first keys are written alike, so it would get `"junit_sha256":null` (run with Python 3.12.3, 2026-10-24).
- `read_record_file` (task 12) has to split the file after each `\n` only, keeping each line's newline, and must not pass `decode` the empty piece that a split leaves after the last newline: `decode` gives `None` for `b""`, as for any line without its newline. Found in task 11's tests phase, 2026-10-24. Rule 7 says it since task 12, 2026-10-25.
- A `--pr` of more than 4,300 digits is ASCII digits above 0, so no usage error by the SPEC, but Python's default limit on converting between `int` and `str` keeps `int()` from reading it, and `json.loads` from reading such a `pr` in a line. No test pins what the command line does with one. Task 11's test of a `pr` of 4,301 digits assumes that default: with `PYTHONINTMAXSTRDIGITS=0`, which lifts it, that line would be a record.
- A string that holds a high surrogate followed by a low one, as two code points, would not come back the same from `encode` and then `decode`: `json.loads` joins their two escapes into one character. No input gives one: `os.fsdecode` and the command line give only the low surrogates U+DC80 to U+DCFF, and a JUnit attribute cannot hold a surrogate. No test pins it.
- `decode` gives `None` whatever `json.loads` raises, as Rule 7 says, by catching `Exception`, and not only the four exceptions that task 11's tests provoke: `JSONDecodeError`, `UnicodeDecodeError`, the `ValueError` for a number of 4,301 digits and `RecursionError`. Any other, such as a `MemoryError`, also makes the line one that is not a record, so the tool would name that line instead of ending with an unexpected failure, both with exit 1. `KeyboardInterrupt` and `SystemExit` are not `Exception`s and go through. No test pins any other exception; a `MemoryError` from `json.loads`, made with `unittest.mock` outside the tests, gave `None` (run with Python 3.12.3, 2026-10-24).
- With several lines that are not records, the SPEC does not say which one `NotARecord` names, as it does not say which invalid pattern the floor configuration's rejection names; each of task 12's tests has a single such line. Found in task 12's tests phase, 2026-10-25. `read_record_file` names the first: it decodes the lines in the file's order and stops at the first that is not a record, as `read_floor` stops at the first invalid pattern, so a file whose lines 2 and 4 are not records gives line 2 (run with Python 3.12.3, 2026-10-25).
- Task 12's tests cannot tell Rule 8's append, one write of the whole line to a file opened for appending, from two writes or from a rewrite of the file in place, which leave the same bytes and the same inode; and none appends after a last line torn by a killed runner or a full disk, so an `append_record` that read the file and wrote a newline before its line would pass them. `evaluate` never appends after a torn line: it reads the record file first, and a torn line is not a record. Found in task 12's tests phase, 2026-10-25. `append_record` encodes the line before it checks the path or opens anything, so a record that `encode` cannot write (note 44) creates no file. It opens the file with `Path.open("ab")`, whose flags are `O_WRONLY|O_APPEND|O_CREAT|O_CLOEXEC` (seen in Python's `open` audit event), and calls `write` once, with the whole line, through Python's default buffer, 4,096 bytes here, the file system's block size. In the normal case the buffer hands the line to the system in one `write`: strace showed one for lines of 156 and 34,649 bytes (run with Python 3.12.3 on Linux, 2026-10-25). `BufferedIOBase.write`'s docstring promises only that the whole line is written, not in how many system calls, so the one `write` is CPython's behaviour, to check again when Python is upgraded. Nothing reads the file, whatever its last line holds. If the system writes only part of the line, as when a disk fills during the write, the buffer tries to write the rest and raises `OSError` if it cannot, so `evaluate` would end as any other failure, exit 1, with no branch of its own in `append_record`. Run with Python 3.12.3, 2026-10-25, with the file size limit `RLIMIT_FSIZE` standing in for a full disk and `SIGXFSZ` ignored: K10's line of 218 bytes cut 10 bytes in, and a line of 440,619 bytes cut in its middle, each left the file exactly at the limit and raised `OSError` with `EFBIG`, which only a second write, for the rest, can raise, since with no buffer the same cuts returned with no error; reading the file then gave `NotARecord` for the torn line, whose bytes stay. A second write that succeeds, which would put one line in two writes, was not seen: past that limit every write fails. No test pins the write cut short.
- A `--records` path in a directory that does not exist, or a record file that exists but cannot be written, is read as `None` or as its records, so the run is evaluated and only the append raises `OSError`: any other failure, exit 1, with no record, even for a rejected run, which would otherwise exit with 3. The SPEC takes a missing record file as empty but says nothing of these. Found in task 12's tests phase, 2026-10-25. Task 13's `evaluate` does so: K1's run with `--records ./nodir/records.jsonl` was evaluated and ended as `distiller: unexpected failure: FileNotFoundError`, exit 1, with no directory or file created, and with a record file of mode 0o444 as `PermissionError`, the file left as it was (run with Python 3.12.3, 2026-10-25).
- No test of task 12 gives `read_record_file` or `append_record` a symbolic link (to a regular file, broken or in a loop), a path through a regular file (`ENOTDIR`) or a directory without search permission. The SPEC does not say which of them reading takes as no file, `None`, and which as a file that cannot be read, `OSError`, nor what appending through a broken link does: `os.stat` follows links and finds nothing behind a broken one, and opening that link to append creates the file it names (checked on Linux, 2026-10-25). Found in task 12's tests phase, 2026-10-25. Both functions take as nothing there only what `os.stat`, which `Path.stat` runs, reports as `FileNotFoundError`, a missing directory on the path included, and let any other `OSError` from it through, so that a path the tool cannot look at would stop `evaluate` before the run is evaluated. Run with Python 3.12.3 on Linux, 2026-10-25: a link to a regular file is read as that file, and the append writes to that file, the link staying a link; a broken link is read as `None`, and the append creates the file it names, or raises `FileNotFoundError` when that file's directory is missing too; and a loop of links makes both raise `OSError` with `ELOOP`, a path through a regular file `NotADirectoryError`, and a file in a directory without search permission `PermissionError`, each leaving every file as it was. A directory or a FIFO at the path makes both raise an `OSError` of their own, with no subclass and no errno, before anything opens it.
- A path swapped for a FIFO between `os.stat` and the open would still block `read_record_file` or `append_record`, as it would `read_junit` and `read_floor`. Opening with `O_NONBLOCK` and then checking with `os.fstat`, instead of Rule 3's `os.stat` first, would not block: a FIFO opened that way for reading opens at once, and one opened for writing with no reader fails with `ENXIO` (checked on Linux, 2026-10-25). Found in task 12's tests phase, 2026-10-25.
- The SPEC does not fix the permissions of the record file that the append creates. Found in task 12's tests phase, 2026-10-25. `append_record` sets no mode of its own: the file is created as `open` creates any file, with mode 0o666 less the process's umask, so 0o644 with a umask of 0o022, 0o666 with 0o000 and 0o600 with 0o077 (run with Python 3.12.3, 2026-10-25).
- ruff takes a comment line that starts with `noqa`, such as one explaining why a test has `# noqa: PT011`, for a directive that silences nothing (RUF100), and the format hook's fix deletes the line: task 12's tests phase had to write such a comment again, worded so that no line of it starts with `noqa`. Found in task 12's tests phase, 2026-10-25.
- Task 13's test of Invariant 1 evaluates the run twice in one process, so it cannot see an order that changes from one process to the next, such as a set's under another hash seed: what keeps such an order out of a record is that `encode` sorts every list it writes (task 10). Found in task 13's tests phase, 2026-10-25. Run by hand as six processes, under `PYTHONHASHSEED` 0 to 5, a run whose rerun file discards three failures gave five orders of `Judgement.not_reproduced` and one of the record's, which `evaluate` sorts (note 40), and six byte-identical record files (run with Python 3.12.3, 2026-10-25).
- Task 13's tests see K7's exit code 0 as what `evaluate.run` returns; that what `cli.main` returns becomes the exit code of `python -m distiller` is shown only by `tests/test_main.py`, with K15's 1. Found in task 13's tests phase, 2026-10-25.
- No test checks what `evaluate` does when the checkout's HEAD is not H: the SPEC asks only for H in a checkout with history, and the git queries name every commit by its id. Found in task 13's tests phase, 2026-10-25. Task 13's `evaluate` reads neither the checkout's HEAD nor its work tree: it resolves H from `--head`, whatever is checked out, and every other git command names commits by their ids. The tests' checkout has `main` checked out, B, while H is pr-7's head; and from a copy of it with `pr-58` checked out, `templates/invoice.html` changed in the work tree and an untracked file added, K1's run gave K1's line (run with git 2.43.0, 2026-10-25).
- A run already recorded is not appended again even with another `--pr` or another M, since the key holds neither; K3's test uses the same inputs, and no test pins the other two. Found in task 13's tests phase, 2026-10-25. `evaluate` looks the run up by its key alone, through `has_evaluated`: with K1's line in the record file, K1's run given `--pr 8`, and given the merge-base's id as M, each warned that the run is already recorded, naming its key, and exited with 0, the file left as it was (run with Python 3.12.3, 2026-10-25).
- `tests/test_evaluate.py` writes the fixture's commit ids and its JUnit file's SHA-256 as literals, in K1's line: git builds the same ids from the same contents, messages, identity and dates, and the module's fixture fails, naming the ids it got, if git builds others. Checked with git 2.43.0 on two machines; CI runs the runner's git. Found in task 13's tests phase, 2026-10-25.
- Until task 14, `evaluate` rejects nothing: an input that task 14 rejects as `unusable-input` ends as an unexpected failure, exit 1, with nothing appended and the record file left as it was (run on the fixture of `tests/test_evaluate.py` with Python 3.12.3 and git 2.43.0, 2026-10-25). A reader's `Rejected` reaches `cli`, which prints `distiller: unexpected failure: Rejected`, for a coverage file that is missing, of 0 bytes, which stays 0 bytes long, or of text; a JUnit or rerun file that is not well-formed; a JUnit test case with no `time`; pytest's internal error; and a floor configuration that is missing or has an invalid pattern. A `None` that one of `evaluate`'s `cast`s lets through makes a later call raise `TypeError`, printed as `distiller: unexpected failure: TypeError`: `hashlib.sha256`, in step 2, before the record file is searched for the run's key, for a JUnit file that is missing or is a directory; `git.merge_base`, which hands the `None` to `subprocess.run`, for a directory that is not a git checkout and for an H or a base that names no commit; `git.changed_paths`, once every input has been read, for a base whose commit shares no history with H; `git.tree_files`, after the diff, for an M that names no commit; and `parse_junit`, through defusedxml's `fromstring`, for a rerun file that is missing. The comment on each `cast` names what task 14 rejects there.
- Until task 15, `evaluate` checks neither whether the checkout is shallow, M's ancestry, the shared lines nor a collection error, and three of the runs that task 15 rejects are evaluated today: their record is appended and the tool exits with 0 (run on the fixture of `tests/test_evaluate.py` with Python 3.12.3 and git 2.43.0, 2026-10-25). K1's run with its coverage at H, given as `--coverage-commit pr-7`, gives K1's line but for `coverage_commit`, which holds H's id; with coverage in which no line is shared, K1's line; and with a JUnit file that holds only a collection error, for `tests/test_report.py`, a `caught` record with `"full_ms":0`, `"tests":1`, `"unmeasured":1`, `"tests_with_row":4` and `"tests_with_row_not_in_run":4`, the error's own test case selected as unmeasured, as the SPEC says. A record file that holds such a record keeps it once task 15 is in: the same inputs find the run already recorded, by its key, in step 2, before any check. A clone made with `--depth 1 --no-single-branch`, in which H and the base resolve but neither M nor a merge-base is there, ends as `distiller: unexpected failure: TypeError`, from `git.changed_paths`, exit 1 with nothing appended; and a JUnit file that declares an entity as `distiller: unexpected failure: Rejected`, like the inputs of note 61.
- `evaluate` asks git for the merge-base of B and H in that order, `git merge-base B H`, as the SPEC words it: "the merge-base of B and H". No test pins the order, and with several best common ancestors it can change which one git prints: for two merge commits X and Y, each of which merged the other's branch, whose two best common ancestors had the same commit date, `git merge-base X Y` printed X's first parent and `git merge-base Y X` Y's, while with different dates both printed the later one (run with git 2.43.0, 2026-10-25). The SPEC's "the one that `git merge-base` prints" does not say in which order git gets the two commits. Since task 13 it says `git merge-base B H`, with B first (2026-10-25).

## Slice 1

Eighteen tasks, each one cycle: a tests session, which cannot read `src/`, then an implement session, with the tests frozen. Task 19 is outside the cycle. The tasks go bottom up through the imports that the technical sheet's signatures and types imply (each type lives in the module that creates it): `messages` and `git` import no module of the package; `junit`, `coverage_at_m` and `floor` use `Rejected` and `RepoPath`; `selection` uses their types; `records` uses `Pair` and `Test`; `evaluate` and `report` sit on top. Each task, once done, leaves main green and depends on no later task.

A module that does not exist yet gets its stubs from the agent, in the tests phase, with its import-linter contract. A signature missing from a module that exists is the user's to write before the tests phase. With `fail_under = 100`, a stub that no test runs turns main red, so `selection` is split into four tasks and `records` into three: the first of each creates the module with its own stubs only.

How to read the fields:
- **Closes**: the behaviour that the task's tests pin down.
- **Covers**: the [core] examples (K, from the technical sheet's table), the other examples and the rules of Slice 1's prose. Other examples are named by their section and position: Selection 1-16, Verdict 1-5, Report 1-17, Invariants 1-4 and Edge 1-22, in the order of `docs/SPEC.md`. Prose rules are named by the term or the paragraph they belong to.
- **Constrained by**: the K examples that the task cites. A task cites a K example when that K's "then" shows what one of the task's own functions returns, raises or leaves in a file, for inputs that the K's "given", fixture included, states explicitly. Its tests use those exact values. In addition, the decode task uses the record lines that K1 and K4 show, which are records by definition, and K15's line holding canary, which is not one. The task's own functions are those under its Stubs, and the fixture that an example uses is part of its "given".
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
- **Constrained by**: K6 (`unsafe-xml`, with `junit` or `rerun`), K8 (`unusable-input`, with `junit` or `rerun`), K13 (the JUnit file is left byte for byte as it was).
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
- **Constrained by**: K1 (the row of `tests/test_report.py::test_render`, `"row":["src/shop/pricing.py","src/shop/report.py"]`), K8 and K14 (`unusable-input`, with `coverage`), K13 (the coverage file is left byte for byte as it was), K14 (an empty file stays 0 bytes long).
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
- **Covers**: prose, Inputs, the floor configuration: blank lines, lines that start with `#`, spaces and tabs at either end, UTF-8 with a byte order mark and `\r\n` endings, a file that is not valid UTF-8. Prose, "The floor is the default patterns...", and "A configuration adds patterns and never removes them". Prose, "Floor patterns have their own syntax...": segment matching, `**`, `*`, the invalid patterns, and its examples (`**/uv.lock`, `config/**`, `**/requirements*.txt`). Prose, the rejection reasons: `floor` for a configuration that cannot be read or has an invalid pattern, with the pattern's line number. Prose, "An input file that exists but is not a regular file...", for the floor configuration. Technical sheet, Rule 9 (lines split on newline only, then spaces and tabs dropped from both ends). Edge 21, Edge 22.
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
- **Constrained by**: K1 (test_render's entry in `"failed_left_out"`, `{"pair":["tests.test_report","test_render"],"node_id":"tests/test_report.py::test_render","row":["src/shop/pricing.py","src/shop/report.py"]}`).
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
- **Covers**: Selection 1-12, and the selection in Selection 13-15 and Edge 6, 8 and 9, whose other figures are task 9's. Invariants 2, 3 and 4. Prose, "The selection is every test in the run that at least one rule picks...": the five rules, every floor hit cited by every test, once (question 8), `conftest` up to pytest's rootdir, and an unmeasured test picked only by `unmeasured` or a floor reason. Prose, Inputs, pytest's rootdir: node ids relative to it, `own file` and `conftest` resolved through it. Edge 1, 3, 10, 11, 12, 13 and 20.
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
- **Covers**: Verdict 1-5. Prose, "A run is red when...": only a pass in the rerun file discards a failure, the test is then marked not reproduced; caught, missed and green. Edge 2, 15, 16, 17, 18 (its first clause; that the rerun file is still rejected is task 14's) and 19.
- **Constrained by**: K1 (`"verdict":"missed"`, `"not_reproduced":[]`, `"failed_left_out":[{"pair":["tests.test_report","test_render"],"node_id":"tests/test_report.py::test_render","row":["src/shop/pricing.py","src/shop/report.py"]}]`), K2 (`"verdict":"green"`, `"not_reproduced":[["tests.test_report","test_render"]]`, `"failed_left_out":[]`).
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

### 9. Figures of an evaluated run
- **Closes**: the changed paths with no column and the import-only ones, how many tests have a row and how many of those are not in the run, and the selected and full-suite durations (D-004).
- **Covers**: Selection 13, 14 and 15. Edge 6, 7, 8 and 9. The selection in Selection 13-15 and Edge 6, 8 and 9 is task 7's. Prose, "A column is a file in at least one row... A changed path that is neither a column nor import-only has no column" (`no_column`, `import_only`). Prose, "A record is one line...": `tests_with_row`, how many tests have a row, and `tests_with_row_not_in_run`, how many of those are not in the run; "A node id with a row is in the run when its pair is in the run's JUnit, so two node ids with one pair are both in the run, or both not". Prose, "`full_ms` is the sum over every test case of the full run's JUnit and `selected_ms` over those of the selected tests; neither uses a `testsuite` element's `time`". Technical sheet, Rule 8, for the two lists of paths (sorted by code point).
- **Constrained by**: K1 (`"selected_ms":0`, `"full_ms":12000`, `"tests_with_row":4`, `"tests_with_row_not_in_run":0`, `"no_column":["templates/invoice.html"]`, `"import_only":[]`).
- **Modules**: `selection`.
- **Stubs**, by the user, before the phase:
  ```python
  def no_column(changed: list[RepoPath], matrix: Matrix) -> list[RepoPath]: ...         # sorted
  def import_only_paths(changed: list[RepoPath], matrix: Matrix) -> list[RepoPath]: ...  # sorted
  def row_counts(rows: dict[NodeId, frozenset[RepoPath]],
                 results: dict[Pair, Result]) -> tuple[int, int]: ...  # tests_with_row, not in the run
  def durations(full: JUnit, selection: Selection) -> tuple[int, int]: ...  # selected_ms, full_ms
  ```
- **Contract**: none.

### 10. Encoding records
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

  The order is "the record's fields in the SPEC's order", that of the prose's "A record is one line...", with `key` where `head` and `junit_sha256` are. No record dataclass has a `format` field: `encode` writes `"format":1` as a constant, the value that K1's and K4's lines fix (open question 2, decided).
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

### 11. Telling a record from a line that is not one
- **Closes**: which lines of a record file are records.
- **Covers**: prose, "A line of a record file is a record only if it is byte for byte what the tool would write...": an empty line, a carriage return, a missing newline, another format; shape only, no agreement between fields. Technical sheet, Rule 7 (`decode`: ASCII, keys and order, exact types, so `true` is not `1`, allowed values, lists sorted with no repeats, `encode` of the result equal to the line).
- **Constrained by**: K1 and K4 (their lines are records, and decode to the values they show), K15 (a line holding `canary` is not a record).
- **Modules**: `records`.
- **Stubs**, by the user, before the phase:
  ```python
  def decode(line: bytes) -> Record | None: ...
  ```
- **Contract**: none.

### 12. The record file
- **Closes**: reading the record file, looking up a key, and appending a line.
- **Covers**: prose, "Before evaluating a run, the tool reads the record file; if it does not exist, the tool treats it as empty and creates it when it appends", as far as reading, the lookups and the append go. Prose, "`pr` is not part of it: a rejected record already there with the same key, reason and input stops the append, whatever its `pr`" (`has_rejected`). Prose, "The record file is not one of these inputs: if it exists but cannot be read, that is any other failure" (`read_record_file` raises `OSError`). Prose, a line that is not a record named by its line number. Technical sheet, Rule 3 for the record file (a FIFO does not block) and Rule 8 (one write of the whole line, to a file opened for appending, created if missing).
- **Constrained by**: K11 (an evaluated record is appended after the rejected one), K13 (the file is created and holds that one line), K15 (line 2 is reported).
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

### 13. Evaluating a run end to end
- **Closes**: `python -m distiller evaluate` on valid inputs: the record file, the key, the evaluated record, the warning for a run already recorded, and the exit codes 0 and 1.
- **Covers**: K1, K2, K3, K7, K13, K15. Selection 16. Invariants 1, its first half (two evaluations, byte-identical record files). Prose, Inputs, the base branch: the diff is `merge-base..H`, never against M. Prose, "Every count and every list of the run's tests takes each pair once". Prose, "Before evaluating a run...": the record file read first, a missing one taken as empty and created, a line that is not a record (nothing appended, exit 1), a run already recorded (nothing appended, a warning, exit 0), an evaluated run appended with exit 0 whatever the verdict. Command line, the exit codes 0 and 1 of `evaluate`. Technical sheet, "How a run goes", steps 1, 2, 4 and 6.
- **Modules**: `evaluate`, through `cli` and `__main__`.
- **Stubs**: none; `evaluate.run` and `RunArgs` exist.
- **Rewrites**: `tests/test_main.py::test_python_m_distiller_exits_with_what_main_returns`, and the `evaluate` case of `tests/test_cli.py::test_the_commands_are_not_implemented_yet`, which the walking skeleton marked for the evaluate tasks.

### 14. Rejecting unusable inputs
- **Closes**: `unusable-input` for every input, the rejected record, its deduplication and exit code 3.
- **Covers**: K8, K10, K11, K14. Prose, the reasons: `unusable-input` with `checkout`, `head`, `base` (no commit, or no common history with H), `coverage` (a file that is missing, cannot be read or is not a coverage data file, or an M that names no commit), `junit`, `rerun` and `floor`. Prose, "An input file that exists but is not a regular file... counts like a missing one", end to end. Prose, "A record is one line...": `head` is H as given when it names no commit, and `junit_sha256` is `null` when there is no such file or it cannot be read. Prose, "If it rejects the run instead, it appends its record unless one with the same key, reason and input is already there, and exits with 3". Prose, "Apart from appending to the record file, the tool never writes to its inputs... whatever the outcome". Edge 18, its second clause (a rerun file with a test case that cannot be used is rejected even when that test did not fail in the full run). Command line, exit 3 of `evaluate`. Technical sheet, "How a run goes", step 5.
- **Modules**: `evaluate`.
- **Stubs**: none.

### 15. The other rejections and the problem order
- **Closes**: `coverage-not-ancestor`, `missing-history`, `unsafe-xml`, `no-shared-lines` and `collection-error` end to end, and which problem decides a run that has several.
- **Covers**: K4, K5, K6, K9, K12. Prose, Inputs, the per-test coverage: M must be the merge-base or one of its ancestors, and coverage with no line recorded for more than one test is `no-shared-lines`. Prose, the reasons: `coverage-not-ancestor`, `missing-history` (as `git rev-parse --is-shallow-repository` reports), `unsafe-xml` with `junit` or `rerun`, `no-shared-lines`, `collection-error`. Prose, "A collection error is...": a full-run JUnit that holds one is rejected. Prose, "When a run has more than one problem, the first in this order decides its record". Technical sheet, "How a run goes", step 3.
- **Modules**: `evaluate`.
- **Stubs**: none.

### 16. Report: miss rate, bound and savings
- **Closes**: the report's main figures over one or more record files, each key counted once.
- **Covers**: Report 1, 2, 3, 4 and 14. Prose, "The miss rate counts pull requests and looks only at evaluated runs". Prose, "Savings are 1 - the selected duration over the full-suite duration...", with the sentence that they are an upper bound (Report 4). Prose, the report: "Every figure in it counts each key once, even when the key appears in several record files"; a figure whose denominator is zero is never a percentage; the sentence that the figures belong to the all-affected selector.
- **Modules**: `report`, through `cli`.
- **Stubs**, by the user, before the phase:
  ```python
  def clopper_pearson_upper(k: int, n: int) -> float | None: ...  # None when n is 0
  ```
- **Rewrites**: the `report` case of `tests/test_cli.py::test_the_commands_are_not_implemented_yet`, which leaves the test with no case, so the test goes.
- **Open questions it needs**: 3 and 4.

### 17. Report: errors, conflicts, rejected runs and order
- **Closes**: what the report does with missing files, lines that are not records, conflicting keys and rejected runs, and that its output does not depend on the order of its inputs.
- **Covers**: Report 13, 15 and 17. Invariants 1, its second half (two reports, byte-identical, whatever the order of the files and of their lines). Prose, the report: a line that is not a record (nothing produced, file and line named, exit 1); every record file must exist and be readable (nothing on stdout, the file named, exit 1), never taken as empty; two evaluated records with one key that differ form a conflict, left out of every figure and listed with its record files; rejected runs shown by reason and input, counting only keys that no evaluated record has. Prose, "The report depends on neither the order of the record files nor that of their lines...": the sort orders. Command line, the exit codes of `report`. Technical sheet, the paragraph after "How a run goes" (all files read before anything is written).
- **Modules**: `report`.
- **Stubs**: none.
- **Open questions it needs**: 4.

### 18. Report: rates, shares, failed tests left out and escaping
- **Closes**: the floor and no-column rates, the unmeasured and not-in-run shares, the list of failed tests left out, the rerun counts, and escaping in the report.
- **Covers**: Report 5-12 and 16. Prose, "The floor rate counts pull requests...". Prose, "The no-column rate counts pull requests...". Prose, the report: "writes every pair, node id and path as a JSON string, the way the records hold it".
- **Modules**: `report`.
- **Stubs**: none.
- **Open questions it needs**: 3, 4 and 5.

### 19. Connect the step to the pilot's CI (outside the cycle)
- **Closes**: the Kill signal's "Slice 1 runs end to end in its CI" on sergiparpal/adaptive-policy-compilation. Work in the pilot's repository, not a tests and implement cycle here.
- **Depends on**: tasks 1-18 merged, and the external requirements below.
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
Each line has the one task that covers it. "Constrains" lists the earlier tasks that cite the K example under Constrained by.

| Item | Task | Constrains |
|---|---|---|
| K1 | 13 | 4, 6, 8, 9, 10, 11 |
| K2 | 13 | 8, 10 |
| K3 | 13 | 1 |
| K4 | 15 | 1, 10, 11 |
| K5 | 15 | 1, 10 |
| K6 | 15 | 1, 3, 10 |
| K7 | 13 | |
| K8 | 14 | 1, 3, 4, 5, 10 |
| K9 | 15 | 1, 10 |
| K10 | 14 | 1 |
| K11 | 14 | 12 |
| K12 | 15 | 1, 10 |
| K13 | 13 | 3, 4, 12 |
| K14 | 14 | 1, 4, 10 |
| K15 | 13 | 1, 11, 12 |
| Selection 1-12 | 7 | |
| Selection 13, 14, 15 | 9 | |
| Selection 16 | 13 | |
| Verdict 1-5 | 8 | |
| Report 1-4, 14 | 16 | |
| Report 5-12, 16 | 18 | |
| Report 13, 15, 17 | 17 | |
| Invariants 1, first half | 13 | |
| Invariants 1, second half | 17 | |
| Invariants 2-4 | 7 | |
| Edge 1, 3, 10, 11, 12, 13, 20 | 7 | |
| Edge 2, 15, 16, 17, 19 | 8 | |
| Edge 4 | 4 | |
| Edge 5 | 2 | |
| Edge 6, 7, 8, 9 | 9 | |
| Edge 14 | 3 | |
| Edge 18, first clause | 8 | |
| Edge 18, second clause | 14 | |
| Edge 21, 22 | 5 | |
| Inputs: PR number required, `--pr` digits above 0 | walking skeleton, `tests/test_cli.py` | |
| Inputs: diff is `merge-base..H`, never against M | 13 | |
| Inputs: M is the merge-base or an ancestor | 15 | |
| Inputs: `no-shared-lines` for coverage with no shared line | 15 | |
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
| Term: column, import-only, no column | 9 | |
| Term: pair rule (`mangle_test_address`) | 6 | |
| Term: lookup by pair, one direction; shared pairs unmeasured | 6 | |
| Term: test cases with one pair merged in one file | 3 | |
| Term: counts and lists take each pair once | 13 | |
| Term: unmeasured test | 6 | |
| Term: floor, default patterns, configuration only adds | 5 | |
| Term: floor pattern syntax and validity | 5 | |
| Term: selection rules and reasons | 7 | |
| Term: red, caught, missed, green; rerun discards | 8 | |
| Term: pass in the rerun file | 3 | |
| Term: collection error recognized | 3 | |
| Term: collection error rejected | 15 | |
| Term: test case that cannot be used; pytest's internal error | 3 | |
| Term: record encoding, keys, order, escapes, sorting | 10 | |
| Term: run key; `head` as given; `junit_sha256` null | 14 | |
| Term: rejected record deduplicated whatever its `pr` | 12 | |
| Term: node id with a row in the run when its pair is | 9 | |
| Rejections: `unusable-input` and its inputs | 14 | |
| Rejections: the other five reasons | 15 | |
| Non-regular or unreadable input file: JUnit | 3 | |
| Non-regular or unreadable input file: coverage | 4 | |
| Non-regular or unreadable input file: floor | 5 | |
| Non-regular or unreadable input file: end to end | 14 | |
| Record file that exists but cannot be read | 12 | |
| Problem order | 15 | |
| Messages: what they name, never quoting a file | 1 | |
| Other failures: one line naming the class, exit 1 | walking skeleton, `tests/test_cli.py` | |
| Record file: read first, created, not a record, already recorded, exit 0 | 13 | |
| Rejected run: appended unless already there, exit 3 | 14 | |
| Usage errors: exit 2, no abbreviation, `--rootdir` rules and normalization | walking skeleton, `tests/test_cli.py` | |
| Inputs never written, whatever the outcome | 14 | |
| git runs only commands that read; no network connection | 2 | |
| Line of a record file is a record only if... | 11 | |
| Miss rate | 16 | |
| Savings | 16 | |
| JUnit time rounded half up per test case | 3 | |
| `full_ms` and `selected_ms` | 9 | |
| Floor rate | 18 | |
| No-column rate | 18 | |
| Report: not a record, missing or unreadable files | 17 | |
| Report: each key once | 16 | |
| Report: conflicts | 17 | |
| Report: rejected runs by reason and input | 17 | |
| Report: zero denominators; all-affected sentence | 16 | |
| Report: pairs, node ids and paths as JSON strings | 18 | |
| Report: order of its lists | 17 | |

Not covered by any task:
- Constraints, Performance (60 s and 1 GB for one run, 10 s for a report): measured in task 19, not tested. The SPEC already marks reading the rows at that size [VERIFY].
- "The report covers one repository and is never given record files from several": a precondition on its use, with no behaviour to test.
- Deployment: tested by no task; it is task 19's checklist.
- "Checked and [VERIFY]": a repository with "dubious ownership", defusedxml on Python 3.14, and which coverage versions write schema 7.

### Open questions
Each one is to be decided before the task that needs it.

1. **A home for `no_column`, `import_only`, `tests_with_row`, `tests_with_row_not_in_run`, `selected_ms` and `full_ms`.** Decided: four pure functions in `selection`, in Interfaces, with task 9 of their own (D-004).
2. **Is `format` a field of `EvaluatedRecord`?** Decided: no record dataclass has a `format` field. `encode` writes `"format":1` as a constant, which is what K1's and K4's lines fix; a field that admits only one valid value would only serve to allow invalid records. `decode` takes only `"format":1`, as the SPEC's sentence on a record file's lines says: a line of another format is not a record (task 11's tests, 2026-10-24).
3. **How percentages are written in the report.** Report 1: "a one-sided 95% Clopper-Pearson upper bound of 86.5%"; Report 2: "an upper bound of 9.5%"; Report 4: "savings of 37.5%"; Report 5: "a floor rate of 25%"; Report 7: "12.5% of tests treated as unmeasured". Readings: (a) one decimal, with `25.0%`; (b) at most one decimal, so `25%` and `37.5%`; (c) another precision, with the examples rounded. And how the bound is rounded to that precision: (a) half up; (b) up, since it is an upper bound; (c) half to even.
4. **The report's layout.** The SPEC says what the report "shows", "lists" and "says", but not its layout or wording. Readings: (a) the tests check only that each figure, list and sentence appears, and every report task adds to the text without breaking the earlier ones; (b) a layout is fixed in the SPEC before task 16, and the tests compare whole outputs.
5. **Report 9, the reason a failed test was left out.** Report 9: "it lists test_render with the reason it was left out (its row, `src/shop/pricing.py` and `src/shop/report.py`, has none of the diff's paths, and no other rule picked it), next to the diff's paths with no column (`templates/invoice.html`) and the import-only ones (none)". A record holds the test's `row`, `no_column` and `import_only`, but not the diff's paths. Readings: (a) the report shows the row and a fixed sentence that no rule picked the test; (b) the report shows the diff's paths, which needs a new record field and so a change to record format 1.
6. **Spaces and comments in the floor configuration.** Decided, 2026-10-20: spaces and tabs at either end of a line are dropped, but no other whitespace; then a line left empty, or starting with `#`, is ignored. So a line of spaces is blank and `  # x` is a comment. Tabs go too, since one left before a pattern would make it match nothing, with no warning. Inputs and Rule 9 say so.
7. **The JUnit files that the notes at the top of this file leave open.** A well-formed file that is not a JUnit, such as `<html><body/></html>`, gives no results and is not rejected; a `time` that rounds to 10^25 s or more, and an XML declaration naming an encoding that Python or expat lacks, end as an unexpected failure, exit 1 with no record; and an entity declaration that expat skips after an unread parameter entity parses. Readings: (a) known limits, written into the technical sheet as they are; (b) changes, each with tests in a tests phase: `unusable-input` for the file that is not a JUnit and for the encoding, every `time` read with enough precision, and `unsafe-xml` for the skipped declaration. Task 14 needs the answer, since it is the first to test the JUnit's rejections end to end.
8. **Which floor hits a selected test's reason cites.** Decided, 2026-10-21: every test cites every pair that `floor_hits` gives, as one floor reason each. A test's reasons are a `frozenset`, so they have no order, and a pair given twice, by a pattern written twice or a default one written again in the configuration, is one reason. A record holds only `floor_matched`, so no reason reaches it or the report. Giving every test its own set of reasons, 10,000 tests and 1,000 floor hits take about 330 MB and under a second (Python 3.13, 2026-10-21), under the SPEC's 1 GB. The prose on the selection says so.
