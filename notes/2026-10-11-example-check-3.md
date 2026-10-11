All four hidden values are determined by the SPEC's own requirements (the rejection catalogue, the record definition, the record-file rules and the exit-code rules) — none of them needs guessing. Here they are, in the order you listed.

## 1. "Given an input the evaluation cannot use, such as a missing coverage file or a JUnit file that is not well-formed XML…"

**Computed then:**

> then nothing is evaluated, a record with `"reason":"unusable-input"` and `"input"` naming the input that cannot be used — `"coverage"` for the missing coverage file, `"junit"` for the JUnit file that is not well-formed XML — is appended, the error message names that input, and the tool exits with code 3.

For the missing coverage file, the appended line is exactly (fixture: record file empty, JUnit present and readable):

```json
{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"unusable-input","input":"coverage"}
```

For the not-well-formed JUnit, the same line with `"input":"junit"` and, in `junit_sha256`, the SHA-256 of that file's bytes — not `null`, because the field is `null` only "if there is no such file or it cannot be read", and the rejection list treats "cannot be read" and "is not well-formed XML" as separate conditions.

**Determining rules:**
- The rejection catalogue: "`unusable-input`, with the input that cannot be used: … `coverage` for a coverage file that is missing, cannot be read or is not a coverage data file … `junit` for a full-run JUnit file that is missing, cannot be read or is not well-formed XML…".
- "If it rejects the run instead, it appends its record unless one with the same key, reason and input is already there, and exits with 3."
- "A rejection's message names its input", and messages "name inputs by their path … and never quote what a file holds" — the later [core] example confirms it for this very case ("the error message names the coverage file again, and the tool exits with code 3").
- Tie-break if several inputs are bad: the problem order puts "the coverage (unusable, …)" before "the full run's JUnit (missing or cannot be read, then `unsafe-xml` or not well-formed, whichever the parser meets first, …)".
- The rule must stay generic: "a floor configuration that cannot be read or has an invalid pattern" and "an input file that exists but is not a regular file … counts like a missing one: `unusable-input`, with that input" — and the edge case on `**.lock` / `data/?.csv` points back to this example.

## 2. "Given the missed run of the first [core] example and no file at the record file's path…"

**Computed then:**

> then the tool treats the missing record file as empty, so no record has the run's key; it evaluates the run, creates the record file when it appends, appends exactly the line of the first [core] example, and exits with code 0.

The created file ends up holding exactly:

```json
{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"missed","merge_base":"<merge-base>","coverage_commit":"<M>","selected_ms":0,"full_ms":12000,"tests":4,"unmeasured":0,"tests_with_row":4,"tests_with_row_not_in_run":0,"floor_matched":false,"rerun_given":false,"not_reproduced":[],"failed_left_out":[{"pair":["tests.test_report","test_render"],"node_id":"tests/test_report.py::test_render","row":["src/shop/pricing.py","src/shop/report.py"]}],"no_column":["templates/invoice.html"],"import_only":[]}
```

**Determining rules:**
- "Before evaluating a run, the tool reads the record file; if it does not exist, the tool treats it as empty and creates it when it appends."
- "Otherwise it evaluates the run, appends its record and exits with 0, whatever the verdict" (as the valid-inputs [core] example says: "a missed run never turns the step red").
- The line is byte-identical to the first [core] example's because a missing file counts as an empty one, "A record holds nothing that changes between two evaluations of the same inputs, such as the time", and the invariant "each time with an empty record file, then the two record files end up byte-identical".
- No "already recorded" warning: that fires only "If an evaluated run's record has the run's key", and the empty file holds none.

## 3. "Given a coverage file that is empty, 0 bytes long…"

**Computed then:**

> then nothing is evaluated, a record with `"reason":"unusable-input"` and `"input":"coverage"` is appended, the error message names the coverage file, and the tool exits with code 3.

```json
{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"unusable-input","input":"coverage"}
```

**Determining rules:**
- "A coverage file is a coverage data file only if coverage reads it without an error and it lists at least one measured file, so an empty file is not one, nor is an SQLite database of something else."
- The rejection catalogue: "`coverage` for a coverage file that is missing, cannot be read or is not a coverage data file" → `unusable-input` with input `coverage`; "…appends its record … and exits with 3".
- "A rejection's message names its input" — the coverage file by path (not M; M is named only "for `coverage-not-ancestor` and for an M that names no commit").
- The problem order puts the coverage's "unusable" check before `coverage-not-ancestor` and `no-shared-lines`, so an empty file is `unusable-input`, not `no-shared-lines`, even though trivially no line in it was recorded for more than one test.

## 4. "Given a record file whose first line is a record and whose second line is not one and holds the text `canary`…"

**Computed then:**

> then the tool appends nothing, the record file is left byte for byte as it was, its error message names the record file and the second line's number, without quoting the line, and it exits with code 1.

**Determining rules:**
- "Before evaluating a run, the tool reads the record file … If the file holds a line that is not a record, the tool appends nothing, names the file and the line number in its error message, without quoting the line, and exits with 1."
- "A line of a record file is a record only if it is byte for byte what the tool would write for a record with those keys and values … Anything else is not a record" — the `canary` line is not one, so the line named is line 2.
- The check runs before evaluation and before any append, and the valid first line makes no difference: the rule fires whenever the file holds a non-record line, so the run never reaches a record of its own.
- Exit code: this is neither an evaluated run (0), a rejection (3) nor a usage error (2); "A usage error exits with 2, and any other failure with 1" — and the rule itself says "exits with 1".
- The message goes to stderr and messages "never quote what a file holds", so it does not contain the text `canary`.

---

**Note on granularity:** the SPEC fixes every observable above (verdict/reason/input, the exact record line, the exit code, what the message names and quotes). The only thing it deliberately leaves open is the exact prose of the stderr messages, which it constrains to the same level as the neighbouring [core] examples ("names the coverage file", "names the file and the line number, without quoting the line") — so there is nothing undetermined to guess at.
