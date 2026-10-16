"""What the hooks share: where things are, the phase, and how to answer.

The user sets .claude/phase by hand, never the agent:
- no file, or an empty one: no phase;
- "tests": write tests from docs/SPEC.md without reading src/;
- "implement <commit>": make the tests of <commit> pass without changing what
  that commit froze (FROZEN_PATHSPECS).
"""

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

# The tests and everything that decides how the checks run. make runs each tool
# from the root, where it reads these files. More is frozen than the tools read
# today, on purpose: one file too few loosens the checks, one too many costs
# nothing.
FROZEN_DIRECTORIES = ("tests", "scripts")
FROZEN_AT_ROOT = (
    "Makefile",
    "pytest.toml",
    ".pytest.toml",
    "pytest.ini",
    ".pytest.ini",
    "tox.ini",
    "setup.cfg",
    ".coveragerc",
    ".coveragerc.toml",
    "pyrightconfig.json",
    ".importlinter",
    ".pre-commit-config.yaml",
    ".gitleaks.toml",
    ".gitleaksignore",
)
# Read in every directory: conftest.py by pytest, the others by ruff and git.
FROZEN_ANYWHERE = (
    "conftest.py",
    "pyproject.toml",
    "ruff.toml",
    ".ruff.toml",
    ".gitattributes",
    ".gitignore",
)
# The same, as git pathspecs.
FROZEN_PATHSPECS = (
    *FROZEN_DIRECTORIES,
    *FROZEN_AT_ROOT,
    *(f":(glob)**/{name}" for name in FROZEN_ANYWHERE),
)


@dataclass(frozen=True)
class Repo:
    root: Path

    @property
    def src(self) -> Path:
        return self.root / "src"

    @property
    def phase_file(self) -> Path:
        return self.root / ".claude" / "phase"

    @property
    def blocked_file(self) -> Path:
        return self.root / ".claude" / "blocked"

    @property
    def tests_log(self) -> Path:
        return self.root / ".claude" / "tests-phase.log"

    @property
    def stop_state(self) -> Path:
        return self.root / ".claude" / "stop-state.json"


@dataclass(frozen=True)
class Phase:
    name: str | None  # None, "tests" or "implement"
    commit: str | None  # the tests commit, only for "implement"


class PhaseError(Exception):
    def __init__(self, text: str) -> None:
        super().__init__(
            f".claude/phase says {text.strip()!r}, which is neither 'tests' nor "
            "'implement <commit>'. The user has to fix it."
        )


def current_repo() -> Repo:
    # Claude Code sets it for every hook: the project root where the session began.
    return Repo(Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve())


def read_phase(repo: Repo) -> Phase:
    try:
        text = repo.phase_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return Phase(None, None)
    match text.split():
        # Empty is no phase: the Bash sandbox can leave a 0-byte file at this path.
        case []:
            return Phase(None, None)
        case ["tests"]:
            return Phase("tests", None)
        case ["implement"]:
            return Phase("implement", None)
        case ["implement", commit]:
            return Phase("implement", commit)
        case _:
            raise PhaseError(text)


def is_inside(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


def is_frozen(path: Path, repo: Repo) -> bool:
    if not is_inside(path, repo.root):
        return False
    in_a_frozen_directory = any(
        is_inside(path, repo.root / name) for name in FROZEN_DIRECTORIES
    )
    at_the_root = path.parent == repo.root and path.name in FROZEN_AT_ROOT
    return in_a_frozen_directory or at_the_root or path.name in FROZEN_ANYWHERE


def read_input() -> dict[str, object]:
    data = json.load(sys.stdin)
    if not isinstance(data, dict):
        message = "the hook input is not a JSON object"
        raise TypeError(message)
    return cast("dict[str, object]", data)


def text_field(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    return value if isinstance(value, str) else None


def object_field(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def run_hook(check: Callable[[dict[str, object]], str | None]) -> None:
    """Run a check; a message goes to Claude on stderr with exit code 2.

    On PreToolUse, exit 2 blocks the call. On PostToolUse the call has already
    run, and exit 2 only shows Claude the message.
    """
    try:
        message = check(read_input())
    except PhaseError as error:
        message = f"{error} Until then, this hook blocks every call it covers."
    except Exception as error:  # noqa: BLE001
        # A hook that crashes exits with 1, which lets the call through.
        message = f"The hook failed, so it blocks the call: {error!r}"
    if message is not None:
        sys.stderr.write(message + "\n")
        raise SystemExit(2)
