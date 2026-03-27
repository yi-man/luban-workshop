# Video Transcribe Tool

视频转文字工具 - 支持字幕提取和语音识别

## 功能介绍

此工具可以将视频转换为文字，支持多种方式：
- 从视频中提取字幕
- 使用 Whisper 进行语音识别
- 自动检测语言
- 英文内容自动翻译成中文

## 安装

### 基础安装

```bash
# 确保项目已安装
cd /path/to/luban-workshop
uv pip install -e .
```

### 安装完整功能依赖

```bash
# 安装视频转录相关依赖
uv pip install -e ".[video-transcribe]"
```

**注意事项：**
- `faster-whisper` 在某些平台可能有兼容性问题
- 只需要字幕提取功能时，可以不安装此可选依赖

## 使用方法

### 基本用法

```bash
# 转写本地视频
uv run video_transcribe "<本地视频路径>"
```

### 完整工作流程

1. **先使用 video_download 工具下载视频**
2. **再使用此工具转写视频**

```bash
# 步骤1：下载视频
uv run video_download "https://www.youtube.com/watch?v=xxx"

# 步骤2：转写视频（假设下载的文件是 video.mp4）
uv run video_transcribe "~/Downloads/video.mp4"
```

## 支持的输入格式

### 本地视频文件

| 格式 | 说明 |
|------|------|
| MP4 | ✅ 推荐 |
| WebM | ✅ 支持 |
| AVI | ✅ 支持 |
| MOV | ✅ 支持 |
| MKV | ✅ 支持 |
| 其他常见格式 | ✅ 大部分都支持 |

### 在线 URL（仅限字幕）

如果传入的是 URL（而非本地路径），工具会尝试直接拉取字幕，**不会下载视频**。

**注意：**
- 此方式仅在有可用字幕时才会工作
- 无法拉取字幕时，会提示先使用 video_download 下载视频

## 工作原理

### 处理流程

1. **检测输入类型**
   - 本地路径：使用本地视频文件
   - 在线 URL：尝试直接拉取字幕

2. **字幕提取**（优先尝试）
   - 使用 yt-dlp 提取内嵌字幕
   - 支持 VTT、SRT 等常见字幕格式
   - 自动提取纯文本内容

3. **语音识别**（备用方式）
   - 无字幕时使用 Whisper 模型
   - 自动检测语言
   - 使用 large-v3 模型提高精度

4. **语言翻译**（可选）
   - 检测到英文时自动翻译为中文
   - 使用 Google Translate API

5. **结果保存**
   - 保存为 Markdown 格式
   - 包含原文和翻译（如有）
   - 默认保存到 `~/Downloads/` 目录

## 支持的语言

| 语言 | 检测 | 翻译 |
|------|------|------|
| 中文 | ✅ | - |
| 英文 | ✅ | ✅ → 中文 |
| 其他 | ⚠️ 部分支持 | ❌ |

## 输出文件

### 文件位置

默认保存到 `~/Downloads/` 目录

### 文件名格式

```
<原视频名>_transcript.md
```

### 文件内容格式

```markdown
# <视频名>

## 中文翻译

[中文翻译内容]

---

## 英文原文

[英文原文内容]

---
*转写自: `<视频路径>`*
```

## 使用示例

### 示例1：基本转写（本地视频）

```bash
# 转写本地视频文件
uv run video_transcribe "/Users/yourname/Downloads/my_video.mp4"
```

输出：
```
[1/4] 使用本地视频: /Users/yourname/Downloads/my_video.mp4
[2/4] 提取文字
  尝试从本地视频下载字幕...
  字幕不可用，改用 Whisper 识别
  加载 Whisper 模型...
  识别中...
  视频路径: /Users/yourname/Downloads/my_video.mp4
  提取文字长度: 1523 字符
  检测语言: 英文
[3/4] 翻译成中文...
[4/4] 结果已保存到: /Users/yourname/Downloads/my_video_transcript.md
```

### 示例2：URL 字幕拉取

```bash
# 尝试从 URL 直接拉取字幕（不下载视频）
uv run video_transcribe "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

输出（成功情况）：
```
[1/4] 尝试从链接拉取字幕: https://www.youtube.com/watch?v=xxx...
[2/4] 提取文字
  尝试下载字幕...
  成功下载字幕
  提取文字长度: 2345 字符
  检测语言: 英文
[3/4] 翻译成中文...
[4/4] 结果已保存到: /Users/yourname/Downloads/video_xxx_transcript.md
```

输出（失败情况）：
```
该链接无法直接拉取字幕。请先使用 video-download 工具下载视频，再传入本地路径：
  uv run video_transcribe <本地视频路径>
```

### 示例3：已下载的 evals 示例

```bash
# 使用我们之前下载的示例视频
uv run video_transcribe "./eval_1_video.mp4"
```

## 依赖说明

### 必需依赖

- yt-dlp - 用于字幕提取

### 可选依赖（仅语音识别需要）

| 依赖 | 用途 |
|------|------|
| faster-whisper | Whisper 语音识别模型 |
| googletrans | Google 翻译 API |

## 常见问题

### 1. 提示 "文件不存在"

确保视频文件路径正确：
```bash
# 检查文件是否存在
ls -la "/path/to/video.mp4"
```

### 2. 缺少 faster-whisper

```
错误: 请先安装 faster-whisper
解决: uv pip install -e ".[video-transcribe]"
```

**注意：** 只需要字幕提取功能时，可以不安装 faster-whisper。

### 3. 翻译失败

可能原因：
- Google Translate API 限制
- 网络连接问题
- 文本过长

解决建议：
- 检查网络连接
- 手动翻译即可

### 4. Whisper 识别速度慢

Whisper large-v3 模型精度高但速度较慢，可以：
- 等待识别完成（首次需要下载模型）
- 如果只需要字幕，确保视频有内嵌字幕

## 平台兼容性

| 平台 | 字幕提取 | Whisper 识别 |
|------|---------|-------------|
| macOS x86_64 | ✅ | ⚠️ 可能有兼容性问题 |
| macOS arm64 | ✅ | ✅ |
| Linux x86_64 | ✅ | ✅ |
| Windows | ✅ | ✅ |

## 相关工具

- **video_download** - 视频下载工具（先下载再转写）
- **yt-dlp** - 底层字幕提取工具

## 性能提示

1. **优先使用内嵌字幕**：有字幕时不需要 Whisper，速度更快
2. **Whisper 模型**：首次运行需要下载模型（约 2GB），后续会快很多
3. **文件大小**：大文件转写时间更长

---

本工具是 luban-workshop 项目的一部分。
