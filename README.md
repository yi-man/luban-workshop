# luban-workshop

A collection of useful executable tools for various tasks.

## Project Structure

```text
luban-workshop/
├── tools/                    # Executable tools directory
│   ├── png2Icons/            # PNG to ICO/ICNS converter
│   │   ├── __init__.py
│   │   └── main.py
│   └── example_tool.py       # Example tool
├── luban_workshop/           # Minimal package namespace
│   └── __init__.py
├── tests/                    # Unit tests
├── AGENTS.md                 # Agent/tool instructions (source)
├── CLAUDE.md -> AGENTS.md    # Symlink for Claude/Cursor compatibility
├── README.md                 # Detailed documentation
├── main.py                   # Main entry point
└── pyproject.toml            # Project configuration
```

## Available Tools

### png2icons

Convert PNG images to ICO (Windows) and ICNS (macOS) icon formats.

**Usage:**

```bash
uv run png2icons <input.png>
```

**Features:**

- Generates ICO files with multiple sizes (16, 24, 32, 48, 64, 128, 256)
- Generates ICNS files for macOS applications
- Automatically handles non-square images by padding with transparency

**Requirements:**

- Python 3.12+
- Pillow library
- macOS tools: sips, iconutil (for ICNS generation on macOS)

## Developer Workflow

Install dependencies:

```bash
uv sync
```

Run tests:

```bash
uv run python -m pytest tests/ -v
```

Tool entrypoint mapping:

- `png2icons` -> `tools.png2Icons.main:main`

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Install the project in development mode:
   ```bash
   uv pip install -e .
   ```

## Testing

Run the unit tests:

```bash
uv run python -m pytest tests/ -v
```
