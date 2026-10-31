from pathlib import Path
from types import ModuleType
from typing import NoReturn

import pytest

from distiller import cli, evaluate, report

# evaluate's required options, each with a value, as on a command line.
REQUIRED = {
    "--pr": "7",
    "--head": "H",
    "--base": "origin/main",
    "--coverage": "m.coverage",
    "--coverage-commit": "M",
    "--junit": "junit.xml",
    "--records": "records.jsonl",
}

WITNESS = "canary-6f2a"


class CanaryError(Exception):
    pass


def command_line(command: str, options: dict[str, str]) -> list[str]:
    words = [command]
    for option, value in options.items():
        words.extend((option, value))
    return words


def without(options: dict[str, str], option: str) -> dict[str, str]:
    return {key: value for key, value in options.items() if key != option}


def run_args_from(argv: list[str], monkeypatch: pytest.MonkeyPatch) -> evaluate.RunArgs:
    received: list[evaluate.RunArgs] = []

    def fake_run(args: evaluate.RunArgs) -> int:
        received.append(args)
        return 3

    monkeypatch.setattr(evaluate, "run", fake_run)
    assert cli.main(argv) == 3
    [args] = received
    return args


def assert_usage_error(
    argv: list[str], directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(argv)

    assert exit_info.value.code == 2
    assert capsys.readouterr().out == ""
    assert list(directory.iterdir()) == []


def fail_with_canary(*_args: object) -> NoReturn:
    error = CanaryError(WITNESS)
    error.add_note(WITNESS)
    raise error from OSError(WITNESS)


def test_evaluate_gets_its_options_as_run_args(monkeypatch: pytest.MonkeyPatch) -> None:
    args = run_args_from(command_line("evaluate", REQUIRED), monkeypatch)

    assert args == evaluate.RunArgs(
        pr=7,
        head="H",
        base="origin/main",
        coverage="m.coverage",
        coverage_commit="M",
        junit="junit.xml",
        rerun=None,
        rootdir="",
        floor_config=None,
        records="records.jsonl",
        checkout=".",
    )


def test_evaluate_gets_its_optional_options(monkeypatch: pytest.MonkeyPatch) -> None:
    options = {
        **REQUIRED,
        "--rerun": "rerun.xml",
        "--rootdir": "backend",
        "--floor-config": "floor.txt",
        "--checkout": "pilot",
    }

    args = run_args_from(command_line("evaluate", options), monkeypatch)

    assert (args.rerun, args.rootdir, args.floor_config, args.checkout) == (
        "rerun.xml",
        "backend",
        "floor.txt",
        "pilot",
    )


@pytest.mark.parametrize(
    ("given", "rootdir"),
    [
        (".", ""),
        ("", ""),
        ("./backend", "backend"),
        ("backend/", "backend"),
        ("backend/./tests", "backend/tests"),
    ],
)
def test_rootdir_drops_its_empty_and_dot_segments(
    given: str, rootdir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv = command_line("evaluate", {**REQUIRED, "--rootdir": given})

    assert run_args_from(argv, monkeypatch).rootdir == rootdir


def test_report_gets_the_record_files(monkeypatch: pytest.MonkeyPatch) -> None:
    received: list[list[str]] = []

    def fake_run(paths: list[str]) -> int:
        received.append(paths)
        return 0

    monkeypatch.setattr(report, "run", fake_run)

    assert cli.main(["report", "a.jsonl", "b.jsonl"]) == 0
    assert received == [["a.jsonl", "b.jsonl"]]


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param([], id="no command"),
        pytest.param(["frobnicate"], id="unknown command"),
        pytest.param(command_line("evaluat", REQUIRED), id="abbreviated command"),
        pytest.param(
            command_line("evaluate", without(REQUIRED, "--junit")), id="missing option"
        ),
        pytest.param(
            command_line("evaluate", {**REQUIRED, "--bogus": "x"}), id="unknown option"
        ),
        # --rec could only be --records: only allow_abbrev=False rejects it.
        pytest.param(
            command_line(
                "evaluate", {**without(REQUIRED, "--records"), "--rec": "r.jsonl"}
            ),
            id="abbreviated option",
        ),
        # --cov could be --coverage or --coverage-commit.
        pytest.param(
            command_line("evaluate", {**without(REQUIRED, "--coverage"), "--cov": "m"}),
            id="ambiguous option",
        ),
        pytest.param(["report"], id="report without record files"),
    ],
)
def test_a_malformed_command_line_is_a_usage_error(
    argv: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert_usage_error(argv, tmp_path, capsys)


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--pr", "0"),
        ("--pr", "00"),
        ("--pr", "-1"),
        ("--pr", "seven"),
        ("--pr", "\u0663"),  # ARABIC-INDIC DIGIT THREE, which int() takes
        ("--rootdir", "/srv/shop"),
        ("--rootdir", ".."),
        ("--rootdir", "backend/../tests"),
    ],
)
def test_a_value_out_of_its_rules_is_a_usage_error(
    option: str,
    value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert_usage_error(
        command_line("evaluate", {**REQUIRED, option: value}), tmp_path, capsys
    )


@pytest.mark.parametrize(
    ("module", "argv"),
    [
        pytest.param(evaluate, command_line("evaluate", REQUIRED), id="evaluate"),
        pytest.param(report, ["report", "records.jsonl"], id="report"),
    ],
)
def test_an_unexpected_failure_is_one_line_that_names_only_its_class(
    module: ModuleType,
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(module, "run", fail_with_canary)

    assert cli.main(argv) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == "distiller: unexpected failure: CanaryError\n"
    assert WITNESS not in output.err
