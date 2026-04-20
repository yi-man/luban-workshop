"""
GLM Coding 抢购 Bot - 最小可行版本 (MVP)

这是一个简化版本，用于快速验证核心流程：
1. API高频轮询检测库存
2. 浏览器自动化点击购买
3. 滑块验证人工介入（不实现AI识别，简化处理）

使用方法:
    python -m glm_coding_bot.simple_bot --phone 13800138000

作者: Assistant
版本: 0.1.0 (MVP)
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiohttp
import click
from playwright.async_api import async_playwright
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

# 配置
BASE_URL = "https://bigmodel.cn"
API_ENDPOINT = "/api/biz/customer/getTokenMagnitude"
PRODUCT_MAP = {
    "Lite": "product-005",
    "Pro": "product-003",
    "Max": "product-047",
}

console = Console()


class SimpleStockMonitor:
    """简化版库存监控器"""

    def __init__(
        self,
        product_id: str,
        poll_interval: float = 0.02,  # 20ms
        cookies_file: str = "cookies.json",
    ):
        self.product_id = product_id
        self.poll_interval = poll_interval
        self.cookies_file = cookies_file
        self._stop = False

    async def check_once(self, session: aiohttp.ClientSession) -> dict:
        """单次检查库存"""
        url = f"{BASE_URL}{API_ENDPOINT}"
        params = {"productId": self.product_id}

        try:
            async with session.get(
                url, params=params, ssl=False, timeout=aiohttp.ClientTimeout(total=2)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "available": data.get("code") == 200,
                        "data": data,
                    }
                return {"available": False, "error": f"HTTP {resp.status}"}
        except asyncio.TimeoutError:
            return {"available": False, "error": "timeout"}
        except Exception as e:
            return {"available": False, "error": str(e)}

    async def wait_for_stock(
        self,
        timeout: float = 120.0,
        on_tick: Optional[callable] = None,
    ) -> bool:
        """等待库存释放"""
        start_time = time.time()
        attempts = 0

        # 加载cookies
        cookies = {}
        if Path(self.cookies_file).exists():
            with open(self.cookies_file) as f:
                cookies = {c["name"]: c["value"] for c in json.load(f)}

        timeout_obj = aiohttp.ClientTimeout(total=2, connect=0.5)

        async with aiohttp.ClientSession(
            cookies=cookies, timeout=timeout_obj
        ) as session:
            console.print(
                f"[blue]开始轮询库存，产品: {self.product_id}[/blue]"
            )
            console.print(f"[dim]轮询间隔: {self.poll_interval*1000:.0f}ms[/dim]")

            while (time.time() - start_time) < timeout and not self._stop:
                attempts += 1
                result = await self.check_once(session)

                if on_tick:
                    on_tick(result, attempts)

                if result.get("available"):
                    elapsed = time.time() - start_time
                    console.print(
                        f"[green bold]✓ 检测到库存！尝试{attempts}次，耗时{elapsed:.2f}秒[/green bold]"
                    )
                    return True

                await asyncio.sleep(self.poll_interval)

        console.print("[yellow]⚠ 轮询超时，未检测到库存[/yellow]")
        return False

    def stop(self):
        """停止轮询"""
        self._stop = True


class SimpleBrowserBot:
    """简化版浏览器机器人"""

    def __init__(self, cookies_file: str = "cookies.json"):
        self.cookies_file = cookies_file
        self.browser = None
        self.context = None
        self.page = None

    async def init(self, headless: bool = False):
        """初始化浏览器"""
        console.print("[blue]启动浏览器...[/blue]")

        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # 加载cookies
        if Path(self.cookies_file).exists():
            with open(self.cookies_file) as f:
                cookies = json.load(f)
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 900}
            )
            await self.context.add_cookies(cookies)
            console.print("[green]✓ 已加载登录cookies[/green]")
        else:
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 900}
            )
            console.print("[yellow]⚠ 未找到cookies，将以未登录状态启动[/yellow]")

        self.page = await self.context.new_page()
        console.print("[green]✓ 浏览器启动完成[/green]")

    async def navigate_to_product(self):
        """导航到产品页面"""
        console.print("[blue]导航到购买页面...[/blue]")
        await self.page.goto("https://bigmodel.cn/glm-coding")
        await self.page.evaluate("() => { window.scrollTo(0, 800); }")
        await asyncio.sleep(0.5)
        console.print("[green]✓ 页面加载完成[/green]")

    async def click_buy_button(self, package: str = "Max"):
        """点击购买按钮"""
        console.print(f"[blue]点击 {package} 套餐购买按钮...[/blue]")

        button_map = {"Lite": 0, "Pro": 1, "Max": 2}
        index = button_map.get(package, 2)

        buttons = await self.page.query_selector_all(".buy-btn")
        if len(buttons) > index:
            await buttons[index].click()
            console.print("[green]✓ 购买按钮已点击[/green]")
            return True
        else:
            console.print("[red]✗ 未找到购买按钮[/red]")
            return False

    async def handle_captcha(self, timeout: float = 15.0) -> bool:
        """处理滑块验证码（简化版：人工介入）"""
        console.print(Panel.fit(
            "[yellow bold]请手动完成滑块验证[/yellow bold]\n"
            f"请在 {timeout} 秒内拖动滑块完成验证",
            title="验证码",
            border_style="yellow"
        ))

        start = time.time()
        while time.time() - start < timeout:
            # 检查是否已跳转（验证成功）
            url = self.page.url
            if "pay" in url or "order" in url:
                console.print("[green]✓ 验证成功！[/green]")
                return True
            await asyncio.sleep(0.5)

        console.print("[red]✗ 验证超时[/red]")
        return False

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            console.print("[dim]浏览器已关闭[/dim]")


@click.command()
@click.option("--phone", prompt="手机号", help="登录手机号")
@click.option("--product", default="Max", type=click.Choice(["Lite", "Pro", "Max"]), help="套餐类型")
@click.option("--time", "target_time", default="10:00:00", help="目标时间 (HH:MM:SS)")
@click.option("--headless", is_flag=True, help="无头模式（不显示浏览器窗口）")
def main(phone: str, product: str, target_time: str, headless: bool):
    """GLM Coding 抢购 Bot - 简化版"""
    console.print(Panel.fit(
        "[bold cyan]GLM Coding 抢购 Bot[/bold cyan]\n"
        "[dim]简化版 - 极速抢购工具[/dim]",
        border_style="cyan"
    ))

    # 检查登录
    cookies_file = Path("cookies.json")
    if not cookies_file.exists():
        console.print("[yellow]未找到登录信息，请先登录[/yellow]")
        console.print(f"请运行: python -m glm_coding_bot.simple_login --phone {phone}")
        return

    # 解析目标时间
    try:
        from datetime import datetime
        now = datetime.now()
        target = datetime.strptime(target_time, "%H:%M:%S")
        target = now.replace(hour=target.hour, minute=target.minute, second=target.second)

        if target < now:
            # 目标时间已过，设为明天
            from datetime import timedelta
            target = target + timedelta(days=1)
    except ValueError:
        console.print("[red]时间格式错误，请使用 HH:MM:SS 格式[/red]")
        return

    # 等待到目标时间前10秒
    wait_seconds = (target - datetime.now()).total_seconds() - 10
    if wait_seconds > 0:
        console.print(f"[blue]等待到 {target.strftime('%H:%M:%S')} (还有 {wait_seconds:.0f} 秒)[/blue]")
        time.sleep(wait_seconds)

    # 开始抢购流程
    asyncio.run(run_bot(product, headless))


async def run_bot(product: str, headless: bool):
    """运行抢购流程"""
    product_id = PRODUCT_MAP.get(product, "product-047")

    # 阶段1: 高频轮询检测库存
    console.print("\n[bold cyan]阶段1: 高频库存检测[/bold cyan]")
    monitor = SimpleStockMonitor(
        product_id=product_id,
        poll_interval=0.02,  # 20ms = 50次/秒
    )

    found = await monitor.wait_for_stock(timeout=60.0)
    if not found:
        console.print("[red]✗ 未检测到库存，抢购结束[/red]")
        return

    # 阶段2: 浏览器执行购买
    console.print("\n[bold cyan]阶段2: 浏览器执行购买[/bold cyan]")
    bot = SimpleBrowserBot()

    try:
        await bot.init(headless=headless)
        await bot.navigate_to_product()

        # 点击购买按钮
        clicked = await bot.click_buy_button(product)
        if not clicked:
            console.print("[red]✗ 点击购买按钮失败[/red]")
            return

        # 处理滑块验证（简化版：人工介入）
        success = await bot.handle_captcha(timeout=15.0)
        if success:
            console.print("\n[green bold]🎉 抢购成功！请尽快完成支付[/green bold]")
        else:
            console.print("\n[yellow]⚠ 验证未完成，请手动检查浏览器[/yellow]")

    finally:
        # 等待用户查看结果
        console.print("\n[dim]10秒后关闭浏览器...[/dim]")
        await asyncio.sleep(10)
        await bot.close()


if __name__ == "__main__":
    main()
