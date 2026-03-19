# Agents

This directory contains various executable tools for the luban-workshop project.

## Tools

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

**Location:** `luban_workshop/tools/png2Icons/`
