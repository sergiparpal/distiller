Below, each hidden value is the example's "then" clause, computed from the SPEC's three governing passages: the **record definition** ("A record is one line…", with the key order and the rejected-record fields), the **record-file/exit-code paragraph** ("Before evaluating a run, the tool reads the record file; …"), and the **verdict / input-validity rules**. `<H>`, `<merge-base>`, `<M>`, `<sha>` are the fixture's placeholders; every example is PR 7, full suite 12.0 s.

### 1. Diff modifies only `templates/invoice.html`; test_render failed; no rerun file
**Then:** the run is **missed**; exactly one record line is appended and the tool **exits 0**. The line (ASCII, no spaces between tokens, newline at the end):

```json
{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"missed","merge_base":"<merge-base>","coverage_commit":"<M>","selected_ms":0,"full_ms":12000,"tests":4,"unmeasured":0,"tests_with_row":4,"tests_with_row_not_in_run":0,"floor_matched":false,"rerun_given":false,"not_reproduced":[],"failed_left_out":[{"pair":["tests.test_report","test_render"],"node_id":"tests/test_report.py::test_render","row":["src/shop/pricing.py","src/shop/report.py"]}],"no_column":["templates/invoice.html"],"import_only":[]}
```

Computation: no rule picks any test (the path is in no row, matches no default floor pattern, is no test's own file or conftest, nothing is unmeasured) → selection and `selected_ms` are 0; no rerun → the failure is not discarded → red; an empty selection holds none of the failed tests → missed; `templates/invoice.html` was never measured, so it is neither a column nor import-only → `no_column`; `src/shop/constants.py` is import-only but not changed → `import_only` empty; the row is sorted by path (`pricing` < `report`).

**Rule:** the record definition (key order, field meanings, sorting); "A run is red when at least one test has a `failure` or an `error` that the rerun file does not discard … A red run is caught when the selection holds at least one of its failed tests and missed otherwise"; "Otherwise it evaluates the run, appends its record and exits with 0, whatever the verdict." (The visible Selection/Verdict examples for this same diff confirm it.)

### 2. Full run in which test_render failed; rerun file in which it passed
**Then:** the pass in the rerun discards the failure; test_render is marked not reproduced; the run is **green**; its record is appended and the tool **exits 0**. Determined fields: `verdict` `"green"`; `rerun_given` `true`; `not_reproduced` `[["tests.test_report","test_render"]]`; `failed_left_out` `[]` (no failure survives the rerun, whatever the diff); `full_ms` `12000`; `tests` `4`; `unmeasured` `0`; `tests_with_row` `4`; `tests_with_row_not_in_run` `0`; plus `format`/`head`/`junit_sha256`/`pr`/`merge_base`/`coverage_commit` as in the fixture. **Not determined by the SPEC:** `selected_ms`, `floor_matched`, `no_column`, `import_only` — they depend on the diff, and neither this example nor the fixture fixes one.

**Rule:** "only a pass in the rerun file discards one, and the test is then marked not reproduced. … A run that is not red is green" (test_render is the only failure: the fixture's run has none unless an example adds one, as the parallel Verdict example states); the record field list; "Otherwise it evaluates the run, appends its record and exits with 0, whatever the verdict."

### 3. Run whose evaluation is already recorded; same inputs again
**Then:** **nothing is appended** (the record file is left unchanged), the tool **warns**, and it **exits 0**.

**Rule:** "If an evaluated run's record has the run's key, nothing is appended, and the tool warns and exits with 0" — with "`head` and `junit_sha256` are the run's key" and "Before evaluating a run, the tool reads the record file" (the check precedes evaluation, so the run is not re-evaluated).

### 4. Coverage at a commit that is neither the merge-base nor one of its ancestors (e.g. at H)
**Then:** the run is **rejected**; the rejected record is appended — unless one with the same key, reason and input is already there — and the tool **exits 3**:

```json
{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"coverage-not-ancestor","input":"coverage"}
```

**Rule:** "M must be the merge-base or one of its ancestors", where the merge-base is that "of B and H", never of M — the SPEC says computing it against M would mean "the check below would reject nothing, not even coverage recorded at H"; "A rejected run's record goes on with `reason`, one of `coverage-not-ancestor`, … and `input`, one of … `coverage` …" (M is part of the coverage input: "the per-test coverage, recorded on the base branch at a commit M … and M itself"); "If it rejects the run instead, it appends its record unless one with the same key, reason and input is already there, and exits with 3."

### 5. Checkout without the history to prove M's ancestry (shallow clone)
**Then:** **rejected** with reason **`missing-history`**, input **`checkout`**; rejected record appended unless one with the same key, reason and input is already there; **exit 3**:

```json
{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"missing-history","input":"checkout"}
```

**Rule:** the reason and input enumerations in the record definition; the head input requires H "in a checkout with history"; "If it rejects the run instead, it appends its record … and exits with 3."

### 6. JUnit file declaring an external entity / nested expansions ("billion laughs")
**Then:** **rejected** with reason **`unsafe-xml`**, input **`junit`**; record appended unless already there; **exit 3**. The file is refused, not parsed — the security decision:

```json
{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"unsafe-xml","input":"junit"}
```

**Rule:** "defusedxml, because the JUnit XML is written by the code under review and is not trusted"; reason `unsafe-xml` in the record definition; "If it rejects the run instead … exits with 3."

### 7. Run with valid inputs, green, caught or missed; evaluation finishes as a CI step
**Then:** the record is appended and the CI step **exits 0 in all three cases**; the verdict never changes the CI result — a missed run exits like a caught one.

**Rule:** "Otherwise it evaluates the run, appends its record and exits with 0, whatever the verdict"; the non-goal "its verdict never changes the CI result: the full suite runs every time, and a missed run exits like a caught one."

### 8. An input the evaluation cannot use (missing coverage file; JUnit that is not well-formed XML)
**Then:** **rejected** with reason **`unusable-input`**, with `input` naming the unusable input — **`coverage`** for the missing coverage file, **`junit`** for the malformed JUnit; record appended unless one with the same key, reason and input is already there; **exit 3** (same record shape as above, `"reason":"unusable-input"`).

**Rule:** the reason/input enumerations in the record definition; "If it rejects the run instead … exits with 3." (The invalid-floor-pattern edge case points here too, with input `floor`.)

### 9. Run rejected because its coverage file was missing; evaluated again with the same inputs
**Then:** rejected again with the same reason and input (`unusable-input` / `coverage`); **nothing is appended**, because a record with the same key, reason and input is already there; **exit 3**.

**Rule:** "If it rejects the run instead, it appends its record unless one with the same key, reason and input is already there, and exits with 3."

### 10. That same rejected run, evaluated again with its coverage file
**Then:** the run is now **evaluated**; its evaluated record **is appended** — the earlier rejected record stays, so the file holds both lines for the same key — and the tool **exits 0**. No warning fires, because the warn rule covers only "an evaluated run's record" with the key, and the record already there is a rejected one. In the report, the key then counts as evaluated and never as rejected. **Not determined:** the `verdict` value (green/caught/missed) — the example fixes no diff and no failures — but the appending and exit code hold "whatever the verdict".

**Rule:** "Otherwise it evaluates the run, appends its record and exits with 0, whatever the verdict" (the duplicate rule is limited to evaluated records); "The report shows the rejected runs by reason and input, counting only the keys that no evaluated run's record has."

### 11. Coverage in which no line was recorded for more than one test (sysmon)
**Then:** **rejected** with reason **`no-shared-lines`** — not `unusable-input` — input **`coverage`**; record appended unless already there; **exit 3**:

```json
{"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"no-shared-lines","input":"coverage"}
```

**Rule:** "coverage in which no line was recorded for more than one test is rejected with a reason of its own, `no-shared-lines`, rather than as an unusable input"; "If it rejects the run instead … exits with 3."

---

**Where the SPEC leaves gaps:** only example 2's diff-dependent fields and example 10's verdict are undetermined above. One caveat on the rejections: the SPEC enumerates the `reason` and `input` values but gives no explicit reason→input table; in each of examples 4–6, 8, 9 and 11 exactly one input value fits the failing input, so I stated it rather than guessing — that is the only interpretive step in the answer.
