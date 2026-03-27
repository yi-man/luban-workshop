# Video Download Tool

视频下载工具 - 支持多平台视频下载

## 功能介绍

此工具支持多种视频平台的下载，包括国内和国际主流平台。

### 支持的平台

| 平台          | 下载方式   | 说明                          |
|---------------|-----------|-------------------------------|
| **抖音**      | Playwright| 支持短链和完整链接             |
| **小红书**    | Playwright| 支持图文和视频笔记             |
| **B站**       | yt-dlp    | 支持登录获取高清               |
| **YouTube**   | yt-dlp    | 支持 4K、HDR                  |
| **Twitter/X** | yt-dlp    |                               |
| **Instagram** | yt-dlp    |                               |
| **其他1700+站点** | yt-dlp |                               |

## 安装

### 基础安装

```bash
# 确保项目已安装
cd /path/to/luban-workshop
uv pip install -e .
```

### 安装视频下载功能依赖

```bash
# 安装视频下载相关依赖
uv pip install -e ".[video]"

# 安装 Playwright 浏览器（必需）
uv run python -m playwright install chromium
```

## 使用方法

### 基本用法

```bash
# 下载视频
uv run video_download "<视频链接>"

# 下载视频并指定输出文件名
uv run video_download "<视频链接>" "我的视频"
```

### 登录相关（可选，用于获取更好画质）

```bash
# 登录B站
uv run video_download login bilibili

# 登录抖音
uv run video_download login douyin

# 登录小红书
uv run video_download login xiaohongshu
```

登录后会打开浏览器，您完成登录后关闭浏览器，Cookie会自动保存供后续使用。

## 平台详细说明

### 抖音 (Douyin)

**支持的链接格式：**
- 短链: `https://v.douyin.com/abc123`
- 完整链接: `https://www.douyin.com/video/1234567890`

**使用示例：**
```bash
# 下载抖音视频
uv run video_download "https://v.douyin.com/abc123"
```

**下载方式说明：**
- 使用 Playwright 无头浏览器访问
- 监听网络请求获取视频 CDN 地址
- 使用普通 HTTP 下载

### 小红书 (Xiaohongshu)

**支持的链接格式：**
- 短链: `https://xhslink.com/abc123`
- 完整链接: `https://www.xiaohongshu.com/discovery/item/<笔记ID>`

**使用示例：**
```bash
# 下载小红书视频
uv run video_download "https://xhslink.com/abc123"
```

**重要提示：**
- 不是所有小红书笔记都有视频
- 图文笔记无法下载视频
- 会自动检测笔记是否包含视频

### B站 (Bilibili)

**支持的链接格式：**
- 短链: `https://b23.tv/abc123`
- 完整链接: `https://www.bilibili.com/video/BV1xx411c7XD`

**使用示例：**
```bash
# 下载B站视频
uv run video_download "https://www.bilibili.com/video/BV1xx411c7XD"
```

**注意事项：**
- 登录后可下载高清视频
- 番剧/付费内容可能不支持

### YouTube

**支持的链接格式：**
- `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
- `https://youtu.be/dQw4w9WgXcQ`

**使用示例：**
```bash
# 下载YouTube视频
uv run video_download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

## 下载选项

### 音频下载（仅支持 yt-dlp 平台）

对于 YouTube、Twitter 等平台，可以直接下载音频：

```bash
# 使用方式：提示中包含"mp3"或"音频"
uv run video_download "帮我下载这个视频的音频 https://www.youtube.com/watch?v=xxx"
```

或者直接使用 yt-dlp：
```bash
yt-dlp -x --audio-format mp3 "<YouTube链接>"
```

### 下载字幕（仅支持 yt-dlp 平台）

```bash
yt-dlp --write-subs --sub-lang zh-CN "<链接>"
```

## 输出文件

- 默认保存到 `~/Downloads/` 目录
- 文件名会根据视频标题自动生成
- 可指定输出文件名（无需加扩展名）

## 常见问题

### Playwright 未安装

```
错误: 需要安装 Playwright
解决: uv run python -m playwright install chromium
```

### FFmpeg 未安装（B站下载失败）

```
提示: 请确保已安装 ffmpeg
解决: brew install ffmpeg (macOS)
      sudo apt install ffmpeg (Linux)
```

### 下载失败

可能原因：
1. 网络连接问题
2. 链接失效或内容受限
3. 需要登录

解决建议：
- 检查网络连接
- 更新 yt-dlp: `uv pip install -U yt-dlp`
- 尝试登录获取更好的画质

## 平台支持对照表

| 功能 | 抖音 | 小红书 | B站 | YouTube/Twitter等 |
|------|------|--------|-----|------------------|
| 短链支持 | ✅ | ✅ | ✅ | ✅ |
| 音频下载 | ❌ | ❌ | ❌ | ✅ |
| 字幕下载 | ❌ | ❌ | ❌ | ✅ |
| 登录支持 | ✅ | ✅ | ✅ | ❌ |
| 无浏览器下载 | ❌ | ❌ | ✅ | ✅ |

## 相关链接

- yt-dlp 官方文档: https://github.com/yt-dlp/yt-dlp
- Playwright 官方文档: https://playwright.dev/

---

本工具是 luban-workshop 项目的一部分。
