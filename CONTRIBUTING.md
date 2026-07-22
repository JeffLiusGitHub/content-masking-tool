# Contributing

Thanks for your interest in Content Masking Tool. This is a local-first,
privacy-focused tool; correctness of the mask → restore round-trip and the
"no original content leaves the machine" guarantee come before everything else.

## Development setup

Prerequisites: [uv](https://astral.sh/uv), and Node.js/npm only if you build the
Claude extension (`.mcpb`).

```bash
uv sync --locked --extra dev

# run the tool
uv run python -m maskingtool mask doc.md          # CLI
uv run python -m maskingtool.mcp_server.server    # MCP stdio server
```

## Before you open a pull request

Run the same checks CI runs:

```bash
uv run pytest                     # full test suite (must stay green)
uv run ruff check src tests       # lint (blocking in CI)
uv run mypy                       # type check (informational for now)
```

Formatting is **not** auto-enforced: the codebase is hand-formatted, so
`ruff format` is intentionally not run in CI. Keep new code consistent with the
file you're editing rather than reformatting whole files.

Guidelines:

- **Tests are required** for behavior changes. This project is test-driven; see
  [TESTPLAN.md](TESTPLAN.md) and [TESTING_GUIDE.md](TESTING_GUIDE.md).
- **Never weaken the round-trip or the leak guarantees.** Any change touching
  masking, the vault, the MCP boundary, or the review flow must keep
  `tests/test_local_only.py` and the vault/round-trip tests passing.
- Match the surrounding code style. Lint config lives in `pyproject.toml`
  (`[tool.ruff]`); the codebase intentionally uses one-line compound statements,
  so E701/E702/E741 are disabled — don't reformat around them.
- Keep changes scoped and describe user-visible effects in the PR.

## Architecture and docs

- Architecture and design: [CLAUDE.md](CLAUDE.md)
- Privacy boundary: [PRIVACY_DESIGN.md](PRIVACY_DESIGN.md)
- Release/build procedure: [RELEASING.md](RELEASING.md)
- Progress log: [PROGRESS.md](PROGRESS.md)

## Reporting bugs and security issues

- General bugs: open a GitHub issue using the template.
- Security issues or **any leak of a real name**: do **not** open a public
  issue — follow [SECURITY.md](SECURITY.md).

## License

By contributing you agree that your contributions are licensed under the
project's [GNU AGPL-3.0](LICENSE).
