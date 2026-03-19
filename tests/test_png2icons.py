import os
import sys
import tempfile
from pathlib import Path
import unittest
from PIL import Image

# 添加项目根目录到路径，以便导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.png2Icons.main import generate_ico, check_macos_tools

class TestPNG2Icons(unittest.TestCase):
    def setUp(self):
        # 创建临时目录用于测试
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # 创建一个测试用的 PNG 文件
        self.test_png = self.temp_path / "test_icon.png"
        img = Image.new('RGBA', (256, 256), (255, 0, 0, 255))  # 红色正方形
        img.save(self.test_png, format='PNG')
        
        # 输出文件路径
        self.test_ico = self.temp_path / "test_icon.ico"
        self.test_icns = self.temp_path / "test_icon.icns"
    
    def tearDown(self):
        # 清理临时目录
        self.temp_dir.cleanup()
    
    def test_generate_ico(self):
        """测试生成 ICO 文件的功能"""
        # 执行生成 ICO 文件
        generate_ico(str(self.test_png), str(self.test_ico))
        
        # 验证文件是否生成
        self.assertTrue(self.test_ico.exists(), "ICO 文件未生成")
        
        # 验证文件大小是否合理
        self.assertGreater(self.test_ico.stat().st_size, 0, "ICO 文件为空")
    
    def test_check_macos_tools(self):
        """测试检查 macOS 工具的功能"""
        from tools.png2Icons.main import check_macos_tools
        # 这个测试只在 macOS 上有意义
        if sys.platform == 'darwin':
            result = check_macos_tools()
            self.assertTrue(result, "macOS 工具检查失败")
        else:
            # 在非 macOS 系统上，这个函数应该返回 False
            result = check_macos_tools()
            self.assertFalse(result, "非 macOS 系统上应该返回 False")
    
    def test_non_square_image(self):
        """测试处理非正方形图片的功能"""
        # 创建一个非正方形的测试图片
        non_square_png = self.temp_path / "non_square.png"
        img = Image.new('RGBA', (100, 200), (0, 255, 0, 255))  # 绿色长方形
        img.save(non_square_png, format='PNG')
        
        # 执行生成 ICO 文件
        non_square_ico = self.temp_path / "non_square.ico"
        generate_ico(str(non_square_png), str(non_square_ico))
        
        # 验证文件是否生成
        self.assertTrue(non_square_ico.exists(), "非正方形图片的 ICO 文件未生成")
        self.assertGreater(non_square_ico.stat().st_size, 0, "非正方形图片的 ICO 文件为空")

if __name__ == '__main__':
    unittest.main()
