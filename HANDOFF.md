# Handoff

## 2026-10-14: Phase 3, the repository prepared for the agent
- Branch `phase-3`, not pushed. `make check` is green inside the Bash sandbox, with the user's settings fragment in place. `make test-hooks` (98 tests) is green from a terminal; inside the sandbox, its implement-phase Stop tests fail, because git in the nested bwrap cannot resolve their commits.
- Checked in real `claude -p` sessions in a throwaway clone: each hook blocks what it should and lets the rest through, a subagent's calls included; the deny rules hold in bypass mode; the Bash sandbox hides the gh token, /mnt and Windows binaries, unsets the credential variables, and reaches only pypi.org once `strictAllowlist` is on. The character check was provoked with one file per kind of character, and with a raw U+2028 in a clone's SPEC.
- For the user: see whether an allow rule in `.claude/settings.json` brings Grep and Glob back (the documentation says only `--allowedTools` does); merge `phase-3`.
