import argparse
import sys
from pathlib import Path

from replay import harness
from replay.pilot import read_pilot


def main(argv: list[str] | None = None) -> int:
    try:
        return _run_command(argv)
    except Exception as error:  # noqa: BLE001
        # One line, with the class and its text, for the user at the terminal.
        sys.stderr.write(f"replay: {type(error).__name__}: {error}\n")
        return 1


def _run_command(argv: list[str] | None) -> int:
    # A usage error raises SystemExit(2) here, which main lets through.
    options = _parser().parse_args(argv)
    pilot = read_pilot(options.pilot)
    work = _absolute(options.work)
    exit_code = harness.replay(
        pilot,
        manifest=_absolute(options.manifest),
        clone=_absolute(options.clone),
        work=work,
        records=_absolute(options.records),
        tool=_absolute(options.tool),
        only=options.only,
    )
    if exit_code == 0:
        summary = Path(work) / "summary.txt"
        sys.stdout.write(summary.read_text(encoding="utf-8"))
    return exit_code


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m replay", allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)

    # Subparsers do not inherit allow_abbrev, so run sets it again.
    run_command = commands.add_parser("run", allow_abbrev=False)
    run_command.add_argument("--pilot", required=True, metavar="PATH")
    run_command.add_argument("--manifest", required=True, metavar="PATH")
    run_command.add_argument("--clone", required=True, metavar="DIR")
    run_command.add_argument("--work", required=True, metavar="DIR")
    run_command.add_argument("--records", required=True, metavar="PATH")
    run_command.add_argument("--tool", required=True, metavar="DIR")
    run_command.add_argument("--only", nargs="+", type=int, metavar="N")
    return parser


def _absolute(path: str) -> str:
    # The replay runs git and the tool in other directories, where a relative
    # path would name something else; resolve also drops any "..".
    return str(Path(path).resolve())
