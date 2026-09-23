# RKAA repository guidance

## Required reading

For each task, read only:

1. docs/codex/MAIN.md
2. docs/progress/current-state.md
3. The active prompt identified in PROMPT_INDEX.md
4. Files explicitly listed by that prompt
5. Direct imports or interfaces required to understand those files

Do not scan the whole repository unless the active prompt explicitly requests architecture discovery.

## Source-of-truth priority

1. SRS requirements referenced by the active prompt
2. Active prompt
3. Architecture documents
4. Existing tests
5. Existing implementation

Report conflicts instead of silently choosing one.

## Scope

- Modify only files allowed by the active prompt.
- Reading one-hop dependencies is allowed.
- Editing dependencies outside scope is forbidden unless required to fix a failing existing interface.
- Do not implement later prompts early.
- Do not change public APIs without explicit permission.

## Commands

- Tests: `pytest`
- Lint: `ruff check .`
- Format check: `ruff format --check .`
- Type check: `<project command>`

## Completion

A task is complete only when:

- focused tests pass;
- affected regression tests pass;
- lint passes;
- no unrelated files changed;
- progress files are updated.

## Efficient repository exploration

Use targeted commands first:

- `rg "<symbol>" src tests`
- `rg --files <relevant-directory>`
- `git diff --stat`
- `git status --short`

Do not begin with recursive reads of every source file.