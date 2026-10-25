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

# K15's record file: K4's line, as tests/test_messages.py writes it, then a line
# that is not a record. The record file is read before any other input, so the
# others, which name nothing in the working directory, are never looked at.
K15_RECORD_FILE = (
    b'{"format":1,"head":"c7d2f4a91b3e5f6082a4c6e8f0b1d3a5c7e9f2b4","junit_sha256":"'
    b'5a1f3c7e9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a1c3e5b7d9f2a4c6e8b0d1f3a","pr":7,'
    b'"verdict":"rejected","reason":"coverage-not-ancestor","input":"coverage"}\n'
    b"canary\n"
)


def test_python_m_distiller_exits_with_what_main_returns(tmp_path: Path) -> None:
    # A package of the same name in the working directory, as the pilot's
    # checkout could hold one: -P keeps it out of sys.path.
    decoy = tmp_path / "distiller"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("", encoding="utf-8")
    (decoy / "__main__.py").write_text("raise SystemExit(97)\n", encoding="utf-8")
    (tmp_path / "records.jsonl").write_bytes(K15_RECORD_FILE)

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-P", "-m", "distiller", *COMMAND],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        capture_output=True,
        check=False,
    )

    # K15: main returns 1, and the message it prints names the record file. A
    # process that ended without the exit code main returns would exit with 0.
    assert result.returncode == 1
    assert result.stdout == b""
    assert b"records.jsonl" in result.stderr
