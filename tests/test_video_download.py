import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from tools.video_download.main import main

def test_main_requires_arguments():
    """测试 main 函数在没有参数时显示帮助信息"""
    with pytest.raises(SystemExit):
        main()

def test_detect_platform_douyin():
    """测试平台检测功能 - 抖音"""
    from tools.video_download.main import detect_platform

    # 测试抖音链接
    text1 = "https://v.douyin.com/abc123"
    platform1, url1 = detect_platform(text1)
    assert platform1 == "douyin"

    text2 = "https://www.douyin.com/video/1234567890"
    platform2, url2 = detect_platform(text2)
    assert platform2 == "douyin"

def test_detect_platform_xiaohongshu():
    """测试平台检测功能 - 小红书"""
    from tools.video_download.main import detect_platform

    text1 = "https://www.xiaohongshu.com/discovery/item/abc123"
    platform1, url1 = detect_platform(text1)
    assert platform1 == "xiaohongshu"

    text2 = "https://xhslink.com/abc123"
    platform2, url2 = detect_platform(text2)
    assert platform2 == "xiaohongshu"

def test_detect_platform_bilibili():
    """测试平台检测功能 - B站"""
    from tools.video_download.main import detect_platform

    text1 = "https://www.bilibili.com/video/BV12345"
    platform1, url1 = detect_platform(text1)
    assert platform1 == "bilibili"

    text2 = "https://b23.tv/abc123"
    platform2, url2 = detect_platform(text2)
    assert platform2 == "bilibili"

def test_clean_filename():
    """测试文件名清理功能"""
    from tools.video_download.main import clean_filename

    dirty_filename = "测试 文件名/with:special*characters"
    clean = clean_filename(dirty_filename)
    assert "/" not in clean
    assert ":" not in clean
    assert "*" not in clean
    assert len(clean) > 0
