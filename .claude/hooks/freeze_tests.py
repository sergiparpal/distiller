"""PreToolUse on Edit and Write: the implement phase freezes the oracle.

The agent can also write through Bash; the Stop hook catches that with git.
"""

from pathlib import Path

from phase import (
    current_repo,
    is_frozen,
    object_field,
    read_phase,
    run_hook,
    text_field,
)

BLOCKED = (
    "{path} is frozen in the implement phase (.claude/phase): tests/, the Makefile, "
    "pyproject.toml and every conftest.py. If a test looks wrong, write the test "
    "name, the SPEC example and your reason to .claude/blocked and stop."
)


def check(data: dict[str, object]) -> str | None:
    repo = current_repo()
    if read_phase(repo).name != "implement":
        return None
    file_path = text_field(object_field(data, "tool_input"), "file_path")
    if file_path is None:
        return "The Edit or Write call has no file_path, so it is blocked."
    path = Path(file_path).resolve()
    if is_frozen(path, repo):
        return BLOCKED.format(path=path)
    return None


if __name__ == "__main__":
    run_hook(check)
