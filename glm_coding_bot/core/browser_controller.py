"""浏览器控制器模块

提供浏览器预热、快速点击购买、滑块验证处理等功能
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from rich.console import Console
from rich.panel import Panel

from glm_coding_bot.config import get_config
from glm_coding_bot.core.captcha_solver import CaptchaSolver
from glm_coding_bot.utils.logger import get_logger

console = Console()
logger = get_logger()


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

        self.cookies_file = cookies_file or str(config.cookies_file)
        self.headless = headless
        self.width = width
        self.height = height
        self.base_url = config.base_url

        self._playwright = None
        self._browser: Optional[Browser] = None
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

            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context_options: dict = {
                "viewport": {"width": self.width, "height": self.height},
            }

            cookies_path = Path(self.cookies_file)
            if cookies_path.exists():
                with open(cookies_path) as f:
                    cookies_data = json.load(f)
                    cookies = []
                    for c in cookies_data:
                        if not c.get("name") or not c.get("value"):
                            continue
                        cookie = {
                            "name": c["name"],
                            "value": c["value"],
                            "domain": c.get("domain", ".bigmodel.cn"),
                            "path": c.get("path", "/"),
                        }
                        if c.get("expires"):
                            cookie["expires"] = c["expires"]
                        if c.get("secure") is not None:
                            cookie["secure"] = c["secure"]
                        if c.get("httpOnly") is not None:
                            cookie["httpOnly"] = c["httpOnly"]
                        if c.get("sameSite"):
                            cookie["sameSite"] = c["sameSite"]
                        cookies.append(cookie)
                    context_options["cookies"] = cookies
                    console.print(f"[green]已加载 {len(cookies)} 个cookies[/green]")
            else:
                console.print("[yellow]未找到cookies文件[/yellow]")

            self._context = await self._browser.new_context(**context_options)
            self._page = await self._context.new_page()

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

    async def click_buy_button(self, package: str = "Max") -> bool:
        """点击购买按钮"""
        if not self._page:
            console.print("[red]页面未加载[/red]")
            return False

        try:
            console.print(f"[blue]点击 {package} 套餐购买按钮...[/blue]")

            button_map = {"Lite": 0, "Pro": 1, "Max": 2}
            index = button_map.get(package)

            if index is None:
                console.print(f"[red]无效套餐类型: {package}[/red]")
                return False

            buttons = await self._page.query_selector_all(".buy-btn")
            if len(buttons) > index:
                await buttons[index].click()
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
        if self._browser:
            await self._browser.close()
            console.print("[dim]浏览器已关闭[/dim]")

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def quick_buy(package: str = "Max", cookies_file: str = "cookies.json"):
    """快速购买函数"""
    async with BrowserController(cookies_file=cookies_file) as bot:
        if await bot.navigate_to_purchase():
            await bot.click_buy_button(package)
            await bot.wait_for_captcha(timeout=10)
            await asyncio.sleep(30)
