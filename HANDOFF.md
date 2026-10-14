# Handoff

## 2026-10-14: Phase 3, the repository prepared for the agent
- Branch `phase-3`, not pushed. Before the last three commits, which touch only `.claude/settings.json` and the docs, `make check` and `make test-hooks` (98 tests) were green.
- Checked in real `claude -p` sessions in a throwaway clone: each hook blocks what it should and lets the rest through, a subagent's calls included; the deny rules hold in bypass mode; the Bash sandbox hides the gh token, /mnt and Windows binaries, unsets the credential variables, and reaches only pypi.org once `strictAllowlist` is on.
- For the user: add the sandbox fragment of D-003 to `~/.claude/settings.json`, without which `make check` and `git commit` fail inside the sandbox; decide how the tests phase searches and stubs existing modules (D-003, Consequences); merge `phase-3`.
