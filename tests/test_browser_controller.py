"""Tests for BrowserController module."""

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.config import Config
from tools.glm_coding_bot.core.browser_controller import BrowserController


class TestBrowserController:
    """BrowserController测试类"""

    @pytest.fixture
    def controller(self):
        return BrowserController(headless=True, cookies_file="test_cookies.json")

    @pytest.fixture
    def mock_config(self, tmp_path):
        return Config(user_data_dir=tmp_path / ".glm-coding-bot")

    def _make_mock_playwright(self):
        mock_pw = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_context.pages = []
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_pw.chromium.launch_persistent_context = AsyncMock(return_value=mock_context)

        return mock_pw, mock_context, mock_page

    def test_accepts_legacy_cookies_file_kwarg(self, controller):
        assert controller.cookies_file == "test_cookies.json"

    @pytest.mark.asyncio
    async def test_init_success(self, controller, mock_config):
        mock_pw, mock_context, mock_page = self._make_mock_playwright()

        with (
            patch("tools.glm_coding_bot.core.browser_controller.async_playwright") as mock_async_pw,
            patch("tools.glm_coding_bot.core.browser_controller.get_config", return_value=mock_config),
        ):
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)

            success = await controller.init()

        assert success is True
        assert controller._context is mock_context
        assert controller._page is mock_page
        mock_pw.chromium.launch_persistent_context.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_init_failure(self, controller):
        with patch("tools.glm_coding_bot.core.browser_controller.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(side_effect=Exception("Launch failed"))

            success = await controller.init()

        assert success is False

    @pytest.mark.asyncio
    async def test_navigate_to_purchase_success(self, controller):
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        controller._context = mock_context
        controller._page = mock_page
        controller._initialized = True

        mock_page.goto = AsyncMock(return_value=SimpleNamespace(status=200))
        mock_page.evaluate = AsyncMock()

        success = await controller.navigate_to_purchase()

        assert success is True
        mock_page.goto.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_click_buy_button_success(self, controller):
        mock_page = AsyncMock()
        mock_btn = AsyncMock()

        controller._page = mock_page
        controller._initialized = True
        controller._select_period_tab = AsyncMock(return_value=True)

        mock_page.query_selector_all = AsyncMock(return_value=[mock_btn, mock_btn, mock_btn])

        success = await controller.click_buy_button("Max", "quarterly")

        assert success is True
        controller._select_period_tab.assert_awaited_once_with("quarterly")
        mock_btn.click.assert_awaited()

    @pytest.mark.asyncio
    async def test_click_buy_button_invalid_package(self, controller):
        controller._page = AsyncMock()
        controller._initialized = True

        success = await controller.click_buy_button("InvalidPackage")

        assert success is False

    @pytest.mark.asyncio
    async def test_close(self, controller):
        mock_context = AsyncMock()

        controller._context = mock_context

        await controller.close()

        mock_context.close.assert_awaited_once()

    def test_get_stats(self, controller):
        controller.stats["navigation_count"] = 5
        controller.stats["click_count"] = 10
        controller.stats["error_count"] = 2
        controller._start_time = time.time() - 60

        stats = controller.get_stats()

        assert stats["navigation_count"] == 5
        assert stats["click_count"] == 10
        assert stats["error_count"] == 2
        assert stats["uptime"] >= 60


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
