"""Tests for CaptchaSolver module"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.captcha_solver import CaptchaSolver


class TestCaptchaSolver:
    """CaptchaSolver测试类"""

    @pytest.fixture
    def solver(self):
        return CaptchaSolver(model_path=None, max_retries=2, retry_delay=0.01)

    def test_init_without_model(self, solver):
        assert solver.model_path is None
        assert solver.session is None
        assert solver.max_retries == 2

    def test_init_with_model_file_not_exists(self, tmp_path):
        nonexistent_model = tmp_path / "nonexistent.onnx"
        solver = CaptchaSolver(model_path=str(nonexistent_model))

        assert solver.model_path == nonexistent_model
        assert solver.session is None

    @pytest.mark.asyncio
    async def test_solve_slider_manual_fallback(self, solver):
        mock_page = AsyncMock()

        solver._get_slider_image = AsyncMock(return_value=None)
        solver._manual_solve = AsyncMock(return_value=True)

        result = await solver.solve_slider(mock_page, timeout=1.0)

        assert result is True
        solver._manual_solve.assert_called_once()

    @pytest.mark.asyncio
    async def test_solve_slider_all_failures(self, solver):
        mock_page = AsyncMock()

        solver._get_slider_image = AsyncMock(return_value=None)
        solver._manual_solve = AsyncMock(return_value=False)

        result = await solver.solve_slider(mock_page, timeout=0.5, manual_fallback=True)

        assert result is False

    @pytest.mark.asyncio
    async def test_drag_slider_success(self, solver):
        mock_page = AsyncMock()
        mock_page.mouse.move = AsyncMock()
        mock_page.mouse.down = AsyncMock()
        mock_page.mouse.up = AsyncMock()

        mock_slider = AsyncMock()
        mock_slider.bounding_box = AsyncMock(return_value={
            "x": 100, "y": 200, "width": 40, "height": 40,
        })
        mock_page.query_selector = AsyncMock(return_value=mock_slider)

        result = await solver._drag_slider(mock_page, position=300)

        assert result is True
        mock_page.mouse.down.assert_called_once()
        mock_page.mouse.up.assert_called_once()

    @pytest.mark.asyncio
    async def test_drag_slider_no_slider_found(self, solver):
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        result = await solver._drag_slider(mock_page, position=300)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_captcha_exists_true(self, solver):
        mock_page = AsyncMock()

        mock_element = AsyncMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_page.query_selector = AsyncMock(return_value=mock_element)

        result = await solver._check_captcha_exists(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_captcha_exists_false(self, solver):
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        result = await solver._check_captcha_exists(mock_page)

        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
