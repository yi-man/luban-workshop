"""
Tests for BrowserController module

测试内容：
- 浏览器初始化和关闭
- 页面导航
- 元素交互
- Cookie管理
- 错误处理
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from glm_coding_bot.core.browser_controller import BrowserController, BrowserError, NavigationError


class TestBrowserController:
    """BrowserController测试类"""

    @pytest.fixture
    def controller(self):
        """创建BrowserController实例"""
        return BrowserController(
            headless=True,
            cookies_file="test_cookies.json",
            max_retries=2,
        )

    @pytest.fixture
    def mock_playwright(self):
        """创建mock playwright对象"""
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.cookies = AsyncMock(return_value=[
            {"name": "test", "value": "value", "domain": ".bigmodel.cn"}
        ])

        return mock_pw, mock_browser, mock_context, mock_page

    @pytest.mark.asyncio
    async def test_init_success(self, controller, mock_playwright):
        """测试成功初始化"""
        mock_pw, mock_browser, mock_context, mock_page = mock_playwright

        with patch("glm_coding_bot.core.browser_controller.async_playwright") as mock_async_pw:
            mock_async_pw.start = AsyncMock(return_value=mock_pw)

            success = await controller.init()

            assert success is True
            assert controller.browser is not None
            assert controller.context is not None
            assert controller.page is not None

    @pytest.mark.asyncio
    async def test_init_retry_on_failure(self, controller):
        """测试初始化失败重试"""
        with patch("glm_coding_bot.core.browser_controller.async_playwright") as mock_async_pw:
            mock_async_pw.start = AsyncMock(side_effect=Exception("Launch failed"))

            with pytest.raises(BrowserError):
                await controller.init()

    @pytest.mark.asyncio
    async def test_navigate_to_purchase_success(self, controller, mock_playwright):
        """测试成功导航到购买页面"""
        mock_pw, mock_browser, mock_context, mock_page = mock_playwright

        controller.browser = mock_browser
        controller.context = mock_context
        controller.page = mock_page

        # Mock page.goto
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.evaluate = AsyncMock()

        success = await controller.navigate_to_purchase()

        assert success is True
        mock_page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigate_to_purchase_http_error(self, controller, mock_playwright):
        """测试导航HTTP错误"""
        mock_pw, mock_browser, mock_context, mock_page = mock_playwright

        controller.browser = mock_browser
        controller.context = mock_context
        controller.page = mock_page

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_page.goto = AsyncMock(return_value=mock_response)

        with pytest.raises(NavigationError):
            await controller.navigate_to_purchase()

    @pytest.mark.asyncio
    async def test_click_buy_button_success(self, controller, mock_playwright):
        """测试成功点击购买按钮"""
        mock_pw, mock_browser, mock_context, mock_page = mock_playwright

        controller.browser = mock_browser
        controller.context = mock_context
        controller.page = mock_page

        # Mock page methods
        mock_page.wait_for_selector = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=AsyncMock())

        success = await controller.click_buy_button("Max")

        assert success is True

    @pytest.mark.asyncio
    async def test_click_buy_button_invalid_package(self, controller, mock_playwright):
        """测试无效套餐类型"""
        mock_pw, mock_browser, mock_context, mock_page = mock_playwright

        controller.browser = mock_browser
        controller.context = mock_context
        controller.page = mock_page

        success = await controller.click_buy_button("InvalidPackage")

        assert success is False

    @pytest.mark.asyncio
    async def test_close(self, controller, mock_playwright, tmp_path):
        """测试关闭浏览器"""
        mock_pw, mock_browser, mock_context, mock_page = mock_playwright

        controller.browser = mock_browser
        controller.context = mock_context
        controller.page = mock_page
        controller._playwright = mock_pw
        controller.cookies_file = tmp_path / "test_cookies.json"

        # Mock context.cookies
        mock_context.cookies = AsyncMock(return_value=[
            {"name": "test", "value": "value", "domain": ".bigmodel.cn", "expires": 9999999999}
        ])

        await controller.close()

        # Verify cookies were saved
        assert controller.cookies_file.exists()
        saved_cookies = json.loads(controller.cookies_file.read_text())
        assert len(saved_cookies) == 1
        assert saved_cookies[0]["name"] == "test"

        # Verify browser was closed
        mock_browser.close.assert_called_once()

    def test_get_stats(self, controller):
        """测试获取统计信息"""
        import time

        controller.stats["navigation_count"] = 5
        controller.stats["click_count"] = 10
        controller.stats["error_count"] = 2
        controller.stats["start_time"] = time.time() - 60  # 60秒前启动

        stats = controller.get_stats()

        assert stats["navigation_count"] == 5
        assert stats["click_count"] == 10
        assert stats["error_count"] == 2
        assert stats["uptime"] >= 60


class TestBrowserControllerIntegration:
    """集成测试类"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要真实浏览器环境")
    async def test_real_browser_launch(self):
        """测试真实浏览器启动（需要本地Chrome）"""
        controller = BrowserController(headless=True)

        try:
            success = await controller.init()
            assert success is True

            # 测试导航到实际页面
            nav_success = await controller.navigate_to_purchase()
            assert nav_success is True

        finally:
            await controller.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])