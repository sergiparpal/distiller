# ruff: noqa: INP001
"""D-024's checks of a finalist, before any record of it exists.

For one finalist: its environments built at the heads of its oldest and newest
red pull requests; its suite run twice at each of three base commits, those of
its oldest, middle and newest red pull requests, and every test that fails in
one of those six runs, which D-024 deselects; and a sample of its red pull
requests, evenly spread over its CSV's rows by date, each replayed with its own
suite alone, a full run and one rerun of the tests that failed, with those
tests deselected. The Distiller never runs here.

It runs the harness's own modules, by the interfaces of the SPEC, so that each
build and each suite run is the replay's: worktrees in the work directory,
environments from each commit's own lock file, and the suite inside bubblewrap
with no network but the loopback. Run from the repository's root:
    PYTHONPATH=src .venv/bin/python notes/pilot-search/feasibility.py
    --pilot <TOML> --csv <project>-red-runs.csv --clone <clone>
    --work <directory outside the repository> --out <JSON file>
"""

import argparse
import csv
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from replay import checkout, environment, suite
from replay.pilot import Pilot, read_pilot
from replay.steps import StepResult

SAMPLE_SIZE = 10
RUNS_AT_EACH_BASE = 2
TAIL_CHARACTERS = 2000


def log(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def rows_of(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return sorted(rows, key=lambda row: (row["run_started"], row["run_id"]))


def rows_in_clone(rows: list[dict[str, str]], clone: str) -> list[dict[str, str]]:
    """The rows whose head the clone holds: a head that GitHub no longer gave
    cannot be checked out, so it is neither oldest, newest nor in the sample."""
    return [row for row in rows if checkout.has_commit(clone, row["head"])]


def oldest_middle_newest(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [rows[0], rows[len(rows) // 2], rows[-1]]


def evenly_spread(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """SAMPLE_SIZE rows spread evenly by date, the first and the last included."""
    if len(rows) <= SAMPLE_SIZE:
        return rows
    last = len(rows) - 1
    indexes = sorted({round(i * last / (SAMPLE_SIZE - 1)) for i in range(SAMPLE_SIZE)})
    return [rows[index] for index in indexes]


def folder_for(work: Path, name: str) -> str:
    return str(work / "feasibility" / name)


def tail_of(step: StepResult, work: Path) -> str:
    """The end of what a step printed, kept when it did not succeed, with the
    work directory and the home written as `<work>` and `~`, so that no local
    path, and no user name in one, reaches the repository."""
    output = step.output.replace(str(work), "<work>").replace(str(Path.home()), "~")
    return output[-TAIL_CHARACTERS:]


def build_at(pilot: Pilot, clone: str, commit: str, work: Path) -> dict[str, Any]:
    folder = folder_for(work, commit[:12])
    checkout.add_worktree(clone, commit, folder)
    try:
        built = environment.build(pilot, folder, for_coverage=False)
    finally:
        checkout.remove_worktree(clone, folder)
    log(f"environment at {commit[:12]}: exit {built.exit_code}, {built.seconds:.0f} s")
    result: dict[str, Any] = {
        "commit": commit,
        "exit_code": built.exit_code,
        "seconds": built.seconds,
    }
    if built.exit_code != 0:
        result["output_tail"] = tail_of(built, work)
    return result


def failures_at_base(
    pilot: Pilot, clone: str, row: dict[str, str], work: Path
) -> dict[str, Any]:
    base = checkout.base_commit(clone, pilot.base_branch, row["run_started"])
    if base is None:
        return {"run_id": row["run_id"], "base": None, "runs": []}
    folder = folder_for(work, f"base-{base[:12]}")
    checkout.add_worktree(clone, base, folder)
    try:
        built = environment.build(pilot, folder, for_coverage=False)
        runs: list[dict[str, Any]] = []
        if built.exit_code == 0:
            for attempt in range(1, RUNS_AT_EACH_BASE + 1):
                junit = folder_for(work, f"base-{base[:12]}-{attempt}.xml")
                ran = suite.full_run(pilot, folder, str(work), junit)
                runs.append(run_summary(ran, work))
    finally:
        checkout.remove_worktree(clone, folder)
    failed = [run["failed"] for run in runs]
    log(f"base {base[:12]}: build {built.exit_code}, failed {failed}")
    result: dict[str, Any] = {
        "run_id": row["run_id"],
        "base": base,
        "build": built.exit_code,
        "runs": runs,
    }
    if built.exit_code != 0:
        result["output_tail"] = tail_of(built, work)
    return result


def run_summary(ran: StepResult, work: Path) -> dict[str, Any]:
    """A suite run's exit code and failed tests, and, when it failed with no
    failed test, as when pytest cannot start, the end of what it printed."""
    summary: dict[str, Any] = {"exit_code": ran.exit_code, "failed": list(ran.failed)}
    if ran.exit_code not in (0, 1) or (ran.exit_code == 1 and not ran.failed):
        summary["output_tail"] = tail_of(ran, work)
    return summary


def deselected(bases: list[dict[str, Any]]) -> list[str]:
    tests: set[str] = set()
    for base in bases:
        for run in base["runs"]:
            tests.update(run["failed"])
    return sorted(tests)


def with_deselected(pilot: Pilot, tests: list[str]) -> Pilot:
    options = list(pilot.pytest)
    for test in tests:
        options += ["--deselect", test]
    return dataclasses.replace(pilot, pytest=tuple(options))


def replay_with_suite(
    pilot: Pilot, clone: str, row: dict[str, str], work: Path
) -> dict[str, Any]:
    head = row["head"]
    folder = folder_for(work, f"head-{row['run_id']}")
    checkout.add_worktree(clone, head, folder)
    try:
        result = full_run_and_rerun(pilot, folder, row, work)
    finally:
        checkout.remove_worktree(clone, folder)
    log(f"#{row['pull_request']} run {row['run_id']}: {result}")
    return result


def full_run_and_rerun(
    pilot: Pilot, folder: str, row: dict[str, str], work: Path
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "pull_request": row["pull_request"],
        "run_id": row["run_id"],
    }
    built = environment.build(pilot, folder, for_coverage=False)
    result["build"] = built.exit_code
    if built.exit_code != 0:
        result["output_tail"] = tail_of(built, work)
        return result
    full = suite.full_run(pilot, folder, str(work), f"{folder}-full.xml")
    result["full_run"] = run_summary(full, work)
    result["full_run"]["failed"] = len(full.failed)
    if not full.failed:
        result["red"] = False
        return result
    again = suite.rerun(pilot, folder, str(work), full.failed, f"{folder}-rerun.xml")
    still = sorted(set(full.failed) & set(again.failed))
    result["rerun"] = {"exit_code": again.exit_code, "failed": len(again.failed)}
    result["failed_twice"] = still
    result["red"] = bool(still)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--clone", required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    pilot = read_pilot(arguments.pilot)
    clone = arguments.clone
    all_rows = rows_of(arguments.csv)
    rows = rows_in_clone(all_rows, clone)
    work = arguments.work
    report: dict[str, Any] = {"project": pilot.project}
    present = {row["run_id"] for row in rows}
    report["heads_not_in_clone"] = [
        row["run_id"] for row in all_rows if row["run_id"] not in present
    ]
    oldest_and_newest = [rows[0]["head"], rows[-1]["head"]]
    report["environments"] = [
        build_at(pilot, clone, h, work) for h in oldest_and_newest
    ]
    bases = [
        failures_at_base(pilot, clone, row, work) for row in oldest_middle_newest(rows)
    ]
    report["bases"] = bases
    report["deselected"] = deselected(bases)
    checked = with_deselected(pilot, report["deselected"])
    sample = evenly_spread(rows)
    report["sample"] = [replay_with_suite(checked, clone, row, work) for row in sample]
    report["red_in_sample"] = sum(1 for result in report["sample"] if result.get("red"))
    text = json.dumps(report, indent=1) + "\n"
    arguments.out.write_text(text, encoding="utf-8")
    log(f"done: {report['red_in_sample']} of {len(sample)} red in the sample")


if __name__ == "__main__":
    main()
