# The plugins of Slice 2's Rule 4, checked, 2026-11-20

The SPEC's Slice 2 held under [VERIFY] whether the plugins that its Rule 4 adds
change any test's outcome, and D-011 held it for pytest-timeout. On
2026-11-20, as the user asked, the agent checked it on the window's replay of
2026-11-19 (`2026-11-19-window-replay.md`), and only read: the JUnit files and
the logs that the replay kept in `~/code/distiller-replay/`, the pilots'
clones and, through `gh api`, poetry's CI jobs.

## What Rule 4 adds

- pytest-timeout 2.4.0, to each of poetry's environments, 42 at the heads and
  42 at M, whose locks lack it. urllib3's locks hold pytest-timeout 2.4.0, so
  the harness adds nothing to urllib3's environments at the heads. Every suite
  run of both pilots that printed pytest's header, 235 of 237, says
  `timeout: 120.0s` and `timeout method: signal` (FACT).
- coverage 7.16.2 and pytest-cov 7.1.0, to M's environments, for the coverage
  run alone. Their install replaced the lock's coverage, of versions from
  7.11.0 to 7.17.2, in 86 of the 88, replaced poetry's pytest-cov 7.0.0 in 16,
  and added pytest-cov to 43 of urllib3's (FACT, from the install's output in
  the logs).

## pytest-timeout

- It changed the outcome of five tests at four of poetry's pull requests, all
  in `tests/console/commands/test_init.py`: `test_predefined_all_options` at
  #10746 and #10956, `test_interactive_rejects_invalid_version_constraint` at
  #10751, and `test_predefined_all_options` and
  `test_predefined_multiple_authors` at #10889. Each was in a loop that wrote
  an error line again and again, as its traceback shows, until pytest-timeout
  failed it at 120 s, in the full run and again in the rerun (FACT).
- Without the plugin, such a test would have kept its run going until the
  run's own limit, with no JUnit file. The harness hands the tool the JUnit
  file's path whatever the run did, so the tool would have rejected the run,
  and none of the four would have a red record (INFERENCE, not run). D-011
  chose the plugin so as not to lose such pull requests, #10956 among them.
- The CI seems to have hung on them too: poetry's job took 26.4 minutes in
  #10889's run, 62.2 in #10956's, 70.4 in #10746's and 118.1 in #10751's,
  against 0.5 to 2.6 minutes in each of the window's other 38 runs of poetry's
  (FACT, through `gh api` on 2026-11-20). That the same tests hung there is an
  inference, since GitHub no longer gives those runs' logs.
- No other effect was seen. Besides the tests that pytest-timeout stopped, no
  test of either pilot took more than 10.4 s in any run, so the limit cut no
  test that was only slow (FACT). With the signal method, pytest-timeout sets
  an interval timer and a handler for `SIGALRM` around each test; none of the
  68 commits of poetry's that the replay ran, heads and Ms, uses `SIGALRM`,
  `signal.alarm` or an interval timer (FACT, by `git grep`), so nothing of
  poetry's shares them with it (INFERENCE).

## coverage and pytest-cov at M

- No test failed in any of poetry's 42 coverage runs at M, and no test reached
  the limit at any M of either pilot: the longest took 8.4 s (FACT).
- At urllib3's Ms, only `test_http2_probe_blocked_per_thread` failed, at 21 of
  the 46, and it fails without coverage too: in the 42 pull requests where it
  ran both at M, with coverage, and at the head, without, it failed at M in 17
  and at the head in 23 (FACT). Nothing shows that coverage makes it fail more
  often (INFERENCE).
- The outcomes at M feed only the replay's count of inherited failures: the
  tool reads the coverage at M, not its JUnit file.

## Outside Rule 4: urllib3's own pytest-timeout

urllib3's own pytest-timeout, given the harness's 120 s (Rule 5), failed the
probe test at the limit in the full runs of #5097 and #5228. It changed
neither verdict: #5097 was caught by other tests, and #5228 is green, since
the rerun discarded both of its failures (FACT).

## What it means for the Bet

The four pull requests of poetry are among the 52 with a red run, all of them
caught, and red as the SPEC defines it, since the rerun does not discard their
failures. Three of them, #10746, #10751 and #10956, are red from a test that
hung and nothing else; #10889 has three other failures too. With the report's
`clopper_pearson_upper`, the bound is 14.2% for 3 missed pull requests out of
52, 15.1% for 3 out of 49 and 15.4% for 3 out of 48 (FACT). Whether they
count is the user's to say, in the Bet's outcome.
