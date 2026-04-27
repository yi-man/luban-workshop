"""库存监控器模块

提供高频API轮询功能，用于检测库存释放
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import aiohttp
from rich.console import Console

from tools.glm_coding_bot.config import get_config
from tools.glm_coding_bot.utils.logger import get_logger

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


def _extract_business_signal(result_data: dict | None) -> tuple[bool, int | None, int | None]:
    if not isinstance(result_data, dict):
        return False, None, None

    tokens = result_data.get("tokens")
    times = result_data.get("times")
    magnitude = result_data.get("magnitude")

    parsed_tokens = tokens if type(tokens) is int else None
    parsed_times = times if type(times) is int else None

    if parsed_tokens is not None and parsed_tokens > 0:
        return True, parsed_tokens, parsed_times
    if parsed_times is not None and parsed_times > 0:
        return True, parsed_tokens, parsed_times
    if type(magnitude) is int and magnitude > 0:
        return True, parsed_tokens, parsed_times

    return False, parsed_tokens, parsed_times


def _extract_product_id(result_data: dict | None, fallback_product_id: str) -> str:
    if not isinstance(result_data, dict):
        return fallback_product_id

    product_id = result_data.get("productId")
    if isinstance(product_id, str) and product_id:
        return product_id

    return fallback_product_id


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
        poll_interval: float = 0.02,
        max_poll_duration: float = 120.0,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        config = get_config()

        self.product_id = product_id or config.target_product
        self.poll_interval = poll_interval
        self.max_poll_duration = max_poll_duration
        self._external_session = session

        self.base_url = config.base_url
        self.api_timeout = config.api_timeout

        self._stock_available_event = asyncio.Event()
        self._should_stop = False
        self._last_stock_info: Optional[StockInfo] = None

    async def check_stock_once(self, session: Optional[aiohttp.ClientSession] = None) -> StockInfo:
        """单次库存检查"""
        url = f"{self.base_url}/api/biz/customer/getTokenMagnitude"
        params = {"productId": self.product_id}

        s = session or self._external_session
        own_session = s is None

        try:
            if own_session:
                timeout = aiohttp.ClientTimeout(total=self.api_timeout)
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get(url, params=params) as resp:
                        return await self._parse_response(resp)
            else:
                async with s.get(url, params=params) as resp:
                    return await self._parse_response(resp)

        except asyncio.TimeoutError:
            logger.debug(f"库存检查超时: {self.product_id}")
            return StockInfo(product_id=self.product_id, available=False, raw_data={"error": "timeout"})
        except Exception as e:
            logger.debug(f"库存检查异常: {e}")
            return StockInfo(product_id=self.product_id, available=False, raw_data={"error": str(e)})

    async def _parse_response(self, resp: aiohttp.ClientResponse) -> StockInfo:
        """解析API响应"""
        if resp.status != 200:
            return StockInfo(product_id=self.product_id, available=False, raw_data={"status": resp.status})

        try:
            data = await resp.json()

            if data.get("code") != 200:
                return StockInfo(product_id=self.product_id, available=False, raw_data=data)

            result_data = data.get("data")
            available, tokens, times = _extract_business_signal(result_data)
            product_id = _extract_product_id(result_data, self.product_id)

            return StockInfo(
                product_id=product_id,
                available=available,
                tokens=tokens,
                times=times,
                raw_data=data,
            )

        except Exception as e:
            return StockInfo(product_id=self.product_id, available=False, raw_data={"error": str(e)})

    async def wait_for_stock(
        self,
        timeout: Optional[float] = None,
        on_poll: Optional[Callable[[StockInfo], None]] = None,
    ) -> bool:
        """等待库存释放"""
        timeout = timeout or self.max_poll_duration
        start_time = asyncio.get_event_loop().time()
        attempts = 0

        logger.info(f"开始高频轮询，目标产品: {self.product_id}")
        logger.info(f"轮询间隔: {self.poll_interval*1000:.0f}ms ({1/self.poll_interval:.0f}次/秒)")

        timeout_obj = aiohttp.ClientTimeout(total=self.api_timeout)

        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            while (asyncio.get_event_loop().time() - start_time) < timeout and not self._should_stop:
                attempts += 1

                stock_info = await self.check_stock_once(session=session)

                if on_poll:
                    on_poll(stock_info)

                if stock_info.available:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    logger.info(f"检测到库存释放！尝试次数: {attempts}, 耗时: {elapsed:.2f}秒")
                    self._last_stock_info = stock_info
                    self._stock_available_event.set()
                    return True

                await asyncio.sleep(self.poll_interval)

        logger.warning(f"轮询超时，未检测到库存。总尝试次数: {attempts}")
        return False

    def get_last_stock_info(self) -> Optional[StockInfo]:
        return self._last_stock_info

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        return self._external_session

    def stop(self) -> None:
        self._should_stop = True


@dataclass
class StockSignal:
    product_id: str
    raw_hit: bool = False
    confirmed: bool = False
    confidence: int = 0
    first_hit_at: float | None = None
    confirmed_at: float | None = None
    last_raw_response: dict | None = None


class StockSignalMonitor:
    def __init__(self, product_id: str, poll_interval: float = 0.02):
        self.monitor = StockMonitor(product_id=product_id, poll_interval=poll_interval)

    @property
    def product_id(self) -> str:
        return self.monitor.product_id

    @property
    def poll_interval(self) -> float:
        return self.monitor.poll_interval

    async def check_once(self, session: Optional[aiohttp.ClientSession] = None) -> StockInfo:
        return await self.monitor.check_stock_once(session=session)

    async def confirm_hit(self) -> StockSignal:
        external_session = self.monitor.session
        if external_session is not None:
            return await self._confirm_hit_with_session(external_session)

        timeout = aiohttp.ClientTimeout(total=self.monitor.api_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            return await self._confirm_hit_with_session(session)

    async def wait_for_confirmed_hit(self, timeout: Optional[float] = None) -> StockSignal:
        timeout = self.monitor.max_poll_duration if timeout is None else timeout
        external_session = self.monitor.session
        if external_session is not None:
            return await self._wait_for_confirmed_hit_with_session(timeout, external_session)

        timeout_obj = aiohttp.ClientTimeout(total=self.monitor.api_timeout)
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            return await self._wait_for_confirmed_hit_with_session(timeout, session)

    async def _wait_for_confirmed_hit_with_session(
        self,
        timeout: float,
        session: aiohttp.ClientSession,
    ) -> StockSignal:
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        last_signal = StockSignal(product_id=self.product_id)

        while (loop.time() - start_time) < timeout and not self.monitor._should_stop:
            signal = await self._confirm_hit_with_session(session)
            last_signal = signal
            if signal.confirmed:
                return signal
            await asyncio.sleep(self.poll_interval)

        return last_signal

    async def _confirm_hit_with_session(self, session: aiohttp.ClientSession) -> StockSignal:
        first = await self.check_once(session=session)
        signal = StockSignal(
            product_id=first.product_id,
            raw_hit=first.available,
            confidence=1 if first.available else 0,
            first_hit_at=first.timestamp if first.available else None,
            last_raw_response=first.raw_data,
        )
        if not first.available:
            return signal

        await asyncio.sleep(self.poll_interval)
        second = await self.check_once(session=session)
        signal.product_id = second.product_id
        signal.last_raw_response = second.raw_data
        if second.available and second.product_id == first.product_id:
            signal.confirmed = True
            signal.confidence = 2
            signal.confirmed_at = second.timestamp
        return signal


async def check_stock(product_id: str) -> StockInfo:
    monitor = StockMonitor(product_id=product_id)
    return await monitor.check_stock_once()


async def wait_stock(
    product_id: str,
    timeout: float = 120.0,
    poll_interval: float = 0.02,
) -> bool:
    monitor = StockMonitor(product_id=product_id, poll_interval=poll_interval)
    return await monitor.wait_for_stock(timeout=timeout)
