"""Tests for StockMonitor module"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.stock_monitor import StockMonitor


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


class TestStockMonitor:
    """StockMonitor测试类"""

    @pytest.fixture
    def monitor(self):
        return StockMonitor(product_id="product-test-123", poll_interval=0.01)

    @pytest.mark.asyncio
    async def test_check_once_with_stock(self, monitor):
        mock_resp = _make_mock_response(status=200, json_data={
            "code": 200,
            "data": {"magnitude": 100, "productId": "product-test-123"},
        })
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)

        result = await monitor.check_stock_once(session=mock_session)

        assert result.available is True

    @pytest.mark.asyncio
    async def test_check_once_without_stock(self, monitor):
        mock_resp = _make_mock_response(status=200, json_data={"code": 200, "data": None})
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)

        result = await monitor.check_stock_once(session=mock_session)

        assert result.available is False

    @pytest.mark.asyncio
    async def test_check_once_api_error(self, monitor):
        mock_resp = _make_mock_response(status=500)
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)

        result = await monitor.check_stock_once(session=mock_session)

        assert result.available is False

    @pytest.mark.asyncio
    async def test_check_once_timeout(self, monitor):
        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=asyncio.TimeoutError())

        result = await monitor.check_stock_once(session=mock_session)

        assert result.available is False

    @pytest.mark.asyncio
    async def test_wait_for_stock_success(self, monitor):
        mock_resp = _make_mock_response(status=200, json_data={
            "code": 200,
            "data": {"magnitude": 100, "productId": "product-test-123"},
        })
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await monitor.wait_for_stock(timeout=1.0)
            assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_stock_timeout(self, monitor):
        mock_resp = _make_mock_response(status=200, json_data={"code": 200, "data": None})
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await monitor.wait_for_stock(timeout=0.1)
            assert result is False

    def test_stop(self, monitor):
        assert monitor._should_stop is False
        monitor.stop()
        assert monitor._should_stop is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
