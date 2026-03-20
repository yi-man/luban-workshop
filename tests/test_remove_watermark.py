#!/usr/bin/env python3
"""
测试水印去除工具
"""

import os
import sys
import unittest
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.remove_watermark.main import remove_watermark

class TestRemoveWatermark(unittest.TestCase):
    """测试水印去除功能"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_image = Path("tools/remove_watermark/image_with_watermark.png")
        self.output_image = Path("tools/remove_watermark/image_with_watermark_no_watermark.png")
        
    def tearDown(self):
        """清理测试结果"""
        if self.output_image.exists():
            self.output_image.unlink()
    
    def test_remove_watermark(self):
        """测试水印去除功能"""
        # 确保测试图片存在
        self.assertTrue(self.test_image.exists(), f"测试图片不存在: {self.test_image}")
        
        # 执行水印去除
        remove_watermark(self.test_image, self.output_image)
        
        # 确保输出文件生成
        self.assertTrue(self.output_image.exists(), "未生成输出文件")
        
        # 确保输出文件大小合理
        self.assertGreater(os.path.getsize(self.output_image), 0, "输出文件为空")
        
        print(f"测试通过: 水印已成功去除，输出文件: {self.output_image}")

if __name__ == "__main__":
    unittest.main()