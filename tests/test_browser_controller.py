"""Tests for BrowserController module."""

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.config import Config
from tools.glm_coding_bot.core.browser_controller import BrowserController, PageState


@pytest.fixture
def controller():
    return BrowserController(headless=True, cookies_file="test_cookies.json")


class TestBrowserController:
    """BrowserController测试类"""

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


@pytest.mark.asyncio
async def test_get_page_state_reports_hot_ready_when_button_clickable(controller):
    mock_page = AsyncMock()
    mock_page.url = f"{controller.base_url}/glm-coding"
    mock_page.viewport_size = {"width": controller.width, "height": controller.height}
    controller._page = mock_page
    controller._initialized = True
    controller._select_period_tab = AsyncMock(side_effect=AssertionError("refresh should not mutate page state"))
    controller._is_period_tab_ready = AsyncMock(return_value=True)
    controller._has_login_prompt = AsyncMock(return_value=False)
    controller._has_blocking_overlay = AsyncMock(return_value=False)

    mock_button = AsyncMock()
    mock_button.is_visible = AsyncMock(return_value=True)
    mock_button.is_enabled = AsyncMock(return_value=True)
    mock_button.bounding_box = AsyncMock(return_value={"x": 100, "y": 250, "width": 180, "height": 48})
    mock_page.query_selector_all = AsyncMock(return_value=[mock_button, mock_button, mock_button])

    state = await controller.refresh_page_state("Max", "quarterly")

    assert state.warm_ready is True
    assert state.hot_ready is True


@pytest.mark.asyncio
async def test_get_page_state_requires_glm_coding_route(controller):
    mock_page = AsyncMock()
    mock_page.url = f"{controller.base_url}/dashboard"
    mock_page.viewport_size = {"width": controller.width, "height": controller.height}
    controller._page = mock_page
    controller._initialized = True
    controller._is_period_tab_ready = AsyncMock(return_value=True)
    controller._has_login_prompt = AsyncMock(return_value=False)
    controller._has_blocking_overlay = AsyncMock(return_value=False)

    mock_button = AsyncMock()
    mock_button.is_visible = AsyncMock(return_value=True)
    mock_button.is_enabled = AsyncMock(return_value=True)
    mock_button.bounding_box = AsyncMock(return_value={"x": 100, "y": 250, "width": 180, "height": 48})
    mock_page.query_selector_all = AsyncMock(return_value=[mock_button, mock_button, mock_button])

    state = await controller.refresh_page_state("Max", "quarterly")

    assert state.route_ok is False
    assert state.warm_ready is False
    assert state.hot_ready is False


@pytest.mark.asyncio
async def test_get_page_state_requires_expected_origin(controller):
    mock_page = AsyncMock()
    mock_page.url = "https://example.com/glm-coding"
    mock_page.viewport_size = {"width": controller.width, "height": controller.height}
    controller._page = mock_page
    controller._initialized = True
    controller._is_period_tab_ready = AsyncMock(return_value=True)
    controller._has_login_prompt = AsyncMock(return_value=False)
    controller._has_blocking_overlay = AsyncMock(return_value=False)

    mock_button = AsyncMock()
    mock_button.is_visible = AsyncMock(return_value=True)
    mock_button.is_enabled = AsyncMock(return_value=True)
    mock_button.bounding_box = AsyncMock(return_value={"x": 100, "y": 250, "width": 180, "height": 48})
    mock_page.query_selector_all = AsyncMock(return_value=[mock_button, mock_button, mock_button])

    state = await controller.refresh_page_state("Max", "quarterly")

    assert state.route_ok is False
    assert state.warm_ready is False
    assert state.hot_ready is False


@pytest.mark.asyncio
async def test_is_period_tab_ready_requires_selected_state(controller):
    controller._page = Mock()
    mock_locator = AsyncMock()
    mock_tab = AsyncMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_locator.first = mock_tab
    mock_tab.is_visible = AsyncMock(return_value=True)
    mock_tab.evaluate = AsyncMock(return_value=False)
    controller._page.locator = Mock(return_value=mock_locator)

    ready = await controller._is_period_tab_ready("quarterly")

    assert ready is False


@pytest.mark.asyncio
async def test_get_page_state_ignores_hidden_overlay_nodes(controller):
    mock_page = AsyncMock()
    mock_page.url = f"{controller.base_url}/glm-coding"
    mock_page.viewport_size = {"width": controller.width, "height": controller.height}
    controller._page = mock_page
    controller._initialized = True
    controller._is_period_tab_ready = AsyncMock(return_value=True)
    controller._has_login_prompt = AsyncMock(return_value=False)

    mock_button = AsyncMock()
    mock_button.is_visible = AsyncMock(return_value=True)
    mock_button.is_enabled = AsyncMock(return_value=True)
    mock_button.bounding_box = AsyncMock(return_value={"x": 100, "y": 250, "width": 180, "height": 48})

    hidden_overlay = AsyncMock()
    hidden_overlay.is_visible = AsyncMock(return_value=False)

    async def query_selector_all(selector):
        if selector == ".buy-btn":
            return [mock_button, mock_button, mock_button]
        if selector == ".captcha-component, .tencent-captcha-dy, .ant-modal-mask":
            return [hidden_overlay]
        return []

    mock_page.query_selector_all = AsyncMock(side_effect=query_selector_all)

    state = await controller.refresh_page_state("Max", "quarterly")

    assert state.captcha_blocking is False
    assert state.hot_ready is True


@pytest.mark.asyncio
async def test_get_page_state_visible_overlay_blocks_hot_ready(controller):
    mock_page = AsyncMock()
    mock_page.url = f"{controller.base_url}/glm-coding"
    mock_page.viewport_size = {"width": controller.width, "height": controller.height}
    controller._page = mock_page
    controller._initialized = True
    controller._is_period_tab_ready = AsyncMock(return_value=True)
    controller._has_login_prompt = AsyncMock(return_value=False)

    mock_button = AsyncMock()
    mock_button.is_visible = AsyncMock(return_value=True)
    mock_button.is_enabled = AsyncMock(return_value=True)
    mock_button.bounding_box = AsyncMock(return_value={"x": 100, "y": 250, "width": 180, "height": 48})

    visible_overlay = AsyncMock()
    visible_overlay.is_visible = AsyncMock(return_value=True)

    async def query_selector_all(selector):
        if selector == ".buy-btn":
            return [mock_button, mock_button, mock_button]
        if selector == ".captcha-component, .tencent-captcha-dy, .ant-modal-mask":
            return [visible_overlay]
        return []

    mock_page.query_selector_all = AsyncMock(side_effect=query_selector_all)

    state = await controller.refresh_page_state("Max", "quarterly")

    assert state.captcha_blocking is True
    assert state.hot_ready is False


@pytest.mark.asyncio
async def test_attempt_recover_only_repositions_existing_page(controller):
    controller._page = AsyncMock()
    controller.navigate_to_purchase = AsyncMock()
    controller._select_period_tab = AsyncMock(return_value=True)
    controller._resolve_buy_button = AsyncMock(return_value=AsyncMock())
    controller.refresh_page_state = AsyncMock(return_value=PageState(warm_ready=True, hot_ready=True))

    recovered = await controller.attempt_recover("Max", "quarterly")

    assert recovered is True
    controller._page.evaluate.assert_awaited_once_with("() => window.scrollTo(0, 800)")
    controller.refresh_page_state.assert_awaited_once_with("Max", "quarterly")
    controller.navigate_to_purchase.assert_not_awaited()


@pytest.mark.asyncio
async def test_attempt_recover_fails_when_page_is_still_not_ready(controller):
    controller._page = AsyncMock()
    controller._select_period_tab = AsyncMock(return_value=True)
    controller._resolve_buy_button = AsyncMock(return_value=AsyncMock())
    controller.refresh_page_state = AsyncMock(return_value=PageState(warm_ready=True, hot_ready=False))

    recovered = await controller.attempt_recover("Max", "quarterly")

    assert recovered is False
    controller.refresh_page_state.assert_awaited_once_with("Max", "quarterly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
