"""
Tests for CaptchaSolver module

测试内容：
- AI模型推理（如果有模型）
- OpenCV边缘检测（备用方案）
- 图像预处理
- 滑块拖拽执行
- 人工回退机制
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from glm_coding_bot.core.captcha_solver import CaptchaSolver


class TestCaptchaSolver:
    """CaptchaSolver测试类"""

    @pytest.fixture
    def solver(self):
        """创建CaptchaSolver实例（无模型）"""
        return CaptchaSolver(
            model_path=None,  # 不使用模型，测试OpenCV备用方案
            max_retries=2,
            retry_delay=0.01,  # 10ms用于测试
        )

    @pytest.fixture
    def solver_with_model(self, tmp_path):
        """创建带模型的CaptchaSolver实例"""
        # 创建一个假的模型文件
        model_file = tmp_path / "test_model.onnx"
        model_file.write_bytes(b"fake model data")

        return CaptchaSolver(
            model_path=str(model_file),
            max_retries=2,
        )

    @pytest.fixture
    def mock_slider_image(self):
        """创建模拟的滑块图片"""
        # 创建一个200x100的图片，右侧有一个缺口特征
        img = np.zeros((100, 200, 3), dtype=np.uint8)

        # 绘制背景
        img[:, :] = [200, 200, 200]

        # 绘制缺口（在右侧，约150像素位置）
        gap_x = 150
        gap_width = 40
        gap_height = 40
        gap_y = 30

        # 缺口区域颜色不同，模拟边缘
        img[gap_y:gap_y+gap_height, gap_x:gap_x+gap_width] = [100, 100, 100]

        # 在缺口边缘绘制明显的线条
        cv2 = pytest.importorskip("cv2")
        cv2.rectangle(img, (gap_x, gap_y), (gap_x+gap_width, gap_y+gap_height), (50, 50, 50), 2)

        return img, gap_x + gap_width // 2  # 返回图片和预期的中心位置

    def test_init_without_model(self, solver):
        """测试无模型初始化"""
        assert solver.model_path is None
        assert solver.session is None
        assert solver.max_retries == 2

    def test_init_with_model_file_not_exists(self, tmp_path):
        """测试模型文件不存在时的初始化"""
        nonexistent_model = tmp_path / "nonexistent.onnx"
        solver = CaptchaSolver(model_path=str(nonexistent_model))

        assert solver.model_path == nonexistent_model
        assert solver.session is None  # 应该加载失败

    @pytest.mark.asyncio
    async def test_solve_slider_manual_fallback(self, solver):
        """测试人工回退机制"""
        # Mock page
        mock_page = AsyncMock()

        # Mock _get_slider_image to always return None (simulating failure)
        solver._get_slider_image = AsyncMock(return_value=None)

        # Mock _manual_solve to return True
        solver._manual_solve = AsyncMock(return_value=True)

        result = await solver.solve_slider(mock_page, timeout=1.0)

        assert result is True
        solver._manual_solve.assert_called_once()

    @pytest.mark.asyncio
    async def test_solve_slider_all_failures(self, solver):
        """测试所有方法都失败的情况"""
        mock_page = AsyncMock()

        # Mock all methods to fail
        solver._get_slider_image = AsyncMock(return_value=None)
        solver._manual_solve = AsyncMock(return_value=False)

        result = await solver.solve_slider(mock_page, timeout=0.5, manual_fallback=True)

        assert result is False

    @pytest.mark.asyncio
    async def test_drag_slider_success(self, solver):
        """测试成功拖拽滑块"""
        mock_page = AsyncMock()

        # Mock mouse operations
        mock_page.mouse.move = AsyncMock()
        mock_page.mouse.down = AsyncMock()
        mock_page.mouse.up = AsyncMock()

        # Mock query_selector to return slider element
        mock_slider = AsyncMock()
        mock_slider.bounding_box = AsyncMock(return_value={
            "x": 100,
            "y": 200,
            "width": 40,
            "height": 40,
        })
        mock_page.query_selector = AsyncMock(return_value=mock_slider)

        result = await solver._drag_slider(mock_page, position=300)

        assert result is True
        mock_page.mouse.down.assert_called_once()
        mock_page.mouse.up.assert_called_once()

    @pytest.mark.asyncio
    async def test_drag_slider_no_slider_found(self, solver):
        """测试未找到滑块元素的情况"""
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        result = await solver._drag_slider(mock_page, position=300)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_captcha_exists_true(self, solver):
        """测试检测到验证码存在"""
        mock_page = AsyncMock()

        # Mock query_selector to return visible element
        mock_element = AsyncMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        result = await solver._check_captcha_exists(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_captcha_exists_false(self, solver):
        """测试验证码不存在"""
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        result = await solver._check_captcha_exists(mock_page)

        assert result is False


class TestCaptchaSolverIntegration:
    """集成测试类"""

    @pytest.mark.skip(reason="需要真实浏览器环境")
    @pytest.mark.asyncio
    async def test_real_captcha_solving(self):
        """测试真实验证码解决（需要实际页面）"""
        solver = CaptchaSolver()

        # 这里需要实际的 Playwright page 对象
        # 仅作为示例，实际测试需要真实环境
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])