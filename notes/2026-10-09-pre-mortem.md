# Pre-mortem: Slice 1

Read: `docs/SPEC.md`, `docs/C6-destilador-revisada.md`, `notes/2026-10-07-junit-coverage-contexts.md` and `notes/2026-10-08-example-check.md`.

Premise: Slice 1 has been built and the project has failed. Either it was not finished, or it did not work on a real repository, or its figures were not trusted or could not decide what §13.2 of C6 decides. §13.2 leaves file tracing (§6) unbuilt if the share of misses caused by a file dependency is marginal, or if the share of PRs that trigger the floor is low. Both figures come from shadow mode.

The ten causes are ranked by how likely each is to have caused the failure, most likely first. Each one gives what happened, the earliest signal that would have given it away, and the change to the spec that would prevent it or surface it sooner. Where a cause touches a [core] example, it says which one and nothing more.

## 1. Too few misses to decide anything

**What happened.** Three weeks of shadow on the pilot gave a few dozen PRs with a red run and one to three misses. The bound on the miss rate stayed wide, and the share of file-dependency misses rested on a handful of cases, so §13.2 could not tell "marginal" from chance.

**Earliest signal.** The pilot's CI history, before anything is wired. The number of PRs with a failed test run per week is the n that the window will collect, and it can be counted today.

**Spec change** (open question). How many misses must the window collect before §13.2 may call the file-dependency share marginal? What do "marginal" and "low" mean in numbers, and can the pilot reach that count within the appetite? The arithmetic is lopsided. With the report's one-sided 95% Clopper–Pearson bound, 0 file-dependency misses out of 3 only bounds the share below 63.2%. Bounding it below 10% takes 29 misses with no file dependency among them, which is about 580 PRs with a red run if one in twenty is missed. On the other hand, 3 out of 3 already puts the share above 36.8%. So the slice can show quickly that tracing is needed, and only slowly that it is not. The sample would grow if §13.2 accepted every failed test left out, which records already keep for caught runs too. The Bet's Appetite and Kill signal are still placeholders, and they are yours.

## 2. The miss rate measured CI noise

**What happened.** Flaky failures, outages and failures inherited from the base branch all counted as red runs, and they pushed the rate both ways. A single unrelated failure usually fell outside a small selection and became a miss. An outage that failed hundreds of tests was caught by almost any selection. The rate measured the health of the CI as much as the selector.

**Earliest signal.** The same test failing in several unrelated PRs within a few days. This shows in the pilot's CI history before Slice 1 exists, and in the records' `failed_left_out` from the first week.

**Spec change** (example in Report). A failed test left out in more than one PR is listed with those PRs, because a failure that recurs across unrelated PRs is noise rather than a selector error. The open question on inherited failures covers one of the three sources. The count of red runs without a rerun file warns about another, but leaves those runs in the rate.

## 3. The floor rate could not move the decision

**What happened.** Whatever the floor rate came out at, it could not say what tracing would buy. §6 motivates tracing by what the floor costs on `config/`, but §9.3 keeps the floor when tracing is on. The figure also lumped dependency bumps (lockfiles, `requirements*.txt`, `pyproject.toml`) together with configuration changes. And the floor's breadth pushes the two figures of §13.2 in opposite directions. A broad floor leaves few file-dependency misses and a narrow one leaves few floor matches, so under §13.2's "or" both of them said "don't build".

**Earliest signal.** Today, from git alone: run the floor patterns over the pilot's merged PRs and split the result by pattern. This figure needs neither coverage nor JUnit. If it comes out low, §13.2 is decided before Slice 1 records a single run.

**Spec change** (open question). Given §9.3, what does tracing change for a PR that matches the floor, and so what does the floor rate decide? If the answer is a rate per pattern, records cannot give it, because they keep only `floor_matched`. Changing that affects the [core] example that fixes the record line.

## 4. Nothing in the record says "file dependency"

**What happened.** The spec calls the floor rate "one of the two figures" for §13.2, but the report computes no second figure. Each miss came with its row and with the diff's no-column and import-only paths, and someone sorted them by hand. `no_column` mixed several things: what §6 would trace (templates, fixtures, golden files), code that coverage never measured (`tests/factories.py` under `--cov=src`, files in the repository's `omit` list), files that are new since M, and CI or documentation paths. The resulting share depended on who did the sorting.

**Earliest signal.** The pilot's coverage configuration. A `source` narrower than the repository's Python code, or an `omit` list, guarantees `.py` paths with no column. After that, the first missed run whose `no_column` holds a `.py` file that existed at M.

**Spec change** (non-goal, with an open question). Slice 1 classifies no miss by cause; a person does that, from the report. The open question is which categories that person uses and which of them the record can tell apart without tracing.

## 5. Red runs never reached the tool

**What happened.** The step was wired like any other step. Either it was skipped when the test step failed, which is the default in GitHub Actions and most CIs, or it was placed in a job that needs the test job, so it saw almost only green runs. Runs that hung or crashed left no JUnit and ended as `unusable-input` rejections, which the miss rate never counts. The report showed a quiet repository.

**Earliest signal.** The CI configuration: the step has no `if: always()` or equivalent. After the first week, the recorded runs, and the red ones among them, do not match the CI's own count of PR runs and failed runs.

**Spec change** (constraint). The step runs whatever the outcome of the test step. Slice 1 counts as running on a repository only once a week of records matches the CI's list of PR runs.

## 6. The pilot's CI did not have the shape Slice 1 takes

**What happened.** The repositories that most need a selector often split their suite across shards. That means several JUnit files per run, and coverage at M that has to go through `coverage combine`, which the spike did not test. Others run a matrix of Python versions and systems against a single M. So either the pilot was swapped for a smaller unsharded repository, which made cause 1 worse, or the JUnit files were merged ad hoc, under a key that depends on how they were merged.

**Earliest signal.** The pilot's CI configuration shows shards, a matrix, or more than one pytest invocation per PR.

**Spec change** (open question decided, or non-goal). Decide the open question on sharded runs before choosing the pilot. Or turn it into a non-goal that names the shape Slice 1 needs: one pytest run per job, in M's environment. Settling it changes what `junit_sha256` hashes, which affects the [core] examples whose records show it.

## 7. Collection errors decided a share of the red runs

**What happened.** PR runs that broke an import stopped at collection: pytest ran no test, and the JUnit held a single collection error. The spec leaves these runs open, so the implementation made the choice. Counted as an unmeasured test, such a run is always caught; any other choice makes it missed or drops it. Unless these runs were rejected, `tests_with_row_not_in_run` jumped, and that is the share the report relies on to expose broken matching.

**Earliest signal.** In the pilot's CI history, PR runs that stopped with "error during collection". In the records, the first run whose `tests_with_row_not_in_run` equals `tests_with_row`.

**Spec change** (example). Turn the open question on collection errors into a decision for Slice 1, written as an example. Because the decision changes what is stored, that example would be [core], so its value is yours.

## 8. M was too heavy to produce and to read

**What happened.** The suite under `ctrace` with test contexts ran slower and wrote a large file. A custom job had to store that file and, for each PR, find the newest one that is an ancestor of the merge-base. When that job lagged, runs were rejected or were evaluated against old rows. Reading the file through `contexts_by_lineno()`, which returns every line's contexts when a row needs only the files, missed the 60 s / 1 GB limit.

**Earliest signal.** One instrumented run of the pilot's suite, timed and sized, and one read of its data file through the public API, both before the reader is written. The spike measured neither.

**Spec change** (constraint, with an open question). The constraint limits the coverage run at M: its overhead, its file size and how often it runs. The spec limits the evaluation but not the run the evaluation depends on. The open question is what gives way if the public API cannot read M within the limit: the rule to use only the public API, or the limit.

## 9. H was not the tree that ran

**What happened.** On GitHub's `pull_request` event the checkout is a merge of the PR into the current base (`github.sha`), but H was passed as the PR's head (`github.event.pull_request.head.sha`). The tree that failed held base commits that the diff did not, and their failures counted against the selector.

**Earliest signal.** The CI configuration, before wiring: the event and the checkout ref. Once wired, the first record's `head` differs from `git rev-parse HEAD` in the run's checkout.

**Spec change** (constraint or edge case). H is the commit that the full run tested, which is the checkout's HEAD, with GitHub's merge commit as the example.

## 10. A rejection turned someone's PR red

**What happened.** In the first days, shallow clones and a missing M made the tool exit with 3 on real PRs, and a non-zero exit fails a CI step unless the step is told otherwise. The step was then either set to never fail, which also muted its crashes, or removed. The non-goal says the verdict never changes the CI result, but `rejected` is also a verdict.

**Earliest signal.** Before any run: a step without `continue-on-error` or its equivalent. In the first days: a rejected run on a PR, which shows as a red check that the PR's author did not cause.

**Spec change** (non-goal or constraint). State whether a rejection may fail the PR's CI and, if it may not, how the step is wired. This affects the [core] examples that end with exit code 3.

## Below the cut

- `sysmon` under xdist. Each worker is a separate process, so a line is recorded once per worker, and lines end up shared by up to as many tests as there are workers. Then `no-shared-lines` does not fire even though the rows are partial. This is an inference from the spike's single-process finding and was not tested; one spike scenario (`COVERAGE_CORE=sysmon`, `-n 4`) settles it. On Python 3.14, a wrapper that does not pass `COVERAGE_CORE` through gets there unnoticed; tox, for instance, passes only the variables it is told to.
- pytest's rootdir. The fixture, `own file`, `conftest` and one edge case all assume it, but it is not among the inputs. In a monorepo, a wrong guess silences `own file` and `conftest`.
- Savings. They come from JUnit times, not from the CI minutes or wall time that a buyer pays for. A session fixture's setup is charged to whichever test ran first, so a selection that leaves that test out looks cheaper than it is.
- Very large records. A run in which hundreds of tests fail writes every one of them, with its row, into `failed_left_out`. A few such records may break the report's 10 s limit.
- Reading the all-affected miss rate as the rate in regime. It is a floor on what any selector over the same rows would miss. §5's set cover picks fewer tests, so it can only miss as often or more often.

## Across the ten

Most of the earliest signals can be read before Slice 1 is written: from the pilot's CI configuration and history, its git log, or one instrumented run. The spec names no pilot repository, and a constraint that named one would bring most of these signals forward. Causes 1, 3 and 4 concern §13.2 itself. As written, its rule has no thresholds, one of its figures does not measure what tracing changes, and Slice 1 does not compute the other.
