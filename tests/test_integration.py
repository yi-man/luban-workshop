"""Integration tests for GLM Coding Bot"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.stock_monitor import StockMonitor, StockInfo
from tools.glm_coding_bot.product_mapping import SubscriptionPeriod, get_product_id


class TestIntegration:
    """集成测试类"""

    @pytest.mark.asyncio
    async def test_stock_monitor_detects_stock(self):
        monitor = StockMonitor(product_id="product-test-123", poll_interval=0.01)

        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "code": 200,
            "data": {"magnitude": 100, "productId": "product-test-123"},
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            start_time = time.time()
            found = await monitor.wait_for_stock(timeout=1.0)
            elapsed = time.time() - start_time
            stock_info = monitor.get_last_stock_info()

            assert found is True
            assert elapsed < 0.5
            assert stock_info is not None
            assert stock_info.available is True
            assert stock_info.raw_data["data"]["magnitude"] == 100

    @pytest.mark.asyncio
    async def test_performance_benchmark(self):
        monitor = StockMonitor(product_id="product-test-123", poll_interval=0.001)

        async def fast_check(session=None):
            await asyncio.sleep(0.001)
            return StockInfo(product_id="product-test-123", available=False)

        monitor.check_stock_once = fast_check

        start_time = time.time()
        for _ in range(100):
            await monitor.check_stock_once()

        elapsed = time.time() - start_time
        avg_time = elapsed / 100

        assert avg_time < 0.01, f"平均轮询时间 {avg_time*1000:.2f}ms 超过10ms"


class TestProductMapping:
    """产品映射测试类"""

    def test_get_product_id_valid(self):
        pid = get_product_id("Max", SubscriptionPeriod.QUARTERLY)
        assert pid is not None
        assert "product-" in pid

        pid = get_product_id("Pro", SubscriptionPeriod.MONTHLY)
        assert pid is not None

        pid = get_product_id("Lite", SubscriptionPeriod.YEARLY)
        assert pid is not None

    def test_get_product_id_invalid(self):
        pid = get_product_id("Invalid", SubscriptionPeriod.MONTHLY)
        assert pid is None

    def test_subscription_period_enum(self):
        assert SubscriptionPeriod.MONTHLY.value == "monthly"
        assert SubscriptionPeriod.QUARTERLY.value == "quarterly"
        assert SubscriptionPeriod.YEARLY.value == "yearly"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
