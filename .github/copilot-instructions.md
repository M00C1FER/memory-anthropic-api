# Copilot Coding Agent — Instructions

## Project context

`memory-tool-conformance` — Conformance test suite + filesystem reference implementation for the LLM memory tool 6-op contract (view/create/str_replace/insert/delete/rename). Drop-in CI dependency for any memory server author.

## Coding rules

- Python 3.10+ minimum.
- Type hints on every public function; prefer `TypedDict` or `@dataclass` over loose dicts for structured payloads.
- `pathlib.Path` over `os.path`.
- No bare `except:` — catch specific exceptions or `Exception` with logging.
- Imports sorted: stdlib, third-party, local (per `isort` defaults).
- No new dependencies without justification in the PR description.

## Tests

- Every new public function: unit test in `tests/`.
- Tests run via `pytest` from repo root (no special setup).
- Aim for the same coverage as surrounding code; do not introduce regressions.
- Mock external services / network calls; tests must run offline.

## File naming

- snake_case for Python modules.
- Test files: `test_<module>.py` mirroring the module they test.

## Don't touch

- Existing public API signatures — extend, don't break.
- `.github/workflows/` unless the issue says so.
- Existing badge URLs in README — keep them; they're tied to CI.

## Acceptance signal

A PR is ready for review when:
1. `pytest` passes locally.
2. README renders without broken links.
3. Public API contracts unchanged (no breaking changes without major version bump).
4. No new third-party deps unless justified.
