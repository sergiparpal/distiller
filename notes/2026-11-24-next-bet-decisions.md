# Decisions for the next bet, 2026-11-24

The next bet replays the red pull requests of new pilots, whose figures nobody
has seen (option B of `2026-11-20-next-bet-options.md`, note 103 of
`TASKS.md`). The user writes it. This sheet lists what its lines, the
Hypothesis, the Appetite and the Kill signal, and its slice's non-goals have to
settle, each with the facts that bear on it and the agent's view. Nothing is
decided here, and no figure of the Distiller exists for any new pilot: every
fact below comes from CI outcomes and from the pilots' own suites
(`2026-11-21-new-pilot-search.md`), so D-007 still lets each choice be made.

Labels: **FACT**; **INFERENCE**; **OPINION**, the agent's view.

## 1. What the bet measures

- Options: (a) the miss rate's bound alone, as the current Bet; (b) with the
  savings too, option C, over all the pilots' pull requests; (c) with the
  failed tests left out classified afterwards by a person, as D-021 to D-023
  did for the window.
- FACT: each passing candidate's other pull request runs are saved,
  `pilot-search/<project>-pull-request-runs.json`, so (b) can still be chosen
  before the first record; it would replay green pull requests too, and bring
  back each pilot's floor configuration, which D-015 left out of Slice 2
  because no savings figure was asked for.
- FACT: §13.2's share can be called marginal only with at least 29 classified
  failed tests left out with no file dependency, 15 more than the window's 14
  (D-023), and only from pull requests whose figures nobody has seen.
- OPINION: (a), with (c) after the outcome, as for the window. The savings ask
  for floors chosen per pilot and for green pull requests, and are a bet of
  their own.

## 2. Which pilots

Of the 18 that passed D-024's funnel, 14 have a suite that runs in the sandbox
and environments that build from their lock files (FACT, step 3):

| Pilot | Expected red PRs (INFERENCE) | Of the 14's total | Not built, of 15 | Replay, hours (INFERENCE) |
|---|---|---|---|---|
| zha-device-handlers | 132 | 31% | 0 | 1.4 |
| pydantic | 82 | 19% | 4 | 2.6 |
| EvoScientist | 37 | 9% | 0 | 13.3 |
| click | 32 | 8% | 0 | 0.1 |
| python-sdk | 30 | 7% | 0 | 0.6 |
| rally | 20 | 5% | 2 | 0.6 |
| maigret | 18 | 4% | 1 | 1.5 |
| chonkie | 16 | 4% | 0 | 2.1 |
| mitmproxy | 14 | 3% | 0 | 0.2 |
| pydantic-settings | 14 | 3% | 0 | 0.1 |
| gdsfactory | 12 | 3% | 1 | 0.6 |
| electricitymaps-contrib | 10 | 2% | 7 | 0.2 |
| verifiers | 5 | 1% | 0 | 0.1 |
| wemake-python-styleguide | 4 | 1% | 0 | 0.2 |

Expected red pull requests: the share of each one's sample of ten that stayed
red, times its CSV's rows. Replay hours: two and a half suite runs a pull
request, at step 3's pace, which includes its builds. Both are rough
(INFERENCE). Left out: pr-agent, whose commits ask for different versions of
uv, and manim, whose suite needs a display; DataDesigner and PennyLane do not
build from their lock files.

- FACT: Slice 1's report counts pull requests by number alone, and ten pairs
  of the 14 share at least one number. The largest set of them that shares
  none, by expected red pull requests, is 8 pilots and some 333: zha,
  pydantic, EvoScientist, click, rally, mitmproxy, electricitymaps-contrib and
  verifiers, some 18 hours of replay. A set of 9 without EvoScientist gives
  some 326 in some 7 hours: zha, pydantic, click, rally, mitmproxy,
  electricitymaps-contrib, verifiers, chonkie and pydantic-settings
  (INFERENCE, from the expected counts).
- FACT: zha and pydantic together hold half of the 14's expected red pull
  requests, so a pooled bound would mostly measure them.
- Options: (a) the set of 9 or of 8, with no change to the report; (b) all 14,
  with a slice in which the report counts a pull request by its project and its
  number; (c) a few pilots only, such as the top four.
- OPINION: (a), the set of 9: no change to Slice 1, the replay fits in a day of
  the user's machine, and EvoScientist's 13 hours buy only 9% of the pull
  requests. The report's breakdown by pilot, which the harness's summary
  already gives, shows how much zha and pydantic weigh.

## 3. The window

- FACT: each pilot's CSV holds every red pull request that GitHub listed on
  2026-11-21, its oldest from 2025-12-15 (rally) to 2026-10-19 (verifiers),
  where a job took its present name late in the year. GitHub drops about a day
  of the oldest runs each day, but the replay needs only the CSV, the heads,
  kept in the clones, and the clones' history.
- Options: (a) each pilot's CSV as it is, to 2026-11-21; (b) one start date for
  all, which drops the older rows of some.
- OPINION: (a). A start of the bet's own choosing would be a second rule to
  justify, and the CSVs already fix what each pilot gives, before any record.

## 4. The bound, and the least number of red pull requests

The bound that n pull requests with a red run give with k missed (FACT, by
`clopper_pearson_upper`):

| n | k = 0 | k = 3 | k = 5 | k = 10 | k = 20 |
|---|---|---|---|---|---|
| 100 | 3.0% | 7.6% | 10.2% | 16.4% | 27.7% |
| 200 | 1.5% | 3.8% | 5.2% | 8.3% | 14.2% |
| 300 | 1.0% | 2.6% | 3.5% | 5.6% | 9.5% |

- FACT: the window gave 3 missed out of 52, all from one flaky test (D-017);
  the misses of new pilots are not known, and cannot be before the first
  record.
- Options: a bound below 15%, as now, which 300 pull requests pass with up to
  34 misses; below 10%, which 200 pass with up to 12 and 300 with up to 21; or
  below 5%, which 200 pass with up to 4 and 300 with up to 8 (FACT, by
  `clopper_pearson_upper`).
- OPINION: the bet should be one that a bad selector fails: below 10% over at
  least 200 pull requests with a red run, so that the expected 300 leave room
  for builds that fail and samples that were lucky. Which figure is the user's.

## 5. Environments not built

- FACT: the Kill signal counts the environments not built against 20% of the
  pull requests replayed. At step 3, electricitymaps-contrib built 8 of 15
  and pydantic 11 of 15, for want of the uv version that some commits ask for
  and, at one of pydantic's, for Rust code that no longer compiles; the others
  built at least 13 of 15.
- Options: (a) 20% pooled over all pilots, as now; (b) 20% for each pilot.
- OPINION: (a), pooled, as the bound is: the two pilots that build least hold
  a fifth of the expected pull requests, so a pooled 20% holds unless more
  fail than step 3 saw (INFERENCE).

## 6. Flaky tests and the tests deselected

- FACT: D-024 deselects every test that fails in two runs at each of three base
  commits, and no other: from none, for four of the 14, to 134, chonkie's,
  likely for want of the network. The window's three misses came from a flaky
  test that failed at 21 of urllib3's Ms, which such a rule would likely have
  caught at three Ms (INFERENCE).
- Options: (a) D-024's rule as it ran; (b) more base commits or more runs, more
  replay time before the first record.
- OPINION: (a), with its deselections written into each pilot's configuration
  before the first record, as D-016 did for poetry.

## 7. What the slice changes in the harness

Each change takes a tests phase and an implement phase, as Slice 2's tasks did
(FACT):

- The report counting a pull request by project and number: only for pilots
  that share numbers, decision 2 (b).
- The plugins installed from outside the worktree: the harness runs `uv pip
  install` there with the user's uv, and a commit's `required-version` refuses
  it (step 3, electricitymaps-contrib and pydantic); outside the project, uv
  would read no such setting (INFERENCE) [VERIFY].
- A uv chosen for each commit, for pilots like pr-agent; and a display in the
  sandbox, for manim: OPINION, not for this bet.
- No change for the system's Python or for `--no-preview`: the pilot
  configurations already name them (note 105).
- OPINION: the second change only, which raises what electricitymaps-contrib
  and pydantic build, if the set of 9 is taken.

## 8. Appetite

- FACT: the current Bet's was 3 weeks; Slice 2's task 0 and its eight cycles
  were all done on 2026-11-18, and its window took 3.2 hours of steps.
- INFERENCE: for the set of 9, one cycle for the plugin install, the pilot
  configurations fixed with their deselections, some 7 hours of steps on the
  user's machine and the report: some 2 weeks.
- OPINION: 3 weeks, as before, for a margin; the user's.

## 9. Before the bet is written

- Note 102: checked on 2026-11-22, and good for a bet written by 2026-12-09.
- D-007: the pilots, the window, the thresholds and each pilot's deselections
  are fixed before the first record.
- Note 104, the window's manifest, and the current Bet's outcome are due by
  2026-12-09 and do not depend on these decisions.
- The scratchpad holds the funnel's cache and the step 3 logs; nothing the bet
  needs is only there: the CSVs, the JSON files, the pilot configurations and
  the clones are in the repository or in `~/code/distiller-pilots/`.
