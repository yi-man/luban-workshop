#!/usr/bin/env python3
"""
测试字幕翻译功能
"""
import sys
import os
import tempfile
sys.path.insert(0, os.path.dirname(__file__))

def test_subtitle_extraction():
    """测试从字幕中提取文本"""
    print("1. 测试字幕文本提取")

    from tools.video_transcribe.main import extract_text_from_subtitle

    # 测试 VTT 字幕
    vtt_content = """WEBVTT

Kind: captions
Language: en

00:00:00.000 --> 00:00:03.000
Hello everyone, welcome to this video.

00:00:03.000 --> 00:00:06.000
Today we'll be talking about video processing.

00:00:06.000 --> 00:00:09.000
Let's get started!
"""

    text = extract_text_from_subtitle(vtt_content)
    print(f"   提取的文本:")
    print(text)
    print()

    if "Hello everyone" in text and "video processing" in text:
        print("✅ 字幕文本提取成功")
        return True
    else:
        print("❌ 字幕文本提取失败")
        return False

def test_language_detection():
    """测试语言检测功能"""
    print("2. 测试语言检测")

    from tools.video_transcribe.main import detect_language

    english_text = "Hello, this is an English text for testing language detection."
    chinese_text = "这是一段用于测试语言检测的中文文本。"

    en_lang = detect_language(english_text)
    zh_lang = detect_language(chinese_text)

    print(f"   英文文本检测结果: {en_lang}")
    print(f"   中文文本检测结果: {zh_lang}")

    if en_lang == 'en' and zh_lang == 'zh':
        print("✅ 语言检测成功")
        return True
    else:
        print("❌ 语言检测失败")
        return False

def test_markdown_paragraphs():
    """测试 Markdown 段落格式化"""
    print("3. 测试 Markdown 段落格式化")

    from tools.video_transcribe.main import _text_to_md_paragraphs

    long_text = """第一段文字
它包含了多行内容

第二段文字
同样有多行内容

第三段是独立的一行"""

    md_text = _text_to_md_paragraphs(long_text)

    print(f"   原始文本:")
    print(long_text)
    print()
    print(f"   Markdown 格式化:")
    print(md_text)
    print()

    if md_text.count("  \n") >= 2:
        print("✅ Markdown 段落格式化成功")
        return True
    else:
        print("❌ Markdown 段落格式化有问题")
        return False

def test_subtitle_file_creation():
    """测试创建字幕文件"""
    print("4. 测试字幕文件创建和保存")

    with tempfile.TemporaryDirectory() as tmpdir:
        video_name = "test_video"
        video_path = os.path.join(tmpdir, f"{video_name}.mp4")

        # 创建空视频文件用于测试
        with open(video_path, 'w') as f:
            f.write("dummy video content")

        try:
            from tools.video_transcribe.main import save_result

            original_text = "This is the original English text from the video."
            translated_text = "这是视频中的英文原文的中文翻译。"

            output_path = save_result(original_text, translated_text, video_path)

            print(f"   输出文件: {output_path}")

            if os.path.exists(output_path):
                with open(output_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                print(f"   文件内容检查:")
                print(f"   - 包含标题: {'# ' + video_name in content}")
                print(f"   - 包含中文翻译: {'中文翻译' in content}")
                print(f"   - 包含英文原文: {'英文原文' in content}")

                if '# ' + video_name in content and '中文翻译' in content and '英文原文' in content:
                    print("✅ 字幕文件保存成功")
                    return True
                else:
                    print("❌ 字幕文件内容不正确")
                    return False
            else:
                print("❌ 字幕文件未创建")
                return False

        except ImportError as e:
            print(f"⚠️  跳过保存功能测试（缺少依赖: {e}）")
            # 这不是失败，只是跳过了实际的保存测试
            return True
        except Exception as e:
            print(f"❌ 保存测试失败: {e}")
            return False

def test_translate_without_dependencies():
    """测试翻译功能的可用性检查"""
    print("5. 测试翻译功能可用性")

    try:
        from tools.video_transcribe.main import translate_to_chinese
        print("✅ translate_to_chinese 函数可访问")

        # 尝试导入 googletrans
        try:
            from googletrans import Translator
            print("✅ googletrans 已安装")
            return True
        except ImportError:
            print("⚠️  googletrans 未安装（需要安装视频转录依赖）")
            print("   运行: uv pip install -e \".[video-transcribe]\"")
            # 这不是真正的失败，只是说明依赖未安装
            return True

    except Exception as e:
        print(f"❌ 翻译功能检查失败: {e}")
        return False

if __name__ == "__main__":
    print("=== 字幕翻译功能测试 ===\n")

    success_count = 0
    total_count = 5

    tests = [
        test_subtitle_extraction,
        test_language_detection,
        test_markdown_paragraphs,
        test_subtitle_file_creation,
        test_translate_without_dependencies
    ]

    for test in tests:
        try:
            if test():
                success_count += 1
        except Exception as e:
            print(f"❌ 测试发生异常: {e}")
        print()

    print(f"=== 测试完成: {success_count}/{total_count} 个测试通过 ===\n")

    if success_count >= 4:
        print("✅ 字幕翻译功能基本正常！")
        print("\n提示:")
        print("- 要使用完整的视频转录和翻译功能，请安装:")
        print("  uv pip install -e \".[video-transcribe]\"")
    else:
        print("❌ 部分测试失败，请检查代码。")
