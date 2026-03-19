# Agents

This file lists the available executable tools in the luban-workshop project.
`CLAUDE.md` is a symlink to this file for Claude/Cursor compatibility.

## Quick Commands

```bash
uv sync
uv run python -m pytest tests/ -v
uv run png2icons <input.png>
```

## Repository Layout

- `tools/`: executable tools (current location)
- `tests/`: unit tests for tools
- `pyproject.toml`: script entrypoints and dependencies

## Tools

- **png2icons**: Convert PNG images to ICO (Windows) and ICNS (macOS) icon formats

## Entrypoints

- `png2icons` -> `tools.png2Icons.main:main`

## Requirements

- Each tool must have corresponding unit tests in the `tests/` directory
- Tests should cover core functionality and edge cases

For detailed usage and documentation, please refer to `README.md`.

