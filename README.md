# luban-workshop

A collection of useful executable tools for various tasks.

## Project Structure

```text
luban-workshop/
├── tools/                    # Executable tools directory
│   ├── png2Icons/            # PNG to ICO/ICNS converter
│   ├── remove_watermark/     # Watermark removal tool
│   ├── video_download/       # Multi-platform video downloader
│   ├── video_transcribe/     # Video to text transcription
│   └── glm_coding_bot/       # GLM Coding Plan 抢购工具
├── tests/                    # Unit tests
├── examples/                 # Usage examples
├── AGENTS.md                 # Agent/tool instructions (source)
├── CLAUDE.md -> AGENTS.md    # Symlink for Claude/Cursor compatibility
├── README.md                 # Detailed documentation
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

### video_download

Multi-platform video download tool supporting major platforms.

**Usage:**

```bash
uv run video_download "<视频链接>" [输出文件名]
```

**Supported Platforms:**

| 平台 | 下载方式 |
|-----|---------|
| 抖音 | Playwright (无头浏览器) |
| 小红书 | Playwright (无头浏览器) |
| B站 | yt-dlp |
| YouTube / Twitter / Instagram | yt-dlp |
| 其他 1700+ 站点 | yt-dlp |

**Login (optional, for better quality):**

```bash
uv run video_download login bilibili
uv run video_download login douyin
uv run video_download login xiaohongshu
```

**Features:**

- Supports short links and full links
- Auto-detects platform
- Optional login for better quality
- Saves to ~/Downloads/ directory

**Detailed documentation:** See [tools/video_download/README.md](tools/video_download/README.md)

### video_transcribe

Video to text transcription tool with subtitle extraction and speech recognition.

**Usage:**

```bash
# First download the video using video_download
uv run video_transcribe "<本地视频路径>"
```

**Features:**

- Extract embedded subtitles using yt-dlp
- Speech recognition using Whisper (fallback)
- Auto language detection
- English to Chinese translation (auto-detected)
- Saves as Markdown with original and translated text

**Workflow:**

1. Use `video_download` to download the video
2. Use `video_transcribe` on the local file

**Supported formats:** MP4, WebM, AVI, MOV, MKV, etc.

**Detailed documentation:** See [tools/video_transcribe/README.md](tools/video_transcribe/README.md)

### remove_watermark

Watermark removal tool using OpenCV inpainting.

**Usage:**

```bash
uv run remove_watermark <input_image>
```

**Features:**

- Auto-detects and removes watermark from bottom-right corner
- Preserves background using inpainting
- Generates output image with `_no_watermark` suffix

### glm-coding-bot

GLM Coding Plan 抢购工具 — API 高频轮询检测库存 + 浏览器自动化购买 + 滑块验证码识别。

**安装浏览器（首次使用）：**

```bash
playwright install chromium
```

**使用：**

```bash
# 1. 登录（首次使用）
uv run glm-coding-bot login --phone 13800138000

# 2. 抢购
uv run glm-coding-bot buy                                    # 默认 Max 套餐 / 包季 / 10:00:00
uv run glm-coding-bot buy --package Pro --period monthly     # 自定义套餐和周期
uv run glm-coding-bot buy --now                              # 立即执行
uv run glm-coding-bot buy --headless                         # 无头模式

# 3. 仅监控库存
uv run glm-coding-bot monitor --duration 120

# 4. 功能测试
uv run glm-coding-bot test
```

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--package` | 套餐类型 | `Lite`, `Pro`, `Max` |
| `--period` | 订阅周期 | `monthly`, `quarterly`, `yearly` |
| `--time` | 抢购时间 | `HH:MM:SS` |
| `--headless` | 无头模式 | flag |
| `--now` | 立即执行 | flag |

**Detailed documentation:** See [tools/glm_coding_bot/README.md](tools/glm_coding_bot/README.md)

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
- `video_download` -> `tools.video_download.main:main`
- `video_transcribe` -> `tools.video_transcribe.main:main`
- `remove_watermark` -> `tools.remove_watermark.main:main`
- `glm-coding-bot` -> `tools.glm_coding_bot.cli:cli`

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
