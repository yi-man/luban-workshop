#!/usr/bin/env python3
"""
视频转文字脚本

用法:
  uv run video-transcribe "<本地视频路径>"

请先使用 video-download 工具下载视频，再将得到的本地路径传入本工具。
若传入的是 URL，则仅尝试拉取字幕（不下载视频）；无法拉取时会提示先使用 video-download。
"""
import sys
import os
import re
import subprocess
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.expanduser('~/Downloads')


def detect_language(text):
    """简单检测文本语言"""
    # 统计中文字符
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.strip())
    if total_chars == 0:
        return 'en'
    return 'zh' if chinese_chars / total_chars > 0.3 else 'en'


def download_subtitles(url):
    """尝试用 yt-dlp 直接下载字幕"""
    print("  尝试下载字幕...")

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            'yt-dlp',
            '--write-subs',
            '--write-auto-subs',
            '--sub-lang', 'en,zh-CN',
            '--skip-download',
            '--output', os.path.join(tmpdir, 'subtitle'),
            url
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"  yt-dlp: {result.returncode}")

        if result.returncode == 0:
            for f in os.listdir(tmpdir):
                if f.endswith('.vtt') or f.endswith('.srt'):
                    subtitle_path = os.path.join(tmpdir, f)
                    with open(subtitle_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    text = extract_text_from_subtitle(content)
                    if text:
                        print(f"  成功下载字幕")
                        return text

    return None


def get_subtitles_with_ytdlp(video_path):
    """用本地视频路径下载字幕（yt-dlp 也支持本地文件）"""
    print("  尝试从本地视频下载字幕...")

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            'yt-dlp',
            '--write-subs',
            '--write-auto-subs',
            '--sub-lang', 'en,zh-CN',
            '--skip-download',
            '--output', os.path.join(tmpdir, 'subtitle'),
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            # 查找生成的字幕文件
            for f in os.listdir(tmpdir):
                if f.endswith('.vtt') or f.endswith('.srt'):
                    subtitle_path = os.path.join(tmpdir, f)
                    with open(subtitle_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # 提取纯文本
                    text = extract_text_from_subtitle(content)
                    if text:
                        print(f"  成功下载字幕")
                        return text

    return None


def extract_text_from_subtitle(content):
    """从字幕文件中提取纯文本"""
    lines = content.split('\n')
    text_lines = []
    skip_metadata = True  # 跳过 WEBVTT 头部

    for line in lines:
        line = line.strip()
        # 跳过 WEBVTT 头部和元数据
        if skip_metadata:
            if line == 'WEBVTT' or line.startswith('Kind:') or line.startswith('Language:'):
                continue
            if line and not line.startswith('[') and '-->' not in line:
                skip_metadata = False
        # 跳过时间轴和空行
        if not line or '-->' in line or line.isdigit():
            continue
        # 跳过标签和音符符号
        if line.startswith('<') or line == '♪' or line == '[]':
            continue
        # 清理音符
        line = line.replace('♪', '').strip()
        if line:
            text_lines.append(line)

    return '\n'.join(text_lines)


def transcribe_with_whisper(video_path):
    """使用 faster-whisper 语音识别"""
    print("  使用 Whisper 识别语音...")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("错误: 请先安装 faster-whisper")
        print("  uv sync")
        return None

    # 加载模型 (使用 large-v3 模型以提高精度)
    print("  加载 Whisper 模型...")
    model = WhisperModel("large-v3", device="cpu", compute_type="int8")

    # 转写
    print("  识别中...")
    segments, info = model.transcribe(video_path, language=None)  # 自动检测语言

    # 合并所有段落
    text_parts = []
    for segment in segments:
        text_parts.append(segment.text.strip())

    return ' '.join(text_parts)


def translate_to_chinese(text):
    """使用 Google API 翻译成中文"""
    print("[3/4] 翻译成中文...")

    try:
        import asyncio
        from googletrans import Translator
    except ImportError:
        print("  错误: 请先安装 googletrans")
        print("  pip3 install googletrans")
        return None

    try:
        translator = Translator()
        # 分段翻译以避免超限
        paragraphs = text.split('\n\n')
        translated = []

        for para in paragraphs:
            if para.strip():
                # 新版 googletrans 是异步的
                result = asyncio.run(translator.translate(para, src='en', dest='zh-cn'))
                translated.append(result.text)

        return '\n\n'.join(translated)
    except Exception as e:
        print(f"  翻译失败: {e}")
        return None


def _escape_markdown(text):
    """转义 Markdown 特殊字符，防止格式混乱"""
    return text.replace('`', '\\`').replace('*', '\\*').replace('_', '\\_').replace('#', '\\#')


def _text_to_md_paragraphs(text):
    """将长文本按段落整理，便于 Markdown 阅读"""
    if not text or not text.strip():
        return ""
    # 按双换行分段落，单换行合并为同一段
    blocks = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not blocks:
        # 无双换行则整段输出，内部单换行保留
        return text.strip().replace("\n", "  \n")  # 双空格 = Markdown 换行
    return "\n\n".join(
        p.replace("\n", "  \n") if "\n" in p else p for p in blocks
    )


def save_result(original_text, translated_text, video_path):
    """保存结果为 Markdown 文件"""
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    safe_video_name = _escape_markdown(video_name)
    safe_path = _escape_markdown(video_path)
    output_path = os.path.join(DOWNLOADS_DIR, f"{video_name}_transcript.md")

    lines = []
    lines.append(f"# {safe_video_name}")
    lines.append("")
    if translated_text:
        lines.append("## 中文翻译")
        lines.append("")
        lines.append(_text_to_md_paragraphs(translated_text))
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 英文原文")
        lines.append("")
        lines.append(_text_to_md_paragraphs(original_text))
    else:
        lines.append("## 正文")
        lines.append("")
        lines.append(_text_to_md_paragraphs(original_text))
    lines.append("")
    lines.append("---")
    lines.append(f"*转写自: `{safe_path}`*")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[4/4] 结果已保存到: {output_path}")
    return output_path


def transcribe(input_arg):
    """主流程：接受本地视频路径或 URL（仅尝试拉取字幕）。"""
    input_arg = input_arg.strip()
    is_url = input_arg.startswith('http://') or input_arg.startswith('https://')
    video_path = None
    text = None

    if is_url:
        # 仅尝试拉取字幕，不下载视频
        print(f"[1/4] 尝试从链接拉取字幕: {input_arg[:60]}...")
        print("[2/4] 提取文字")
        text = download_subtitles(input_arg)
        if not text:
            print("该链接无法直接拉取字幕。请先使用 video-download 工具下载视频，再传入本地路径：")
            print("  uv run video-transcribe <本地视频路径>")
            return
    else:
        # 本地路径：先展开 ~
        video_path = os.path.expanduser(input_arg)
        if not os.path.isfile(video_path):
            print(f"错误: 文件不存在: {video_path}")
            print("请先使用 video-download 工具下载视频，再传入得到的本地路径。")
            return
        print(f"[1/4] 使用本地视频: {video_path}")
        print("[2/4] 提取文字")
        text = get_subtitles_with_ytdlp(video_path)
        if not text:
            print("  字幕不可用，改用 Whisper 识别")
            text = transcribe_with_whisper(video_path)
        print(f"  视频路径: {video_path}")
    if not text:
        print("错误: 无法提取文字，请确保视频有声音")
        return

    print(f"  提取文字长度: {len(text)} 字符")

    lang = detect_language(text)
    print(f"  检测语言: {'中文' if lang == 'zh' else '英文'}")

    translated = None
    if lang == 'en':
        translated = translate_to_chinese(text)

    if not video_path:
        video_path = f"video_{int(time.time())}"
    save_result(text, translated, video_path)


def main():
    if len(sys.argv) < 2:
        print("用法: uv run video-transcribe <本地视频路径>")
        print("请先使用 video-download 工具下载视频，再将得到的路径传入本工具。")
        sys.exit(1)

    transcribe(sys.argv[1])


if __name__ == '__main__':
    main()
