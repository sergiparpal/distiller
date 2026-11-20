# Native test selection, checked, 2026-11-21

C6 §12 lists one risk as unverified, the only row of its ledger still
unchecked: "Los CI nativos regalan selección afectada", that native CIs give
affected-test selection away. Its mitigation names a wedge if it happens: the
segment that needs an audit of why a test did not run, which a free "run what
is affected" does not give, and which has no incentive to publish its own
failure rate (translated). As the user asked on 2026-11-20, option E of
`2026-11-20-next-bet-options.md`, the agent checked it on 2026-11-20 and
2026-11-21, reading only: the documentation, pricing pages, changelogs and
repositories of twelve CI platforms and of the main test-selection services
and tools, through two research agents, and then the pages that decide the
answer, fetched again on their own. "Not found" below means that the pages
read did not say it, not that it does not exist.

## Native CIs

| Platform | Selects tests from the change | Python with pytest |
|---|---|---|
| CircleCI | Yes: Smarter Testing, generally available since 2026-10-13 | Yes |
| Harness CI | Yes: Test Intelligence | Yes, pytest 8.0 to 9.0.2 |
| Azure Pipelines | Yes: Test Impact Analysis, for managed code only | No |
| GitLab | Runs the RSpec specs related to the change first, then the whole suite | No |
| TeamCity | By module, for Maven and Gradle | No |
| Buildkite | A preview, "under development" | n/a |
| GitHub Actions, Bitbucket Pipelines, Jenkins' core, Semaphore, Google Cloud Build, AWS CodeBuild | Not found: their filters skip whole workflows, jobs, blocks or builds | n/a |

- CircleCI (FACT): "Smarter Testing is now generally available for all Cloud
  customers" (changelog, 2026-10-13). "CircleCI tracks which tests exercise
  which source files, then uses that analysis to skip tests that cover
  unchanged source files"; on a feature branch it also runs a test that is
  new, that failed on the branch's previous run, or whose covered file was
  removed; and it names pytest among its frameworks (set-up guide, last
  updated 2026-10-13). "A test atom is the smallest unit of work your test
  runner can execute on its own, usually a test file." Its pricing page lists
  "Intelligent test selection" on Free, Performance and Scale: "Each plan
  includes a free monthly threshold: 1,000 test atoms on Free, 10,000 on
  Performance, and 100,000 on Scale"; usage above it "is billed at 3,000
  credits per 100,000 test atoms evaluated, rounded up" (changelog).
- Harness CI (FACT): Test Intelligence uses "a list of added/modified files
  with the call graph to identify which tests to run", and lists Python 3.8+
  and pytest 8.0+ up to 9.0.2. Which plans include it: unconfirmed.
- Azure Pipelines (FACT): Test Impact Analysis, in the VSTest task, "is
  currently scoped to only managed code", and .NET Core is among what it does
  not support.
- GitLab (FACT): Fail fast testing, in Premium and Ultimate, "runs the test
  specs most relevant to your merge request changes before the rest of the
  suite runs", for a Ruby on Rails project that uses RSpec.

So the risk has happened on CircleCI, for pytest too and with a free monthly
allowance. On GitHub Actions, the CI of both Slice 2 pilots and of Slice 1's
pilot, nothing of the kind was found.

## The wedge

- Why a test did not run. No native CI found gives a reason for each test
  that it skips. CircleCI's job output gives "the reason for selection" of the
  tests it runs and shows the skipped ones in its "Test" tab, with no reason
  on the page; Harness shows the call graph behind each selected test and,
  for the others, a count, "Skipped by TI"; Azure marks a skipped test
  `NotImpacted`. Develocity's Predictive Test Selection gives one: "The Build
  Scan indicates which tests were selected and which weren't along with the
  reason why", for JVM tests run through JUnit Platform only (FACT).
- A measured miss rate. No native CI publishes one. CircleCI's blog says
  that its selection "is safe to rely on", while its set-up guide says that
  "Code coverage cannot detect every relationship between source files and
  test atoms"; Harness's page shows "0 false positives" with no method
  (FACT). Two paid services compute a figure for the customer (FACT):
  - CloudBees Smart Tests, Launchable until its general availability of
    2026-04-02: "Confidence is the probability that the subset will catch a
    failing session", "aggregated across all the evaluation test sessions".
    Its observation mode runs every test and records the subset's results
    apart, to measure "Whether the subset would have caught a failing
    session" and "How much time could have been saved by running only the
    subset of tests". Its unit is a failing session, not a failed test, and
    it ranks tests by the similarity between source code and test code and by
    their failure history: "PTS currently does not depend on code coverage
    information." That the evaluation sessions are the customer's own is an
    inference: the page ties them to the sessions "used to train your model".
  - Develocity: "The simulator works by comparing actual test results from
    Build Scan data to what would have happened if the build used Predictive
    Test Selection", with "% Test failures predicted", and "The system is
    calibrated to catch over 99% of non-flaky test task/goal failures for
    many different types of projects and changesets": a target of the
    vendor's, for the JVM.
- Datadog's Test Impact Analysis publishes no such figure, and says that it
  "might skip impacted tests with the out-of-the-box configuration", after
  changes in library dependencies, compiler options, external services or
  data files (FACT). pytest-testmon measures none either, and its service
  advises running every test on the main branches "so that the occasional
  miss is not a problem" (FACT).
- None of the pages read gives a one-sided bound on a miss rate over pull
  requests with a red run, as Slice 1's report does (INFERENCE, from the
  pages read).

## What it means (OPINION)

- C6 §12's row is checked: the risk has happened, on CircleCI, and its rule,
  which skips the tests whose coverage holds no changed file, is close to the
  all-affected, file-level selector that the Distiller measures. A selector
  alone is no longer something to offer a team on CircleCI.
- The wedge holds, narrower than C6 put it: the free selection gives no reason
  for what it skips and no measured miss rate. A reason for each skipped test
  and a shadow measurement exist, but in paid services: Develocity's for the
  JVM, and CloudBees' for failing sessions, from a model. What none of the
  pages shows is what Slice 1's report gives: a miss rate with its bound, over
  a team's own pull requests with a red run, for a coverage-based selection of
  pytest tests. C6 §11 already puts the product there: not a promise but a
  dial, each of its levels with a measured and published error rate (FACT).
- An option that `2026-11-20-next-bet-options.md` lacks: measuring the miss
  rate of a selection that another tool made, such as CircleCI's on a project
  that uses it, from that project's own history. It needs such a project with
  red runs, and the test atoms that the selection ran in a form a tool can
  read [VERIFY: whether CircleCI's job output or API gives them].
- Whether C6's row changes is the user's to say.

## Also found

- coverage.py's `sysmon` core is "Only available in Python 3.12+, and the
  default in Python 3.14+", and "does not yet support plugins, dynamic
  contexts, or some concurrency libraries" (FACT). The coverage at M needs
  per-test contexts, which pytest-cov records as dynamic contexts: Slice 1's
  Deployment sets `COVERAGE_CORE=ctrace`, and Slice 2's pilots run Python
  3.12, where `sysmon` is not the default. On Python 3.14, a run at M that
  does not set the core would lose its contexts (INFERENCE).
- Codecov's Automated Test Selection: the pull request "Hide and mark
  ATS-related commands as deprecated" was merged into its CLI on 2025-03-18
  (FACT), while its documentation still calls it an open beta.

## Limits

- The research agents and the second fetches read the pages through a tool
  that passes them through a model, which can shorten long sentences. The
  quotes from CircleCI's changelog, pricing page and set-up guide, Harness's
  test page, CloudBees' two pages on subsets, Develocity's page, Datadog's
  page, coverage.py's configuration page and Codecov's pull request were
  fetched a second time, on their own, and said the same; the others come
  from the research agents' reading alone.
- Prices and plans are those that the pages showed on 2026-11-20 and
  2026-11-21. Harness's plans for Test Intelligence and CloudBees' prices
  were not found.
- Not looked at: Appsurify and Trunk.

## Sources

- CircleCI: https://circleci.com/changelog/smarter-testing-is-now-generally-available/,
  https://circleci.com/pricing/,
  https://circleci.com/docs/guides/test/set-up-test-impact-analysis/ and
  https://circleci.com/blog/smarter-testing-stop-running-tests-that-dont-matter/
- Harness: https://developer.harness.io/docs/continuous-integration/use-ci/run-tests/ti-overview
  and https://developer.harness.io/docs/continuous-integration/use-ci/run-tests/tests-v2
- Azure Pipelines: https://learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis?view=azure-devops
- GitLab: https://docs.gitlab.com/ci/testing/fail_fast_testing/
- GitHub Actions: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Buildkite: https://github.com/buildkite/test-engine-client
- CloudBees Smart Tests: https://docs.cloudbees.com/docs/cloudbees-smart-tests/latest/send-data-to-smart-tests/subset/choose-a-subset-optimization-target,
  https://docs.cloudbees.com/docs/cloudbees-smart-tests/latest/send-data-to-smart-tests/subset/observe-subset-behavior,
  https://docs.cloudbees.com/docs/cloudbees-smart-tests/latest/features/predictive-test-selection/how-we-select-tests
  and https://www.cloudbees.com/newsroom/cloudbees-smart-tests-brings-control-to-ai-generated-code
- Develocity: https://docs.develocity.ai/predictive-test-selection
- Datadog: https://docs.datadoghq.com/tests/test_impact_analysis/
- pytest-testmon: https://testmon.net/
- coverage.py: https://coverage.readthedocs.io/en/latest/config.html
- Codecov: https://github.com/codecov/codecov-cli/pull/662
