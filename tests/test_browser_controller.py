"""Tests for BrowserController module"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.browser_controller import BrowserController


class TestBrowserController:
    """BrowserController测试类"""

    @pytest.fixture
    def controller(self):
        return BrowserController(headless=True, cookies_file="test_cookies.json")

    def _make_mock_playwright(self):
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        return mock_pw, mock_browser, mock_context, mock_page

    @pytest.mark.asyncio
    async def test_init_success(self, controller):
        mock_pw, mock_browser, mock_context, mock_page = self._make_mock_playwright()

        with patch("tools.glm_coding_bot.core.browser_controller.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)

            success = await controller.init()

            assert success is True
            assert controller._browser is not None
            assert controller._context is not None
            assert controller._page is not None

    @pytest.mark.asyncio
    async def test_init_failure(self, controller):
        with patch("tools.glm_coding_bot.core.browser_controller.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(side_effect=Exception("Launch failed"))

            success = await controller.init()
            assert success is False

    @pytest.mark.asyncio
    async def test_navigate_to_purchase_success(self, controller):
        mock_pw, mock_browser, mock_context, mock_page = self._make_mock_playwright()

        controller._browser = mock_browser
        controller._context = mock_context
        controller._page = mock_page
        controller._initialized = True

        mock_page.goto = AsyncMock(return_value=AsyncMock(status=200))
        mock_page.evaluate = AsyncMock()

        success = await controller.navigate_to_purchase()

        assert success is True
        mock_page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_buy_button_success(self, controller):
        mock_pw, mock_browser, mock_context, mock_page = self._make_mock_playwright()

        controller._browser = mock_browser
        controller._context = mock_context
        controller._page = mock_page
        controller._initialized = True

        mock_btn = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[mock_btn, mock_btn, mock_btn])

        success = await controller.click_buy_button("Max")

        assert success is True

    @pytest.mark.asyncio
    async def test_click_buy_button_invalid_package(self, controller):
        mock_pw, mock_browser, mock_context, mock_page = self._make_mock_playwright()

        controller._browser = mock_browser
        controller._context = mock_context
        controller._page = mock_page
        controller._initialized = True

        success = await controller.click_buy_button("InvalidPackage")

        assert success is False

    @pytest.mark.asyncio
    async def test_close(self, controller):
        mock_pw, mock_browser, mock_context, mock_page = self._make_mock_playwright()

        controller._browser = mock_browser
        controller._context = mock_context
        controller._page = mock_page
        controller._playwright = mock_pw

        await controller.close()

        mock_browser.close.assert_called_once()

    def test_get_stats(self, controller):
        import time

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
