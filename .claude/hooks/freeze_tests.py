"""PreToolUse on Edit and Write: the implement phase freezes the oracle, and the
tests phase freezes what configures the checks.

The agent can also write through Bash; the Stop hook catches that with git.
"""

from pathlib import Path

from phase import (
    can_read_phase,
    current_repo,
    is_frozen,
    is_frozen_in_tests,
    is_on_phase_file,
    object_field,
    read_phase,
    run_hook,
    text_field,
)

BLOCKED = (
    "{path} is frozen in the implement phase (.claude/phase), with tests/, "
    "scripts/, the Makefile and every file that configures the tools make runs: "
    "see FROZEN_AT_ROOT and FROZEN_ANYWHERE in .claude/hooks/phase.py. If a test "
    "looks wrong, write the test name, the SPEC example and your reason to "
    ".claude/blocked and stop."
)
BLOCKED_IN_TESTS = (
    "{path} is frozen in the tests phase (.claude/phase): the tests phase writes "
    "tests/ and the import-linter contract in pyproject.toml, never scripts/, the "
    "Makefile or a file that configures the tools make runs, in tests/ or anywhere "
    "else: see TESTS_PHASE_PATHSPECS in .claude/hooks/phase.py. If the phase needs "
    "one, write the reason to .claude/blocked and stop."
)


def check(data: dict[str, object]) -> str | None:
    repo = current_repo()
    if not can_read_phase(repo) and is_on_phase_file(data, repo):
        # A broken phase file: the agent writes it again (D-018).
        return None
    phase = read_phase(repo).name
    if phase not in ("tests", "implement"):
        return None
    file_path = text_field(object_field(data, "tool_input"), "file_path")
    if file_path is None:
        return "The Edit or Write call has no file_path, so it is blocked."
    path = Path(file_path).resolve()
    if phase == "implement" and is_frozen(path, repo):
        return BLOCKED.format(path=path)
    if phase == "tests" and is_frozen_in_tests(path, repo):
        return BLOCKED_IN_TESTS.format(path=path)
    return None


if __name__ == "__main__":
    run_hook(check)
