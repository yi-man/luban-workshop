"""
Tests for StockMonitor module

测试内容：
- 库存检测逻辑
- API轮询机制
- 超时处理
- 错误恢复
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保能导入项目模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from glm_coding_bot.core.stock_monitor import StockMonitor


class TestStockMonitor:
    """StockMonitor测试类"""

    @pytest.fixture
    def monitor(self):
        """创建StockMonitor实例"""
        return StockMonitor(
            product_id="product-test-123",
            poll_interval=0.01,  # 10ms用于测试
        )

    @pytest.fixture
    def mock_response_has_stock(self):
        """模拟有库存的API响应"""
        return {
            "code": 200,
            "data": {
                "magnitude": 100,
                "productId": "product-test-123",
            },
            "message": "success",
        }

    @pytest.fixture
    def mock_response_no_stock(self):
        """模拟无库存的API响应"""
        return {
            "code": 200,
            "data": None,
            "message": "no stock",
        }

    @pytest.mark.asyncio
    async def test_check_once_with_stock(self, monitor, mock_response_has_stock):
        """测试检测到有库存的情况"""
        # Mock aiohttp session
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_has_stock)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_resp)

        result = await monitor.check_once(mock_session)

        assert result["has_stock"] is True
        assert result["data"] == mock_response_has_stock

    @pytest.mark.asyncio
    async def test_check_once_without_stock(self, monitor, mock_response_no_stock):
        """测试无库存的情况"""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_no_stock)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_resp)

        result = await monitor.check_once(mock_session)

        assert result["has_stock"] is False

    @pytest.mark.asyncio
    async def test_check_once_api_error(self, monitor):
        """测试API错误情况"""
        mock_resp = AsyncMock()
        mock_resp.status = 500

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_resp)

        result = await monitor.check_once(mock_session)

        assert result["has_stock"] is False
        assert "error" in result

    @pytest.mark.asyncio
    async def test_check_once_timeout(self, monitor):
        """测试超时情况"""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await monitor.check_once(mock_session)

        assert result["has_stock"] is False
        assert result.get("error") == "timeout"

    @pytest.mark.asyncio
    async def test_wait_for_stock_success(self, monitor, mock_response_has_stock):
        """测试成功等待库存"""
        # Mock session and response
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response_has_stock)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await monitor.wait_for_stock(timeout=1.0)
            assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_stock_timeout(self, monitor):
        """测试等待超时"""
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"code": 200, "data": None})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await monitor.wait_for_stock(timeout=0.1)
            assert result is False


class TestStockMonitorIntegration:
    """集成测试类"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要实际网络连接")
    async def test_real_api_call(self):
        """测试真实API调用（需要网络）"""
        monitor = StockMonitor(
            product_id="product-5d3a03",  # Max季度
            poll_interval=0.1,
        )

        import aiohttp
        async with aiohttp.ClientSession() as session:
            result = await monitor.check_once(session)

            assert "has_stock" in result
            assert isinstance(result["has_stock"], bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])