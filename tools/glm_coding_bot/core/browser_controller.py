"""浏览器控制器模块

提供浏览器预热、快速点击购买、滑块验证处理等功能
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import async_playwright, BrowserContext, Page
from rich.console import Console
from rich.panel import Panel

from tools.glm_coding_bot.config import get_config
from tools.glm_coding_bot.core.captcha_solver import CaptchaSolver
from tools.glm_coding_bot.utils.logger import get_logger

console = Console()
logger = get_logger()


@dataclass
class PageState:
    session_ok: bool = False
    route_ok: bool = False
    period_ok: bool = False
    button_present: bool = False
    button_clickable: bool = False
    viewport_ok: bool = False
    captcha_blocking: bool = False
    warm_ready: bool = False
    hot_ready: bool = False
    last_checked_at: float = 0.0
    last_failure_reason: str | None = None


class BrowserController:
    """浏览器控制器

    管理浏览器生命周期，提供：
    - 浏览器预热（提前启动、预登录）
    - 快速点击购买按钮
    - 滑块验证码处理（支持人工介入）
    """

    def __init__(
        self,
        cookies_file: Optional[str] = None,
        headless: bool = False,
        width: int = 1280,
        height: int = 900,
    ):
        config = get_config()

        self.headless = headless
        self.width = width
        self.height = height
        self.base_url = config.base_url
        # Backward-compatible legacy kwarg. Persistent browser profiles
        # replace JSON cookie injection, but callers may still pass this.
        self.cookies_file = cookies_file

        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._initialized = False
        self._start_time = time.time()

        self.stats = {
            "navigation_count": 0,
            "click_count": 0,
            "error_count": 0,
        }

    async def init(self) -> bool:
        """初始化浏览器"""
        if self._initialized:
            return True

        console.print("[blue]启动浏览器...[/blue]")

        try:
            self._playwright = await async_playwright().start()

            config = get_config()
            user_data_dir = config.user_data_dir
            user_data_dir.mkdir(parents=True, exist_ok=True)

            self._context = await self._playwright.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=self.headless,
                viewport={"width": self.width, "height": self.height},
                args=[
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

            self._initialized = True
            console.print("[green]浏览器初始化完成[/green]")
            return True

        except Exception as e:
            console.print(f"[red]浏览器初始化失败: {e}[/red]")
            logger.exception("Browser init failed")
            self.stats["error_count"] += 1
            return False

    async def navigate_to_purchase(self) -> bool:
        """导航到购买页面"""
        if not self._initialized:
            console.print("[red]浏览器未初始化[/red]")
            return False

        try:
            console.print("[blue]导航到购买页面...[/blue]")
            await self._page.goto(f"{self.base_url}/glm-coding")
            await self._page.evaluate("() => { window.scrollTo(0, 800); }")
            await asyncio.sleep(0.5)

            self.stats["navigation_count"] += 1
            console.print("[green]页面加载完成[/green]")
            return True

        except Exception as e:
            console.print(f"[red]导航失败: {e}[/red]")
            self.stats["error_count"] += 1
            return False

    async def _select_period_tab(self, period: str) -> bool:
        """选择订阅周期 tab，确保点击的是目标周期。"""
        if not self._page:
            return False

        period_keywords = {
            "monthly": ["连续包月", "包月", "monthly", "月"],
            "quarterly": ["连续包季", "包季", "quarterly", "季"],
            "yearly": ["连续包年", "包年", "yearly", "年"],
        }
        keywords = period_keywords.get(period, [])
        if not keywords:
            console.print(f"[red]无效周期类型: {period}[/red]")
            return False

        for keyword in keywords:
            locator = self._page.locator(f"text={keyword}")
            if await locator.count():
                try:
                    await locator.first.click(timeout=2000)
                    await asyncio.sleep(0.2)
                    return True
                except Exception:
                    continue
        return False

    async def click_buy_button(self, package: str = "Max", period: str = "quarterly") -> bool:
        """点击购买按钮"""
        if not self._page:
            console.print("[red]页面未加载[/red]")
            return False

        try:
            console.print(f"[blue]点击 {package} 套餐购买按钮（{period}）...[/blue]")

            button_map = {"Lite": 0, "Pro": 1, "Max": 2}
            index = button_map.get(package)

            if index is None:
                console.print(f"[red]无效套餐类型: {package}[/red]")
                return False

            period_selected = await self._select_period_tab(period)
            if not period_selected:
                console.print("[yellow]未找到周期标签，继续尝试直接点击购买按钮[/yellow]")

            button = await self._resolve_buy_button(package)
            if button is not None:
                await button.scroll_into_view_if_needed()
                await asyncio.sleep(0.1)
                await button.click()
                self.stats["click_count"] += 1
                console.print("[green]购买按钮已点击[/green]")
                return True
            else:
                console.print("[red]未找到购买按钮[/red]")
                self.stats["error_count"] += 1
                return False

        except Exception as e:
            console.print(f"[red]点击按钮失败: {e}[/red]")
            self.stats["error_count"] += 1
            return False

    async def refresh_page_state(self, package: str, period: str) -> PageState:
        state = PageState(last_checked_at=time.time())
        if not self._page:
            state.last_failure_reason = "page-missing"
            return state

        page_url = getattr(self._page, "url", "") or ""

        state.session_ok = not await self._has_login_prompt()
        state.route_ok = self.base_url in page_url
        state.period_ok = await self._is_period_tab_ready(period)
        button = await self._resolve_buy_button(package)
        state.button_present = button is not None
        if button is not None:
            state.button_clickable = await button.is_visible() and await button.is_enabled()
            state.viewport_ok = await self._is_button_in_viewport(button)
        state.captcha_blocking = await self._has_blocking_overlay()
        state.warm_ready = all(
            [
                state.session_ok,
                state.route_ok,
                state.period_ok,
                state.button_present,
                state.viewport_ok,
            ]
        )
        state.hot_ready = state.warm_ready and state.button_clickable and not state.captcha_blocking
        if not state.hot_ready:
            state.last_failure_reason = "not-hot-ready"
        return state

    async def attempt_recover(self, package: str, period: str) -> bool:
        if not self._page:
            return False
        await self._page.evaluate("() => window.scrollTo(0, 800)")
        await asyncio.sleep(0.05)
        await self._select_period_tab(period)
        state = await self.refresh_page_state(package, period)
        return state.hot_ready

    async def click_purchase(self, package: str, period: str) -> bool:
        return await self.click_buy_button(package, period)

    async def _resolve_buy_button(self, package: str):
        if not self._page:
            return None
        button_map = {"Lite": 0, "Pro": 1, "Max": 2}
        buttons = await self._page.query_selector_all(".buy-btn")
        index = button_map.get(package)
        if index is None or len(buttons) <= index:
            return None
        return buttons[index]

    async def _has_login_prompt(self) -> bool:
        if not self._page:
            return True
        for selector in ("text=登录 / 注册", "text=登录/注册", "text=登录"):
            locator = self._page.locator(selector)
            if await locator.count() and await locator.first.is_visible():
                return True
        return False

    async def _is_period_tab_ready(self, period: str) -> bool:
        if not self._page:
            return False

        period_keywords = {
            "monthly": ["连续包月", "包月", "monthly", "月"],
            "quarterly": ["连续包季", "包季", "quarterly", "季"],
            "yearly": ["连续包年", "包年", "yearly", "年"],
        }
        keywords = period_keywords.get(period, [])
        if not keywords:
            return False

        selected_state_script = """
        (el) => {
            const selectedTokens = new Set([
                "active",
                "selected",
                "current",
                "checked",
                "is-active",
                "is-selected",
                "ant-tabs-tab-active",
            ]);
            const nodes = [
                el,
                el.closest('[role="tab"]'),
                el.closest('button'),
                el.closest('[aria-selected]'),
                el.closest('[data-state]'),
                el.parentElement,
                el.parentElement?.parentElement,
            ].filter(Boolean);

            return nodes.some((node) => {
                const attrs = [
                    node.getAttribute("aria-selected"),
                    node.getAttribute("aria-pressed"),
                    node.getAttribute("aria-current"),
                    node.getAttribute("data-state"),
                    node.getAttribute("data-selected"),
                    node.getAttribute("data-active"),
                ];
                if (attrs.includes("true")) {
                    return true;
                }
                if (attrs.includes("active") || attrs.includes("selected") || attrs.includes("current")) {
                    return true;
                }

                const className = typeof node.className === "string" ? node.className : "";
                return className
                    .toLowerCase()
                    .split(/\\s+/)
                    .some((token) => selectedTokens.has(token));
            });
        }
        """

        for keyword in keywords:
            locator = self._page.locator(f"text={keyword}")
            count = await locator.count()
            if not count:
                continue
            for index in range(count):
                candidate = locator.first if index == 0 else locator.nth(index)
                try:
                    if not await candidate.is_visible():
                        continue
                    if await candidate.evaluate(selected_state_script):
                        return True
                except Exception:
                    continue
        return False

    async def _is_button_in_viewport(self, button) -> bool:
        if not self._page:
            return False

        box = await button.bounding_box()
        if not box:
            return False

        width = box.get("width", 0)
        height = box.get("height", 0)
        x = box.get("x", -1)
        y = box.get("y", -1)
        if width <= 0 or height <= 0 or x < 0 or y < 0:
            return False

        viewport = getattr(self._page, "viewport_size", None)
        if not viewport:
            return True

        return x + width <= viewport["width"] and y + height <= viewport["height"]

    async def _has_blocking_overlay(self) -> bool:
        if not self._page:
            return False
        overlays = await self._page.query_selector_all(".captcha-component, .tencent-captcha-dy, .ant-modal-mask")
        for overlay in overlays:
            try:
                if await overlay.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def handle_captcha(self, timeout: float = 15.0) -> bool:
        """处理滑块验证码

        使用 CaptchaSolver 尝试自动解决，失败后回退到人工。
        """
        if not self._page:
            return False

        solver = CaptchaSolver()
        return await solver.solve_slider(self._page, timeout=timeout, manual_fallback=True)

    async def wait_for_captcha(self, timeout: float = 5.0) -> bool:
        """等待滑块验证码出现"""
        try:
            start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start) < timeout:
                captcha = await self._page.query_selector(
                    ".tencent-captcha-dy, .captcha-component, iframe[src*='captcha']"
                )
                if captcha:
                    console.print("[yellow]检测到滑块验证码[/yellow]")
                    return True
                await asyncio.sleep(0.2)
            return False
        except Exception:
            return False

    def get_stats(self) -> dict:
        """获取浏览器操作统计"""
        stats = dict(self.stats)
        stats["uptime"] = time.time() - self._start_time
        return stats

    async def close(self):
        """关闭浏览器"""
        if self._context:
            await self._context.close()
            console.print("[dim]浏览器已关闭[/dim]")

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def quick_buy(package: str = "Max", cookies_file: Optional[str] = None):
    """快速购买函数"""
    async with BrowserController(cookies_file=cookies_file) as bot:
        if await bot.navigate_to_purchase():
            await bot.click_buy_button(package, "quarterly")
            await bot.wait_for_captcha(timeout=10)
            await asyncio.sleep(30)
