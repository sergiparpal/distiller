import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from replay import checkout, suite
from replay.environment import build
from replay.manifest import ManifestLine, missing_heads, problems, read_manifest
from replay.pilot import Pilot
from replay.steps import StepResult, ToolInputs
from replay.tool import evaluate as evaluate_with_tool

# Replays one pilot's pull requests of the manifest, as "How a replay goes"
# says: for each, the base commit and M, a worktree and an environment for
# each, the coverage at M, the full run and its rerun at the tested head, and
# the tool's evaluate. Each pilot's log, <work>/<project>.log, holds one JSON
# object a line: a start for each run, a step for each step, and a done for
# each pull request, which a run started again skips. At the end of a run,
# <work>/summary.txt is written again from every log in the work directory.

# The terminal's colour codes, which the log keeps no output of (Rule 9).
COLOUR_CODES = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

# The lock files whose SHA-256 an environment's step names (Replaying 2).
LOCK_FILES = ("uv.lock", "poetry.lock")

# A pull request is red when its record says one of these.
RED_VERDICTS = ("caught", "missed")

# What a pull request's folder holds: its worktrees, and the inputs kept for
# the tool.
M_WORKTREE = "m"
HEAD_WORKTREE = "head"
M_COVERAGE = "m.coverage"
M_JUNIT = "junit-m.xml"
FULL_RUN_JUNIT = "junit.xml"
RERUN_JUNIT = "rerun.xml"


@dataclass(frozen=True)
class _Replay:
    """What every pull request of one replay shares."""

    pilot: Pilot
    clone: str
    work: Path
    records: str
    tool: str
    log: Path


class _NotReplayedError(Exception):
    """A pull request that is not replayed, with the reason that the log gives."""


def replay(  # noqa: PLR0913, one argument for each option of the command line
    pilot: Pilot,
    *,
    manifest: str,
    clone: str,
    work: str,
    records: str,
    tool: str,
    only: list[int] | None,
) -> int:
    lines, others = _lines_of(pilot, manifest)
    found = problems(lines, others)
    if found:
        return _refuse("\n".join(found))
    log = Path(work) / f"{pilot.project}.log"
    sha256 = _sha256_of(Path(manifest))
    refusal = _manifest_refusal(log, sha256, Path(records)) or _only_refusal(
        lines, only
    )
    if refusal is not None:
        return _refuse(refusal)
    Path(work).mkdir(parents=True, exist_ok=True)
    _append(log, {"event": "start", "manifest_sha256": sha256, "pilot": pilot.project})
    shared = _Replay(
        pilot=pilot, clone=clone, work=Path(work), records=records, tool=tool, log=log
    )
    _replay_lines(shared, _not_done(_chosen(lines, only), log))
    _write_summary(Path(work))
    return 0


def _lines_of(
    pilot: Pilot, manifest: str
) -> tuple[list[ManifestLine], list[ManifestLine]]:
    # The pilot's lines of the manifest, and every other pilot's.
    by_project: dict[str, list[ManifestLine]] = {}
    for line in read_manifest(manifest):
        by_project.setdefault(line.project, []).append(line)
    lines = by_project.pop(pilot.project, [])
    others = [line for project_lines in by_project.values() for line in project_lines]
    return lines, others


def _refuse(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 1


def _manifest_refusal(log: Path, sha256: str, records: Path) -> str | None:
    # Rule 2: a log names the manifest of the replay that wrote it, and with
    # no log, a record file that holds records came from a manifest that
    # nothing names.
    if log.exists():
        first = _entries_of(log)[0]["manifest_sha256"]
        if first != sha256:
            return (
                f"{log} is of another manifest, {first}: "
                f"this one, {sha256}, replays nothing"
            )
        return None
    if _holds_records(records):
        return (
            f"{records} holds records, "
            "and no log in the work directory says of which manifest"
        )
    return None


def _holds_records(records: Path) -> bool:
    return records.exists() and records.read_text(encoding="utf-8").strip() != ""


def _only_refusal(lines: list[ManifestLine], only: list[int] | None) -> str | None:
    if only is None:
        return None
    numbers = {line.pull_request for line in lines}
    lacking = [str(number) for number in only if number not in numbers]
    if lacking:
        return f"the pilot's lines of the manifest hold no #{', #'.join(lacking)}"
    return None


def _chosen(lines: list[ManifestLine], only: list[int] | None) -> list[ManifestLine]:
    if only is None:
        return lines
    return [line for line in lines if line.pull_request in only]


def _not_done(lines: list[ManifestLine], log: Path) -> list[ManifestLine]:
    # Replaying 6: a run started again skips each pull request that the log
    # shows done.
    done = {
        entry["pull_request"] for entry in _entries_of(log) if entry["event"] == "done"
    }
    return [line for line in lines if line.pull_request not in done]


def _replay_lines(shared: _Replay, lines: list[ManifestLine]) -> None:
    # Manifest 4: the heads not in the clone are listed before any step.
    missing = missing_heads(lines, shared.clone)
    for line in missing:
        _done(shared.log, line, why="head not in the clone")
    for line in lines:
        if line not in missing:
            _replay_pull_request(shared, line)


def _replay_pull_request(shared: _Replay, line: ManifestLine) -> None:
    # Whatever happened, the worktrees added are removed (Invariants 3).
    worktrees: list[Path] = []
    try:
        verdict, inherited = _replay_steps(shared, line, worktrees)
    except _NotReplayedError as reason:
        _done(shared.log, line, why=str(reason))
    else:
        _done(shared.log, line, verdict=verdict, inherited=inherited)
    finally:
        for worktree in reversed(worktrees):
            checkout.remove_worktree(shared.clone, str(worktree))


def _replay_steps(
    shared: _Replay, line: ManifestLine, worktrees: list[Path]
) -> tuple[str, list[str]]:
    # The steps of "How a replay goes", 3 to 6; gives the record's verdict and
    # the failures inherited from M.
    base = _base_commit(shared, line)
    m = _merge_base(shared, line, base)
    folder = shared.work / shared.pilot.project / str(line.pull_request)
    folder.mkdir(parents=True, exist_ok=True)
    m_worktree = _add_worktree(shared, m, folder / M_WORKTREE, worktrees)
    _build(shared, line, m_worktree, at_m=True)
    at_m = suite.record_coverage(
        shared.pilot,
        str(m_worktree),
        str(folder),
        str(folder / M_COVERAGE),
        str(folder / M_JUNIT),
    )
    _step(shared.log, line, "coverage at M", at_m)
    head = _add_worktree(shared, line.tested_head, folder / HEAD_WORKTREE, worktrees)
    _build(shared, line, head, at_m=False)
    full, rerun_file = _full_run_and_rerun(shared, line, head, folder)
    inputs = ToolInputs(
        pull_request=_number_of(line),
        head=line.tested_head,
        base=base,
        m=m,
        coverage_file=str(folder / M_COVERAGE),
        junit_file=str(folder / FULL_RUN_JUNIT),
        rerun_file=rerun_file,
        floor_config=shared.pilot.floor_config,
        records=shared.records,
        checkout=shared.clone,
    )
    _step(
        shared.log,
        line,
        "tool",
        evaluate_with_tool(shared.tool, inputs),
        inputs=asdict(inputs),
    )
    inherited = sorted(set(full.failed) & set(at_m.failed))
    return _verdict_of(shared.records, line), inherited


def _number_of(line: ManifestLine) -> int:
    # The manifest's problems stop a replay with a line of no number.
    return int(str(line.pull_request))


def _base_commit(shared: _Replay, line: ManifestLine) -> str:
    base = checkout.base_commit(
        shared.clone, shared.pilot.base_branch, line.run_started
    )
    if base is None:
        reason = "no base commit before the run"
        raise _NotReplayedError(reason)
    return base


def _merge_base(shared: _Replay, line: ManifestLine, base: str) -> str:
    m = checkout.merge_base(shared.clone, base, line.tested_head)
    if m is None:
        reason = "no common history with the base"
        raise _NotReplayedError(reason)
    return m


def _add_worktree(
    shared: _Replay, commit: str, folder: Path, worktrees: list[Path]
) -> Path:
    checkout.add_worktree(shared.clone, commit, str(folder))
    worktrees.append(folder)
    return folder


def _build(shared: _Replay, line: ManifestLine, worktree: Path, *, at_m: bool) -> None:
    # An environment that cannot be built leaves the pull request not replayed.
    where = "M" if at_m else "the head"
    result = build(shared.pilot, str(worktree), for_coverage=at_m)
    _step(
        shared.log,
        line,
        f"environment at {where}",
        result,
        lock_files=_lock_files(worktree),
    )
    if result.exit_code != 0:
        reason = f"environment at {where} not built"
        raise _NotReplayedError(reason)


def _full_run_and_rerun(
    shared: _Replay, line: ManifestLine, head: Path, folder: Path
) -> tuple[StepResult, str | None]:
    # Rule 7: the tests that failed in the full run run once more; the rerun
    # file, none when nothing failed.
    full = suite.full_run(
        shared.pilot, str(head), str(folder), str(folder / FULL_RUN_JUNIT)
    )
    _step(shared.log, line, "full run", full)
    if not full.failed:
        return full, None
    rerun_file = str(folder / RERUN_JUNIT)
    again = suite.rerun(shared.pilot, str(head), str(folder), full.failed, rerun_file)
    _step(shared.log, line, "rerun", again)
    return full, rerun_file


def _lock_files(worktree: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for name in LOCK_FILES:
        path = worktree / name
        if path.exists():
            found[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def _verdict_of(records: str, line: ManifestLine) -> str:
    # The verdict of the tool's record of this run, the last that names the
    # pull request and its head. A tool that appended none, as it does when it
    # exits with neither 0 nor 3, leaves a KeyError here, which stops the
    # replay.
    verdicts: dict[tuple[int | None, str], str] = {}
    for text in Path(records).read_text(encoding="utf-8").splitlines():
        record = json.loads(text)
        verdicts[(record["pr"], record["head"])] = record["verdict"]
    return verdicts[(line.pull_request, line.tested_head)]


def _step(
    log: Path, line: ManifestLine, name: str, result: StepResult, **extra: object
) -> None:
    entry: dict[str, object] = {
        "event": "step",
        "pull_request": line.pull_request,
        "step": name,
        "exit_code": result.exit_code,
        "seconds": result.seconds,
        "output": COLOUR_CODES.sub("", result.output),
        **extra,
    }
    _append(log, entry)


def _done(
    log: Path,
    line: ManifestLine,
    *,
    why: str | None = None,
    verdict: str | None = None,
    inherited: list[str] | None = None,
) -> None:
    entry: dict[str, object] = {
        "event": "done",
        "pull_request": line.pull_request,
        "replayed": why is None,
        "why": why,
        "verdict": verdict,
        "inherited": inherited or [],
    }
    _append(log, entry)


def _append(log: Path, entry: dict[str, object]) -> None:
    with log.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")


def _entries_of(log: Path) -> list[dict[str, Any]]:
    lines = log.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_summary(work: Path) -> None:
    # For each pilot whose log is in the work directory, in the order of their
    # names, then for both (Summary 2).
    lines: list[str] = []
    counts_of_all: Counter[str] = Counter()
    reasons_of_all: Counter[str] = Counter()
    for log in sorted(work.glob("*.log")):
        counts, reasons = _counts_of(_entries_of(log))
        lines += _summary_lines(log.stem, counts, reasons)
        counts_of_all.update(counts)
        reasons_of_all.update(reasons)
    lines += _summary_lines("both", counts_of_all, reasons_of_all)
    text = "".join(f"{line}\n" for line in lines)
    (work / "summary.txt").write_text(text, encoding="utf-8")


def _counts_of(entries: list[dict[str, Any]]) -> tuple[Counter[str], Counter[str]]:
    # The counts of a pilot's pull requests, from the last done entry of each,
    # and the reasons of those not replayed.
    done = {
        entry["pull_request"]: entry for entry in entries if entry["event"] == "done"
    }
    counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    for entry in done.values():
        counts["replayed" if entry["replayed"] else "not replayed"] += 1
        counts["red"] += entry["verdict"] in RED_VERDICTS
        counts["inherited failures"] += len(entry["inherited"])
        if not entry["replayed"]:
            reasons[entry["why"]] += 1
    return counts, reasons


def _summary_lines(name: str, counts: Counter[str], reasons: Counter[str]) -> list[str]:
    totals = (
        f"{name}: replayed {counts['replayed']}, "
        f"not replayed {counts['not replayed']}, "
        f"red {counts['red']}, inherited failures {counts['inherited failures']}"
    )
    by_reason = [
        f"{name}: not replayed, {why}: {reasons[why]}" for why in sorted(reasons)
    ]
    return [totals, *by_reason]
