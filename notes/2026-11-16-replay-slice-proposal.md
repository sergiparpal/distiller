# Proposal: a first slice that replays a pilot's pull requests

A proposal for the first slice of a next bet, written on 2026-11-16 at the
user's request, from `notes/2026-11-16-pilot-candidates.md` and
`notes/2026-11-16-offline-replay.md`. Nothing here is decided, and nothing in
`docs/SPEC.md` changes: the bet, its hypothesis, appetite and kill signal, its
non-goals and the "then" of any [core] example are the user's. Where this note
proposes one of those, it says so.

Labels: **FACT** = seen in this repository or in the replays of 2026-11-16;
**INFERENCE**; **OPINION**; **[VERIFY]** = not checked.

## What the slice would measure

The miss rate that Slice 1 could not measure, since its pilot never went red
(D-007): how often the all-affected, file-level selector leaves out every test
that failed in a pull request's run. Slice 1's tool evaluates the runs as it
is; what the slice adds is the runs, replayed offline from a project whose CI
the Distiller cannot join. If every pull request of the window is replayed, and
not only the red ones, the report gives the savings too.

## The pilot and the window, fixed before any figure

D-007 asks that a next bet choose its pilot before it sees any figure from it.
So, before the first record, the user fixes (OPINION on each):

- The pilot: urllib3/urllib3, whose CI runs its tests with no network, whose
  environment `uv sync --frozen` rebuilds from each commit's `uv.lock`, and
  whose red runs from a pull request's own change replayed as red; poetry needed
  a new environment within four weeks and has integration tests that cannot be
  replayed (FACT, in the two notes).
- The job: "Ubuntu 3.12", one pytest invocation on Linux CPython, as the search
  counted it.
- The window: by dates only, such as the pull requests whose runs started from
  2026-05-16 to 2026-11-15, six months, never by what a replay gives. Six to
  eight months is what about 30 red pull requests that count would take, if a
  third of the CI's red ones count, as two of urllib3's latest six did
  (INFERENCE, from six pull requests).
- The floor configuration, as D-005 chose the last pilot's before its first
  record: urllib3's tests read the certificates under `dummyserver/certs/`
  (FACT: `cacert.pem`, `cacert.key`, `server.crt` and `server.key` are there,
  and its HTTPS tests use them [VERIFY]), files that coverage cannot see, so
  `dummyserver/certs/**` is a candidate pattern.

## What would be built

A replay harness: a program apart from the tool, which prepares each run's
inputs and then runs `python -P -m distiller evaluate` as the CI step did. The
tool's code does not change (INFERENCE: every input is a name or a path on its
command line). The harness opens what the tool must not: it fetches from GitHub
and installs from PyPI, so it cannot live inside `src/distiller`, which
Constraints keep offline.

Its input is a manifest, fixed before the first record and committed: one line
per pull request of the window, with its number, the head that its run tested,
the base commit that the run saw [VERIFY: from the run's `pull_request` event],
the run's id and, read from the CI's log with its colour codes taken out, the
summary line and the tests that failed in "Ubuntu 3.12". A script that reads
GitHub through `gh` writes it once, as the search's scripts did; the replays
then need no access to GitHub but the fetch of the heads.

For each pull request of the manifest, the harness:

1. fetches its tested head, by `pull/<n>/head` or by the commit's id, which
   brought every head of 2026-11-16's replays (FACT);
2. takes as M the merge-base of the base commit and the head;
3. builds the environment of M, and the one of the head, each from its own
   `uv.lock` with `uv sync --frozen`, keeping a cache of wheels;
4. records the coverage at M: the suite at M, with `--cov=urllib3`,
   `--cov-context=test`, `COVERAGE_CORE=ctrace`, no static context, and
   coverage 7.16.2, the version that `requirements.txt` pins for the tool;
5. runs the full suite at the head once, in one pytest invocation, with
   `--junitxml`, no network but the loopback, as urllib3's nox session runs it,
   and a time limit per test;
6. runs again, with the same options, the tests that failed, into the rerun
   file;
7. runs `distiller evaluate`, appending to the replay's record file;
8. keeps a log of every step: the commands, their exit codes, their times, and
   what failed at M as well as at the head.

What failed at M costs nothing more, since the suite runs there for the coverage,
and it tells an inherited failure apart: a test that fails at the head and at
its merge-base did not fail for the pull request's change. Three of urllib3's
latest six red pull requests, and likely three of poetry's, failed that way
(FACT for urllib3; INFERENCE for poetry). The record cannot hold it, since its
format is fixed, but the harness's log can, and the SPEC's open question on
failures inherited from the base branch could use it (OPINION).

## What the slice would not do

Proposed non-goals, the user's to keep or change:

- It does not change the Distiller: no new field in a record, no new input.
- It never chooses a pull request, a window or a floor pattern after seeing a
  record.
- No other pilot, no other job: no Windows, macOS, pypy or integration session.
- It does not explain a red run of the CI that replays green, such as urllib3's
  #5278: the record holds what the replay saw, and the log the CI's summary.
- No network in the suite runs; the network is only for fetching and
  installing, before them.

## Examples it could be checked against

Proposals only: whether any becomes a [core] example, and its "then", are the
user's. Each is something that the replays of 2026-11-16 showed could happen.

- Given a manifest line for urllib3's #5375 at its tested head, when it is
  replayed, then the full run's JUnit holds 5 failed tests of
  `test/test_response.py`, as the CI's summary did, and a record is appended.
- Given a pull request whose head's `uv.lock` differs from the base branch's,
  when it is replayed, then the head's environment is built from the head's own
  `uv.lock`, and the log names it.
- Given a test that hangs, when the full run is replayed, then that test fails
  at the time limit, the run goes on, and the next pull request is replayed.
- Given a full run that ends in pytest's internal error, as poetry's #11226 did,
  when it is evaluated, then the run is recorded as rejected with
  `unusable-input` and `junit`, as Slice 1 already does.
- Given a test that fails at the head and at its merge-base, when the pull
  request is replayed, then the log marks that failure as inherited.
- Given the inputs that a replay kept, when they are evaluated twice, then both
  record files are byte-identical, as Slice 1's Invariant 1 says. Two replays of
  one pull request cannot be: the tests' times differ.

## Cost

- Building the harness: a few days of work (OPINION).
- Per pull request: an environment from a warm cache, tens of seconds; the run
  at M with test contexts, likely longer than the 24 to 40 s of a plain run
  [VERIFY]; the run at the head, 24 to 40 s on 16 threads (FACT, from the
  replays); a rerun of a few tests, seconds. Two to three minutes in all
  (INFERENCE).
- Six months of urllib3: some 70 to 140 red pull requests, from those red in a
  Linux job's tests to those red in the test workflow at all, a few hours; every
  pull request, some 380, about a day (INFERENCE, from passes 2 and 3 of the
  search: 109 pull requests in 52 days, 41 of them red, 21 in a Linux job's
  tests).

## What could end it early

Proposals for the bet's kill signal, the user's to write:

- Environments that cannot be rebuilt over the window, for wheels gone from
  PyPI or a Python that `uv` cannot find [VERIFY: not tried beyond six weeks].
- Far fewer red pull requests that replay as red than a third: below some number
  in the first weeks of the window, the 30 are out of reach.
- Inherited failures that fail again in the rerun counting against the selector
  in more runs than its own misses would.

## Open questions

1. H: the head that the run tested, or a merge of it into the base commit that
   the run saw, as the CI tested. For urllib3's #5278, both passed (FACT); one
   case says little.
2. Which pull requests: every one of the window, for the savings too, or only
   those that the CI saw red, for the miss rate alone.
3. Where the harness lives: in this repository, as a second program with its
   own tests and an import-linter contract that keeps it out of `distiller`, or
   in a repository of its own.
4. The rerun: once, as the last pilot's workflow did, or more, for tests as
   flaky as urllib3's `test_http2_probe_blocked_per_thread`, which failed in 3
   of 10 runs at one commit (FACT).
5. The time limit per test: 120 s held for urllib3 (FACT), and is a guess for
   any other suite.
