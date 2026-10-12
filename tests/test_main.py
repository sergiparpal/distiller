import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

COMMAND = [
    "evaluate",
    "--pr",
    "7",
    "--head",
    "H",
    "--base",
    "origin/main",
    "--coverage",
    "m.coverage",
    "--coverage-commit",
    "M",
    "--junit",
    "junit.xml",
    "--records",
    "records.jsonl",
]


def test_python_m_distiller_exits_with_what_main_returns(tmp_path: Path) -> None:
    # A package of the same name in the working directory, as the pilot's
    # checkout could hold one: -P keeps it out of sys.path.
    decoy = tmp_path / "distiller"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("", encoding="utf-8")
    (decoy / "__main__.py").write_text("raise SystemExit(97)\n", encoding="utf-8")

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-P", "-m", "distiller", *COMMAND],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr == b"distiller: unexpected failure: NotImplementedError\n"
