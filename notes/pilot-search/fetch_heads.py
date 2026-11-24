# ruff: noqa: INP001
"""Clone a candidate that passed D-024's criteria, and keep each red pull
request's head by a ref of its own, `refs/window/<run id>`, as the window's
clones of urllib3 and poetry do.

A head comes by its commit id or, if GitHub gives it no longer that way, with
its pull request's `pull/<n>/head`. Run from the repository's root:
    .venv/bin/python notes/pilot-search/fetch_heads.py --repository <owner/name>
    --csv notes/pilot-search/<project>-red-runs.csv --clone <directory>
"""

import argparse
import csv
import subprocess
import sys
from collections import Counter
from pathlib import Path

SECONDS_PER_COMMAND = 1800


def git(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=SECONDS_PER_COMMAND,
        check=False,
    )


def has_commit(clone: Path, commit: str) -> bool:
    found = git(["-C", str(clone), "cat-file", "-e", f"{commit}^{{commit}}"])
    return found.returncode == 0


def keep_head(clone: Path, row: dict[str, str]) -> str:
    commit = row["head"]
    if not has_commit(clone, commit):
        git(["-C", str(clone), "fetch", "--quiet", "origin", commit])
    if not has_commit(clone, commit) and row["pull_request"]:
        pull = f"pull/{row['pull_request']}/head"
        git(["-C", str(clone), "fetch", "--quiet", "origin", pull])
    if not has_commit(clone, commit):
        return "not found"
    ref = f"refs/window/{row['run_id']}"
    git(["-C", str(clone), "update-ref", ref, commit])
    return "kept"


def clone_once(repository: str, clone: Path) -> None:
    if clone.exists():
        return
    url = f"https://github.com/{repository}.git"
    cloned = git(["clone", "--quiet", url, str(clone)])
    if cloned.returncode != 0:
        message = f"git clone {url} failed: {cloned.stderr.strip()[:300]}"
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--clone", type=Path, required=True)
    arguments = parser.parse_args()
    clone_once(arguments.repository, arguments.clone)
    with arguments.csv.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    outcomes = Counter(keep_head(arguments.clone, row) for row in rows)
    missing = [
        row["run_id"] for row in rows if not has_commit(arguments.clone, row["head"])
    ]
    sys.stdout.write(f"{arguments.repository}: {dict(outcomes)}\n")
    if missing:
        sys.stdout.write(f"runs whose head is not in the clone: {missing}\n")


if __name__ == "__main__":
    main()
