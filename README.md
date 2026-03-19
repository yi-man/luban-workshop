# luban-workshop

A collection of useful executable tools for various tasks.

## Project Structure

```
luban-workshop/
├── luban_workshop/           # Main package
│   ├── tools/                # Tools directory
│   │   ├── png2Icons/        # PNG to ICO/ICNS converter
│   │   └── example_tool.py   # Example tool
│   └── __init__.py
├── tests/                    # Unit tests
├── AGENTS.md                 # List of available tools
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

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   uv install
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
