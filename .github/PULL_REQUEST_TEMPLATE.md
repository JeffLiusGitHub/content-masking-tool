<!-- Describe the change and its user-visible effect. -->

## What and why

## Checklist

- [ ] `uv run pytest` passes
- [ ] `uv run ruff check src tests` passes
- [ ] Tests added/updated for behavior changes
- [ ] The mask → restore round-trip and the no-leak guarantees are preserved
      (see `tests/test_local_only.py`, vault/round-trip tests)
- [ ] Docs updated if behavior or usage changed
- [ ] No real names in code, tests, fixtures, or this PR
