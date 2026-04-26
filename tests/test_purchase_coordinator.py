"""Tests for PurchaseCoordinator state machine."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.browser_controller import PageState
from tools.glm_coding_bot.core.purchase_coordinator import PurchaseCoordinator
from tools.glm_coding_bot.core.stock_monitor import StockSignal


def make_signal(*, confirmed: bool = True, product_id: str = "product-test-123") -> StockSignal:
    return StockSignal(
        product_id=product_id,
        raw_hit=True,
        confirmed=confirmed,
        confidence=2 if confirmed else 1,
    )


def make_coordinator(
    *,
    page_states,
    signal=None,
    attempt_recover=True,
    click_purchase=True,
):
    page_controller = AsyncMock()
    page_controller.refresh_page_state = AsyncMock(side_effect=page_states)
    page_controller.attempt_recover = AsyncMock(return_value=attempt_recover)
    page_controller.click_purchase = AsyncMock(return_value=click_purchase)

    signal_monitor = AsyncMock()
    signal_monitor.confirm_hit = AsyncMock(return_value=signal or make_signal())

    coordinator = PurchaseCoordinator(
        package="Max",
        period="quarterly",
        product_id="product-test-123",
        page_controller=page_controller,
        signal_monitor=signal_monitor,
    )

    return coordinator, page_controller, signal_monitor


@pytest.mark.asyncio
async def test_run_fails_when_warmup_not_ready():
    coordinator, page_controller, _ = make_coordinator(
        page_states=[PageState(warm_ready=False, hot_ready=False)]
    )

    result = await coordinator.run()

    assert result.success is False
    assert result.failure_reason == "warmup-not-ready"
    assert coordinator.session.phase == "FAILED"
    assert coordinator.session.failure_reason == "warmup-not-ready"
    assert coordinator.session.commit_started is False
    assert coordinator.session.commit_completed is False
    assert coordinator.session.recovery_used is False
    page_controller.click_purchase.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_does_not_commit_when_stock_unconfirmed():
    coordinator, page_controller, signal_monitor = make_coordinator(
        page_states=[PageState(warm_ready=True, hot_ready=True)],
        signal=make_signal(confirmed=False),
    )

    result = await coordinator.run()

    assert result.success is False
    assert result.failure_reason == "stock-unconfirmed"
    assert coordinator.session.failure_reason == "stock-unconfirmed"
    signal_monitor.confirm_hit.assert_awaited_once()
    page_controller.click_purchase.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_does_not_commit_when_signal_product_mismatches():
    coordinator, page_controller, _ = make_coordinator(
        page_states=[PageState(warm_ready=True, hot_ready=True)],
        signal=make_signal(product_id="product-other-999"),
    )

    result = await coordinator.run()

    assert result.success is False
    assert result.failure_reason == "stock-product-mismatch"
    assert coordinator.session.failure_reason == "stock-product-mismatch"
    page_controller.click_purchase.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_commits_when_stock_and_page_ready():
    coordinator, page_controller, _ = make_coordinator(
        page_states=[
            PageState(warm_ready=True, hot_ready=True),
            PageState(warm_ready=True, hot_ready=True),
        ]
    )

    result = await coordinator.run()

    assert result.success is True
    assert result.phase == "COMPLETED"
    assert coordinator.session.phase == "COMPLETED"
    assert coordinator.session.failure_reason is None
    assert coordinator.session.commit_started is True
    assert coordinator.session.commit_completed is True
    assert coordinator.session.recovery_used is False
    page_controller.attempt_recover.assert_not_awaited()
    page_controller.click_purchase.assert_awaited_once_with("Max", "quarterly")


@pytest.mark.asyncio
async def test_run_successful_recovery_rechecks_state_before_commit():
    coordinator, page_controller, _ = make_coordinator(
        page_states=[
            PageState(warm_ready=True, hot_ready=False),
            PageState(warm_ready=True, hot_ready=False),
            PageState(warm_ready=True, hot_ready=True),
        ],
        attempt_recover=True,
    )

    result = await coordinator.run()

    assert result.success is True
    assert coordinator.session.recovery_used is True
    assert coordinator.session.commit_started is True
    assert coordinator.session.commit_completed is True
    assert page_controller.refresh_page_state.await_count == 3
    assert page_controller.attempt_recover.await_count == 1
    page_controller.click_purchase.assert_awaited_once_with("Max", "quarterly")


@pytest.mark.asyncio
async def test_run_uses_single_recovery_before_fail():
    coordinator, page_controller, _ = make_coordinator(
        page_states=[
            PageState(warm_ready=True, hot_ready=False),
            PageState(warm_ready=True, hot_ready=False),
        ],
        attempt_recover=False,
    )

    result = await coordinator.run()

    assert result.success is False
    assert result.failure_reason == "recovery-failed"
    assert coordinator.session.phase == "FAILED"
    assert coordinator.session.failure_reason == "recovery-failed"
    assert coordinator.session.commit_started is False
    assert coordinator.session.commit_completed is False
    assert coordinator.session.recovery_used is True
    page_controller.attempt_recover.assert_awaited_once_with("Max", "quarterly")
    page_controller.click_purchase.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_returns_click_failure_reason():
    coordinator, page_controller, _ = make_coordinator(
        page_states=[
            PageState(warm_ready=True, hot_ready=True),
            PageState(warm_ready=True, hot_ready=True),
        ],
        click_purchase=False,
    )

    result = await coordinator.run()

    assert result.success is False
    assert result.failure_reason == "click-failed"
    assert coordinator.session.phase == "FAILED"
    assert coordinator.session.failure_reason == "click-failed"
    assert coordinator.session.commit_started is True
    assert coordinator.session.commit_completed is False
    assert coordinator.session.recovery_used is False
    page_controller.click_purchase.assert_awaited_once_with("Max", "quarterly")


@pytest.mark.asyncio
async def test_run_resets_session_state_between_runs():
    coordinator, page_controller, signal_monitor = make_coordinator(
        page_states=[
            PageState(warm_ready=True, hot_ready=True),
            PageState(warm_ready=True, hot_ready=True),
        ],
    )

    first_result = await coordinator.run()

    assert first_result.success is True
    assert coordinator.session.commit_started is True
    assert coordinator.session.commit_completed is True

    page_controller.refresh_page_state = AsyncMock(
        side_effect=[PageState(warm_ready=False, hot_ready=False)]
    )
    page_controller.attempt_recover = AsyncMock(return_value=True)
    page_controller.click_purchase = AsyncMock(return_value=True)
    signal_monitor.confirm_hit = AsyncMock(return_value=make_signal())

    second_result = await coordinator.run()

    assert second_result.success is False
    assert second_result.failure_reason == "warmup-not-ready"
    assert coordinator.session.phase == "FAILED"
    assert coordinator.session.failure_reason == "warmup-not-ready"
    assert coordinator.session.commit_started is False
    assert coordinator.session.commit_completed is False
    assert coordinator.session.recovery_used is False
    page_controller.click_purchase.assert_not_awaited()
