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
    first_raw = {"data": {"magnitude": 1}}
    second_raw = {"data": {"magnitude": 2}}
    responses = [
        StockInfo(product_id="product-test-123", available=True, raw_data=first_raw, timestamp=100.0),
        StockInfo(product_id="product-test-123", available=True, raw_data=second_raw, timestamp=101.0),
    ]

    async def fake_check_once(session=None):
        return responses.pop(0)

    monkeypatch.setattr(monitor, "check_once", fake_check_once)

    signal = await monitor.confirm_hit()

    assert signal.product_id == "product-test-123"
    assert signal.raw_hit is True
    assert signal.confirmed is True
    assert signal.confidence == 2
    assert signal.first_hit_at == 100.0
    assert signal.confirmed_at == 101.0
    assert signal.last_raw_response == second_raw


@pytest.mark.asyncio
async def test_signal_monitor_rejects_unconfirmed_hit(monkeypatch):
    monitor = StockSignalMonitor(product_id="product-test-123", poll_interval=0.02)
    first_raw = {"data": {"magnitude": 1}}
    second_raw = {"data": {}}
    responses = [
        StockInfo(product_id="product-test-123", available=True, raw_data=first_raw, timestamp=200.0),
        StockInfo(product_id="product-test-123", available=False, raw_data=second_raw, timestamp=201.0),
    ]

    async def fake_check_once(session=None):
        return responses.pop(0)

    monkeypatch.setattr(monitor, "check_once", fake_check_once)

    signal = await monitor.confirm_hit()

    assert signal.product_id == "product-test-123"
    assert signal.confirmed is False
    assert signal.raw_hit is True
    assert signal.confidence == 1
    assert signal.first_hit_at == 200.0
    assert signal.confirmed_at is None
    assert signal.last_raw_response == second_raw


@pytest.mark.asyncio
async def test_signal_monitor_confirm_hit_reuses_shared_session():
    monitor = StockSignalMonitor(product_id="product-test-123", poll_interval=0.02)
    first_payload = {
        "code": 200,
        "data": {"magnitude": 1, "productId": "product-test-123"},
    }
    second_payload = {
        "code": 200,
        "data": {"magnitude": 2, "productId": "product-test-123"},
    }
    responses = [
        _make_mock_response(status=200, json_data=first_payload),
        _make_mock_response(status=200, json_data=second_payload),
    ]
    mock_session = MagicMock()
    mock_session.get = MagicMock(side_effect=responses)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    client_session_factory = MagicMock(return_value=mock_session)
    sleep_mock = AsyncMock()

    with patch("tools.glm_coding_bot.core.stock_monitor.aiohttp.ClientSession", client_session_factory):
        with patch("tools.glm_coding_bot.core.stock_monitor.asyncio.sleep", sleep_mock):
            signal = await monitor.confirm_hit()

    assert client_session_factory.call_count == 1
    assert mock_session.get.call_count == 2
    assert signal.raw_hit is True
    assert signal.confirmed is True
    assert signal.confidence == 2
    assert signal.first_hit_at is not None
    assert signal.confirmed_at is not None
    assert signal.confirmed_at >= signal.first_hit_at
    assert signal.last_raw_response == second_payload
    sleep_mock.assert_awaited_once_with(0.02)


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

    def test_exposes_configured_shared_session(self):
        shared_session = MagicMock()
        monitor = StockMonitor(product_id="product-test-123", session=shared_session)

        assert monitor.session is shared_session

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
