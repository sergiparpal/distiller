# Options for the next bet, 2026-11-20

As the user asked on 2026-11-20, before the Bet's outcome of 2026-12-09: where
the product document puts the next step, what the window's replay leaves for
it, and options for the next bet, each with what it would show, what it needs,
what it costs and what it risks. The Bet is the user's to write; the options
and the view at the end are the agent's. No figure of a pilot was computed for
this note: those quoted come from `2026-11-19-window-replay.md`,
`2026-11-19-window-report.txt` and `2026-11-20-plugins-check.md`, and the
bounds below are the report's `clopper_pearson_upper` on made-up counts.

## Where the product document puts the next step

C6's deployment phases, §13 (FACT, translated):

1. Shadow, with no authority: it gives the miss rate and the estimated
   savings, and the misses are classified by cause.
2. Scope decision: if the share of misses from a file dependency is marginal,
   or the share of pull requests that trigger the floor today is low, file
   tracing (§6) is not built and the product stays pure coverage. Both numbers
   come from phase 1.
3. Regime: the model selects, shards and orders.
4. Night: the whole suite, instrumented, every night.

Slices 1 and 2 gave phase 1's miss rate (FACT). The rest of phase 1, and both
numbers of phase 2, are not measured yet:

- Savings: 16.8% on Slice 1's pilot (D-007), whose tests read its own data
  files. Slice 2 gives none (Non-goals): the report's 39.2% over the window
  does not apply, since only the pull requests whose job failed were replayed.
- Misses by cause: the user classified the window's three misses as failures
  of a flaky test that urllib3 fixed (D-017), so none came from a file
  dependency. 0 out of 3 bounds that share below 63.2% only; bounding it below
  10% takes 29 classified failed tests left out with no file dependency (the
  SPEC's open question on the thresholds for §13.2).
- The other 11 failed tests left out, all in caught runs, are not classified:
  four tests of client certificates at #4962, the same four at #5050, and
  three parametrizations of one test at #5097. None of them failed at its M:
  the only test that failed at any of urllib3's Ms is the flaky probe test.
- The floor: its rate over the window, 18.3%, 15 of 82 evaluated pull
  requests, is over pull requests whose job failed, with the default patterns
  alone (D-015), so it says little of phase 2's share.
- "Marginal" and "low" have no numbers yet (the SPEC's open questions).

## What else the window leaves

- The bound, 14.2% for 3 missed out of 52, rests on two choices that keep the
  records as replayed (D-017, D-019), and one more miss would make it 16.7%
  (FACT). How many pull requests with a red run a bound below 10% takes, for
  each count of misses:

  | Missed | Smallest n |
  |---|---|
  | 0 | 29 |
  | 1 | 46 |
  | 2 | 61 |
  | 3 | 76 |
  | 4 | 89 |
  | 6 | 116 |
  | 8 | 142 |

  At the window's share of misses, 3 in 52, 9 misses out of 156 give 9.8%:
  some three times the window (INFERENCE, if the misses kept that share).
- Most evaluated pull requests change a path that no row holds: the no-column
  rate is 74.4%, 61 of 82 (FACT). The pilots' coverage measures their package
  alone, `coverage_source` in `pilots/*.toml` (FACT), so test files, changelog
  entries and docs have no column.
- #5097 (FACT): its paths with no column are `test/test_ssl.py` and
  `test/test_util.py`; the failed tests left out are three parametrizations of
  `test_create_urllib3_context_ssl_version_and_ssl_min_max_version_errors` in
  `TestSSL` of `test/contrib/test_pyopenssl.py`, whose rows hold neither path;
  and at its head `test/contrib/test_pyopenssl.py` imports `TestSSL` from
  `test_ssl` and `TestUtilSSL` from `test_util`, so pytest collects those
  classes again under its own node ids. It suggests (INFERENCE) that a test
  whose code is in another file than its node id's has no column and no rule
  that reaches that code: a change to `test/test_ssl.py` picks the tests
  collected there, by their own file, and not their copies. Classifying them
  is the user's (Non-goals).
- The rerun discarded 117 failures as not reproduced, and the 5 inherited
  failures were all urllib3's flaky probe test (FACT).
- Cost: 3.2 h of steps for 88 pull requests, a median of 129 s each in
  urllib3 and 108 s in poetry (FACT).
- The scripts that wrote the manifest from GitHub's runs are not in the
  repository: they stayed in the scratchpads of the sessions of 2026-11-16 to
  2026-11-18, which may be gone, and the notes say what they did
  (`HANDOFF.md`). A new window or pilot needs them written again.

## Options

### A. Classify the failed tests left out, and give §13.2's thresholds numbers

- Shows: phase 2's first input, from data in hand.
- Needs: the user writes "marginal" and "low" as numbers first, before any
  more failed tests are classified (D-007); then, for each of the 11, the
  agent gathers what a person needs, as above for #5097: the diff, the row,
  the imports and the run's log; and the user classifies.
- Costs: a day or two, and no run (OPINION).
- Risks: 14 classified failed tests settle little: bounding the share of file
  dependencies below 10% takes 29 with none. It is an input to phase 2, not
  its decision.

### B. More pull requests with a red run, from new pilots

- Shows: a bound tighter than 14.2%, on pilots whose figures nobody has seen,
  and more failed tests left out for A.
- Needs: pilots chosen from their CI's outcomes alone, before any figure
  (D-007); the manifest's scripts again; a TOML file for each pilot; the
  harness as it is.
- Costs: some 150 pull requests with a red run, about three times the window,
  would take some 9 h of steps on suites like these two (INFERENCE: 3.2 h for
  88 gave 52). Finding the pilots costs more: the search of 2026-11-16 looked
  at 30 Python projects and kept two (`2026-11-16-pilot-candidates.md`).
- Risks: few projects qualify. That search set aside base branches red in
  nearly half their runs (sphinx, flask), test workflows that fail mostly in
  lint, coverage gates or mypy (isort, starlette, attrs), too few red pull
  requests (jinja) and failures that depend on the environment (pytest); and
  older heads may not rebuild.
- A later window of urllib3 and poetry, from 2026-11-16 on, is data nobody has
  seen, but slow: the window gave 52 pull requests with a red run in 11.5
  months, some 4 to 5 a month (INFERENCE).

### C. The savings, phase 1's other figure

- Shows: the savings that §10 asks for, over all of a pilot's pull requests,
  on projects other than Slice 1's pilot.
- Needs: a manifest of every pull request of a window, green ones too
  [VERIFY: whether the harness replays a green run's row as it is]; and, if
  the savings must hold with a floor, each pilot's floor patterns, which D-015
  left out of Slice 2.
- Costs: D-010 rejected replaying every pull request of the window, some 830,
  as days of compute for a figure that that bet did not ask for. A fixed
  random sample, drawn before any replay, keeps it to hours: some 3 h of
  steps for 100 pull requests (INFERENCE).
- Risks: on urllib3 and poetry, the report's 39.2% over red pull requests has
  been seen, so a threshold set now would not be blind (D-007); on new pilots,
  as in B, it would be. And the figure is an upper bound: JUnit times leave
  out start-up and collection, while §10 compares the selected subset's
  duration with the full run's.

### D. A column for test code

- Shows: whether #5097's kind of gap lets failures through.
- Needs: the test files in the coverage at M, or a rule that follows imports
  between test modules: a change to the pilots' coverage or to Slice 1's
  rules, so a slice of its own, measured on data not yet seen (D-007).
- Costs: a cycle or two (OPINION).
- Risks: no miss of the window came from it, and A's classification says
  first whether it matters.

### E. The product document's last unchecked risk

- Shows: whether the product is worth more work. C6 §12 marks one risk as
  unverified, the only row of its ledger still unchecked: that native CIs give
  affected-test selection away (FACT). The wedge it names, if they do, is the
  segment that needs to audit why a test did not run: a free "run what is
  affected" does not give that, and has no incentive to publish its own miss
  rate.
- Needs: research, with sources, on what CI providers and test-analytics
  services offer today. No code.
- Costs: hours (OPINION).
- Risks: none to the code.

## The agent's view (OPINION)

A and E first: both are cheap, need no run and bear on whether the rest is
worth building, and A says whether D is. Of the bets that measure something
new, B tests the method best: the harness exists, and a bound on pilots whose
figures nobody has seen tells whether the window's was luck. C answers the
other half of phase 1, and on new pilots it can ride along with B, at the cost
of their green pull requests. Whichever it is, its pilots, window and
thresholds are fixed before any record (D-007).
