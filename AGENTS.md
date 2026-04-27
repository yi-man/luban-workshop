# Agents

This file lists the available executable tools in the luban-workshop project.
`CLAUDE.md` is a symlink to this file for Claude/Cursor compatibility.

## Quick Commands

```bash
uv sync
uv run python -m pytest tests/ -v
uv run png2icons <input.png>
uv run glm-coding-bot --help
```

## Repository Layout

- `tools/`: executable tools
- `tests/`: unit tests for tools
- `pyproject.toml`: script entrypoints and dependencies

## Tools

- **png2icons**: Convert PNG images to ICO (Windows) and ICNS (macOS) icon formats
- **glm-coding-bot**: GLM Coding Plan 抢购工具 (API轮询 + 浏览器自动化 + 验证码识别)

## Entrypoints

- `png2icons` -> `tools.png2Icons.main:main`
- `remove_watermark` -> `tools.remove_watermark.main:main`
- `video_download` -> `tools.video_download.main:main`
- `video_transcribe` -> `tools.video_transcribe.main:main`
- `glm-coding-bot` -> `tools.glm_coding_bot.cli:cli`

## Requirements

- Each tool must have corresponding unit tests in the `tests/` directory
- Tests should cover core functionality and edge cases

For detailed usage and documentation, please refer to `README.md`.
