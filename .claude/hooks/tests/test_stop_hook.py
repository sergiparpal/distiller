"""Contract tests of the Stop hook, run as Claude Code runs it, against small git
repositories whose Makefile goes red when a marker file exists."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import cast

import pytest

HOOKS = Path(__file__).resolve().parent.parent
REAL_REPO = HOOKS.parent.parent

MAKEFILE = """\
verify:
\t@test ! -e RED || { echo "verify is red"; exit 1; }

format lint types:
\t@test ! -e LINT-RED || { echo "$@ is red"; exit 1; }
"""

# Runs inside the sandbox as make verify, and fails on anything it can reach.
PROBE = """\
import os, socket, sys
from pathlib import Path

failures = []
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3)
    failures.append("the network is reachable")
except OSError:
    pass
extra = set(os.listdir(Path.home())) - {".nvm", ".cache"}
if extra:
    failures.append(f"the home directory shows {sorted(extra)}")
if Path("/mnt").is_dir() and os.listdir("/mnt"):
    failures.append("/mnt is not empty")
for name in ("FAKE_TOKEN", "FAKE_API_KEY", "FAKE_SECRET"):
    if name in os.environ:
        failures.append(f"{name} is in the environment")
if "KEEP_ME" not in os.environ:
    failures.append("KEEP_ME was removed too")
try:
    Path(".claude/settings.local.json").read_text()
    failures.append("settings.local.json can be read")
except OSError:
    pass
outside = Path(Path("outside-path.txt").read_text())
outside.parent.mkdir(parents=True, exist_ok=True)
outside.write_text("written from the sandbox")
Path("written-inside.txt").write_text("written from the sandbox")
print("\\n".join(failures))
sys.exit(1 if failures else 0)
"""


def git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for directory in ("src/pkg", "tests", ".claude"):
        (root / directory).mkdir(parents=True)
    (root / "src/pkg/core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests/test_core.py").write_text("VALUE = 2\n", encoding="utf-8")
    (root / "Makefile").write_text(MAKEFILE, encoding="utf-8")
    (root / "pyproject.toml").write_text("[tool.pytest]\n", encoding="utf-8")
    (root / ".gitignore").write_text(".claude/\nRED\nLINT-RED\n", encoding="utf-8")
    git(root, "init", "--quiet")
    git(root, "add", ".")
    commit(root, "the tests")
    return root


def commit(repo: Path, message: str) -> str:
    git(repo, "add", ".")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


def set_phase(repo: Path, text: str) -> None:
    (repo / ".claude/phase").write_text(text, encoding="utf-8")


def implement(repo: Path) -> str:
    sha = git(repo, "rev-parse", "HEAD")
    set_phase(repo, f"implement {sha}\n")
    return sha


def stop(
    repo: Path,
    prompt: str | None = "prompt-1",
    *,
    active: bool = False,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    payload: dict[str, object] = {
        "session_id": "session",
        "hook_event_name": "Stop",
        "stop_hook_active": active,
        "cwd": str(repo),
    }
    if prompt is not None:
        payload["prompt_id"] = prompt
    return subprocess.run(
        [shutil.which("python3") or "python3", str(HOOKS / "check_on_stop.py")],
        input=json.dumps(payload),
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo), **(environment or {})},
        capture_output=True,
        text=True,
        check=False,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return cast("dict[str, object]", json.loads(result.stdout))


def blocks(result: subprocess.CompletedProcess[str]) -> str:
    """The reason, when the hook blocked the stop the way Claude Code needs it."""
    assert result.returncode == 2
    answer = output(result)
    assert answer["decision"] == "block"
    reason = cast("str", answer["reason"])
    assert reason in result.stderr
    return reason


def ends_turn(result: subprocess.CompletedProcess[str]) -> str:
    """The reason, when the hook ended the turn for the user to decide."""
    assert result.returncode == 0
    answer = output(result)
    assert answer["continue"] is False
    return cast("str", answer["stopReason"])


# Green and red


def test_green_lets_the_agent_stop(repo: Path) -> None:
    result = stop(repo)

    assert (result.returncode, result.stdout) == (0, "")


def test_red_blocks_the_stop(repo: Path) -> None:
    (repo / "RED").touch()

    reason = blocks(stop(repo))

    assert "`make verify` is red" in reason
    assert "verify is red" in reason
    assert ".claude/blocked" in reason


def test_red_blocks_twice_and_then_ends_the_turn(repo: Path) -> None:
    (repo / "RED").touch()

    blocks(stop(repo, "prompt-1"))
    blocks(stop(repo, "prompt-1", active=True))
    reason = ends_turn(stop(repo, "prompt-1", active=True))

    assert "still not done after 2 rounds" in reason
    blocks(stop(repo, "prompt-2"))


def test_without_a_prompt_id_a_stop_no_hook_caused_starts_a_turn(repo: Path) -> None:
    (repo / "RED").touch()

    blocks(stop(repo, None))
    blocks(stop(repo, None, active=True))
    ends_turn(stop(repo, None, active=True))
    blocks(stop(repo, None, active=False))


def test_blocked_excuses_red(repo: Path) -> None:
    (repo / "RED").touch()
    (repo / ".claude/blocked").write_text(
        "\ntest_core: the SPEC example says 1\n", encoding="utf-8"
    )

    result = stop(repo)

    assert result.returncode == 0
    assert output(result)["systemMessage"] == (
        "The turn ended blocked: test_core: the SPEC example says 1 "
        "(`make verify` is red.)"
    )


def test_a_hung_check_counts_as_red(repo: Path) -> None:
    (repo / "Makefile").write_text("verify:\n\t@sleep 10\n", encoding="utf-8")

    reason = blocks(stop(repo, environment={"STOP_HOOK_DEADLINE_SECONDS": "1"}))

    assert "did not finish in 1 s" in reason


# The tests phase


def test_the_tests_phase_expects_red_tests(repo: Path) -> None:
    set_phase(repo, "tests\n")
    (repo / "RED").touch()

    assert stop(repo).returncode == 0


def test_the_tests_phase_checks_format_lint_and_types(repo: Path) -> None:
    set_phase(repo, "tests\n")
    (repo / "LINT-RED").touch()

    reason = blocks(stop(repo))

    assert "`make format lint types` is red" in reason


# The implement phase


def test_implement_with_untouched_frozen_files_lets_the_agent_stop(repo: Path) -> None:
    implement(repo)
    (repo / "src/pkg/core.py").write_text("VALUE = 3\n", encoding="utf-8")

    assert stop(repo).returncode == 0


@pytest.mark.parametrize(
    "relative",
    ["tests/test_core.py", "Makefile", "pyproject.toml"],
)
def test_implement_catches_a_changed_frozen_file(repo: Path, relative: str) -> None:
    sha = implement(repo)
    with (repo / relative).open("a", encoding="utf-8") as frozen:
        frozen.write("\n# changed through Bash\n")

    reason = blocks(stop(repo))

    assert f"restore with: git checkout {sha} -- {relative}" in reason


@pytest.mark.parametrize(
    "relative", ["tests/test_new.py", "conftest.py", "src/conftest.py"]
)
def test_implement_catches_a_new_frozen_file(repo: Path, relative: str) -> None:
    implement(repo)
    (repo / relative).write_text("VALUE = 4\n", encoding="utf-8")

    reason = blocks(stop(repo))

    assert f"delete, as they are new: {relative}" in reason


def test_implement_catches_a_frozen_file_changed_in_a_later_commit(repo: Path) -> None:
    implement(repo)
    (repo / "tests/test_core.py").write_text("VALUE = 5\n", encoding="utf-8")
    commit(repo, "weaken the test")

    assert "tests/test_core.py" in blocks(stop(repo))


def test_blocked_does_not_excuse_a_changed_frozen_file(repo: Path) -> None:
    implement(repo)
    (repo / "tests/test_core.py").write_text("VALUE = 6\n", encoding="utf-8")
    (repo / ".claude/blocked").write_text("a test looks wrong\n", encoding="utf-8")

    assert "tests/test_core.py" in blocks(stop(repo))


# What the agent cannot fix ends the turn at once


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        ("implement\n", "names no commit"),
        ("implement 0000000000000000000000000000000000000000\n", "no commit here"),
        ("implement HEAD~5\n", "no commit here"),
        ("implementing\n", "neither 'tests' nor"),
    ],
)
def test_a_broken_phase_file_ends_the_turn(
    repo: Path, phase: str, expected: str
) -> None:
    set_phase(repo, phase)

    assert expected in ends_turn(stop(repo))


@pytest.mark.parametrize("phase", [None, "tests\n", "implement HEAD\n"])
def test_a_log_that_read_src_ends_the_turn_in_every_phase(
    repo: Path, phase: str | None
) -> None:
    if phase is not None:
        set_phase(repo, phase)
    entry = {"tool": "Read", "paths": [str(repo / "src/pkg/core.py")]}
    (repo / ".claude/tests-phase.log").write_text(
        json.dumps(entry) + "\n", encoding="utf-8"
    )

    reason = ends_turn(stop(repo))

    assert "read inside src/" in reason
    assert "src/pkg/core.py" in reason


def test_a_clean_log_changes_nothing(repo: Path) -> None:
    entries = [
        {"tool": "Read", "paths": [str(repo / "tests/test_core.py")]},
        {"tool": "Bash", "paths": [], "command": "git status"},
    ]
    (repo / ".claude/tests-phase.log").write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8"
    )

    assert stop(repo).returncode == 0


def test_a_log_line_the_hook_did_not_write_ends_the_turn(repo: Path) -> None:
    (repo / ".claude/tests-phase.log").write_text("cat src/x\n", encoding="utf-8")

    assert "that the hook did not write" in ends_turn(stop(repo))


def test_without_bwrap_nothing_runs(repo: Path, tmp_path: Path) -> None:
    (repo / "RED").touch()
    empty = tmp_path / "bin"
    empty.mkdir()

    reason = ends_turn(stop(repo, environment={"PATH": str(empty)}))

    assert "bubblewrap is not installed" in reason


# The sandbox


def test_the_checks_run_offline_hidden_and_without_credentials(
    repo: Path, tmp_path: Path
) -> None:
    (repo / "probe.py").write_text(PROBE, encoding="utf-8")
    (repo / "Makefile").write_text("verify:\n\t@python3 probe.py\n", encoding="utf-8")
    (repo / ".claude/settings.local.json").write_text("canary", encoding="utf-8")
    outside = tmp_path / "outside" / "written.txt"
    (repo / "outside-path.txt").write_text(str(outside), encoding="utf-8")
    credentials = {"FAKE_TOKEN": "x", "FAKE_API_KEY": "x", "FAKE_SECRET": "x"}

    result = stop(repo, environment={**credentials, "KEEP_ME": "x"})

    assert (result.returncode, result.stdout) == (0, "")
    assert (repo / "written-inside.txt").exists()
    assert not outside.exists()
    assert (repo / ".claude/settings.local.json").read_text() == "canary"


@pytest.mark.skipif(
    (REAL_REPO / ".claude/phase").exists(), reason="a phase is set in this repository"
)
def test_this_repository_is_green_inside_the_sandbox() -> None:
    result = stop(REAL_REPO, "test-hooks")

    assert (result.returncode, result.stdout) == (0, "")
