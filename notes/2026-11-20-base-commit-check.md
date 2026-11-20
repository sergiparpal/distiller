# The base commits of the window's runs, checked, 2026-11-20

The SPEC's Slice 2 held under [VERIFY] whether, for the window's runs other
than K16's, the last commit of the base branch before a run started, the base
commit that `checkout.base_commit` gives, is the one that the run saw. On
2026-11-20, as the user asked, the agent checked it for the 90 runs of
`2026-11-17-window-red-runs.csv` from two sources that GitHub still gave, and
only read: each run's job log, and the pushes to `main` that GitHub's
repository activity lists. Both are kept here, before GitHub drops them:
`2026-11-20-base-commit-merges.csv`, the merge that each log named, and
`2026-11-20-main-pushes.csv`, the pushes.

## How

- The harness's base commits: the `--base` of each tool step in the replay's
  logs, `~/code/distiller-replay/urllib3.log` and `poetry.log`, for the 88 pull
  requests replayed; and, for all 90, the walk of `checkout.base_commit`,
  `git rev-list --first-parent --timestamp main` in each pilot's clone, to the
  last commit whose committer date is before the manifest's run start. The two
  gave the same commit for each of the 88 (FACT).
- The logs: for each row, through `gh api`, the run
  (`repos/<repository>/actions/runs/<id>`), its jobs
  (`repos/<repository>/actions/runs/<id>/jobs?filter=latest`) and the log of
  the pilot's job, "Ubuntu 3.12" or "Ubuntu (Python 3.12) / pytest"
  (`repos/<repository>/actions/jobs/<id>/logs`). In a log, the checkout's line
  `HEAD is now at <merge> Merge <head> into <base>` names the commit that the
  run merged the head into.
- The pushes:
  `repos/<repository>/activity?ref=refs/heads/main&time_period=year`, which
  gave 172 pushes to urllib3's `main`, from 2025-11-20 to 2026-11-14, and 266
  to poetry's, from 2025-11-21 to 2026-11-19, all of them `pr_merge`. Each
  push's `before` is the previous push's `after`, so the list misses no change
  to `main` over that time (FACT). `main`'s tip when a run was created is the
  `after` of the last push before it.

## What they showed

- The logs: GitHub gave the job's log of 31 runs, 16 of urllib3's and 15 of
  poetry's, from 2026-09-04 to 2026-11-14, K16's and K17's among them. In all
  31, the checkout merged the manifest's head into the harness's base commit
  (FACT). Of the other 59 runs, from 2025-12-03 to 2026-08-17, 58 logs
  answered HTTP 410, and urllib3's #3720's run answered HTTP 404. A run's own
  record gives no base: its `pull_requests` was empty in each of the 88 runs
  that GitHub gave.
- The pushes: in each of the 31 runs with a log, `main`'s tip when the run was
  created is the commit that its log names; and in each of the 90 runs, the
  harness's base commit is `main`'s tip when the run was created (FACT).
- So the 59 runs with no log merged their heads into the harness's base commit
  too, if each run merged into `main`'s tip when it was created, as each of the
  31 did (INFERENCE). It fails only if GitHub built a run's merge before the
  base branch's last push and did not build it again. Among the 59, the base
  that reached `main` closest before its run was poetry's #10742's, 13.5
  minutes before; among the 31, poetry's #11010's reached it 1.3 minutes before
  its run, and the run merged into it.

## Also seen

- The manifest's run start is the run's `created_at`, in each of the 88 runs
  that GitHub gave. It differs from `run_started_at` only for poetry's #11151:
  its run had a second attempt, whose job started at 06:11:49 on 2026-11-01,
  two and a half minutes after the run was created, and that attempt's log
  names the harness's base commit too.
- 13 of the 59 bases with no log were committed by a maintainer, not by
  GitHub, so their committer dates need not be when they reached `main`; the
  pushes show that each reached it before its run was created. All 31 bases
  with a log were committed by GitHub.
- GitHub no longer gives two of the window's runs: urllib3's #3720's, of
  2025-12-03, and poetry's #11226's, K17's, whose job's log it still gave.
- GitHub gave the logs of runs from 2026-09-04 on and none of runs up to
  2026-08-17, so it keeps a job's log for some time in between, likely 90
  days, which would make the logs of September's runs go in early December
  (INFERENCE). The pushes were asked for over the last year, which began on
  2025-11-20, eleven days before the window's first day.
