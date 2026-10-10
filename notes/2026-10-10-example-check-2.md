# The three hidden values

All three examples are **rejections**, and the SPEC fixes one common skeleton for them, so I'll state it once:

* **Procedure / exit code** — "Before evaluating a run, the tool reads the record file; … If it rejects the run instead, it appends its record unless one with the same key, reason and input is already there, and exits with 3." The fixture's record file is empty, so the record **is** appended.
* **Record shape** — "Every record starts with these keys, in this order: `format` …; `head`, H's full commit id, or H as given if it names no commit in the checkout; `junit_sha256`, the SHA-256 of the full run's JUnit file, or `null` if there is no such file; `pr` …; and `verdict` … A rejected run's record goes on with `reason` … and `input` …" — ASCII, no spaces between tokens, newline at the end.
* **Fixture values** — `pr` is 7; in all three setups H is the checked-out head (so it names a commit and `head` is `<H>`) and the JUnit file exists (so `junit_sha256` is `<sha>` — in the collection-error and malformed-JUnit cases, the SHA of *that* example's file).
* **Message** — "Warnings and error messages go to stderr. They name inputs by their path … and never quote what a file holds. A rejection's message names its input …"

So the only work per example is the `reason`/`input` pair — which the SPEC fixes in each case.

---

## 1. The shallow checkout

> **then** nothing is evaluated, exactly this line is appended:
> ```
> {"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"missing-history","input":"checkout"}
> ```
> the error message names the checkout, and the tool exits with code 3.

**Determining rules**

* **Rejection list**: "`missing-history`, with `checkout`, when the checkout is shallow, as `git rev-parse --is-shallow-repository` reports: a shallow clone usually lacks M and the merge-base, so git cannot tell whether M is an ancestor." A `--depth 1` clone makes that command report true → `missing-history` / `checkout`.
* **Problem order** — this rule is what makes the value determinate: "When a run has more than one problem, the first in this order decides its record: the checkout (not a git checkout, then shallow); H; the base branch; the coverage (unusable, then `coverage-not-ancestor`, then `no-shared-lines`); …" A depth‑1 clone at H normally also lacks B (a parent of the merge commit) and M, which would otherwise be `unusable-input` with `base` ("a base branch that names no commit") and with `coverage` ("an M that names no commit"). The checkout problem comes first, so `missing-history` wins.
* Record shape, append-and-exit-3, and "A rejection's message names its input" (here, the checkout).

**Not determined by the SPEC:** the literal text of the stderr message (only the constraint above — stderr, names the checkout by path, quotes nothing — is fixed).

---

## 2. An input the evaluation cannot use

> **then** nothing is evaluated, a record with `"reason":"unusable-input"` and the `"input"` that cannot be used is appended, the error message names that input, and the tool exits with code 3.

For the two cases the example names, the SPEC fixes the exact lines:

* missing coverage file → `"input":"coverage"`:
  ```
  {"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"unusable-input","input":"coverage"}
  ```
* JUnit not well-formed XML → `"input":"junit"`:
  ```
  {"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"unusable-input","input":"junit"}
  ```

**Determining rules**

* **Rejection list**: "`unusable-input`, with the input that cannot be used: `checkout` for a directory that is not a git checkout, `head` for an H that names no commit, `base` for a base branch that names no commit, or whose commit shares no history with H …, `coverage` for a coverage file that is missing or is not a coverage data file, or for an M that names no commit, `junit` for a full-run JUnit file that is missing or is not well-formed XML, `rerun` for such a rerun file, and `floor` for a floor configuration that cannot be read or has an invalid pattern." This mapping is exactly what the generic "an input the evaluation cannot use" resolves through.
* **Problem order**: coverage is decided before the JUnit, and within the JUnit "missing, then `unsafe-xml` or not well-formed, whichever the parser meets first, then `collection-error`" — so a malformed JUnit that declares no entity is `unusable-input`/`junit`, not `unsafe-xml`.
* Record shape, append-and-exit-3, message-names-its-input (as above).
* **Corroboration in the SPEC**: the report example has r1 "first rejected with `"reason":"unusable-input"` and `"input":"coverage"`, because its coverage file was missing" (fixing the exact strings), and the two following [core] examples presuppose this first evaluation ("the record file is left byte for byte as it was, the error message names the coverage file again, and the tool exits with code 3").
* **Special case the SPEC fixes**: when the unusable input is a floor configuration with an invalid pattern (the case the `**.lock` / `data/?.csv` edge case points back to here), "The message for an invalid floor pattern names the configuration file and the pattern's line number."

**Not determined by the SPEC:** the literal message text.

---

## 3. The collection error

> **then** nothing is evaluated, exactly this line is appended:
> ```
> {"format":1,"head":"<H>","junit_sha256":"<sha>","pr":7,"verdict":"rejected","reason":"collection-error","input":"junit"}
> ```
> the error message names the JUnit file, and the tool exits with code 3.

(`<sha>` is the SHA-256 of *this* JUnit — the one holding only the collection error. The uncollectable file, `tests/test_report.py`, appears nowhere in the record: a rejected record carries nothing beyond the standard prefix plus `reason` and `input`.)

**Determining rules**

* **Terms**: "A run whose full-run JUnit holds a collection error is rejected with `collection-error`, with the input `junit`: evaluated, it would always count as caught, since the error has no row and is selected as unmeasured, and every test with a row would count as not in the run." (The clause after the colon is the SPEC's stated rationale for rejecting rather than evaluating.)
* **Rejection list**: "`collection-error`, with `junit`, for a full-run JUnit file that holds a collection error."
* **Problem order**: the fixture's coverage raises no problem, and the JUnit is present, well-formed and declares no entity, so the order "missing, then `unsafe-xml` or not well-formed …, then `collection-error`" reaches — and fires — the collection-error check.
* Record shape, append-and-exit-3, message-names-its-input (the JUnit file).

**Not determined by the SPEC:** the literal message text (including whether it mentions `tests/test_report.py` — the SPEC only requires it to name the JUnit file and quote nothing from it).

---

## Summary

| Example | Verdict | Reason | Input | Exit |
|---|---|---|---|---|
| Shallow checkout | rejected | `missing-history` | `checkout` | 3 |
| Unusable input | rejected | `unusable-input` | the input that cannot be used (`coverage` / `junit` in the named cases) | 3 |
| Collection error | rejected | `collection-error` | `junit` | 3 |

Everything above — the verdict, reason, input, the exact record line (given the fixture's `<H>`/`<sha>` placeholders), that the line is appended, and the exit code — is determined by the SPEC. The only thing it does **not** determine for any of the three is the exact wording of the stderr message; it fixes only what the message must do (go to stderr, name the input by its path, never quote file contents — plus, for the invalid-floor-pattern case, name the configuration file and the pattern's line number). I have not guessed that text.
