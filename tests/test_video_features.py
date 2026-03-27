#!/usr/bin/env python3
"""
测试视频下载和转录功能
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from tools.video_download.main import detect_platform, clean_filename, extract_url, check_ytdlp

print("=== 测试视频下载功能 ===")

# 1. 测试平台检测
print("\n1. 测试平台检测:")

test_urls = [
    ("抖音短链", "https://v.douyin.com/abc123"),
    ("抖音长链", "https://www.douyin.com/video/1234567890"),
    ("小红书长链", "https://www.xiaohongshu.com/discovery/item/645c2a1f000000001a001234"),
    ("小红书短链", "https://xhslink.com/abc123"),
    ("B站长链", "https://www.bilibili.com/video/BV1234567890"),
    ("B站短链", "https://b23.tv/abc123"),
    ("YouTube链接", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
]

for description, url in test_urls:
    platform, final_url = detect_platform(url)
    print(f"  {description}:")
    print(f"    URL: {url}")
    print(f"    检测平台: {platform}")
    print(f"    最终URL: {final_url}")

# 2. 测试文件名清理
print("\n2. 测试文件名清理:")
dirty_filenames = [
    "测试视频: 你好世界.mp4",
    "视频/包含/路径/分隔符.mp4",
    "视频*星号*和*问号?.mp4",
    "视频带空格 和下划线.mp4",
]

for dirty in dirty_filenames:
    clean = clean_filename(dirty)
    print(f"  '{dirty}'")
    print(f"  -> '{clean}.mp4'")

# 3. 测试 URL 提取
print("\n3. 测试 URL 提取:")
text_with_urls = [
    "看看这个视频 https://www.douyin.com/video/123456789 挺有意思的",
    "分享 https://www.bilibili.com/video/BV12345",
]

for text in text_with_urls:
    url = extract_url(text)
    print(f"  原文: {text}")
    print(f"  提取: {url}")

# 4. 检查 yt-dlp
print("\n4. 检查 yt-dlp:")
ytdlp_available = check_ytdlp()
print(f"  yt-dlp 可用: {ytdlp_available}")

print("\n=== 视频下载功能测试完成 ===")

print("\n=== 测试视频转录功能 ===")

try:
    from tools.video_transcribe.main import detect_language, _escape_markdown, extract_text_from_subtitle

    # 1. 测试语言检测
    print("\n1. 测试语言检测:")
    texts = [
        ("中文测试", "这是一段中文文本，用于测试语言检测功能。"),
        ("英文测试", "This is an English text for language detection."),
        ("混合文本", "这是一个包含 some English words 的文本。"),
    ]

    for desc, text in texts:
        lang = detect_language(text)
        print(f"  {desc}: {lang}")

    # 2. 测试 Markdown 转义
    print("\n2. 测试 Markdown 转义:")
    markdown_text = "这是包含`代码`、*斜体*和**粗体**的文本。"
    escaped = _escape_markdown(markdown_text)
    print(f"  原文: {markdown_text}")
    print(f"  转义: {escaped}")

    # 3. 测试字幕提取
    print("\n3. 测试字幕提取:")
    vtt_content = """WEBVTT

    00:00:00.000 --> 00:00:02.000
    这是第一句字幕

    00:00:02.000 --> 00:00:04.000
    这是第二句字幕

    00:00:04.000 --> 00:00:06.000
    这是第三句字幕
    """

    extracted = extract_text_from_subtitle(vtt_content)
    print(f"  提取的文本长度: {len(extracted)}")
    print(f"  提取内容:\n{extracted}")

    print("\n=== 视频转录功能测试完成 ===")

except ImportError as e:
    print(f"\n跳过转录功能测试（缺少依赖: {e}）")

print("\n所有测试完成！")
