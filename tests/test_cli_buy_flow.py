"""Tests for CLI buy orchestration through PurchaseCoordinator."""

from datetime import datetime as real_datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from tools.glm_coding_bot import cli as cli_module
from tools.glm_coding_bot.config import Config
from tools.glm_coding_bot.core.browser_controller import CheckoutResult, PageState
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
    controller.refresh_page_state = AsyncMock(
        return_value=PageState(
            current_url="https://bigmodel.cn/glm-coding",
            session_ok=True,
            route_ok=True,
            period_ok=True,
            button_present=True,
            button_clickable=True,
            viewport_ok=True,
            captcha_blocking=False,
            warm_ready=True,
            hot_ready=True,
        )
    )
    controller.click_buy_button = AsyncMock(return_value=True)
    controller.handle_captcha = AsyncMock(return_value=True)
    controller.complete_balance_only_checkout = AsyncMock(
        return_value=CheckoutResult(success=True, phase="COMPLETED")
    )
    controller.close = AsyncMock(return_value=None)
    controller.get_stats = Mock(
        return_value={
            "navigation_count": 0,
            "click_count": 0,
            "error_count": 0,
        }
    )
    return controller


class FakeDatetime(real_datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 4, 28, 9, 49, 0)

    @classmethod
    def strptime(cls, date_string, fmt):
        parsed = real_datetime.strptime(date_string, fmt)
        return cls(parsed.year, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second)


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

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True, dry_run=False)

    assert constructor_kwargs["package"] == "Max"
    assert constructor_kwargs["period"] == "quarterly"
    assert constructor_kwargs["product_id"] == expected_product_id
    assert constructor_kwargs["page_controller"] is page_controller
    assert isinstance(constructor_kwargs["signal_monitor"], StockSignalMonitor)
    assert constructor_kwargs["signal_monitor"].product_id == expected_product_id
    assert constructor_kwargs["signal_monitor"]._checker is not None
    assert events == ["init", "navigate", "run"]
    coordinator.run.assert_awaited_once()
    page_controller.init.assert_awaited_once()
    page_controller.navigate_to_purchase.assert_awaited_once()
    page_controller.complete_balance_only_checkout.assert_awaited_once_with(timeout=15.0)
    page_controller.handle_captcha.assert_not_awaited()
    sleep.assert_not_awaited()


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

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True, dry_run=False)

    coordinator.run.assert_awaited_once()
    page_controller.complete_balance_only_checkout.assert_not_awaited()
    page_controller.handle_captcha.assert_not_awaited()
    sleep.assert_not_awaited()
    assert any("抢购失败: stock-unconfirmed" in message for message in messages)


@pytest.mark.asyncio
async def test_buy_reports_insufficient_balance_when_balance_only_checkout_rejects(monkeypatch, tmp_path):
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot")
    cookie_file = config.user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    coordinator = AsyncMock()
    coordinator.run = AsyncMock(
        return_value=PurchaseResult(success=True, phase="COMPLETED")
    )
    page_controller = make_page_controller()
    page_controller.complete_balance_only_checkout = AsyncMock(
        return_value=CheckoutResult(
            success=False,
            phase="FAILED",
            failure_reason="insufficient-balance",
        )
    )
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
    monkeypatch.setattr(cli_module.asyncio, "sleep", AsyncMock(return_value=None))
    monkeypatch.setattr(
        cli_module.console,
        "print",
        lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args)),
    )

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True, dry_run=False)

    coordinator.run.assert_awaited_once()
    page_controller.complete_balance_only_checkout.assert_awaited_once_with(timeout=15.0)
    assert any("余额不足" in message for message in messages)


@pytest.mark.asyncio
async def test_buy_dry_run_stops_after_page_probe(monkeypatch, tmp_path):
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot")
    cookie_file = config.user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    page_controller = make_page_controller()
    messages: list[str] = []
    purchase_coordinator = Mock(side_effect=AssertionError("dry-run should not construct coordinator"))

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
    monkeypatch.setattr(cli_module, "PurchaseCoordinator", purchase_coordinator)
    monkeypatch.setattr(cli_module, "BrowserController", lambda **kwargs: page_controller)
    monkeypatch.setattr(cli_module, "Status", DummyStatus)
    sleep = AsyncMock(return_value=None)
    monkeypatch.setattr(cli_module.asyncio, "sleep", sleep)
    monkeypatch.setattr(
        cli_module.console,
        "print",
        lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args)),
    )

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True, dry_run=True)

    purchase_coordinator.assert_not_called()
    page_controller.init.assert_awaited_once()
    page_controller.navigate_to_purchase.assert_awaited_once()
    page_controller.refresh_page_state.assert_awaited_once_with("Max", "quarterly")
    page_controller.handle_captcha.assert_not_awaited()
    sleep.assert_not_awaited()
    assert any("Dry Run" in message or "dry-run" in message for message in messages)
    assert any("current_url=https://bigmodel.cn/glm-coding" in message for message in messages)
    assert any("hot_ready=True" in message for message in messages)


@pytest.mark.asyncio
async def test_buy_dry_run_reports_not_ready_state(monkeypatch, tmp_path):
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot")
    cookie_file = config.user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    page_controller = make_page_controller()
    page_controller.refresh_page_state = AsyncMock(
        return_value=PageState(
            current_url="https://bigmodel.cn/html/rate-limit.html?redirect=%2Fglm-coding",
            session_ok=True,
            route_ok=False,
            period_ok=True,
            button_present=True,
            button_clickable=False,
            viewport_ok=True,
            captcha_blocking=False,
            warm_ready=False,
            hot_ready=False,
            last_failure_reason="not-hot-ready",
        )
    )
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
    monkeypatch.setattr(
        cli_module,
        "PurchaseCoordinator",
        Mock(side_effect=AssertionError("dry-run should not construct coordinator")),
    )
    monkeypatch.setattr(cli_module, "BrowserController", lambda **kwargs: page_controller)
    monkeypatch.setattr(cli_module, "Status", DummyStatus)
    monkeypatch.setattr(cli_module.asyncio, "sleep", AsyncMock(return_value=None))
    monkeypatch.setattr(
        cli_module.console,
        "print",
        lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args)),
    )

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True, dry_run=True)

    assert any("current_url=https://bigmodel.cn/html/rate-limit.html?redirect=%2Fglm-coding" in message for message in messages)
    assert any("route_ok=False" in message for message in messages)
    assert any("last_failure_reason=not-hot-ready" in message for message in messages)


def test_compute_buy_schedule_opens_browser_before_commit_window():
    now_dt = real_datetime(2026, 4, 28, 9, 49, 0)

    schedule = cli_module._compute_buy_schedule(
        now_dt=now_dt,
        target_time="10:00:00",
        ntp_offset_ms=0.0,
        prewarm_seconds=600.0,
        commit_lead_seconds=10.0,
    )

    assert schedule.target_at == real_datetime(2026, 4, 28, 10, 0, 0)
    assert schedule.prewarm_at == real_datetime(2026, 4, 28, 9, 50, 0)
    assert schedule.commit_at == real_datetime(2026, 4, 28, 9, 59, 50)


@pytest.mark.asyncio
async def test_buy_dry_run_waits_until_prewarm_before_opening_browser(monkeypatch, tmp_path):
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot", prewarm_seconds=600.0)
    cookie_file = config.user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    page_controller = make_page_controller()
    messages: list[str] = []

    monkeypatch.setattr(cli_module, "datetime", FakeDatetime)
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
    monkeypatch.setattr(
        cli_module,
        "PurchaseCoordinator",
        Mock(side_effect=AssertionError("dry-run should not construct coordinator")),
    )
    monkeypatch.setattr(cli_module, "BrowserController", lambda **kwargs: page_controller)
    monkeypatch.setattr(cli_module, "Status", DummyStatus)
    sleep = AsyncMock(return_value=None)
    monkeypatch.setattr(cli_module.asyncio, "sleep", sleep)
    monkeypatch.setattr(
        cli_module.console,
        "print",
        lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args)),
    )

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=False, dry_run=True)

    page_controller.init.assert_awaited_once()
    page_controller.navigate_to_purchase.assert_awaited_once()
    sleep.assert_awaited_once_with(60.0)
    assert any("等待到 09:50:00" in message for message in messages)
