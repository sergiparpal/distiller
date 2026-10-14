"""PostToolUse on Edit and Write: format and lint the Python file just edited.

ruff format and ruff's safe fixes run silently; what is left goes to Claude.
"""

import subprocess
from pathlib import Path

from phase import current_repo, is_inside, object_field, run_hook, text_field

PYTHON_SUFFIXES = (".py", ".pyi")
FORMAT = ("format", "--force-exclude", "--quiet")
# F401 waits for make check: an import added one edit before its first use
# would be reported, or removed by the fix, in between.
LINT = (
    "check",
    "--fix",
    "--ignore",
    "F401",
    "--force-exclude",
    "--quiet",
    "--output-format",
    "concise",
)


def check(data: dict[str, object]) -> str | None:
    repo = current_repo()
    file_path = text_field(object_field(data, "tool_input"), "file_path")
    if file_path is None:
        return None
    path = Path(file_path).resolve()
    if path.suffix not in PYTHON_SUFFIXES or not is_inside(path, repo.root):
        return None
    ruff = repo.root / ".venv" / "bin" / "ruff"
    if not ruff.exists():
        return f"{ruff} is missing, so {path} was not formatted: run make install."
    formatted = run_ruff(repo.root, [str(ruff), *FORMAT, str(path)])
    if formatted.returncode != 0:
        return f"ruff format could not format {path}:\n{formatted.stdout}"
    linted = run_ruff(repo.root, [str(ruff), *LINT, str(path)])
    if linted.returncode != 0:
        return f"ruff check, after its safe fixes, reports:\n{linted.stdout}"
    return None


def run_ruff(root: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    # ruff writes its own errors to stderr: Claude sees both streams as one.
    return subprocess.run(
        command,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


if __name__ == "__main__":
    run_hook(check)
