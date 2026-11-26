import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

import pytest

from replay import harness, tool
from replay.pilot import Pilot
from replay.steps import ToolInputs

# The tests replay a small pilot, shop, through harness.replay: its clone holds
# a base branch and the heads of eight pull requests, each of a shape that the
# SPEC names. Its environments are built with no network, from local commands
# and a fake uv; its suites run inside bubblewrap; and the real tool, this
# repository, evaluates each run. The replay runs twice, first for one pull
# request alone, so that the second starts again. Decided by the user on
# 2026-11-19, for the SPEC: one work directory for both pilots, a log for each,
# <work>/<project>.log, a JSON object a line, and a summary of every log there,
# <work>/summary.txt; no replay starts when the log names another manifest, nor
# when the record file holds records and the work directory no log of the
# pilot; a pull request with no base commit or no merge-base is not replayed
# either; a red pull request is one whose record says caught or missed; and a
# failure is inherited when its test failed in the full run and in the
# coverage run at M.

# A replay of shop builds 13 environments and runs 13 suites.
pytestmark = pytest.mark.timeout(600)

GIT = shutil.which("git") or "git"

# This repository: the real tool, with its own .venv.
REPOSITORY = Path(__file__).resolve().parents[2]

# The site-packages of the environment that runs these tests, which shop's
# environments add to their own: pytest and its plugins, no network.
TESTS_SITE_PACKAGES = sysconfig.get_paths()["purelib"]

# When the window's runs started: after every commit of the base branch.
RUN_STARTED = "2026-11-10T00:00:00Z"

UNKNOWN_COMMIT = "0123456789abcdef0123456789abcdef01234567"

PYPROJECT = '[tool.pytest.ini_options]\npythonpath = ["."]\n'
BASE_LOCK = "the base's lock\n"
HEAD_LOCK = "the head's lock\n"

RESPONSE = """\
TEXTS = {200: "OK", 201: "Created", 202: "Accepted", 203: "Partial", 204: "Empty"}


def status_text(code):
    return TEXTS[code]
"""
# Every text in lower case: the five tests of test/test_response.py fail.
RESPONSE_BROKEN = """\
TEXTS = {200: "ok", 201: "created", 202: "accepted", 203: "partial", 204: "empty"}


def status_text(code):
    return TEXTS[code]
"""
RESPONSE_TESTS = """\
import pytest

from shop.response import status_text

TEXTS = [
    (200, "OK"),
    (201, "Created"),
    (202, "Accepted"),
    (203, "Partial"),
    (204, "Empty"),
]


@pytest.mark.parametrize(("code", "text"), TEXTS)
def test_status_text(code, text):
    assert status_text(code) == text
"""
TAX_BROKEN = "RATE = 0\n\n\ndef vat(amount):\n    return amount * RATE // 100\n"
TAX = "RATE = 21\n\n\ndef vat(amount):\n    return amount * RATE // 100\n"
TAX_TESTS = "from shop.tax import vat\n\n\ndef test_vat():\n    assert vat(100) == 21\n"
ADDED_TESTS = """\
from shop.response import status_text


def test_added_one():
    assert status_text(200) == "Okay"


def test_added_two():
    assert status_text(204) == "Nothing"
"""
INTERNAL_ERROR_CONFTEST = """\
def pytest_collection_modifyitems(items):
    raise RuntimeError("an internal error of pytest")
"""

# shop's environment, built with no network: a lock file that holds "broken"
# fails it, then a venv whose .pth file adds these tests' own site-packages.
CHECK_LOCK = (
    "import pathlib, sys; "
    "sys.exit('broken' in pathlib.Path('uv.lock').read_text(encoding='utf-8'))"
)
WRITE_PTH = (
    "import pathlib, sys; "
    "version = 'python%d.%d' % sys.version_info[:2]; "
    "site = pathlib.Path('.venv', 'lib', version, 'site-packages'); "
    "pth = site / 'tests-packages.pth'; "
    "pth.write_text(sys.argv[1] + chr(10), encoding='utf-8')"
)
ENVIRONMENT = (
    (sys.executable, "-c", CHECK_LOCK),
    (sys.executable, "-m", "venv", "--without-pip", ".venv"),
    (sys.executable, "-c", WRITE_PTH, TESTS_SITE_PACKAGES),
)

PILOT = Pilot(
    project="shop",
    repository="example/shop",
    base_branch="main",
    job="Ubuntu 3.12",
    python="3.12",
    environment=ENVIRONMENT,
    pytest=("--color=yes",),  # colour codes, which the log must not keep
    coverage_source="shop",
    seconds_per_test=30,
    adds_timeout_plugin=False,
    floor_config=None,
)

# A uv that installs nothing: the plugins are in the environment already.
FAKE_UV = "#!{python} -I\nimport sys\nsys.exit(0)\n"

# Each pull request of shop's window, by number, with its run, and the shape
# that the SPEC names: K16's five failed tests in test/test_response.py,
# Replaying 1's two added tests that fail, K17's internal error of pytest, an
# environment that cannot be built at the head, a head not in the clone,
# Replaying 5's failure inherited from M, a run that started before the base
# branch's first commit, and a head with no history in common with the base.
RUNS = {
    5375: 1001,
    10980: 1002,
    11226: 1003,
    9001: 1004,
    9002: 1005,
    9003: 1006,
    9004: 1007,
    9005: 1008,
}
STARTED = {9004: "2026-01-01T00:00:00Z"}

MANIFEST_COLUMNS: tuple[str, ...] = (
    "project",
    "pull_request",
    "run_id",
    "run_started",
    "head",
    "job",
    "failed_steps",
)


@dataclass(frozen=True)
class Replayed:
    """What the two replays of shop left, and where."""

    work: Path
    clone: Path
    records: Path
    manifest: Path
    heads: dict[int, str]  # each pull request's tested head, by number
    main: str  # the base branch's last commit
    exit_codes: tuple[int, int]


@pytest.fixture(scope="module")
def replayed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Replayed]:
    root = tmp_path_factory.mktemp("harness")
    with pytest.MonkeyPatch.context() as patch:
        isolate(patch, root)
        clone = root / "clone"
        heads, main = build_clone(clone)
        manifest = write_manifest(root / "manifest.csv", rows_of(heads))
        work = root / "work"
        work.mkdir()
        records = root / "records" / "shop.jsonl"
        records.parent.mkdir()
        first = run_replay(manifest, clone, work, records, only=[5375])
        write_other_pilots_log(work)
        second = run_replay(manifest, clone, work, records, only=None)
        yield Replayed(
            work=work,
            clone=clone,
            records=records,
            manifest=manifest,
            heads=heads,
            main=main,
            exit_codes=(first, second),
        )


def isolate(patch: pytest.MonkeyPatch, root: Path) -> None:
    """Keep git to the repositories' own settings, hide the user's home, and
    put a uv that installs nothing first on PATH."""
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
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_uv = fake_bin / "uv"
    fake_uv.write_text(FAKE_UV.format(python=sys.executable), encoding="utf-8")
    fake_uv.chmod(0o700)
    patch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ['PATH']}")


def run_git(
    directory: Path, *arguments: str, environment: dict[str, str] | None = None
) -> str:
    """Run the real git in directory, as the tests' setup does; return its stdout."""
    result = subprocess.run(  # noqa: S603
        [GIT, "-C", str(directory), *arguments],
        capture_output=True,
        check=False,
        env={**os.environ, **(environment or {})},
    )
    assert result.returncode == 0, os.fsdecode(result.stderr)
    return os.fsdecode(result.stdout)


def commit_at(repository: Path, date: str, files: dict[str, str]) -> str:
    """Commit the files at date; return the new commit's full id."""
    for name, text in files.items():
        path = repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    run_git(repository, "add", "--all")
    dates = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    run_git(repository, "commit", "--quiet", "--message", "Change", environment=dates)
    return run_git(repository, "rev-parse", "HEAD").strip()


def head_from(clone: Path, start: str, pull_request: int, files: dict[str, str]) -> str:
    """A pull request's head made from start, kept by its run's ref alone."""
    run_git(clone, "switch", "--quiet", "--detach", start)
    head = commit_at(clone, "2026-03-03T10:00:00+00:00", files)
    run_git(clone, "update-ref", f"refs/window/{RUNS[pull_request]}", head)
    return head


def build_clone(clone: Path) -> tuple[dict[int, str], str]:
    """shop's clone: main, whose second commit fixes a test that its first
    fails, and the heads of the window's pull requests."""
    clone.mkdir()
    run_git(clone, "init", "--quiet", "--initial-branch=main")
    first = commit_at(
        clone,
        "2026-03-01T10:00:00+00:00",
        {
            "pyproject.toml": PYPROJECT,
            "uv.lock": BASE_LOCK,
            "shop/__init__.py": "",
            "shop/response.py": RESPONSE,
            "shop/tax.py": TAX_BROKEN,
            "test/test_response.py": RESPONSE_TESTS,
            "test/test_tax.py": TAX_TESTS,
        },
    )
    main = commit_at(clone, "2026-03-02T10:00:00+00:00", {"shop/tax.py": TAX})
    heads = {
        5375: head_from(clone, main, 5375, {"shop/response.py": RESPONSE_BROKEN}),
        10980: head_from(
            clone,
            main,
            10980,
            {"test/test_added.py": ADDED_TESTS, "uv.lock": HEAD_LOCK},
        ),
        11226: head_from(clone, main, 11226, {"conftest.py": INTERNAL_ERROR_CONFTEST}),
        9001: head_from(clone, main, 9001, {"uv.lock": "broken\n"}),
        9002: UNKNOWN_COMMIT,
        9003: head_from(clone, first, 9003, {"README.md": "A shop.\n"}),
    }
    heads[9004] = heads[5375]
    run_git(clone, "switch", "--quiet", "--orphan", "unrelated")
    heads[9005] = commit_at(
        clone, "2026-03-03T10:00:00+00:00", {"NOTES.md": "Elsewhere.\n"}
    )
    run_git(clone, "update-ref", f"refs/window/{RUNS[9005]}", heads[9005])
    run_git(clone, "switch", "--quiet", "main")
    run_git(clone, "branch", "--quiet", "--delete", "--force", "unrelated")
    return heads, main


def rows_of(heads: dict[int, str]) -> list[dict[str, str]]:
    return [
        {
            "project": "shop",
            "pull_request": str(number),
            "run_id": str(RUNS[number]),
            "run_started": STARTED.get(number, RUN_STARTED),
            "head": heads[number],
            "job": "failed in a test step",
            "failed_steps": "",
        }
        for number in RUNS
    ]


def write_manifest(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_other_pilots_log(work: Path) -> None:
    """The log of another pilot's replay in the same work directory: one pull
    request replayed, red, with an inherited failure, and one not replayed."""
    entries: list[dict[str, object]] = [
        {"event": "start", "manifest_sha256": "0" * 64, "pilot": "other"},
        {
            "event": "done",
            "pull_request": 1,
            "replayed": True,
            "why": None,
            "verdict": "caught",
            "inherited": ["test/test_a.py::test_a"],
        },
        {
            "event": "done",
            "pull_request": 2,
            "replayed": False,
            "why": "head not in the clone",
            "verdict": None,
            "inherited": [],
        },
    ]
    lines = "".join(json.dumps(entry) + "\n" for entry in entries)
    (work / "other.log").write_text(lines, encoding="utf-8")


def run_replay(
    manifest: Path, clone: Path, work: Path, records: Path, only: list[int] | None
) -> int:
    return harness.replay(
        PILOT,
        manifest=str(manifest),
        clone=str(clone),
        work=str(work),
        records=str(records),
        tool=str(REPOSITORY),
        only=only,
    )


def log_of(work: Path, pilot: str = "shop") -> list[dict[str, Any]]:
    lines = (work / f"{pilot}.log").read_text(encoding="utf-8").splitlines()
    return [cast("dict[str, Any]", json.loads(line)) for line in lines]


def done_of(replayed: Replayed, pull_request: int) -> dict[str, Any]:
    """The pull request's done entry, which the log must hold once."""
    (done,) = [
        entry
        for entry in log_of(replayed.work)
        if entry["event"] == "done" and entry["pull_request"] == pull_request
    ]
    return done


def steps_of(replayed: Replayed, pull_request: int, step: str) -> list[dict[str, Any]]:
    return [
        entry
        for entry in log_of(replayed.work)
        if entry["event"] == "step"
        and entry["pull_request"] == pull_request
        and entry["step"] == step
    ]


def inputs_of(replayed: Replayed, pull_request: int) -> dict[str, Any]:
    """The inputs that the replay gave the tool for the pull request."""
    (tool_step,) = steps_of(replayed, pull_request, "tool")
    return cast("dict[str, Any]", tool_step["inputs"])


def records_of(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [cast("dict[str, Any]", json.loads(line)) for line in lines]


def outcomes(junit: str) -> dict[str, str]:
    """Each test case of a JUnit file, as classname::name, with how it ended:
    passed, failure, error or skipped."""
    # The file comes from the replay's own pytest run, so xml's parser will do.
    root = ET.parse(junit).getroot()  # noqa: S314
    found: dict[str, str] = {}
    for case in root.iter("testcase"):
        outcome = "passed"
        for child in case:
            if child.tag in ("failure", "error", "skipped"):
                outcome = child.tag
        found[f"{case.get('classname')}::{case.get('name')}"] = outcome
    return found


def failures_in(junit: str) -> set[str]:
    return {name for name, outcome in outcomes(junit).items() if outcome == "failure"}


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_both_replays_end_with_exit_code_0(replayed: Replayed) -> None:
    assert replayed.exit_codes == (0, 0)


def test_the_logs_first_line_names_the_manifests_sha256(replayed: Replayed) -> None:
    # Rule 2.
    first = log_of(replayed.work)[0]

    assert first["event"] == "start"
    assert (
        first["manifest_sha256"]
        == hashlib.sha256(replayed.manifest.read_bytes()).hexdigest()
    )


def test_k16s_full_run_fails_five_tests_of_test_response_and_the_rerun_again(
    replayed: Replayed,
) -> None:
    # K16's shape: the full run's JUnit holds 5 failed tests, all in
    # test/test_response.py, the rerun file holds those 5 run again, and one
    # record is appended to the pilot's record file.
    inputs = inputs_of(replayed, 5375)

    failed = failures_in(inputs["junit_file"])
    assert len(failed) == 5
    assert all(name.startswith("test.test_response::") for name in failed)
    assert outcomes(inputs["rerun_file"]) == dict.fromkeys(failed, "failure")
    pull_requests = [record["pr"] for record in records_of(replayed.records)]
    assert pull_requests.count(5375) == 1


def test_the_tests_that_a_pull_request_adds_fail_in_the_full_run_and_again(
    replayed: Replayed,
) -> None:
    # Replaying 1's shape: the full run fails the two tests that the pull
    # request adds, the rerun fails them again, and one record is appended.
    inputs = inputs_of(replayed, 10980)

    added = {"test.test_added::test_added_one", "test.test_added::test_added_two"}
    assert failures_in(inputs["junit_file"]) == added
    assert outcomes(inputs["rerun_file"]) == dict.fromkeys(added, "failure")
    pull_requests = [record["pr"] for record in records_of(replayed.records)]
    assert pull_requests.count(10980) == 1


def test_k17s_internal_error_of_pytest_is_rejected_as_unusable_junit(
    replayed: Replayed,
) -> None:
    (record,) = [
        record for record in records_of(replayed.records) if record["pr"] == 11226
    ]

    assert record["verdict"] == "rejected"
    assert record["reason"] == "unusable-input"
    assert record["input"] == "junit"
    assert done_of(replayed, 11226)["verdict"] == "rejected"


def test_the_log_names_the_sha256_of_each_environments_lock_file(
    replayed: Replayed,
) -> None:
    # Replaying 2: a tested head whose lock file differs from its M's.
    (at_m,) = steps_of(replayed, 10980, "environment at M")
    (at_head,) = steps_of(replayed, 10980, "environment at the head")

    assert at_m["lock_files"] == {"uv.lock": sha256_of(BASE_LOCK)}
    assert at_head["lock_files"] == {"uv.lock": sha256_of(HEAD_LOCK)}


def test_a_failure_at_the_tested_head_and_at_m_is_marked_inherited(
    replayed: Replayed,
) -> None:
    # Replaying 5: test_vat fails at the head of 9003 and at its M, main's
    # first commit.
    assert done_of(replayed, 9003)["inherited"] == ["test/test_tax.py::test_vat"]
    assert done_of(replayed, 5375)["inherited"] == []


@pytest.mark.parametrize(
    ("pull_request", "why"),
    [
        (9001, "environment at the head not built"),
        (9002, "head not in the clone"),
        (9004, "no base commit before the run"),
        (9005, "no common history with the base"),
    ],
)
def test_a_pull_request_not_replayed_has_its_reason_and_no_record(
    replayed: Replayed, pull_request: int, why: str
) -> None:
    done = done_of(replayed, pull_request)

    assert done["replayed"] is False
    assert done["why"] == why
    pull_requests = [record["pr"] for record in records_of(replayed.records)]
    assert pull_request not in pull_requests


def test_a_head_not_in_the_clone_is_listed_before_any_run_starts(
    replayed: Replayed,
) -> None:
    # Manifest 4: in the second replay, 9002's done entry comes before its
    # first step.
    entries = log_of(replayed.work)
    last_start = max(
        index for index, entry in enumerate(entries) if entry["event"] == "start"
    )
    after = entries[last_start:]
    first_step = next(
        index for index, entry in enumerate(after) if entry["event"] == "step"
    )
    missing = next(
        index
        for index, entry in enumerate(after)
        if entry["event"] == "done" and entry["pull_request"] == 9002
    )
    assert missing < first_step


def test_an_environment_that_cannot_be_built_is_logged_with_its_exit_code(
    replayed: Replayed,
) -> None:
    (at_head,) = steps_of(replayed, 9001, "environment at the head")

    assert at_head["exit_code"] == 1


def test_one_record_is_appended_for_each_pull_request_replayed(
    replayed: Replayed,
) -> None:
    pull_requests = [record["pr"] for record in records_of(replayed.records)]

    assert pull_requests == [5375, 10980, 11226, 9003]


def test_a_replay_started_again_starts_at_the_first_pull_request_not_done(
    replayed: Replayed,
) -> None:
    # Replaying 6: the first replay did 5375 alone; the second did not do it
    # again.
    entries = log_of(replayed.work)

    assert [entry["event"] for entry in entries].count("start") == 2
    assert len(steps_of(replayed, 5375, "tool")) == 1
    done_entries = [entry for entry in entries if entry["event"] == "done"]
    assert sorted(entry["pull_request"] for entry in done_entries) == sorted(RUNS)


def test_the_kept_inputs_evaluated_again_give_a_byte_identical_record_file(
    replayed: Replayed, tmp_path: Path
) -> None:
    # Invariants 1.
    again = tmp_path / "again.jsonl"
    tool_steps = [
        entry
        for entry in log_of(replayed.work)
        if entry["event"] == "step" and entry["step"] == "tool"
    ]

    for tool_step in tool_steps:
        kept = ToolInputs(**cast("dict[str, Any]", tool_step["inputs"]))
        tool.evaluate(str(REPOSITORY), replace(kept, records=str(again)))

    assert again.read_bytes() == replayed.records.read_bytes()


def test_the_clones_checkout_is_as_it_was(replayed: Replayed) -> None:
    # Invariants 3: whatever each pull request's outcome, its worktrees are
    # removed.
    assert run_git(replayed.clone, "rev-parse", "HEAD").strip() == replayed.main
    assert run_git(replayed.clone, "status", "--porcelain") == ""
    listing = run_git(replayed.clone, "worktree", "list", "--porcelain")
    assert [line for line in listing.splitlines() if line.startswith("worktree ")] == [
        f"worktree {replayed.clone}"
    ]


def test_the_log_keeps_each_steps_output_without_colour_codes(
    replayed: Replayed,
) -> None:
    # Rule 9: pytest ran with --color=yes.
    outputs = [
        entry["output"] for entry in log_of(replayed.work) if entry["event"] == "step"
    ]

    assert any("passed" in output for output in outputs)
    assert not any("\x1b" in output for output in outputs)


def test_the_summary_counts_each_pilot_and_both(replayed: Replayed) -> None:
    # Summary 2: replayed, not replayed and why, red, and inherited failures,
    # for each pilot and for both.
    summary = (replayed.work / "summary.txt").read_text(encoding="utf-8")

    assert summary.splitlines() == [
        "other: replayed 1, not replayed 1, red 1, inherited failures 1",
        "other: not replayed, head not in the clone: 1",
        "shop: replayed 4, not replayed 4, red 3, inherited failures 1",
        "shop: not replayed, environment at the head not built: 1",
        "shop: not replayed, head not in the clone: 1",
        "shop: not replayed, no base commit before the run: 1",
        "shop: not replayed, no common history with the base: 1",
        "both: replayed 5, not replayed 5, red 4, inherited failures 2",
        "both: not replayed, environment at the head not built: 1",
        "both: not replayed, head not in the clone: 2",
        "both: not replayed, no base commit before the run: 1",
        "both: not replayed, no common history with the base: 1",
    ]


def test_another_manifest_over_the_same_work_replays_nothing_and_says_so(
    replayed: Replayed, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Rule 2 and Invariants 4: one more row makes another manifest.
    rows = rows_of(replayed.heads)
    other = write_manifest(
        tmp_path / "manifest.csv", [*rows, {**rows[0], "pull_request": "9006"}]
    )
    log_before = (replayed.work / "shop.log").read_bytes()
    records_before = replayed.records.read_bytes()
    capsys.readouterr()

    code = run_replay(other, replayed.clone, replayed.work, replayed.records, None)

    assert code == 1
    assert (replayed.work / "shop.log").read_bytes() == log_before
    assert replayed.records.read_bytes() == records_before
    assert capsys.readouterr().err != ""


def test_a_record_file_with_records_and_no_log_replays_nothing(
    replayed: Replayed, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Which manifest the records came from, no log in this work directory says.
    work = tmp_path / "work"
    work.mkdir()
    records_before = replayed.records.read_bytes()
    capsys.readouterr()

    code = run_replay(replayed.manifest, replayed.clone, work, replayed.records, None)

    assert code == 1
    assert replayed.records.read_bytes() == records_before
    assert not (work / "shop.log").exists()
    assert capsys.readouterr().err != ""


def test_a_problem_of_the_manifest_stops_the_replay_before_it_starts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A row with no pull request number: the replay does not start.
    heads = dict.fromkeys(RUNS, UNKNOWN_COMMIT)
    rows = rows_of(heads)
    manifest = write_manifest(
        tmp_path / "manifest.csv", [{**rows[0], "pull_request": ""}, *rows[1:]]
    )
    work = tmp_path / "work"
    work.mkdir()

    code = run_replay(
        manifest, tmp_path / "no-clone", work, tmp_path / "records.jsonl", None
    )

    assert code == 1
    assert list(work.iterdir()) == []
    assert capsys.readouterr().err != ""


def test_a_pull_request_that_the_pilots_lines_lack_stops_the_replay(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = write_manifest(
        tmp_path / "manifest.csv", rows_of(dict.fromkeys(RUNS, UNKNOWN_COMMIT))
    )
    work = tmp_path / "work"
    work.mkdir()

    code = harness.replay(
        PILOT,
        manifest=str(manifest),
        clone=str(tmp_path / "no-clone"),
        work=str(work),
        records=str(tmp_path / "records.jsonl"),
        tool=str(REPOSITORY),
        only=[1234],
    )

    assert code == 1
    assert not (work / "shop.log").exists()
    assert capsys.readouterr().err != ""


# K18's shape (Slice 3, D-031): a pull request of a pilot whose pyproject.toml
# asks for a required-version that the uv on the PATH does not meet, as
# pydantic's #14290 asks uv 0.11.23 for >=0.13.0. The pilot adds pytest-timeout,
# as pydantic's does, so that both of its environments get a plugin; and its
# uv, as uv itself does, refuses to run in such a project, which it looks for in
# its working folder and in each folder above it.
K18_RUN = 1009
K18_PYPROJECT = PYPROJECT + '\n[tool.uv]\nrequired-version = ">=99"\n'
K18_PILOT = replace(PILOT, adds_timeout_plugin=True)
REFUSING_UV = """\
#!{python} -I
import sys
from pathlib import Path

here = Path.cwd()
for folder in (here, *here.parents):
    project = folder / "pyproject.toml"
    if project.is_file():
        if "required-version" in project.read_text(encoding="utf-8"):
            print("error: Required uv version", file=sys.stderr)
            sys.exit(2)
sys.exit(0)
"""


@dataclass(frozen=True)
class ReplayedK18:
    """What the replay of K18's shape left."""

    work: Path
    records: Path
    exit_code: int


@pytest.fixture(scope="module")
def replayed_k18(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ReplayedK18]:
    root = tmp_path_factory.mktemp("harness-k18")
    with pytest.MonkeyPatch.context() as patch:
        isolate(patch, root)
        refusing_uv = root / "fake-bin" / "uv"
        refusing_uv.write_text(
            REFUSING_UV.format(python=sys.executable), encoding="utf-8"
        )
        clone = root / "clone"
        head = build_k18_clone(clone)
        row = {
            "project": "shop",
            "pull_request": "14290",
            "run_id": str(K18_RUN),
            "run_started": RUN_STARTED,
            "head": head,
            "job": "failed in a test step",
            "failed_steps": "",
        }
        manifest = write_manifest(root / "manifest.csv", [row])
        work = root / "work"
        work.mkdir()
        records = root / "records" / "shop.jsonl"
        records.parent.mkdir()
        code = harness.replay(
            K18_PILOT,
            manifest=str(manifest),
            clone=str(clone),
            work=str(work),
            records=str(records),
            tool=str(REPOSITORY),
            only=None,
        )
        yield ReplayedK18(work=work, records=records, exit_code=code)


def build_k18_clone(clone: Path) -> str:
    """A clone whose pyproject.toml asks for a required-version, with the head of
    one pull request, K16's change, kept by its run's ref; return that head."""
    clone.mkdir()
    run_git(clone, "init", "--quiet", "--initial-branch=main")
    main = commit_at(
        clone,
        "2026-03-01T10:00:00+00:00",
        {
            "pyproject.toml": K18_PYPROJECT,
            "uv.lock": BASE_LOCK,
            "shop/__init__.py": "",
            "shop/response.py": RESPONSE,
            "shop/tax.py": TAX,
            "test/test_response.py": RESPONSE_TESTS,
            "test/test_tax.py": TAX_TESTS,
        },
    )
    run_git(clone, "switch", "--quiet", "--detach", main)
    head = commit_at(
        clone, "2026-03-03T10:00:00+00:00", {"shop/response.py": RESPONSE_BROKEN}
    )
    run_git(clone, "update-ref", f"refs/window/{K18_RUN}", head)
    run_git(clone, "switch", "--quiet", "main")
    return head


def test_k18s_environments_are_built_with_their_plugins_and_one_record_appended(
    replayed_k18: ReplayedK18,
) -> None:
    # K18's shape: both of its environments are built, the plugins' install
    # among their steps, and one record is appended to the pilot's record file.
    built = [
        entry
        for entry in log_of(replayed_k18.work)
        if entry["event"] == "step"
        and entry["step"] in ("environment at M", "environment at the head")
    ]

    assert replayed_k18.exit_code == 0
    assert [entry["step"] for entry in built] == [
        "environment at M",
        "environment at the head",
    ]
    assert all(entry["exit_code"] == 0 for entry in built)
    assert all("pip install" in entry["output"] for entry in built)
    assert [record["pr"] for record in records_of(replayed_k18.records)] == [14290]
