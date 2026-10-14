"""Contract tests of the PreToolUse and PostToolUse hooks, run as Claude Code runs
them: python3, the event as JSON on stdin, CLAUDE_PROJECT_DIR set."""

import json
import os
import subprocess
from pathlib import Path
from typing import cast

import pytest

HOOKS = Path(__file__).resolve().parent.parent
REAL_REPO = HOOKS.parent.parent


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for directory in ("src/pkg", "tests", "docs", ".claude"):
        (root / directory).mkdir(parents=True)
    (root / "src/pkg/core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests/test_core.py").write_text("VALUE = 2\n", encoding="utf-8")
    (root / "docs/SPEC.md").write_text("# SPEC\n", encoding="utf-8")
    return root


def set_phase(repo: Path, text: str) -> None:
    (repo / ".claude/phase").write_text(text, encoding="utf-8")


def tool_call(repo: Path, tool: str, **tool_input: object) -> dict[str, object]:
    return {
        "session_id": "session",
        "hook_event_name": "PreToolUse",
        "cwd": str(repo),
        "tool_name": tool,
        "tool_input": tool_input,
    }


def run_hook(
    script: str, repo: Path, payload: dict[str, object] | str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(HOOKS / script)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
        capture_output=True,
        text=True,
        check=False,
    )


def log_entries(repo: Path) -> list[dict[str, object]]:
    log = repo / ".claude/tests-phase.log"
    if not log.exists():
        return []
    lines = log.read_text(encoding="utf-8").splitlines()
    return [cast("dict[str, object]", json.loads(line)) for line in lines]


# freeze_tests.py: PreToolUse on Edit and Write


@pytest.mark.parametrize(
    "relative",
    [
        "tests/test_core.py",
        "tests/test_new.py",
        "Makefile",
        "pyproject.toml",
        "conftest.py",
        "src/conftest.py",
        "tests/deep/conftest.py",
    ],
)
def test_implement_freezes_the_oracle(repo: Path, relative: str) -> None:
    set_phase(repo, "implement 0123abc\n")
    call = tool_call(repo, "Edit", file_path=str(repo / relative))

    result = run_hook("freeze_tests.py", repo, call)

    assert result.returncode == 2
    assert "is frozen in the implement phase" in result.stderr


@pytest.mark.parametrize(
    "relative", ["src/pkg/core.py", "src/pkg/new.py", "docs/SPEC.md", "README.md"]
)
def test_implement_lets_the_rest_be_edited(repo: Path, relative: str) -> None:
    set_phase(repo, "implement 0123abc\n")
    call = tool_call(repo, "Write", file_path=str(repo / relative), content="x")

    result = run_hook("freeze_tests.py", repo, call)

    assert (result.returncode, result.stderr) == (0, "")


@pytest.mark.parametrize("phase", ["", "\n", "tests\n"])
def test_other_phases_leave_tests_editable(repo: Path, phase: str) -> None:
    set_phase(repo, phase)
    call = tool_call(repo, "Edit", file_path=str(repo / "tests/test_core.py"))

    assert run_hook("freeze_tests.py", repo, call).returncode == 0


def test_no_phase_file_leaves_tests_editable(repo: Path) -> None:
    call = tool_call(repo, "Edit", file_path=str(repo / "tests/test_core.py"))

    assert run_hook("freeze_tests.py", repo, call).returncode == 0


def test_implement_with_no_commit_still_freezes(repo: Path) -> None:
    set_phase(repo, "implement\n")
    call = tool_call(repo, "Edit", file_path=str(repo / "tests/test_core.py"))

    assert run_hook("freeze_tests.py", repo, call).returncode == 2


def test_a_symlink_into_tests_is_frozen(repo: Path) -> None:
    set_phase(repo, "implement 0123abc\n")
    link = repo / "src/pkg/link.py"
    link.symlink_to(repo / "tests/test_core.py")
    call = tool_call(repo, "Edit", file_path=str(link))

    assert run_hook("freeze_tests.py", repo, call).returncode == 2


def test_tests_outside_the_repo_are_not_frozen(repo: Path, tmp_path: Path) -> None:
    set_phase(repo, "implement 0123abc\n")
    call = tool_call(repo, "Write", file_path=str(tmp_path / "other/tests/x.py"))

    assert run_hook("freeze_tests.py", repo, call).returncode == 0


def test_an_unknown_phase_blocks_every_edit(repo: Path) -> None:
    set_phase(repo, "implment 0123abc\n")
    call = tool_call(repo, "Edit", file_path=str(repo / "docs/SPEC.md"))

    result = run_hook("freeze_tests.py", repo, call)

    assert result.returncode == 2
    assert "neither 'tests' nor 'implement <commit>'" in result.stderr


# guard_reads.py: PreToolUse on Read, Grep, Glob, Bash, WebFetch and MCP tools


def test_reading_src_is_blocked(repo: Path) -> None:
    set_phase(repo, "tests\n")
    call = tool_call(repo, "Read", file_path=str(repo / "src/pkg/core.py"))

    result = run_hook("guard_reads.py", repo, call)

    assert result.returncode == 2
    assert "src/ is not read" in result.stderr
    assert log_entries(repo) == []


def test_reading_outside_src_is_allowed_and_logged(repo: Path) -> None:
    set_phase(repo, "tests\n")
    call = tool_call(repo, "Read", file_path=str(repo / "tests/test_core.py"))

    result = run_hook("guard_reads.py", repo, call)

    assert (result.returncode, result.stderr) == (0, "")
    [entry] = log_entries(repo)
    assert entry["tool"] == "Read"
    assert entry["paths"] == [str(repo / "tests/test_core.py")]
    assert entry["command"] is None


def test_reading_src_through_a_symlink_is_blocked(repo: Path) -> None:
    set_phase(repo, "tests\n")
    link = repo / "tests/link.py"
    link.symlink_to(repo / "src/pkg/core.py")
    call = tool_call(repo, "Read", file_path=str(link))

    assert run_hook("guard_reads.py", repo, call).returncode == 2


@pytest.mark.parametrize(
    ("path", "returncode"),
    [
        (None, 2),
        (".", 2),
        ("src", 2),
        ("src/pkg", 2),
        ("tests", 0),
        ("docs/SPEC.md", 0),
    ],
)
def test_grep_is_checked_by_where_it_searches(
    repo: Path, path: str | None, returncode: int
) -> None:
    set_phase(repo, "tests\n")
    tool_input: dict[str, object] = {"pattern": "VALUE"}
    if path is not None:
        tool_input["path"] = path
    call = tool_call(repo, "Grep", **tool_input)

    assert run_hook("guard_reads.py", repo, call).returncode == returncode


@pytest.mark.parametrize(
    ("pattern", "path", "returncode"),
    [
        ("**/*.py", None, 2),
        ("src/**", None, 2),
        ("*/pkg/*.py", None, 2),
        ("s*/pkg/core.py", None, 2),
        ("src", None, 2),
        ("*.py", "src/pkg", 2),
        ("tests/*.py", None, 0),
        ("*.md", None, 0),
        ("docs/**", None, 0),
        ("*.py", "tests", 0),
    ],
)
def test_glob_is_checked_by_what_it_can_list(
    repo: Path, pattern: str, path: str | None, returncode: int
) -> None:
    set_phase(repo, "tests\n")
    tool_input: dict[str, object] = {"pattern": pattern}
    if path is not None:
        tool_input["path"] = path
    call = tool_call(repo, "Glob", **tool_input)

    assert run_hook("guard_reads.py", repo, call).returncode == returncode


def test_an_absolute_glob_into_src_is_blocked(repo: Path) -> None:
    set_phase(repo, "tests\n")
    call = tool_call(repo, "Glob", pattern=str(repo / "src/pkg/*.py"))

    assert run_hook("guard_reads.py", repo, call).returncode == 2


@pytest.mark.parametrize(
    "command",
    [
        "make format",
        "make lint",
        "make types",
        "make test-red",
        "git status",
        "git diff -- tests/",
        "  git status\n",
    ],
)
def test_the_allowed_commands_run_and_are_logged(repo: Path, command: str) -> None:
    set_phase(repo, "tests\n")
    call = tool_call(repo, "Bash", command=command)

    assert run_hook("guard_reads.py", repo, call).returncode == 0
    [entry] = log_entries(repo)
    assert (entry["tool"], entry["command"], entry["paths"]) == ("Bash", command, [])


@pytest.mark.parametrize(
    "command",
    [
        "cat src/pkg/core.py",
        "git diff",
        "git diff -- src/",
        "make test",
        "make check",
        "make format && cat src/pkg/core.py",
        "ls",
    ],
)
def test_every_other_command_is_blocked(repo: Path, command: str) -> None:
    set_phase(repo, "tests\n")
    call = tool_call(repo, "Bash", command=command)

    result = run_hook("guard_reads.py", repo, call)

    assert result.returncode == 2
    assert "Bash runs only" in result.stderr
    assert log_entries(repo) == []


@pytest.mark.parametrize(
    "tool", ["WebFetch", "mcp__plugin_semantic-diff-weaver_semantic-diff-weaver__x"]
)
def test_web_and_mcp_tools_are_blocked(repo: Path, tool: str) -> None:
    set_phase(repo, "tests\n")
    call = tool_call(repo, tool, url="https://example.com")

    assert run_hook("guard_reads.py", repo, call).returncode == 2


@pytest.mark.parametrize("phase", [None, "implement 0123abc\n"])
def test_other_phases_read_src_unlogged(repo: Path, phase: str | None) -> None:
    if phase is not None:
        set_phase(repo, phase)
    for call in [
        tool_call(repo, "Read", file_path=str(repo / "src/pkg/core.py")),
        tool_call(repo, "Bash", command="cat src/pkg/core.py"),
        tool_call(repo, "WebFetch", url="https://example.com"),
    ]:
        assert run_hook("guard_reads.py", repo, call).returncode == 0
    assert not (repo / ".claude/tests-phase.log").exists()


def test_an_unknown_phase_blocks_every_read(repo: Path) -> None:
    set_phase(repo, "test\n")
    call = tool_call(repo, "Read", file_path=str(repo / "docs/SPEC.md"))

    assert run_hook("guard_reads.py", repo, call).returncode == 2


def test_a_hook_that_cannot_read_its_input_blocks(repo: Path) -> None:
    set_phase(repo, "tests\n")

    result = run_hook("guard_reads.py", repo, "not json")

    assert result.returncode == 2
    assert "The hook failed, so it blocks the call" in result.stderr


def test_a_hook_without_its_project_dir_blocks(repo: Path) -> None:
    environment = {
        name: value
        for name, value in os.environ.items()
        if name != "CLAUDE_PROJECT_DIR"
    }
    call = tool_call(repo, "Read", file_path=str(repo / "docs/SPEC.md"))

    result = subprocess.run(
        ["python3", str(HOOKS / "guard_reads.py")],
        input=json.dumps(call),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2


# format_edited.py: PostToolUse on Edit and Write


@pytest.fixture
def python_repo(repo: Path) -> Path:
    (repo / ".venv/bin").mkdir(parents=True)
    (repo / ".venv/bin/ruff").symlink_to(REAL_REPO / ".venv/bin/ruff")
    (repo / "pyproject.toml").write_text(
        '[tool.ruff.lint]\nselect = ["E", "F", "I"]\n', encoding="utf-8"
    )
    return repo


def edited(repo: Path, relative: str, content: str) -> subprocess.CompletedProcess[str]:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    call = tool_call(repo, "Write", file_path=str(path), content=content)
    call["hook_event_name"] = "PostToolUse"
    return run_hook("format_edited.py", repo, call)


def test_an_edited_file_is_formatted_silently(python_repo: Path) -> None:
    result = edited(python_repo, "src/pkg/core.py", "x=[1,2 ,3]\n")

    assert (result.returncode, result.stderr) == (0, "")
    assert (python_repo / "src/pkg/core.py").read_text() == "x = [1, 2, 3]\n"


def test_safe_fixes_are_applied_silently(python_repo: Path) -> None:
    result = edited(
        python_repo, "src/pkg/core.py", "import sys\nimport os\n\nos, sys\n"
    )

    assert result.returncode == 0
    assert (python_repo / "src/pkg/core.py").read_text().startswith("import os\n")


def test_an_import_not_used_yet_is_kept_and_not_reported(python_repo: Path) -> None:
    result = edited(python_repo, "src/pkg/core.py", "import os\n")

    assert (result.returncode, result.stderr) == (0, "")
    assert (python_repo / "src/pkg/core.py").read_text() == "import os\n"


def test_what_ruff_cannot_fix_goes_to_claude(python_repo: Path) -> None:
    result = edited(python_repo, "src/pkg/core.py", "print(undefined_name)\n")

    assert result.returncode == 2
    assert "F821" in result.stderr


def test_a_syntax_error_goes_to_claude(python_repo: Path) -> None:
    result = edited(python_repo, "src/pkg/core.py", "def f(:\n")

    assert result.returncode == 2
    assert "could not format" in result.stderr


def test_other_files_are_left_alone(python_repo: Path, tmp_path: Path) -> None:
    for relative in ["docs/notes.md", "../outside.py"]:
        result = edited(python_repo, relative, "x=[1,2 ,3]\n")

        assert (result.returncode, result.stderr) == (0, "")
        assert (python_repo / relative).read_text() == "x=[1,2 ,3]\n"
    assert (tmp_path / "outside.py").exists()


def test_without_ruff_claude_is_told_to_install(repo: Path) -> None:
    result = edited(repo, "src/pkg/core.py", "x=[1,2 ,3]\n")

    assert result.returncode == 2
    assert "run make install" in result.stderr
