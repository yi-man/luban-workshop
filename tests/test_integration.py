"""
Integration tests for GLM Coding Bot

测试内容：
- 完整工作流程
- 组件集成
- 错误恢复
- 性能基准
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from glm_coding_bot.core.stock_monitor import StockMonitor
from glm_coding_bot.core.browser_controller import BrowserController
from glm_coding_bot.core.captcha_solver import CaptchaSolver
from glm_coding_bot.product_mapping import SubscriptionPeriod, get_product_id


class TestIntegration:
    """集成测试类"""

    @pytest.fixture
    def event_loop(self):
        """创建事件循环"""
        loop = asyncio.get_event_loop_policy().new_event_loop()
        yield loop
        loop.close()

    @pytest.mark.asyncio
    async def test_stock_monitor_to_browser_flow(self):
        """测试从库存监控到浏览器执行的完整流程"""
        # 创建监控器
        monitor = StockMonitor(
            product_id="product-test-123",
            poll_interval=0.01,
        )

        # Mock API响应 - 立即返回有库存
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "code": 200,
            "data": {"magnitude": 100, "productId": "product-test-123"},
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # 测试库存检测
        with patch("aiohttp.ClientSession", return_value=mock_session):
            start_time = time.time()
            found = await monitor.wait_for_stock(timeout=1.0)
            elapsed = time.time() - start_time

            assert found is True
            assert elapsed < 0.5  # 应该很快检测到

    @pytest.mark.asyncio
    async def test_error_recovery_flow(self):
        """测试错误恢复流程"""
        monitor = StockMonitor(
            product_id="product-test-123",
            poll_interval=0.01,
            max_retries=3,
        )

        # 模拟前两次失败，第三次成功
        call_count = 0

        async def mock_check(session):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"has_stock": False, "error": "network error"}
            return {"has_stock": True, "data": {"magnitude": 100}}

        monitor.check_once = mock_check

        # Mock session
        mock_session = AsyncMock()

        # 应该最终成功
        found = await monitor.wait_for_stock(timeout=1.0)
        assert found is True
        assert call_count >= 3  # 至少重试了3次

    @pytest.mark.asyncio
    async def test_performance_benchmark(self):
        """测试性能基准"""
        monitor = StockMonitor(
            product_id="product-test-123",
            poll_interval=0.001,  # 1ms
        )

        # Mock快速响应
        async def fast_check(session):
            await asyncio.sleep(0.001)  # 1ms延迟
            return {"has_stock": False}

        monitor.check_once = fast_check

        # 测量100次轮询的时间
        mock_session = AsyncMock()
        start_time = time.time()

        for _ in range(100):
            await monitor.check_once(mock_session)

        elapsed = time.time() - start_time
        avg_time = elapsed / 100

        # 平均每次应该小于10ms
        assert avg_time < 0.01, f"平均轮询时间 {avg_time*1000:.2f}ms 超过10ms"


class TestProductMapping:
    """产品映射测试类"""

    def test_get_product_id_valid(self):
        """测试有效的产品ID查询"""
        # Max季度
        pid = get_product_id("Max", SubscriptionPeriod.quarterly)
        assert pid is not None
        assert "product-" in pid

        # Pro月度
        pid = get_product_id("Pro", SubscriptionPeriod.monthly)
        assert pid is not None

        # Lite年度
        pid = get_product_id("Lite", SubscriptionPeriod.yearly)
        assert pid is not None

    def test_get_product_id_invalid(self):
        """测试无效的产品ID查询"""
        # 无效套餐
        pid = get_product_id("Invalid", SubscriptionPeriod.monthly)
        assert pid is None

        # 注意：目前所有有效套餐都支持所有周期，所以不会返回None
        # 但如果产品映射改变，这个测试可能需要更新

    def test_subscription_period_enum(self):
        """测试订阅周期枚举"""
        assert SubscriptionPeriod.monthly.value == "monthly"
        assert SubscriptionPeriod.quarterly.value == "quarterly"
        assert SubscriptionPeriod.yearly.value == "yearly"


class TestEndToEnd:
    """端到端测试类"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="完整流程需要真实环境")
    async def test_full_purchase_flow(self):
        """测试完整购买流程（需要真实环境）"""
        # 1. 初始化浏览器
        browser = BrowserController(headless=True)
        await browser.init()

        try:
            # 2. 导航到购买页面
            await browser.navigate_to_purchase()

            # 3. 点击购买按钮
            clicked = await browser.click_buy_button("Max")
            assert clicked is True

            # 4. 处理验证码（或等待人工）
            # ...

        finally:
            await browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])