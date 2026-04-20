"""浏览器控制器模块

提供浏览器预热、快速点击购买、滑块验证处理等功能
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, Callable

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from rich.console import Console
from rich.panel import Panel

from glm_coding_bot.config import get_config
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
        """
        Args:
            cookies_file: cookies文件路径
            headless: 是否使用无头模式
            width: 浏览器窗口宽度
            height: 浏览器窗口高度
        """
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

    async def init(self) -> bool:
        """初始化浏览器

        启动浏览器，加载cookies，准备就绪

        Returns:
            是否初始化成功
        """
        if self._initialized:
            return True

        console.print("[blue]启动浏览器...[/blue]")

        try:
            self._playwright = await async_playwright().start()

            # 启动浏览器
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )

            # 创建上下文
            context_options = {
                "viewport": {"width": self.width, "height": self.height},
            }

            # 加载cookies
            cookies_path = Path(self.cookies_file)
            if cookies_path.exists():
                with open(cookies_path) as f:
                    cookies_data = json.load(f)
                    # 转换为playwright格式
                    cookies = []
                    for c in cookies_data:
                        cookie = {
                            "name": c.get("name"),
                            "value": c.get("value"),
                            "domain": c.get("domain", ".bigmodel.cn"),
                            "path": c.get("path", "/"),
                        }
                        cookies.append(cookie)
                    context_options["cookies"] = cookies
                    console.print(f"[green]✓ 已加载 {len(cookies)} 个cookies[/green]")
            else:
                console.print("[yellow]⚠ 未找到cookies文件[/yellow]")

            self._context = await self._browser.new_context(**context_options)

            # 创建页面
            self._page = await self._context.new_page()

            self._initialized = True
            console.print("[green]✓ 浏览器初始化完成[/green]")
            return True

        except Exception as e:
            console.print(f"[red]✗ 浏览器初始化失败: {e}[/red]")
            logger.exception("Browser init failed")
            return False

    async def navigate_to_purchase(self) -> bool:
        """导航到购买页面

        访问购买页面并滚动到购买区域

        Returns:
            是否导航成功
        """
        if not self._initialized:
            console.print("[red]浏览器未初始化[/red]")
            return False

        try:
            console.print("[blue]导航到购买页面...[/blue]")
            await self._page.goto(f"{self.base_url}/glm-coding")

            # 滚动到购买区域
            await self._page.evaluate("() => { window.scrollTo(0, 800); }")
            await asyncio.sleep(0.5)

            console.print("[green]✓ 页面加载完成[/green]")
            return True

        except Exception as e:
            console.print(f"[red]导航失败: {e}[/red]")
            return False

    async def click_buy_button(self, package: str = "Max") -> bool:
        """点击购买按钮

        Args:
            package: 套餐类型 (Lite/Pro/Max)

        Returns:
            是否点击成功
        """
        if not self._page:
            console.print("[red]页面未加载[/red]")
            return False

        try:
            console.print(f"[blue]点击 {package} 套餐购买按钮...[/blue]")

            # 根据套餐类型选择按钮索引
            button_map = {"Lite": 0, "Pro": 1, "Max": 2}
            index = button_map.get(package, 2)

            # 查找并点击按钮
            buttons = await self._page.query_selector_all(".buy-btn")
            if len(buttons) > index:
                await buttons[index].click()
                console.print("[green]✓ 购买按钮已点击[/green]")
                return True
            else:
                console.print("[red]✗ 未找到购买按钮[/red]")
                return False

        except Exception as e:
            console.print(f"[red]点击按钮失败: {e}[/red]")
            return False

    async def wait_for_captcha(self, timeout: float = 5.0) -> bool:
        """等待滑块验证码出现

        Args:
            timeout: 等待超时时间（秒）

        Returns:
            是否检测到验证码
        """
        try:
            start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start) < timeout:
                # 检查验证码元素
                captcha = await self._page.query_selector(
                    ".tencent-captcha-dy, .captcha-component, iframe[src*='captcha']"
                )
                if captcha:
                    console.print("[yellow]⚠ 检测到滑块验证码[/yellow]")
                    return True
                await asyncio.sleep(0.2)
            return False
        except Exception:
            return False

    async def close(self):
        """关闭浏览器"""
        if self._browser:
            await self._browser.close()
            console.print("[dim]浏览器已关闭[/dim]")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 便捷函数
async def quick_buy(package: str = "Max", cookies_file: str = "cookies.json"):
    """快速购买函数"""
    async with BrowserController(cookies_file=cookies_file) as bot:
        if await bot.navigate_to_purchase():
            await bot.click_buy_button(package)
            await bot.wait_for_captcha(timeout=10)
            # 等待用户完成
            await asyncio.sleep(30)


if __name__ == "__main__":
    # 测试
    async def test():
        async with BrowserController() as bot:
            await bot.navigate_to_purchase()

    asyncio.run(test())
