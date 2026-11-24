# ruff: noqa: INP001
"""D-024's criteria, applied to each candidate from its CI outcomes alone.

For each candidate of candidates.json that passes the files, in the order of
their names: its job, its job's duration, its base branch and the pull requests
whose job failed, each measured as D-024 says, cheapest first, stopping at the
first criterion it fails. Each candidate's result goes into the cache
directory, so that a run stopped half way goes on where it stopped. The
candidates that pass get a CSV of their red pull requests, in the columns of
notes/2026-11-17-window-red-runs.csv, and a JSON file of all the pull request
runs of their job's workflow. No user name, branch name or title is written.

Run from the repository's root, with a cache directory outside it:
    .venv/bin/python notes/pilot-search/funnel.py --out notes/pilot-search
    --cache <directory>
"""

import argparse
import csv
import json
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from github import (
    PAGE_SIZE,
    GitHub,
    GitHubError,
    all_pages,
    list_runs,
    log,
    moment_of,
)

# D-024's thresholds.
MIN_RED = 20
MIN_AUTHORS = 5
MOST_SECONDS = 5 * 60
# Fewer than 10% of the base branch's runs failed, and at least 80% of the red
# pull requests failed in a test step: written as whole numbers, failed * 10 <
# ran and tests * 5 >= known * 4, so that no rounding decides a criterion.
BASE_FACTOR = 10
TEST_STEP_NUMERATOR = 4
TEST_STEP_DENOMINATOR = 5
AUTHOR_SHARE_DENOMINATOR = 3
# How D-024 samples.
LATEST_RUNS_PER_WORKFLOW = 3
SUCCESSFUL_RUNS = 10
MOST_SUCCESSFUL_RUNS_LOOKED_AT = 40
PUSH_RUNS = 100
SMALL_PAGE_SIZE = 20
STEP_WORDS = ("test", "pytest", "nox", "tox")
PYTHON_312_WORDS = ("3.12", "py312", "cp312")
OTHER_PYTHONS = ("pypy", "graalpy")
LINUX_WORDS = ("ubuntu", "linux")
EARLIEST = datetime(2025, 1, 1, tzinfo=UTC)
CSV_COLUMNS = (
    "project",
    "pull_request",
    "run_id",
    "run_started",
    "head",
    "job",
    "failed_steps",
)


@dataclass
class Candidate:
    """What the stages learn about one candidate, in memory only."""

    github: GitHub
    repository: str
    measured: dict[str, Any] = field(default_factory=dict[str, Any])
    default_branch: str = ""
    workflow_id: int = 0
    job_name: str = ""
    failed_runs: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    pull_requests: dict[int, dict[str, Any]] = field(
        default_factory=dict[int, dict[str, Any]]
    )
    heads: dict[tuple[str, str], list[dict[str, Any]]] = field(
        default_factory=dict[tuple[str, str], list[dict[str, Any]]]
    )
    # The pull requests whose fork was deleted, by their head's branch.
    orphans: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict[str, list[dict[str, Any]]]
    )
    red: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


def runs_path(candidate: Candidate) -> str:
    return (
        f"repos/{candidate.repository}/actions/workflows/{candidate.workflow_id}/runs"
    )


def jobs_of(candidate: Candidate, run_id: int) -> list[dict[str, Any]]:
    path = f"repos/{candidate.repository}/actions/runs/{run_id}/jobs"
    try:
        return all_pages(candidate.github, path, {}, "jobs")
    except GitHubError as error:
        if error.not_found:
            return []
    # A run with hundreds of jobs can make GitHub answer HTTP 502 for every
    # page of 100: smaller pages take it less time to write.
    return all_pages(candidate.github, path, {}, "jobs", page_size=SMALL_PAGE_SIZE)


def job_in_run(candidate: Candidate, run_id: int) -> dict[str, Any] | None:
    for job in jobs_of(candidate, run_id):
        if job["name"] == candidate.job_name:
            return job
    return None


def is_test_step(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in STEP_WORDS)


def job_matches(job: dict[str, Any]) -> bool:
    name = job["name"].lower()
    labels = " ".join(job["labels"]).lower()
    on_linux = any(word in labels for word in LINUX_WORDS)
    on_312 = any(word in name for word in PYTHON_312_WORDS)
    other_python = any(word in name for word in OTHER_PYTHONS)
    runs_tests = any(is_test_step(step["name"]) for step in job.get("steps", []))
    return on_linux and on_312 and runs_tests and not other_python


def numbers_given(run: dict[str, Any], repository: str) -> list[int]:
    ending = f"/repos/{repository}".lower()
    numbers: list[int] = []
    for pull_request in run["pull_requests"]:
        base_repository = pull_request["base"]["repo"]
        # GitHub sometimes gives a pull request of a run with no base repository.
        if base_repository and base_repository["url"].lower().endswith(ending):
            numbers.append(pull_request["number"])
    return numbers


def head_owner(run: dict[str, Any]) -> str | None:
    repository = run.get("head_repository")
    # A fork that was deleted, or whose owner's account was, has no owner.
    if not repository or not repository.get("owner"):
        return None
    return repository["owner"]["login"]


def bound_key(run: dict[str, Any], repository: str) -> str:
    """A key that two runs of one pull request share, which can only count one
    pull request as two, never two as one: enough for an upper bound."""
    given = numbers_given(run, repository)
    if given:
        return f"#{given[0]}"
    return f"{head_owner(run)}:{run['head_branch']}:{run['display_title']}"


def duration_in_seconds(job: dict[str, Any]) -> float:
    elapsed = moment_of(job["completed_at"]) - moment_of(job["started_at"])
    return elapsed.total_seconds()


def count_failed_runs(candidate: Candidate) -> str | None:
    path = f"repos/{candidate.repository}/actions/runs"
    parameters: dict[str, str | int] = {
        "event": "pull_request",
        "status": "failure",
        "per_page": 1,
    }
    count = candidate.github.get_object(path, parameters)["total_count"]
    candidate.measured["failed_pull_request_runs"] = count
    if count < MIN_RED:
        return "fewer than 20 failed pull request runs"
    return None


def failed_count_of_workflow(candidate: Candidate, workflow_id: int) -> int:
    path = f"repos/{candidate.repository}/actions/workflows/{workflow_id}/runs"
    parameters: dict[str, str | int] = {
        "event": "pull_request",
        "status": "failure",
        "per_page": 1,
    }
    return candidate.github.get_object(path, parameters)["total_count"]


def matching_jobs(
    candidate: Candidate, workflow: dict[str, Any]
) -> list[tuple[int, str, int]]:
    path = f"repos/{candidate.repository}/actions/workflows/{workflow['id']}/runs"
    parameters: dict[str, str | int] = {
        "event": "pull_request",
        "status": "completed",
        "per_page": LATEST_RUNS_PER_WORKFLOW,
    }
    runs = candidate.github.get_object(path, parameters)["workflow_runs"]
    found: list[tuple[int, str, int]] = []
    for run in runs:
        jobs = jobs_of(candidate, run["id"])
        found.extend(
            (len(job["name"]), job["name"], workflow["id"])
            for job in jobs
            if job_matches(job)
        )
    return found


def find_job(candidate: Candidate) -> str | None:
    about = candidate.github.get_object(f"repos/{candidate.repository}")
    candidate.default_branch = about["default_branch"]
    path = f"repos/{candidate.repository}/actions/workflows"
    workflows = all_pages(candidate.github, path, {}, "workflows")
    names = {workflow["id"]: workflow["name"] for workflow in workflows}
    found: list[tuple[int, str, int]] = []
    for workflow in workflows:
        if failed_count_of_workflow(candidate, workflow["id"]) > 0:
            found += matching_jobs(candidate, workflow)
    if not found:
        return "no Linux CPython 3.12 job with a test step"
    _, candidate.job_name, candidate.workflow_id = min(found)
    candidate.measured["job"] = candidate.job_name
    candidate.measured["workflow"] = names[candidate.workflow_id]
    return None


def time_the_job(candidate: Candidate) -> str | None:
    parameters: dict[str, str | int] = {
        "event": "pull_request",
        "status": "success",
        "per_page": MOST_SUCCESSFUL_RUNS_LOOKED_AT,
    }
    response = candidate.github.get_object(runs_path(candidate), parameters)
    seconds: list[float] = []
    for run in response["workflow_runs"]:
        job = job_in_run(candidate, run["id"])
        if job is not None and job["conclusion"] == "success":
            seconds.append(duration_in_seconds(job))
        if len(seconds) == SUCCESSFUL_RUNS:
            break
    if not seconds:
        return "no successful pull request run of the job"
    median = statistics.median(seconds)
    candidate.measured["median_minutes"] = round(median / 60, 2)
    candidate.measured["successful_runs_timed"] = len(seconds)
    if median > MOST_SECONDS:
        return "median duration above 5 minutes"
    return None


def job_ran(job: dict[str, Any] | None) -> bool:
    return job is not None and job["conclusion"] in ("success", "failure")


def count_base_failures(
    candidate: Candidate, runs: list[dict[str, Any]]
) -> tuple[int, int]:
    """The base branch's runs in which the job failed, and in which it ran.

    The failed runs come first. A successful run can only add to the runs in
    which the job ran, so once fewer than 10% failed, the rest is not read."""
    failed = 0
    ran = 0
    for run in [run for run in runs if run["conclusion"] == "failure"]:
        job = job_in_run(candidate, run["id"])
        if job_ran(job):
            ran += 1
        if job is not None and job["conclusion"] == "failure":
            failed += 1
    for run in [run for run in runs if run["conclusion"] == "success"]:
        if failed * BASE_FACTOR < ran:
            break
        if job_ran(job_in_run(candidate, run["id"])):
            ran += 1
    return failed, ran


def check_the_base_branch(candidate: Candidate) -> str | None:
    parameters: dict[str, str | int] = {
        "event": "push",
        "branch": candidate.default_branch,
        "status": "completed",
        "per_page": PUSH_RUNS,
    }
    runs = candidate.github.get_object(runs_path(candidate), parameters)
    listed = runs["workflow_runs"]
    candidate.measured["base_push_runs"] = len(listed)
    if not listed:
        return "no push run of the job's workflow on the default branch"
    failed, ran = count_base_failures(candidate, listed)
    candidate.measured["base_failed"] = failed
    candidate.measured["base_ran_at_least"] = ran
    if ran == 0:
        return "the job ran in no push run of the default branch"
    if failed * BASE_FACTOR >= ran:
        return "the job failed in 10% or more of the base branch's push runs"
    return None


def list_failed_runs(candidate: Candidate) -> str | None:
    parameters: dict[str, str | int] = {"event": "pull_request", "status": "failure"}
    end = datetime.now(UTC) + timedelta(days=1)
    runs = list_runs(candidate.github, runs_path(candidate), parameters, EARLIEST, end)
    unique = {run["id"]: run for run in runs}
    candidate.failed_runs = list(unique.values())
    keys = {bound_key(run, candidate.repository) for run in candidate.failed_runs}
    candidate.measured["failed_runs_of_the_workflow"] = len(candidate.failed_runs)
    candidate.measured["pull_requests_at_most"] = len(keys)
    if len(keys) < MIN_RED:
        return "fewer than 20 pull requests with a failed run of the job's workflow"
    return None


def remember(candidate: Candidate, pull_request: dict[str, Any]) -> None:
    user = pull_request["user"] or {"login": "ghost", "type": "User"}
    entry = {
        "number": pull_request["number"],
        "author": user["login"],
        "bot": user["type"] == "Bot",
        "created_at": moment_of(pull_request["created_at"]),
        "closed_at": closed_at_of(pull_request),
    }
    candidate.pull_requests[pull_request["number"]] = entry
    branch = pull_request["head"]["ref"]
    head_user = pull_request["head"]["user"]
    if head_user is not None:
        key = (head_user["login"], branch)
        candidate.heads.setdefault(key, []).append(entry)
    if pull_request["head"]["repo"] is None:
        candidate.orphans.setdefault(branch, []).append(entry)


def closed_at_of(pull_request: dict[str, Any]) -> datetime | None:
    if pull_request["closed_at"] is None:
        return None
    return moment_of(pull_request["closed_at"])


def load_pull_requests(candidate: Candidate) -> None:
    """Every pull request updated since the earliest failed run, newest first."""
    earliest = min(moment_of(run["created_at"]) for run in candidate.failed_runs)
    path = f"repos/{candidate.repository}/pulls"
    page = 1
    while True:
        parameters: dict[str, str | int] = {
            "state": "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": PAGE_SIZE,
            "page": page,
        }
        items = candidate.github.get_list(path, parameters)
        for pull_request in items:
            remember(candidate, pull_request)
        if len(items) < PAGE_SIZE:
            return
        if moment_of(items[-1]["updated_at"]) < earliest:
            return
        page += 1


def was_open(pull_request: dict[str, Any], moment: datetime) -> bool:
    if pull_request["created_at"] > moment:
        return False
    return pull_request["closed_at"] is None or moment <= pull_request["closed_at"]


def number_of(candidate: Candidate, run: dict[str, Any]) -> int | None:
    given = numbers_given(run, candidate.repository)
    if given:
        return given[0]
    owner = head_owner(run)
    if owner is None:
        # A run whose fork was deleted has no owner: its pull request is one,
        # from a deleted fork too, whose head has the run's branch.
        heads = candidate.orphans.get(run["head_branch"], [])
    else:
        heads = candidate.heads.get((owner, run["head_branch"]), [])
    created = moment_of(run["created_at"])
    open_then = [entry for entry in heads if was_open(entry, created)]
    if not open_then:
        return None
    latest = max(open_then, key=lambda entry: entry["created_at"])
    return latest["number"]


def group_by_pull_request(
    candidate: Candidate,
) -> dict[str, tuple[int | None, list[dict[str, Any]]]]:
    groups: dict[str, tuple[int | None, list[dict[str, Any]]]] = {}
    for run in candidate.failed_runs:
        number = number_of(candidate, run)
        if number is None:
            key = f"?{head_owner(run)}:{run['head_branch']}"
        else:
            key = f"#{number}"
        groups.setdefault(key, (number, []))[1].append(run)
    return groups


def latest_failed_job(
    candidate: Candidate, runs: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    newest_first = sorted(runs, key=lambda run: run["created_at"], reverse=True)
    for run in newest_first:
        job = job_in_run(candidate, run["id"])
        if job is not None and job["conclusion"] == "failure":
            return run, job
    return None


def outcome_of(job: dict[str, Any]) -> tuple[str, str]:
    steps = job.get("steps") or []
    if not steps:
        return "failed, steps no longer given", ""
    failed = [step["name"] for step in steps if step["conclusion"] == "failure"]
    if any(is_test_step(name) for name in failed):
        return "failed in a test step", "; ".join(failed)
    return "failed in another step", "; ".join(failed)


def author_of(
    candidate: Candidate, number: int | None, run: dict[str, Any]
) -> tuple[str, bool]:
    if number is not None and number in candidate.pull_requests:
        entry = candidate.pull_requests[number]
        return entry["author"], entry["bot"]
    actor = run.get("actor") or {"login": f"unknown, run {run['id']}", "type": "User"}
    return actor["login"], actor["type"] == "Bot"


def red_row(
    candidate: Candidate, number: int | None, run: dict[str, Any], job: dict[str, Any]
) -> dict[str, Any]:
    outcome, failed_steps = outcome_of(job)
    author, bot = author_of(candidate, number, run)
    return {
        "pull_request": number,
        "run_id": run["id"],
        "run_started": run["run_started_at"],
        "created_at": run["created_at"],
        "head": run["head_sha"],
        "job": outcome,
        "failed_steps": failed_steps,
        "author": author,
        "bot": bot,
    }


def find_red_pull_requests(candidate: Candidate) -> str | None:
    load_pull_requests(candidate)
    groups = list(group_by_pull_request(candidate).values())
    left = len(groups)
    for number, runs in groups:
        left -= 1
        found = latest_failed_job(candidate, runs)
        if found is not None:
            candidate.red.append(red_row(candidate, number, *found))
        if len(candidate.red) + left < MIN_RED:
            candidate.measured["red_pull_requests_at_most"] = len(candidate.red) + left
            return "fewer than 20 red pull requests"
    candidate.measured["red_pull_requests"] = len(candidate.red)
    return None


def check_the_authors(candidate: Candidate) -> str | None:
    counts = Counter(row["author"] for row in candidate.red)
    top = max(counts.values())
    candidate.measured["authors"] = len(counts)
    candidate.measured["most_by_one_author"] = top
    candidate.measured["bot_authored"] = sum(1 for row in candidate.red if row["bot"])
    if len(counts) < MIN_AUTHORS:
        return "fewer than 5 authors"
    if top * AUTHOR_SHARE_DENOMINATOR > len(candidate.red):
        return "one author has more than a third of the red pull requests"
    return None


def check_the_steps(candidate: Candidate) -> str | None:
    outcomes = Counter(row["job"] for row in candidate.red)
    in_tests = outcomes["failed in a test step"]
    known = in_tests + outcomes["failed in another step"]
    candidate.measured["red_with_steps"] = known
    candidate.measured["red_in_a_test_step"] = in_tests
    if known == 0:
        return "no red pull request whose failed job came with its steps"
    if in_tests * TEST_STEP_DENOMINATOR < known * TEST_STEP_NUMERATOR:
        return "fewer than 80% of the red pull requests failed in a test step"
    return None


STAGES = (
    count_failed_runs,
    find_job,
    list_failed_runs,
    time_the_job,
    check_the_base_branch,
    find_red_pull_requests,
    check_the_authors,
    check_the_steps,
)


def anonymous_rows(candidate: Candidate) -> list[dict[str, Any]]:
    """The red rows, oldest first, with each author given as a number."""
    rows = sorted(candidate.red, key=lambda row: (row["run_started"], row["run_id"]))
    numbers: dict[str, int] = {}
    anonymous: list[dict[str, Any]] = []
    for row in rows:
        number = numbers.setdefault(row["author"], len(numbers) + 1)
        anonymous.append({**row, "author": f"author {number}"})
    return anonymous


def evaluate(github: GitHub, repository: str) -> dict[str, Any]:
    candidate = Candidate(github=github, repository=repository)
    stopped_at = None
    for stage in STAGES:
        log(f"  {repository}: {stage.__name__}, {github.calls} calls")
        stopped_at = stage(candidate)
        if stopped_at is not None:
            break
    return {
        "repository": repository,
        "passed": stopped_at is None,
        "stopped_at": stopped_at,
        "measured": candidate.measured,
        "workflow_id": candidate.workflow_id,
        "red": anonymous_rows(candidate),
        "all_runs": all_runs_if_passed(candidate, stopped_at),
    }


def all_runs_if_passed(
    candidate: Candidate, stopped_at: str | None
) -> list[dict[str, Any]]:
    """Every pull request run of the job's workflow, for option C."""
    if stopped_at is not None:
        return []
    end = datetime.now(UTC) + timedelta(days=1)
    parameters: dict[str, str | int] = {"event": "pull_request"}
    runs = list_runs(candidate.github, runs_path(candidate), parameters, EARLIEST, end)
    unique = {run["id"]: run for run in runs}
    return [
        {
            "pull_request": number_of(candidate, run),
            "run_id": run["id"],
            "run_started": run["run_started_at"],
            "created_at": run["created_at"],
            "head": run["head_sha"],
            "conclusion": run["conclusion"],
        }
        for run in sorted(unique.values(), key=lambda run: run["created_at"])
    ]


def cache_path(cache: Path, repository: str) -> Path:
    return cache / (repository.replace("/", "__") + ".json")


def result_of(github: GitHub, cache: Path, repository: str) -> dict[str, Any] | None:
    path = cache_path(cache, repository)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        result = evaluate(github, repository)
    except (GitHubError, KeyError, TypeError, ValueError) as error:
        # Not cached, so that the next run tries this candidate again.
        log(f"{repository}: stopped by {type(error).__name__}: {error}")
        return None
    path.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    return result


def write_red_csv(out: Path, result: dict[str, Any]) -> None:
    project = result["repository"].split("/")[1]
    path = out / f"{project}-red-runs.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for row in result["red"]:
            number = "" if row["pull_request"] is None else row["pull_request"]
            writer.writerow(
                (
                    project,
                    number,
                    row["run_id"],
                    row["run_started"],
                    row["head"],
                    row["job"],
                    row["failed_steps"],
                )
            )


def write_all_runs(out: Path, result: dict[str, Any]) -> None:
    project = result["repository"].split("/")[1]
    path = out / f"{project}-pull-request-runs.json"
    text = json.dumps(result["all_runs"], indent=1) + "\n"
    path.write_text(text, encoding="utf-8")


def summary_of(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "repository": result["repository"],
        "passed": result["passed"],
        "stopped_at": result["stopped_at"],
        "measured": result["measured"],
    }


def passing_candidates(out: Path) -> list[str]:
    listed = json.loads((out / "candidates.json").read_text("utf-8"))
    return [entry["repository"] for entry in listed["candidates"] if entry["passes"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    arguments = parser.parse_args()
    arguments.cache.mkdir(parents=True, exist_ok=True)
    repositories = arguments.only or passing_candidates(arguments.out)
    repositories = repositories[arguments.shard :: arguments.shards]
    github = GitHub()
    summaries: list[dict[str, Any]] = []
    for index, repository in enumerate(repositories, start=1):
        log(f"{index}/{len(repositories)} {repository}, {github.calls} calls so far")
        result = result_of(github, arguments.cache, repository)
        if result is None:
            continue
        summaries.append(summary_of(result))
        if result["passed"]:
            write_red_csv(arguments.out, result)
            write_all_runs(arguments.out, result)
    if not arguments.only and arguments.shards == 1:
        text = json.dumps(summaries, indent=1) + "\n"
        (arguments.out / "funnel.json").write_text(text, encoding="utf-8")
    log(
        f"done: {sum(1 for s in summaries if s['passed'])} passed, {github.calls} calls"
    )


if __name__ == "__main__":
    main()
