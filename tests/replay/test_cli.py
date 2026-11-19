import csv
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

import pytest

from replay import cli, harness
from replay.pilot import Pilot

# The command line of Slice 2, python -m replay run. Most tests give main a
# command line alone, or with a fake harness.replay that keeps what it is
# given; the others run the real replay over a small pilot, shop, none of
# whose manifest's heads is in its clone, so that each pull request is listed
# as not replayed and nothing is built or run, and one runs python -m replay
# as a process. Decided by the user on 2026-11-19, for the SPEC: a replay that
# ends with 0 prints its summary on stdout; an unexpected failure, a pilot or
# a manifest that is refused included, is one line on stderr,
# replay: <class>: <message>, and exit 1; and main gives the replay each path
# made absolute, since the replay runs git and the tool from other
# directories.

GIT = shutil.which("git") or "git"

# This repository: its src/, from which python -m replay runs, and the
# checkout of the tool that the real replay is given.
REPOSITORY = Path(__file__).resolve().parents[2]
SRC = REPOSITORY / "src"

UNKNOWN_COMMIT = "0123456789abcdef0123456789abcdef01234567"

PILOT_TOML = """\
project = "shop"
repository = "example/shop"
base_branch = "main"
job = "Ubuntu 3.12"
python = "3.12"
environment = [["uv", "sync", "--frozen"]]
pytest = ["-p", "no:cacheprovider"]
coverage_source = "shop"
seconds_per_test = 30
adds_timeout_plugin = false
"""

# The pilot that PILOT_TOML describes.
SHOP = Pilot(
    project="shop",
    repository="example/shop",
    base_branch="main",
    job="Ubuntu 3.12",
    python="3.12",
    environment=(("uv", "sync", "--frozen"),),
    pytest=("-p", "no:cacheprovider"),
    coverage_source="shop",
    seconds_per_test=30,
    adds_timeout_plugin=False,
    floor_config=None,
)

# run's options, each with a value, as on a command line: paths relative to
# the working directory.
REQUIRED = {
    "--pilot": "shop.toml",
    "--manifest": "manifest.csv",
    "--clone": "clone",
    "--work": "work",
    "--records": "records.jsonl",
    "--tool": "tool",
}

MANIFEST_COLUMNS: tuple[str, ...] = (
    "project",
    "pull_request",
    "run_id",
    "run_started",
    "head",
    "job",
    "failed_steps",
)

WITNESS = "canary-6f2a"
NOTE = "a note on the canary"
CAUSE = "the canary's cause"


class CanaryError(Exception):
    pass


@dataclass(frozen=True)
class ReplayCall:
    """What main gave harness.replay."""

    pilot: Pilot
    manifest: str
    clone: str
    work: str
    records: str
    tool: str
    only: list[int] | None


@dataclass(frozen=True)
class Shop:
    """A small pilot's files, for the real replay: none of its manifest's
    heads is in its clone."""

    pilot: Path
    manifest: Path
    clone: Path
    work: Path
    records: Path


@pytest.fixture
def shop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Shop:
    isolate_git(monkeypatch, tmp_path)
    clone = tmp_path / "clone"
    build_clone(clone)
    pilot = tmp_path / "shop.toml"
    pilot.write_text(PILOT_TOML, encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    return Shop(
        pilot=pilot,
        manifest=write_manifest(tmp_path / "manifest.csv", [1, 2, 3]),
        clone=clone,
        work=work,
        records=tmp_path / "records.jsonl",
    )


def isolate_git(patch: pytest.MonkeyPatch, root: Path) -> None:
    """Keep git to the clone's own settings, and hide the user's home."""
    for name in list(os.environ):
        if name.startswith("GIT_"):
            patch.delenv(name)
    home = root / "home"
    home.mkdir()
    patch.setenv("HOME", str(home))
    patch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    patch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    patch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    patch.setenv("GIT_CEILING_DIRECTORIES", str(root))
    for role in ("AUTHOR", "COMMITTER"):
        patch.setenv(f"GIT_{role}_NAME", "Distiller Tests")
        patch.setenv(f"GIT_{role}_EMAIL", "tests@distiller.invalid")


def run_git(directory: Path, *arguments: str) -> None:
    """Run the real git in directory, as the tests' setup does."""
    result = subprocess.run(  # noqa: S603
        [GIT, "-C", str(directory), *arguments],
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, os.fsdecode(result.stderr)


def build_clone(clone: Path) -> None:
    """shop's clone: one commit on main, which no row of the manifest names."""
    clone.mkdir()
    run_git(clone, "init", "--quiet", "--initial-branch=main")
    (clone / "README.md").write_text("A shop.\n", encoding="utf-8")
    run_git(clone, "add", "--all")
    run_git(clone, "commit", "--quiet", "--message", "Start")


def write_manifest(path: Path, pull_requests: list[int]) -> Path:
    """One row of shop for each pull request, its head not in the clone."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for number in pull_requests:
            row = {
                "project": "shop",
                "pull_request": str(number),
                "run_id": str(1000 + number),
                "run_started": "2026-11-10T00:00:00Z",
                "head": UNKNOWN_COMMIT,
                "job": "failed in a test step",
                "failed_steps": "",
            }
            writer.writerow(row)
    return path


def command_line(command: str, options: dict[str, str]) -> list[str]:
    words = [command]
    for option, value in options.items():
        words.extend((option, value))
    return words


def without(options: dict[str, str], option: str) -> dict[str, str]:
    return {key: value for key, value in options.items() if key != option}


def options_of(shop: Shop) -> dict[str, str]:
    """run's options for shop, with this repository as the tool."""
    return {
        "--pilot": str(shop.pilot),
        "--manifest": str(shop.manifest),
        "--clone": str(shop.clone),
        "--work": str(shop.work),
        "--records": str(shop.records),
        "--tool": str(REPOSITORY),
    }


def log_of(work: Path) -> list[dict[str, Any]]:
    lines = (work / "shop.log").read_text(encoding="utf-8").splitlines()
    return [cast("dict[str, Any]", json.loads(line)) for line in lines]


def exit_code_of(argv: list[str]) -> int | str | None:
    """What main returns, or the code of the SystemExit that it raises."""
    try:
        return cli.main(argv)
    except SystemExit as stop:
        return stop.code


def fake_replay(monkeypatch: pytest.MonkeyPatch, exit_code: int) -> list[ReplayCall]:
    """Put a harness.replay in place that keeps each call and returns
    exit_code."""
    calls: list[ReplayCall] = []

    def replay(  # noqa: PLR0913, harness.replay's own arguments
        pilot: Pilot,
        *,
        manifest: str,
        clone: str,
        work: str,
        records: str,
        tool: str,
        only: list[int] | None,
    ) -> int:
        calls.append(ReplayCall(pilot, manifest, clone, work, records, tool, only))
        return exit_code

    monkeypatch.setattr(harness, "replay", replay)
    return calls


def fail_with_canary(*_args: object, **_kwargs: object) -> NoReturn:
    error = CanaryError(WITNESS)
    error.add_note(NOTE)
    raise error from OSError(CAUSE)


def test_a_replay_that_ends_prints_its_summary_and_exits_with_0(
    shop: Shop, capsys: pytest.CaptureFixture[str]
) -> None:
    code = cli.main(command_line("run", options_of(shop)))

    summary = (shop.work / "summary.txt").read_text(encoding="utf-8")
    assert code == 0
    assert capsys.readouterr().out == summary
    first_line = summary.splitlines()[0]
    assert first_line == "shop: replayed 0, not replayed 3, red 0, inherited failures 0"


def test_only_replays_those_pull_requests_alone(shop: Shop) -> None:
    code = cli.main([*command_line("run", options_of(shop)), "--only", "1", "3"])

    assert code == 0
    done = [entry for entry in log_of(shop.work) if entry["event"] == "done"]
    assert sorted(entry["pull_request"] for entry in done) == [1, 3]


def test_a_replay_that_does_not_start_prints_no_summary(
    shop: Shop, capsys: pytest.CaptureFixture[str]
) -> None:
    # A first replay writes the summary; a second does not start, since its
    # --only names a pull request that shop's lines lack.
    assert cli.main(command_line("run", options_of(shop))) == 0
    capsys.readouterr()

    code = cli.main([*command_line("run", options_of(shop)), "--only", "9"])

    output = capsys.readouterr()
    assert code == 1
    assert output.out == ""
    assert output.err != ""


@pytest.mark.parametrize(
    ("extra", "only"),
    [
        pytest.param([], None, id="without --only"),
        pytest.param(["--only", "3", "4"], [3, 4], id="with --only"),
    ],
)
def test_run_gives_the_replay_the_pilot_it_read_and_its_options(
    extra: list[str],
    only: list[int] | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "shop.toml").write_text(PILOT_TOML, encoding="utf-8")
    calls = fake_replay(monkeypatch, exit_code=1)

    code = cli.main([*command_line("run", REQUIRED), *extra])

    # A replay that does not start: main returns its exit code and adds
    # nothing to what the replay wrote, which here is nothing.
    assert code == 1
    output = capsys.readouterr()
    assert (output.out, output.err) == ("", "")
    [call] = calls
    assert call.pilot == SHOP
    assert call.only == only
    # Each path, given relative to the working directory, made absolute.
    assert (call.manifest, call.clone, call.work, call.records, call.tool) == (
        str(tmp_path / "manifest.csv"),
        str(tmp_path / "clone"),
        str(tmp_path / "work"),
        str(tmp_path / "records.jsonl"),
        str(tmp_path / "tool"),
    )


MISSING_OPTIONS = [
    pytest.param(command_line("run", without(REQUIRED, option)), id=f"no {option}")
    for option in REQUIRED
]


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param([], id="no command"),
        pytest.param(["frobnicate"], id="unknown command"),
        pytest.param(command_line("ru", REQUIRED), id="abbreviated command"),
        *MISSING_OPTIONS,
        pytest.param(command_line("run", {**REQUIRED, "--bogus": "x"}), id="unknown"),
        # --pil could only be --pilot: only allow_abbrev=False rejects it.
        pytest.param(
            command_line("run", {**without(REQUIRED, "--pilot"), "--pil": "shop.toml"}),
            id="abbreviated option",
        ),
        pytest.param([*command_line("run", REQUIRED), "--only"], id="no number"),
        pytest.param(
            [*command_line("run", REQUIRED), "--only", "x"], id="not a number"
        ),
    ],
)
def test_a_malformed_command_line_is_a_usage_error(
    argv: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert exit_code_of(argv) == 2
    assert capsys.readouterr().out == ""
    assert list(tmp_path.iterdir()) == []


def test_an_unexpected_failure_is_one_line_with_its_class_and_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "shop.toml").write_text(PILOT_TOML, encoding="utf-8")
    monkeypatch.setattr(harness, "replay", fail_with_canary)

    code = cli.main(command_line("run", REQUIRED))

    # Neither the note nor the cause, nor a traceback.
    assert code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == f"replay: CanaryError: {WITNESS}\n"


@pytest.mark.parametrize("option", ["--pilot", "--manifest"])
def test_a_pilot_or_a_manifest_with_no_file_ends_the_replay_with_1(
    option: str, shop: Shop, capsys: pytest.CaptureFixture[str]
) -> None:
    # read_pilot and read_manifest raise, with no fixed type or message.
    options = {**options_of(shop), option: str(shop.work / "missing")}

    code = cli.main(command_line("run", options))

    assert code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert re.fullmatch(r"replay: \w+: .*\n", output.err)
    assert list(shop.work.iterdir()) == []


def test_python_m_replay_exits_with_what_main_returns(tmp_path: Path) -> None:
    # The working directory holds no pilot's file, so main writes its line
    # and returns 1. A process that ended without the exit code main returns
    # would exit with 0.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-P", "-m", "replay", *command_line("run", REQUIRED)],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(SRC)},
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr.startswith(b"replay: ")
