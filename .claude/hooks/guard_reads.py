"""PreToolUse on reads: in the tests phase, src/ stays unread and reads are logged.

Read, Grep and Glob are checked by path. Bash runs only the commands in
ALLOWED_COMMANDS, compared with the whole command. WebFetch and MCP tools are
blocked. Every call that goes through is appended to .claude/tests-phase.log,
which the Stop hook checks in every phase.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from phase import (
    Repo,
    current_repo,
    is_inside,
    object_field,
    read_phase,
    run_hook,
    text_field,
)

ALLOWED_COMMANDS = (
    "make format",
    "make lint",
    "make types",
    "make test-red",
    "git status",
    "git diff -- tests/",
)

WILDCARDS = frozenset("*?[{")

SRC_IS_CLOSED = (
    "In the tests phase (.claude/phase) src/ is not read: {what}. Search or read "
    "outside it, for example in tests/ or docs/."
)


def check(data: dict[str, object]) -> str | None:
    repo = current_repo()
    if read_phase(repo).name != "tests":
        return None
    tool = text_field(data, "tool_name") or ""
    tool_input = object_field(data, "tool_input")
    cwd = Path(text_field(data, "cwd") or repo.root)
    if tool == "Bash":
        return check_command(repo, data, tool_input)
    if tool == "Read":
        return check_read(repo, data, tool_input)
    if tool == "Grep":
        return check_grep(repo, data, cwd, tool_input)
    if tool == "Glob":
        return check_glob(repo, data, cwd, tool_input)
    return f"In the tests phase (.claude/phase) {tool} is blocked."


def check_command(
    repo: Repo, data: dict[str, object], tool_input: dict[str, object]
) -> str | None:
    command = text_field(tool_input, "command") or ""
    if command.strip() not in ALLOWED_COMMANDS:
        allowed = ", ".join(f"`{allowed}`" for allowed in ALLOWED_COMMANDS)
        return (
            f"In the tests phase (.claude/phase) Bash runs only {allowed}. "
            "Use Read, Grep and Glob to read and search."
        )
    append_to_log(repo, data, [], command)
    return None


def check_read(
    repo: Repo, data: dict[str, object], tool_input: dict[str, object]
) -> str | None:
    file_path = text_field(tool_input, "file_path")
    if file_path is None:
        return "The Read call has no file_path, so it is blocked."
    path = Path(file_path).resolve()
    if is_inside(path, repo.src):
        return SRC_IS_CLOSED.format(what=path)
    append_to_log(repo, data, [path], None)
    return None


def check_grep(
    repo: Repo, data: dict[str, object], cwd: Path, tool_input: dict[str, object]
) -> str | None:
    start = (cwd / (text_field(tool_input, "path") or ".")).resolve()
    return check_start(repo, data, start)


def check_start(repo: Repo, data: dict[str, object], start: Path) -> str | None:
    # A search reaches src/ when it starts inside it or in a directory above it.
    if is_inside(start, repo.src) or is_inside(repo.src, start):
        return SRC_IS_CLOSED.format(what=f"a search from {start} reaches src/")
    append_to_log(repo, data, [start], None)
    return None


def check_glob(
    repo: Repo, data: dict[str, object], cwd: Path, tool_input: dict[str, object]
) -> str | None:
    root = cwd / (text_field(tool_input, "path") or ".")
    pattern = root / (text_field(tool_input, "pattern") or "")
    # Glob's "*.md" also matches at any depth, so only where it starts counts.
    return check_start(repo, data, starting_directory(pattern))


def starting_directory(pattern: Path) -> Path:
    """The part of a glob pattern before its first wildcard."""
    parts = pattern.parts
    for index, part in enumerate(parts):
        if WILDCARDS & set(part):
            return Path(*parts[:index]).resolve()
    return pattern.resolve()


def append_to_log(
    repo: Repo, data: dict[str, object], paths: list[Path], command: str | None
) -> None:
    entry = {
        "time": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "session": text_field(data, "session_id"),
        "agent": text_field(data, "agent_id"),
        "tool": text_field(data, "tool_name"),
        "cwd": text_field(data, "cwd"),
        "paths": [str(path) for path in paths],
        "command": command,
    }
    with repo.tests_log.open("a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    run_hook(check)
