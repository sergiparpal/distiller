# distiller

<!-- Every line is a command, a non-standard practice or a rule born from an observed failure. No repo summary: the agent can read the code. -->

## Commands
- `make check`: format, lint, import contracts, types, tests, dependency audit and secret scan. Green here means done.
- `make verify`: `make check` without the dependency audit, which needs the network. The Stop hook runs it after every turn.
- `make test`: tests only.
- `make test-red`: tests without tracebacks, which would show `src/`. In the tests phase, the only way to run them.
- `PYTHONPATH=src .venv/bin/python -m distiller`: run the tool by hand.
- `make protected REF=<commit>`: fails if the Bet, the non-goals or a [core] line of `docs/SPEC.md` differ from REF (HEAD by default). Run it after editing the SPEC.

## Where things are
- Behaviour and acceptance criteria: `docs/SPEC.md`
- Decisions and rejected alternatives: `docs/DECISIONS.md`. Do not re-propose rejected options.
- Backlog: `TASKS.md`. Last session's state: `HANDOFF.md`.

## Rules
- Talk to me in Spanish; write files, code comments and commit messages in English.
- Propose a plan before editing and wait for approval, unless the task fits in one sentence.
- If the spec or the task is ambiguous, ask instead of assuming.
- The Bet, the non-goals and the "then" of every [core] example in docs/SPEC.md are mine: never edit them.
- When an existing sentence of the SPEC says something different from what you are asked to write, report it instead of choosing.
- Write code a beginner can follow: small functions with descriptive names, no clever one-liners and no custom metaprogramming (metaclasses, eval/exec, dynamic attributes, monkey-patching). Well-known libraries and framework idioms are fine. If the simple version is not enough for correctness, performance or security, propose the complex one, explain it in plain words and record it in DECISIONS.md.
- `.claude/phase` is mine, and hooks enforce it. `tests`: write tests from `docs/SPEC.md` without reading `src/`; outside `tests/`, write only the stubs of a new module, from the technical sheet (its signatures, with bodies that raise `NotImplementedError`, as the walking skeleton did), and its import-linter contract, which I review in the tests commit. A signature missing from a module that already exists is mine to write before the phase: if you find one, stop with `.claude/blocked`. `implement <commit>`: make that commit's tests pass without changing, adding or removing any path that `FROZEN_DIRECTORIES`, `FROZEN_AT_ROOT` and `FROZEN_ANYWHERE` in `.claude/hooks/phase.py` name, the only list of them: `tests/`, `scripts/`, the Makefile and the files that configure how the checks run, some of them at any depth.
- Never modify, delete or skip tests unless the task says so.
- If a test looks wrong, if the only way to pass it is special-casing its values, or if the same failure survives two attempts, stop: write the test name, the SPEC example and your reason to `.claude/blocked`. Never work around a test in the implementation.
- Never mix structural changes (renames, moves, refactors) and behaviour changes in one commit.
- Prefer the standard library unless a well-known library makes the code clearer. Ask before adding a dependency: give the exact package name and why.
- Mark any API, flag or version you have not verified with [VERIFY].
- Stay inside the task. Log anything else in `TASKS.md` instead of fixing it.
- Report the commands you ran, their output and what you could not verify. Never claim results you did not observe.

## Rules from observed failures
- Write control and invisible characters as escapes, never raw; `make verify` fails on raw ones. In a Write or Edit call, a typed `\u` escape becomes the raw character (failures: a raw U+2028 landed in docs/SPEC.md, 2026-10-11, and in CLAUDE.md, 2026-10-14).
- Outside the repo, touch only the temporary files you create for the task; never delete anything else (failure: deleted its saved notes outside the repo unasked, 2026-10-11).
- Never read `.claude/settings.local.json` or any other file that holds credentials (failure: read it and printed the OpenRouter key into the session, 2026-10-14).
