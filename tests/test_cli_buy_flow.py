"""Tests for CLI buy orchestration through PurchaseCoordinator."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from tools.glm_coding_bot import cli as cli_module
from tools.glm_coding_bot.config import Config
from tools.glm_coding_bot.core.stock_monitor import StockSignalMonitor
from tools.glm_coding_bot.core.purchase_coordinator import PurchaseResult
from tools.glm_coding_bot.product_mapping import SubscriptionPeriod, get_product_id


class DummyStatus:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def make_page_controller():
    controller = AsyncMock()
    controller.init = AsyncMock(return_value=True)
    controller.navigate_to_purchase = AsyncMock(return_value=True)
    controller.click_buy_button = AsyncMock(return_value=True)
    controller.handle_captcha = AsyncMock(return_value=True)
    controller.close = AsyncMock(return_value=None)
    controller.get_stats = Mock(
        return_value={
            "navigation_count": 0,
            "click_count": 0,
            "error_count": 0,
        }
    )
    return controller


@pytest.mark.asyncio
async def test_buy_wires_expected_coordinator_dependencies_after_browser_warmup(
    monkeypatch, tmp_path
):
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot")
    cookie_file = config.user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    expected_product_id = get_product_id("Max", SubscriptionPeriod("quarterly"))
    constructor_kwargs = {}
    events: list[str] = []
    coordinator = AsyncMock()
    coordinator.run = AsyncMock(
        return_value=PurchaseResult(success=True, phase="COMPLETED")
    )
    page_controller = make_page_controller()
    page_controller.init = AsyncMock(side_effect=lambda: events.append("init"))
    page_controller.navigate_to_purchase = AsyncMock(
        side_effect=lambda: events.append("navigate") or True
    )

    async def run_coordinator():
        events.append("run")
        return PurchaseResult(success=True, phase="COMPLETED")

    coordinator.run = AsyncMock(side_effect=run_coordinator)

    def fake_purchase_coordinator(**kwargs):
        constructor_kwargs.update(kwargs)
        return coordinator

    monkeypatch.setattr(cli_module, "get_config", lambda: config)
    monkeypatch.setattr(
        cli_module,
        "_verify_login_session",
        AsyncMock(return_value=cli_module.SessionCheckResult.valid("ok")),
    )
    monkeypatch.setattr(
        cli_module.TimeSync,
        "sync",
        AsyncMock(return_value=SimpleNamespace(success=True, offset_ms=0.0)),
    )
    monkeypatch.setattr(cli_module, "PurchaseCoordinator", fake_purchase_coordinator)
    monkeypatch.setattr(cli_module, "BrowserController", lambda **kwargs: page_controller)
    monkeypatch.setattr(cli_module, "Status", DummyStatus)
    sleep = AsyncMock(return_value=None)
    monkeypatch.setattr(cli_module.asyncio, "sleep", sleep)

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True)

    assert constructor_kwargs["package"] == "Max"
    assert constructor_kwargs["period"] == "quarterly"
    assert constructor_kwargs["product_id"] == expected_product_id
    assert constructor_kwargs["page_controller"] is page_controller
    assert isinstance(constructor_kwargs["signal_monitor"], StockSignalMonitor)
    assert constructor_kwargs["signal_monitor"].product_id == expected_product_id
    assert events == ["init", "navigate", "run"]
    coordinator.run.assert_awaited_once()
    page_controller.init.assert_awaited_once()
    page_controller.navigate_to_purchase.assert_awaited_once()
    page_controller.handle_captcha.assert_awaited_once_with(timeout=15.0)
    sleep.assert_awaited_once_with(10)


@pytest.mark.asyncio
async def test_buy_stops_when_coordinator_fails(monkeypatch, tmp_path):
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot")
    cookie_file = config.user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    coordinator = AsyncMock()
    coordinator.run = AsyncMock(
        return_value=PurchaseResult(
            success=False,
            phase="FAILED",
            failure_reason="stock-unconfirmed",
        )
    )
    page_controller = make_page_controller()
    messages: list[str] = []

    monkeypatch.setattr(cli_module, "get_config", lambda: config)
    monkeypatch.setattr(
        cli_module,
        "_verify_login_session",
        AsyncMock(return_value=cli_module.SessionCheckResult.valid("ok")),
    )
    monkeypatch.setattr(
        cli_module.TimeSync,
        "sync",
        AsyncMock(return_value=SimpleNamespace(success=True, offset_ms=0.0)),
    )
    monkeypatch.setattr(cli_module, "PurchaseCoordinator", lambda **kwargs: coordinator)
    monkeypatch.setattr(cli_module, "BrowserController", lambda **kwargs: page_controller)
    monkeypatch.setattr(cli_module, "Status", DummyStatus)
    sleep = AsyncMock(return_value=None)
    monkeypatch.setattr(cli_module.asyncio, "sleep", sleep)
    monkeypatch.setattr(
        cli_module.console,
        "print",
        lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args)),
    )

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True)

    coordinator.run.assert_awaited_once()
    page_controller.handle_captcha.assert_not_awaited()
    sleep.assert_not_awaited()
    assert any("抢购失败: stock-unconfirmed" in message for message in messages)
