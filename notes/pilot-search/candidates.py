# ruff: noqa: INP001
"""D-024's candidates and the files its criteria look for.

The candidates are the 28 projects of the search of 2026-11-16 other than urllib3
and poetry, and every repository that GitHub's search gives for D-024's query.
For each one that has a lock file at the root of its default branch, or that
comes from 2026-11-16, it reads whether pytest is named there too.

Run from the repository's root:
    .venv/bin/python notes/pilot-search/candidates.py --out notes/pilot-search
"""

import argparse
import json
from pathlib import Path
from typing import Any

from github import GitHub, GitHubError, log

SEARCHED_ON = "2026-11-21"
SEARCH = "language:Python pushed:>=2026-10-21 archived:false"
FIRST_STAR_RANGES: list[tuple[int, int | None]] = [
    (1000, 1999),
    (2000, 4999),
    (5000, 9999),
    (10000, 49999),
    (50000, None),
]
MOST_RESULTS_PER_SEARCH = 1000
SEEN = {"urllib3/urllib3", "python-poetry/poetry"}
ACCOUNT = "sergiparpal"
FROM_2026_11_16 = (
    "pypa/packaging",
    "scrapy/scrapy",
    "psf/black",
    "sphinx-doc/sphinx",
    "pypa/virtualenv",
    "pylint-dev/pylint",
    "pytest-dev/pytest",
    "tox-dev/tox",
    "pypa/pip",
    "PyCQA/isort",
    "encode/starlette",
    "pallets/flask",
    "pallets/click",
    "pypa/hatch",
    "fastapi/typer",
    "celery/celery",
    "pallets/jinja",
    "jazzband/pip-tools",
    "Textualize/textual",
    "marshmallow-code/marshmallow",
    "pallets/werkzeug",
    "python-attrs/attrs",
    "pytest-dev/pluggy",
    "Textualize/rich",
    "pre-commit/pre-commit",
    "encode/httpx",
    "psf/requests",
    "getsentry/sentry-python",
)

COUNT_QUERY = """
query($text: String!) {
  search(type: REPOSITORY, query: $text, first: 1) { repositoryCount }
}
"""

SEARCH_QUERY = """
query($text: String!, $cursor: String) {
  search(type: REPOSITORY, query: $text, first: 100, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Repository {
        nameWithOwner
        stargazerCount
        uv: object(expression: "HEAD:uv.lock") { id }
        poetry: object(expression: "HEAD:poetry.lock") { id }
      }
    }
  }
}
"""

FILES_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    stargazerCount
    isArchived
    uv: object(expression: "HEAD:uv.lock") { id }
    poetry: object(expression: "HEAD:poetry.lock") { id }
    pyproject: object(expression: "HEAD:pyproject.toml") { ... on Blob { text } }
    pytestIni: object(expression: "HEAD:pytest.ini") { id }
    rootConftest: object(expression: "HEAD:conftest.py") { id }
    testsConftest: object(expression: "HEAD:tests/conftest.py") { id }
  }
}
"""


def star_query(low: int, high: int | None) -> str:
    if high is None:
        return f"{SEARCH} stars:>={low}"
    return f"{SEARCH} stars:{low}..{high}"


def count_repositories(github: GitHub, query: str) -> int:
    return github.graphql(COUNT_QUERY, {"text": query})["search"]["repositoryCount"]


def split_range(low: int, high: int | None) -> list[tuple[int, int | None]]:
    if high is None:
        return [(low, low * 2 - 1), (low * 2, None)]
    middle = (low + high) // 2
    return [(low, middle), (middle + 1, high)]


def star_ranges(github: GitHub) -> list[tuple[int, int | None]]:
    """Ranges of stars small enough that the search gives every repository."""
    ranges: list[tuple[int, int | None]] = []
    waiting = list(FIRST_STAR_RANGES)
    while waiting:
        low, high = waiting.pop(0)
        count = count_repositories(github, star_query(low, high))
        if count <= MOST_RESULTS_PER_SEARCH or low == high:
            ranges.append((low, high))
        else:
            waiting += split_range(low, high)
    return ranges


def search_all(github: GitHub, query: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    variables = {"text": query}
    while True:
        search = github.graphql(SEARCH_QUERY, variables)["search"]
        nodes.extend(search["nodes"])
        if not search["pageInfo"]["hasNextPage"]:
            return nodes
        variables = {"text": query, "cursor": search["pageInfo"]["endCursor"]}


def files_of(github: GitHub, repository: str) -> dict[str, Any] | None:
    owner, name = repository.split("/")
    try:
        data = github.graphql(FILES_QUERY, {"owner": owner, "name": name})
    except GitHubError as error:
        log(f"{repository}: {error}")
        return None
    return data["repository"]


def pytest_is_named(files: dict[str, Any]) -> bool:
    pyproject = files["pyproject"]
    if pyproject is not None and "pytest" in pyproject["text"].lower():
        return True
    others = (files["pytestIni"], files["rootConftest"], files["testsConftest"])
    return any(found is not None for found in others)


def is_excluded(repository: str) -> bool:
    owner = repository.split("/", maxsplit=1)[0]
    return repository.lower() in SEEN or owner.lower() == ACCOUNT


def entry_from_search(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "repository": node["nameWithOwner"],
        "found_by": ["search of 2026-11-21"],
        "stars": node["stargazerCount"],
        "uv_lock": node["uv"] is not None,
        "poetry_lock": node["poetry"] is not None,
        "pytest_named": None,
        "passes": False,
    }


def add_files(entry: dict[str, Any], files: dict[str, Any]) -> None:
    entry["repository"] = files["nameWithOwner"]
    entry["stars"] = files["stargazerCount"]
    entry["archived"] = files["isArchived"]
    entry["uv_lock"] = files["uv"] is not None
    entry["poetry_lock"] = files["poetry"] is not None
    entry["pytest_named"] = pytest_is_named(files)
    has_lock = entry["uv_lock"] or entry["poetry_lock"]
    entry["passes"] = has_lock and entry["pytest_named"] and not files["isArchived"]


def searched_entries(
    github: GitHub, ranges: list[tuple[int, int | None]]
) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for low, high in ranges:
        nodes = search_all(github, star_query(low, high))
        log(f"stars {low} to {high}: {len(nodes)} repositories")
        for node in nodes:
            if node:
                entries[node["nameWithOwner"].lower()] = entry_from_search(node)
    return entries


def add_earlier_candidates(entries: dict[str, dict[str, Any]]) -> None:
    for repository in FROM_2026_11_16:
        key = repository.lower()
        if key in entries:
            entries[key]["found_by"].append("search of 2026-11-16")
            continue
        entries[key] = {
            "repository": repository,
            "found_by": ["search of 2026-11-16"],
            "stars": None,
            "uv_lock": None,
            "poetry_lock": None,
            "pytest_named": None,
            "passes": False,
        }


def merge_renamed(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry for each repository. A project of 2026-11-16 that was renamed,
    as encode/starlette is now Kludex/starlette, takes its new name from the
    files, and the search may have found it under that name too."""
    merged: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = entry["repository"].lower()
        if key not in merged:
            merged[key] = entry
            continue
        kept = merged[key]
        found_by = sorted(set(kept["found_by"]) | set(entry["found_by"]))
        if kept["pytest_named"] is None and entry["pytest_named"] is not None:
            kept = entry
        merged[key] = {**kept, "found_by": found_by}
    return list(merged.values())


def needs_files(entry: dict[str, Any]) -> bool:
    from_before = "search of 2026-11-16" in entry["found_by"]
    return from_before or bool(entry["uv_lock"]) or bool(entry["poetry_lock"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    github = GitHub()
    ranges = star_ranges(github)
    entries = searched_entries(github, ranges)
    found_by_search = len(entries)
    add_earlier_candidates(entries)
    excluded = sorted(
        e["repository"] for e in entries.values() if is_excluded(e["repository"])
    )
    for key in [k for k, e in entries.items() if is_excluded(e["repository"])]:
        del entries[key]
    for entry in entries.values():
        if needs_files(entry):
            files = files_of(github, entry["repository"])
            if files is not None:
                add_files(entry, files)
    merged = merge_renamed(list(entries.values()))
    candidates = sorted(merged, key=lambda e: e["repository"].lower())
    summary = {
        "searched_on": SEARCHED_ON,
        "search": SEARCH,
        "star_ranges": ranges,
        "found_by_search": found_by_search,
        "excluded": excluded,
        "with_a_lock_file": sum(
            1 for e in candidates if e["uv_lock"] or e["poetry_lock"]
        ),
        "passing": sum(1 for e in candidates if e["passes"]),
        "calls": github.calls,
        "candidates": candidates,
    }
    path = arguments.out / "candidates.json"
    path.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    log(f"{summary['passing']} candidates pass the files; {github.calls} calls")


if __name__ == "__main__":
    main()
