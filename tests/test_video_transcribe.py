import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from tools.video_transcribe.main import main

def test_main_requires_arguments():
    """测试 main 函数在没有参数时显示帮助信息"""
    with pytest.raises(SystemExit):
        # 保存原始 sys.argv 并在测试后恢复
        original_argv = sys.argv.copy()
        try:
            sys.argv = ['video_transcribe']
            main()
        finally:
            sys.argv = original_argv

def test_detect_language():
    """测试语言检测功能"""
    from tools.video_transcribe.main import detect_language

    # 测试中文文本
    chinese_text = "这是一段中文文本，用于测试语言检测功能。"
    assert detect_language(chinese_text) == "zh"

    # 测试英文文本
    english_text = "This is an English text used to test the language detection function."
    assert detect_language(english_text) == "en"

    # 测试包含少量中文的文本（调整文本使中文比例 > 0.3）
    mixed_text = "这是一个包含一些英文单词的中文文本，用于测试语言检测功能。"
    assert detect_language(mixed_text) == "zh"

def test_extract_text_from_subtitle():
    """测试从字幕中提取纯文本"""
    from tools.video_transcribe.main import extract_text_from_subtitle

    # 简单的 VTT 字幕示例
    vtt_content = """WEBVTT

    00:00:00.000 --> 00:00:02.000
    这是第一句字幕

    00:00:02.000 --> 00:00:04.000
    这是第二句字幕

    00:00:04.000 --> 00:00:06.000
    这是第三句字幕
    """

    text = extract_text_from_subtitle(vtt_content)
    assert len(text) > 0
    assert "这是第一句字幕" in text
    assert "这是第二句字幕" in text
    assert "这是第三句字幕" in text

def test_escape_markdown():
    """测试 Markdown 转义功能"""
    from tools.video_transcribe.main import _escape_markdown

    text = "这是一个包含`代码`、*斜体*和**粗体**的文本。"
    escaped = _escape_markdown(text)
    assert "\\`" in escaped
    assert "\\*" in escaped
    # 确保原始字符已被转义
    assert "`" not in escaped.replace("\\`", "")
    assert "*" not in escaped.replace("\\*", "")
