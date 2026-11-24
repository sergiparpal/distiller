# ruff: noqa: INP001
"""Read-only calls to GitHub's API, through the gh command line.

Every call is a GET or a GraphQL query: nothing here writes to GitHub. gh takes
its token from the environment and never prints it.
"""

import json
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any

ATTEMPTS = 5
SECONDS_BETWEEN_ATTEMPTS = 15
SECONDS_PER_CALL = 300
PAGE_SIZE = 100
# GitHub gives at most 1,000 runs for a listing filtered by date or by event.
MOST_RUNS_PER_LISTING = 1000
SHORTEST_SPLIT = timedelta(minutes=1)
ONE_SECOND = timedelta(seconds=1)
CHECK_BUDGET_EVERY = 25
CALLS_KEPT_IN_RESERVE = 200
SIGNS_OF_A_PASSING_ERROR = (
    "HTTP 500",
    "HTTP 502",
    "HTTP 503",
    "HTTP 504",
    "rate limit",
    "timed out",
    "timeout",
    "connection reset",
    "Something went wrong",
    "EOF",
    "stream error",
    "error connecting",
)


class GitHubError(Exception):
    """A gh call that failed for good."""

    def __init__(self, arguments: list[str], stderr: str) -> None:
        self.not_found = "HTTP 404" in stderr
        message = f"gh {' '.join(arguments[:4])} failed: {stderr.strip()[:300]}"
        super().__init__(message)


class GitHub:
    """Runs gh, counts its calls and waits when the rate limit runs low."""

    def __init__(self) -> None:
        self.calls = 0

    def get_object(
        self, path: str, parameters: dict[str, str | int] | None = None
    ) -> dict[str, Any]:
        return json.loads(self.run(get_arguments(path, parameters)))

    def get_list(
        self, path: str, parameters: dict[str, str | int] | None = None
    ) -> list[dict[str, Any]]:
        return json.loads(self.run(get_arguments(path, parameters)))

    def graphql(
        self, query: str, variables: dict[str, str] | None = None
    ) -> dict[str, Any]:
        arguments = ["api", "graphql", "-f", f"query={query}"]
        for name, value in (variables or {}).items():
            arguments += ["-f", f"{name}={value}"]
        return json.loads(self.run(arguments))["data"]

    def run(self, arguments: list[str]) -> str:
        self.calls += 1
        if self.calls % CHECK_BUDGET_EVERY == 0:
            wait_if_budget_is_low()
        for attempt in range(1, ATTEMPTS):
            completed = run_gh_once(arguments)
            if completed.returncode == 0:
                return completed.stdout
            if not is_a_passing_error(completed.stderr):
                raise GitHubError(arguments, completed.stderr)
            pause_before_trying_again(completed.stderr, attempt)
        completed = run_gh_once(arguments)
        if completed.returncode == 0:
            return completed.stdout
        raise GitHubError(arguments, completed.stderr)


def get_arguments(path: str, parameters: dict[str, str | int] | None) -> list[str]:
    arguments = ["api", "-X", "GET", path]
    for name, value in (parameters or {}).items():
        arguments += ["-f", f"{name}={value}"]
    return arguments


def run_gh_once(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603
            ["gh", *arguments],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=SECONDS_PER_CALL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # A call that hangs is tried again, as a server error is.
        return subprocess.CompletedProcess(arguments, 1, "", "gh timed out")


def is_a_passing_error(stderr: str) -> bool:
    return any(sign in stderr for sign in SIGNS_OF_A_PASSING_ERROR)


def pause_before_trying_again(stderr: str, attempt: int) -> None:
    if "rate limit" in stderr:
        wait_if_budget_is_low()
    time.sleep(SECONDS_BETWEEN_ATTEMPTS * attempt)


def wait_if_budget_is_low() -> None:
    completed = run_gh_once(["api", "rate_limit"])
    if completed.returncode != 0:
        return
    resources = json.loads(completed.stdout)["resources"]
    for name in ("core", "graphql"):
        if resources[name]["remaining"] < CALLS_KEPT_IN_RESERVE:
            sleep_until(resources[name]["reset"], name)


def sleep_until(reset: int, name: str) -> None:
    seconds = reset - time.time() + 5
    if seconds > 0:
        log(f"the {name} rate limit is low: waiting {round(seconds)} s")
        time.sleep(seconds)


def log(message: str) -> None:
    sys.stderr.write(f"{datetime.now(UTC):%H:%M:%S} {message}\n")
    sys.stderr.flush()


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def moment_of(text: str) -> datetime:
    return datetime.fromisoformat(text)


def all_pages(
    github: GitHub,
    path: str,
    parameters: dict[str, str | int],
    key: str,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Every item of a listing whose items are under `key`, page by page."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        response = github.get_object(
            path, {**parameters, "per_page": page_size, "page": page}
        )
        page_items = response[key]
        items.extend(page_items)
        if len(page_items) < page_size:
            return items
        page += 1


def list_runs(
    github: GitHub,
    path: str,
    parameters: dict[str, str | int],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Every run created from start to end, splitting the span in two while
    GitHub would give only its first 1,000."""
    span = {**parameters, "created": f"{iso(start)}..{iso(end)}"}
    count = github.get_object(path, {**span, "per_page": 1})["total_count"]
    if count == 0:
        return []
    if count >= MOST_RUNS_PER_LISTING and end - start > SHORTEST_SPLIT:
        middle = start + (end - start) / 2
        earlier = list_runs(github, path, parameters, start, middle)
        later = list_runs(github, path, parameters, middle + ONE_SECOND, end)
        return earlier + later
    return all_pages(github, path, span, "workflow_runs")
