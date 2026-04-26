"""Tests for PurchaseCoordinator state machine."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.browser_controller import PageState
from tools.glm_coding_bot.core.purchase_coordinator import PurchaseCoordinator
from tools.glm_coding_bot.core.stock_monitor import StockSignal


@pytest.mark.asyncio
async def test_run_commits_when_stock_and_page_ready():
    page_controller = AsyncMock()
    page_controller.refresh_page_state = AsyncMock(return_value=PageState(warm_ready=True, hot_ready=True))
    page_controller.click_purchase = AsyncMock(return_value=True)

    signal_monitor = AsyncMock()
    signal_monitor.confirm_hit = AsyncMock(
        return_value=StockSignal(
            product_id="product-test-123",
            raw_hit=True,
            confirmed=True,
            confidence=2,
        )
    )

    coordinator = PurchaseCoordinator(
        package="Max",
        period="quarterly",
        product_id="product-test-123",
        page_controller=page_controller,
        signal_monitor=signal_monitor,
    )

    result = await coordinator.run()

    assert result.success is True
    assert result.phase == "COMPLETED"
    page_controller.click_purchase.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_uses_single_recovery_before_fail():
    page_controller = AsyncMock()
    page_controller.refresh_page_state = AsyncMock(
        side_effect=[
            PageState(warm_ready=True, hot_ready=False),
            PageState(warm_ready=True, hot_ready=False),
        ]
    )
    page_controller.attempt_recover = AsyncMock(return_value=False)

    signal_monitor = AsyncMock()
    signal_monitor.confirm_hit = AsyncMock(
        return_value=StockSignal(
            product_id="product-test-123",
            raw_hit=True,
            confirmed=True,
            confidence=2,
        )
    )

    coordinator = PurchaseCoordinator(
        package="Max",
        period="quarterly",
        product_id="product-test-123",
        page_controller=page_controller,
        signal_monitor=signal_monitor,
    )

    result = await coordinator.run()

    assert result.success is False
    assert result.failure_reason == "recovery-failed"
    page_controller.attempt_recover.assert_awaited_once()
