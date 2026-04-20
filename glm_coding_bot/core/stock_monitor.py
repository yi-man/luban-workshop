"""库存监控器模块

提供高频API轮询功能，用于检测库存释放
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Optional

import aiohttp
from rich.console import Console

from glm_coding_bot.config import get_config
from glm_coding_bot.utils.logger import get_logger

console = Console()
logger = get_logger()


@dataclass
class StockInfo:
    """库存信息"""
    product_id: str
    available: bool
    tokens: Optional[int] = None
    times: Optional[int] = None
    raw_data: Optional[Dict] = None
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class StockMonitor:
    """库存监控器

    使用高频API轮询检测库存释放，支持：
    - 每秒20-50次轮询
    - 异步事件通知
    - 可配置的轮询参数
    """

    def __init__(
        self,
        product_id: Optional[str] = None,
        poll_interval: float = 0.02,  # 20ms = 50次/秒
        max_poll_duration: float = 120.0,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """
        Args:
            product_id: 产品ID，如 product-047
            poll_interval: 轮询间隔（秒）
            max_poll_duration: 最大轮询时间（秒）
            session: 可选的aiohttp会话
        """
        config = get_config()

        self.product_id = product_id or config.target_product
        self.poll_interval = poll_interval
        self.max_poll_duration = max_poll_duration
        self.session = session

        self.base_url = config.base_url
        self.api_timeout = config.api_timeout

        # 事件通知
        self._stock_available_event = asyncio.Event()
        self._should_stop = False
        self._last_stock_info: Optional[StockInfo] = None

    async def check_stock_once(self) -> StockInfo:
        """单次库存检查

        Returns:
            库存信息
        """
        url = f"{self.base_url}/api/biz/customer/getTokenMagnitude"
        params = {"productId": self.product_id}

        try:
            if self.session is None:
                # 创建临时会话
                timeout = aiohttp.ClientTimeout(total=self.api_timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, params=params, ssl=False) as resp:
                        return await self._parse_response(resp)
            else:
                # 使用现有会话
                async with self.session.get(url, params=params, ssl=False) as resp:
                    return await self._parse_response(resp)

        except asyncio.TimeoutError:
            logger.debug(f"库存检查超时: {self.product_id}")
            return StockInfo(
                product_id=self.product_id,
                available=False,
                raw_data={"error": "timeout"}
            )
        except Exception as e:
            logger.debug(f"库存检查异常: {e}")
            return StockInfo(
                product_id=self.product_id,
                available=False,
                raw_data={"error": str(e)}
            )

    async def _parse_response(self, resp: aiohttp.ClientResponse) -> StockInfo:
        """解析API响应"""
        if resp.status != 200:
            return StockInfo(
                product_id=self.product_id,
                available=False,
                raw_data={"status": resp.status}
            )

        try:
            data = await resp.json()

            if data.get("code") != 200:
                return StockInfo(
                    product_id=self.product_id,
                    available=False,
                    raw_data=data
                )

            result_data = data.get("data", {})

            # 有数据返回即认为有库存
            return StockInfo(
                product_id=self.product_id,
                available=True,
                tokens=result_data.get("tokens"),
                times=result_data.get("times"),
                raw_data=data
            )

        except Exception as e:
            return StockInfo(
                product_id=self.product_id,
                available=False,
                raw_data={"error": str(e)}
            )

    async def wait_for_stock(
        self,
        timeout: Optional[float] = None,
        on_poll: Optional[Callable[[StockInfo], None]] = None
    ) -> bool:
        """等待库存释放

        高频轮询直到检测到库存或超时

        Args:
            timeout: 超时时间（秒），默认使用 max_poll_duration
            on_poll: 每次轮询的回调函数

        Returns:
            是否在超时前检测到库存
        """
        timeout = timeout or self.max_poll_duration
        start_time = asyncio.get_event_loop().time()
        attempts = 0

        logger.info(f"开始高频轮询，目标产品: {self.product_id}")
        logger.info(f"轮询间隔: {self.poll_interval*1000:.0f}ms ({1/self.poll_interval:.0f}次/秒)")
        logger.info(f"超时时间: {timeout}秒")

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            attempts += 1

            # 检查库存
            stock_info = await self.check_stock_once()

            if on_poll:
                on_poll(stock_info)

            if stock_info.available:
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info(f"🎉 检测到库存释放！尝试次数: {attempts}, 耗时: {elapsed:.2f}秒")
                self._last_stock_info = stock_info
                self._stock_available_event.set()
                return True

            # 等待下一次轮询
            await asyncio.sleep(self.poll_interval)

        # 超时
        logger.warning(f"⏰ 轮询超时，未检测到库存。总尝试次数: {attempts}")
        return False

    def get_last_stock_info(self) -> Optional[StockInfo]:
        """获取最后一次库存信息"""
        return self._last_stock_info

    async def stop(self) -> None:
        """停止监控"""
        self._should_stop = True


# 便捷函数
async def check_stock(product_id: str) -> StockInfo:
    """便捷函数：单次库存检查

    Args:
        product_id: 产品ID

    Returns:
        库存信息
    """
    monitor = StockMonitor(product_id=product_id)
    return await monitor.check_stock_once()


async def wait_stock(
    product_id: str,
    timeout: float = 120.0,
    poll_interval: float = 0.02
) -> bool:
    """便捷函数：等待库存释放

    Args:
        product_id: 产品ID
        timeout: 超时时间（秒）
        poll_interval: 轮询间隔（秒）

    Returns:
        是否检测到库存
    """
    monitor = StockMonitor(
        product_id=product_id,
        poll_interval=poll_interval
    )
    return await monitor.wait_for_stock(timeout=timeout)


if __name__ == "__main__":
    async def test():
        # 测试单次检查
        result = await check_stock("product-047")
        print(f"Stock check result: {result}")

    asyncio.run(test())
