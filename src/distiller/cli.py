import argparse
import sys

from distiller import evaluate, messages, report


def main(argv: list[str] | None = None) -> int:
    try:
        return _run_command(argv)
    except Exception as error:  # noqa: BLE001
        # One line that names the class, never the text: a library's error can
        # quote what a file holds.
        print(messages.unexpected_failure(type(error)), file=sys.stderr)
        return 1


def _run_command(argv: list[str] | None) -> int:
    # A usage error raises SystemExit(2) here, which main lets through.
    options = _parser().parse_args(argv)
    if options.command == "evaluate":
        return evaluate.run(_run_args(options))
    return report.run(options.record_files)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m distiller", allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)

    # Subparsers do not inherit allow_abbrev, so each one sets it again.
    evaluate_command = commands.add_parser("evaluate", allow_abbrev=False)
    evaluate_command.add_argument("--pr", required=True, type=pr_number, metavar="N")
    evaluate_command.add_argument("--head", required=True, metavar="REV")
    evaluate_command.add_argument("--base", required=True, metavar="REV")
    evaluate_command.add_argument("--coverage", required=True, metavar="PATH")
    evaluate_command.add_argument("--coverage-commit", required=True, metavar="REV")
    evaluate_command.add_argument("--junit", required=True, metavar="PATH")
    evaluate_command.add_argument("--rerun", metavar="PATH")
    evaluate_command.add_argument("--rootdir", type=rootdir, default="", metavar="DIR")
    evaluate_command.add_argument("--floor-config", metavar="PATH")
    evaluate_command.add_argument("--records", required=True, metavar="PATH")
    evaluate_command.add_argument("--checkout", default=".", metavar="DIR")

    report_command = commands.add_parser("report", allow_abbrev=False)
    report_command.add_argument("record_files", nargs="+", metavar="RECORD_FILE")
    return parser


# argparse turns a ValueError from these two into a usage error that names the
# function and quotes the value: "argument --pr: invalid pr_number value: '0'".


def pr_number(text: str) -> int:
    # ASCII digits only, since int() also takes other scripts' digits.
    if not (text.isascii() and text.isdigit()) or int(text) == 0:
        raise ValueError
    return int(text)


def rootdir(text: str) -> str:
    segments = text.split("/")
    if text.startswith("/") or ".." in segments:
        raise ValueError
    # "." and "" are the repository root; "./backend" and "backend/" are "backend".
    return "/".join(segment for segment in segments if segment not in {"", "."})


def _run_args(options: argparse.Namespace) -> evaluate.RunArgs:
    return evaluate.RunArgs(
        pr=options.pr,
        head=options.head,
        base=options.base,
        coverage=options.coverage,
        coverage_commit=options.coverage_commit,
        junit=options.junit,
        rerun=options.rerun,
        rootdir=options.rootdir,
        floor_config=options.floor_config,
        records=options.records,
        checkout=options.checkout,
    )
