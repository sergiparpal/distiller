# SPEC: <project-name>
<!-- The Bet is mine: written before the interview, never edited by the agent.
The agent drafts the rest after interviewing me. The non-goals, the expected
values of [core] examples and the properties are mine.
Mark [core] the examples whose "then" cannot be undone: what gets stored and
in what form, a security decision, an action sent outside. When unsure, [core].
Properties: off. While off, write each invariant as one or two concrete
examples. -->

## Bet
- Hypothesis: <falsifiable sentence from the idea protocol>
- Appetite: <N weeks>, ends <YYYY-MM-DD>
- Kill signal: <observable result that ends the project>

## Problem
<Who has it, when, and what they do today.>

## Non-goals
- <What it will not do, even if it is easy.>

## Constraints
- Stack: <...>
- Allowed dependencies: <...>
- Performance: <...>
- Agent safety: <if it is an agent or runs inside one, which leg of the lethal trifecta is cut: private data, untrusted content or external communication>
- If no leg can be cut:
  - Outbound actions: <closed list, destinations fixed by code>
  - Credentials: <held by the harness, never in the model's context>
  - Untrusted input: <read by a tool-less model; schema-validated output>
  - Published output: <no links or Markdown images>
  - Authorization: <actions driven by untrusted content go through belief-ledger-pramana or me>
  - Injection tests: <fixtures with injected instructions and a canary secret>

## Slices
<Add each slice's criteria just before starting it.>

### Slice 1: <behaviour that works end to end>
- Supersedes: <earlier examples this slice changes, or none>
- Given <context>, when <action>, then <observable result>.
- [core] Given <context>, when <action>, then <TO FILL>.
- Edge case: <input> -> <expected output or error>.
- Property (only while properties are on): for every <input>, <invariant that must hold>.

## Technical sheet
<Modules with their risk tier, interfaces, data model. Written in phase 2.
A module that produces the "then" of a [core] example is core. A module with
an irreversible effect that no [core] example observes means a missing example.>

## Open questions
- <...>
