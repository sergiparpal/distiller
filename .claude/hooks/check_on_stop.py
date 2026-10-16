"""Stop: no turn ends red, with the oracle changed, or with src/ read for tests.

Everything this hook runs, git included, runs inside bwrap: no network, the
home directory, /run and /mnt hidden apart from what the checks read, only the
repo writable but not its .venv or .git, and no variable that looks like a
credential. The tests the agent writes run here, and a fixture with a wrong
directory must not reach the user's home, credentials or network, nor leave
behind something that runs outside the sandbox later.

- tests phase: make format lint types, because red tests are expected there;
- any other phase: make verify, which is make check without pip-audit;
- implement phase: the frozen files must also match the commit in .claude/phase;
- every phase: no path in .claude/tests-phase.log may lie inside src/.

What the agent can fix blocks the stop (exit 2) twice per turn; the third
time, and at once for what it cannot fix, the turn ends with the reason for
the user (continue: false). .claude/blocked excuses red checks and nothing else.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn, cast

from phase import (
    FROZEN_PATHSPECS,
    Phase,
    PhaseError,
    Repo,
    current_repo,
    is_inside,
    read_input,
    read_phase,
    text_field,
)

# CLAUDE.md's two attempts, enforced outside the model.
MAX_BLOCKS = 2
# The hook's timeout in .claude/settings.json is 600 s; the tests shorten this.
DEADLINE = int(os.environ.get("STOP_HOOK_DEADLINE_SECONDS", "540"))
OUTPUT_LINES = 40
CREDENTIAL_WORDS = ("TOKEN", "KEY", "SECRET")
HOW_OUT = (
    "Fix it and stop again. If a test looks wrong, or the same failure survives "
    "two attempts, write the test name, the SPEC example and your reason to "
    ".claude/blocked and stop: .claude/blocked excuses red checks, never "
    "changed frozen files."
)


def main() -> None:
    try:
        decide(read_input(), current_repo())
    except Exception as error:  # noqa: BLE001
        end_turn(f"the hook failed, so this turn was not checked: {error!r}")


def decide(data: dict[str, object], repo: Repo) -> NoReturn:
    problem = sandbox_problem(repo)
    if problem is not None:
        end_turn(problem)
    phase, problems = phase_and_unfixable_problems(repo)
    if phase is None or problems:
        end_turn("\n".join(problems) + "\nThe agent cannot fix this: you decide.")
    frozen = frozen_report(repo, phase)
    red = run_checks(repo, phase)
    if frozen is None and red is None:
        save_blocks(repo, data, 0)
        allow(None)
    if frozen is None and red is not None and repo.blocked_file.exists():
        save_blocks(repo, data, 0)
        still_red = red.split("\n")[0]
        allow(f"The turn ended blocked: {first_line(repo)} ({still_red})")
    reasons = "\n".join(text for text in (frozen, red) if text is not None)
    blocks = blocks_so_far(repo, data)
    if blocks >= MAX_BLOCKS:
        end_turn(f"still not done after {blocks} rounds; you decide.\n{reasons}")
    save_blocks(repo, data, blocks + 1)
    block(f"Stop hook: the turn is not done.\n{reasons}\n{HOW_OUT}")


def sandbox_problem(repo: Repo) -> str | None:
    if shutil.which("bwrap") is None:
        return (
            "bubblewrap is not installed, and Stop runs nothing without it: "
            "sudo apt-get install bubblewrap"
        )
    started = run_sandboxed(repo, ["true"], timeout=30)
    if started.returncode != 0:
        return (
            f"bwrap cannot start, and Stop runs nothing without it:\n{started.stderr}"
        )
    return None


def phase_and_unfixable_problems(repo: Repo) -> tuple[Phase | None, list[str]]:
    problems = contamination(repo)
    try:
        phase = read_phase(repo)
    except PhaseError as error:
        return None, [str(error), *problems]
    if phase.name == "implement":
        problems += commit_problems(repo, phase.commit)
    return phase, problems


def contamination(repo: Repo) -> list[str]:
    try:
        text = repo.tests_log.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    bad = [line for line in text.split("\n") if line and not is_clean(line, repo)]
    if not bad:
        return []
    examples = "\n".join(line[:300] for line in bad[:3])
    problem = (
        f".claude/tests-phase.log has lines that read inside src/ or that the "
        f"hook did not write ({len(bad)} of them), so the tests may come from the "
        f"code. For example:\n{examples}"
    )
    return [problem]


def is_clean(line: str, repo: Repo) -> bool:
    try:
        entry: object = json.loads(line)
    except json.JSONDecodeError:
        return False
    if not isinstance(entry, dict):
        return False
    paths = cast("dict[str, object]", entry).get("paths")
    if not isinstance(paths, list):
        return False
    for path in cast("list[object]", paths):
        if not isinstance(path, str) or is_inside(Path(path), repo.src):
            return False
    return True


def commit_problems(repo: Repo, commit: str | None) -> list[str]:
    if commit is None:
        return [".claude/phase says implement but names no commit."]
    found = run_sandboxed(
        repo,
        [
            "git",
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            f"{commit}^{{commit}}",
        ],
        timeout=30,
    )
    if found.returncode != 0:
        return [f".claude/phase names {commit!r}, which is no commit here."]
    return []


def frozen_report(repo: Repo, phase: Phase) -> str | None:
    if phase.name != "implement" or phase.commit is None:
        return None
    changed = git_lines(
        repo, ["diff", "--name-only", phase.commit, "--", *FROZEN_PATHSPECS]
    )
    added = new_frozen_files(repo)
    if not changed and not added:
        return None
    lines = [f"Frozen files differ from {phase.commit}, the tests commit:"]
    if changed:
        lines.append(
            f"  restore with: git checkout {phase.commit} -- {' '.join(changed)}"
        )
    if added:
        lines.append(f"  delete, as they are new: {' '.join(added)}")
    return "\n".join(lines)


def new_frozen_files(repo: Repo) -> list[str]:
    # Only the root .gitignore may hide a new file: it is frozen, so a change to it
    # shows in git diff. Nested .gitignore files and .git/info/exclude do not.
    arguments = ["ls-files", "--others"]
    if (repo.root / ".gitignore").is_file():
        arguments.append("--exclude-from=.gitignore")
    return git_lines(repo, [*arguments, "--", *FROZEN_PATHSPECS])


def git_lines(repo: Repo, arguments: list[str]) -> list[str]:
    result = run_sandboxed(repo, ["git", *arguments], timeout=60)
    if result.returncode != 0:
        message = f"git {' '.join(arguments)} failed: {result.stderr}"
        raise RuntimeError(message)
    return [line for line in result.stdout.split("\n") if line]


def run_checks(repo: Repo, phase: Phase) -> str | None:
    targets = ["format", "lint", "types"] if phase.name == "tests" else ["verify"]
    name = "make " + " ".join(targets)
    try:
        result = subprocess.run(
            sandboxed(repo, ["make", "--no-print-directory", *targets]),
            env=clean_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=DEADLINE,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"`{name}` did not finish in {DEADLINE} s, which counts as red."
    if result.returncode == 0:
        return None
    tail = "\n".join(result.stdout.splitlines()[-OUTPUT_LINES:])
    return f"`{name}` is red.\nThe end of its output:\n{tail}"


def run_sandboxed(
    repo: Repo, command: list[str], timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        sandboxed(repo, command),
        env=clean_environment(),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
    )


def sandboxed(repo: Repo, command: list[str]) -> list[str]:
    home = Path.home()
    arguments = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session"]
    # Everything read-only, then the home directory, /tmp, /run and /mnt emptied.
    # /tmp is a mount point here, not a file anyone writes to. /run holds the
    # sockets of the user's session, such as the session bus, through which
    # systemd starts processes outside the sandbox: a read-only mount still lets
    # anyone connect to a socket.
    arguments += ["--ro-bind", "/", "/", "--tmpfs", str(home), "--tmpfs", "/tmp"]  # noqa: S108
    arguments += ["--tmpfs", "/run"]
    if Path("/mnt").is_dir():
        arguments += ["--tmpfs", "/mnt"]
    # What the checks read from the home directory: node for pyright, and the
    # environment pre-commit built for gitleaks.
    for needed in (home / ".nvm", home / ".cache" / "pre-commit"):
        arguments += ["--ro-bind-try", str(needed), str(needed)]
    arguments += ["--bind", str(repo.root), str(repo.root)]
    # Read-only inside the repository, what runs outside the sandbox later: in
    # .venv, the format hook's ruff and the .pth files Python runs as it starts;
    # in .git, the hooks and the settings git runs at the user's next commit.
    for kept in (repo.root / ".venv", repo.root / ".git"):
        arguments += ["--ro-bind-try", str(kept), str(kept)]
    local_settings = repo.root / ".claude" / "settings.local.json"
    if local_settings.exists():
        # It can hold credentials. Inside, /dev/null sits on it, and a device on a
        # mount of the sandbox's own cannot be opened: reading it fails.
        arguments += ["--ro-bind", "/dev/null", str(local_settings)]
    arguments += ["--dev", "/dev", "--proc", "/proc", "--chdir", str(repo.root)]
    return [*arguments, *command]


def clean_environment() -> dict[str, str]:
    return {
        name: value
        for name, value in os.environ.items()
        if not any(word in name.upper() for word in CREDENTIAL_WORDS)
    }


def blocks_so_far(repo: Repo, data: dict[str, object]) -> int:
    state = read_state(repo)
    same_session = state.get("session") == text_field(data, "session_id")
    prompt = text_field(data, "prompt_id")
    if prompt is not None:
        same_turn = same_session and state.get("prompt") == prompt
    else:
        # Without a prompt id, a stop that no Stop hook caused starts a turn.
        same_turn = same_session and data.get("stop_hook_active") is True
    blocks = state.get("blocks")
    return blocks if same_turn and isinstance(blocks, int) else 0


def save_blocks(repo: Repo, data: dict[str, object], blocks: int) -> None:
    state = {
        "session": text_field(data, "session_id"),
        "prompt": text_field(data, "prompt_id"),
        "blocks": blocks,
    }
    repo.stop_state.write_text(json.dumps(state) + "\n", encoding="utf-8")


def read_state(repo: Repo) -> dict[str, object]:
    try:
        state: object = json.loads(repo.stop_state.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return cast("dict[str, object]", state) if isinstance(state, dict) else {}


def first_line(repo: Repo) -> str:
    text = repo.blocked_file.read_text(encoding="utf-8", errors="replace")
    for line in text.split("\n"):
        if line.strip():
            return line[:200]
    return ".claude/blocked is empty"


def allow(message: str | None) -> NoReturn:
    if message is not None:
        write_json({"systemMessage": message})
    raise SystemExit(0)


def block(reason: str) -> NoReturn:
    # Exit 2 blocks. The reason also goes out as JSON: on Stop, Claude Code reads
    # an exit 2 with empty stdout and "No such file or directory" in stderr as a
    # hook that failed to start, and test output can say just that.
    write_json({"decision": "block", "reason": reason})
    sys.stderr.write(reason + "\n")
    raise SystemExit(2)


def end_turn(reason: str) -> NoReturn:
    write_json({"continue": False, "stopReason": f"Stop hook: {reason}"})
    raise SystemExit(0)


def write_json(output: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(output) + "\n")


if __name__ == "__main__":
    main()
