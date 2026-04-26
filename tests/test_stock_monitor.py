"""Tests for StockMonitor module"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.stock_monitor import StockInfo, StockMonitor, StockSignalMonitor


def _make_mock_response(status=200, json_data=None):
    """Create a mock aiohttp response that supports async context manager."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data or {})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)
    return mock_resp


def _make_mock_session(responses=None):
    """Create a mock aiohttp session with async context manager responses."""
    mock_session = MagicMock()
    if responses is None:
        responses = [_make_mock_response()]

    mock_session.get = MagicMock()
    mock_session.get.return_value = responses[0] if len(responses) == 1 else responses
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    return mock_session


@pytest.fixture
def stock_monitor():
    return StockMonitor(product_id="product-test-123", poll_interval=0.01)


@pytest.mark.asyncio
async def test_check_once_without_business_signal_is_not_available(stock_monitor):
    mock_resp = _make_mock_response(status=200, json_data={"code": 200, "data": {}})
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    result = await stock_monitor.check_stock_once(session=mock_session)

    assert result.available is False


@pytest.mark.asyncio
async def test_check_once_with_positive_magnitude_is_available(stock_monitor):
    mock_resp = _make_mock_response(
        status=200,
        json_data={
            "code": 200,
            "data": {"magnitude": 100, "productId": "product-test-123"},
        },
    )
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    result = await stock_monitor.check_stock_once(session=mock_session)

    assert result.available is True
    assert result.raw_data["data"]["magnitude"] == 100


@pytest.mark.asyncio
async def test_check_once_with_positive_tokens_is_available(stock_monitor):
    mock_resp = _make_mock_response(
        status=200,
        json_data={
            "code": 200,
            "data": {"tokens": 5, "productId": "product-test-123"},
        },
    )
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    result = await stock_monitor.check_stock_once(session=mock_session)

    assert result.available is True
    assert result.tokens == 5


@pytest.mark.asyncio
async def test_check_once_with_positive_times_is_available(stock_monitor):
    mock_resp = _make_mock_response(
        status=200,
        json_data={
            "code": 200,
            "data": {"times": 2, "productId": "product-test-123"},
        },
    )
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    result = await stock_monitor.check_stock_once(session=mock_session)

    assert result.available is True
    assert result.times == 2


@pytest.mark.asyncio
async def test_check_once_with_boolean_business_signal_is_not_available(stock_monitor):
    mock_resp = _make_mock_response(
        status=200,
        json_data={
            "code": 200,
            "data": {"tokens": True, "times": True, "magnitude": True},
        },
    )
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    result = await stock_monitor.check_stock_once(session=mock_session)

    assert result.available is False
    assert result.tokens is None
    assert result.times is None


@pytest.mark.asyncio
async def test_signal_monitor_requires_second_hit(monkeypatch):
    monitor = StockSignalMonitor(product_id="product-test-123", poll_interval=0.02)
    responses = [
        StockInfo(product_id="product-test-123", available=True, raw_data={"data": {"magnitude": 1}}),
        StockInfo(product_id="product-test-123", available=True, raw_data={"data": {"magnitude": 1}}),
    ]

    async def fake_check_once():
        return responses.pop(0)

    monkeypatch.setattr(monitor, "check_once", fake_check_once)

    signal = await monitor.confirm_hit()

    assert signal.confirmed is True
    assert signal.confidence == 2


@pytest.mark.asyncio
async def test_signal_monitor_rejects_unconfirmed_hit(monkeypatch):
    monitor = StockSignalMonitor(product_id="product-test-123", poll_interval=0.02)
    responses = [
        StockInfo(product_id="product-test-123", available=True, raw_data={"data": {"magnitude": 1}}),
        StockInfo(product_id="product-test-123", available=False, raw_data={"data": {}}),
    ]

    async def fake_check_once():
        return responses.pop(0)

    monkeypatch.setattr(monitor, "check_once", fake_check_once)

    signal = await monitor.confirm_hit()

    assert signal.confirmed is False
    assert signal.raw_hit is True


class TestStockMonitor:
    """StockMonitor测试类"""

    @pytest.mark.asyncio
    async def test_check_once_with_stock(self, stock_monitor):
        mock_resp = _make_mock_response(status=200, json_data={
            "code": 200,
            "data": {"magnitude": 100, "productId": "product-test-123"},
        })
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)

        result = await stock_monitor.check_stock_once(session=mock_session)

        assert result.available is True

    @pytest.mark.asyncio
    async def test_check_once_without_stock(self, stock_monitor):
        mock_resp = _make_mock_response(status=200, json_data={"code": 200, "data": None})
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)

        result = await stock_monitor.check_stock_once(session=mock_session)

        assert result.available is False

    @pytest.mark.asyncio
    async def test_check_once_api_error(self, stock_monitor):
        mock_resp = _make_mock_response(status=500)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)

        result = await stock_monitor.check_stock_once(session=mock_session)

        assert result.available is False

    @pytest.mark.asyncio
    async def test_check_once_timeout(self, stock_monitor):
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())

        result = await stock_monitor.check_stock_once(session=mock_session)

        assert result.available is False

    @pytest.mark.asyncio
    async def test_wait_for_stock_success(self, stock_monitor):
        mock_resp = _make_mock_response(status=200, json_data={
            "code": 200,
            "data": {"magnitude": 100, "productId": "product-test-123"},
        })
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await stock_monitor.wait_for_stock(timeout=1.0)
            assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_stock_timeout(self, stock_monitor):
        mock_resp = _make_mock_response(status=200, json_data={"code": 200, "data": None})
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await stock_monitor.wait_for_stock(timeout=0.1)
            assert result is False

    def test_stop(self, stock_monitor):
        assert stock_monitor._should_stop is False
        stock_monitor.stop()
        assert stock_monitor._should_stop is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
