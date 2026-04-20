"""
GLM Coding 半自动抢购 Bot

简化版抢购工具：
1. API高频轮询检测库存 (50次/秒)
2. 检测到库存立即：
   - 播放提示音
   - 自动打开浏览器并登录
   - 导航到购买页面
3. 用户手动完成：
   - 点击"特惠订阅"
   - 完成滑块验证
   - 确认支付

特点：
- 技术实现简单，稳定可靠
- 比纯人工快5-10倍（自动检测+自动登录）
- 避免滑块验证码识别难题
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import aiohttp
from playwright.async_api import async_playwright
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from glm_coding_bot.product_mapping import (
    SubscriptionPeriod,
    get_product_id,
)

console = Console()

# 配置
BASE_URL = "https://bigmodel.cn"
API_ENDPOINT = "/api/biz/customer/getTokenMagnitude"
COOKIES_FILE = Path("cookies.json")


# 播放提示音（跨平台）
def beep():
    """播放提示音"""
    try:
        if sys.platform == "darwin":  # macOS
            import os
            os.system('afplay /System/Library/Sounds/Glass.aiff')
        elif sys.platform == "win32":  # Windows
            import winsound
            winsound.Beep(1000, 500)
        else:  # Linux
            print("\a")  # 终端响铃
    except:
        print("\a")


class SemiAutoStockMonitor:
    """半自动库存监控器"""

    def __init__(
        self,
        product_id: str,
        poll_interval: float = 0.02,  # 20ms = 50次/秒
        cookies_file: Path = COOKIES_FILE,
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
                    # 判断是否有库存：code=200 且有数据返回
                    has_stock = data.get("code") == 200 and data.get("data")
                    return {
                        "has_stock": has_stock,
                        "data": data,
                    }
                return {"has_stock": False, "error": f"HTTP {resp.status}"}
        except asyncio.TimeoutError:
            return {"has_stock": False, "error": "timeout"}
        except Exception as e:
            return {"has_stock": False, "error": str(e)}

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
        if self.cookies_file.exists():
            with open(self.cookies_file) as f:
                cookies = {c["name"]: c["value"] for c in json.load(f)}

        timeout_obj = aiohttp.ClientTimeout(total=2, connect=0.5)

        async with aiohttp.ClientSession(
            cookies=cookies, timeout=timeout_obj
        ) as session:
            console.print(f"[blue]开始高频轮询，产品: {self.product_id}[/blue]")
            console.print(f"[dim]轮询间隔: {self.poll_interval*1000:.0f}ms ({1/self.poll_interval:.0f}次/秒)[/dim]")

            while (time.time() - start_time) < timeout and not self._stop:
                attempts += 1
                result = await self.check_once(session)

                if on_tick:
                    on_tick(result, attempts)

                if result.get("has_stock"):
                    elapsed = time.time() - start_time
                    console.print(f"[green bold]✓ 检测到库存！尝试{attempts}次，耗时{elapsed:.2f}秒[/green bold]")
                    return True

                await asyncio.sleep(self.poll_interval)

            console.print("[yellow]⚠ 轮询超时，未检测到库存[/yellow]")
            return False

    def stop(self):
        """停止轮询"""
        self._stop = True


async def run_semi_auto_buy(
    package: str = "Max",
    period: str = "quarterly",
    target_time: str = "10:00:00",
):
    """执行半自动抢购

    流程：
    1. 高频API轮询检测库存
    2. 检测到库存后播放提示音
    3. 自动打开浏览器并登录
    4. 导航到购买页面
    5. 用户手动完成购买
    """
    from glm_coding_bot.product_mapping import get_product_id, SubscriptionPeriod

    # 获取产品ID
    period_enum = SubscriptionPeriod(period)
    product_id = get_product_id(package, period_enum)

    if not product_id:
        console.print(f"[red]错误: 未找到 {package} - {period} 对应的产品ID[/red]")
        return

    console.print(Panel.fit(
        f"[bold cyan]GLM Coding Bot - 半自动抢购[/bold cyan]\n"
        f"[dim]套餐: {package} | 周期: {period} | 目标: {target_time}[/dim]",
        border_style="cyan"
    ))

    # 计算等待时间
    now = datetime.now()
    target = datetime.strptime(target_time, "%H:%M:%S")
    target = now.replace(hour=target.hour, minute=target.minute, second=target.second)

    if target < now:
        target = target + timedelta(days=1)

    # 提前10秒开始轮询
    start_check_time = target - timedelta(seconds=10)

    if start_check_time > now:
        wait_seconds = (start_check_time - now).total_seconds()
        console.print(f"[blue]等待到 {start_check_time.strftime('%H:%M:%S')} (还有 {wait_seconds:.0f} 秒)[/blue]")
        await asyncio.sleep(wait_seconds)

    # 阶段1: 高频轮询检测库存
    console.print("\n[bold cyan]阶段1: 高频库存检测[/bold cyan]")

    monitor = SemiAutoStockMonitor(
        product_id=product_id,
        poll_interval=0.02,  # 20ms = 50次/秒
    )

    # 检测到库存后立即执行后续操作
    found = await monitor.wait_for_stock(timeout=60.0)

    if not found:
        console.print("[red]✗ 未检测到库存，抢购结束[/red]")
        return

    # 阶段2: 自动打开浏览器
    console.print("\n[bold cyan]阶段2: 自动打开浏览器[/bold cyan]")

    # 播放提示音
    console.print("[green]🔔 正在播放提示音...[/green]")
    beep()
    beep()

    # 启动浏览器
    try:
        from playwright.async_api import async_playwright

        console.print("[blue]启动浏览器...[/blue]")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900}
            )

            # 加载cookies
            cookies_file = Path("cookies.json")
            if cookies_file.exists():
                with open(cookies_file) as f:
                    cookies = json.load(f)
                    await context.add_cookies(cookies)
                console.print("[green]✓ 已加载登录cookies[/green]")
            else:
                console.print("[yellow]⚠ 未找到cookies，将以未登录状态启动[/yellow]")

            page = await context.new_page()

            # 导航到购买页面
            console.print("[blue]导航到购买页面...[/blue]")
            await page.goto("https://bigmodel.cn/glm-coding")
            await page.evaluate("() => { window.scrollTo(0, 800); }")

            console.print("[green]✓ 浏览器准备就绪！[/green]")
            console.print(Panel.fit(
                "[bold yellow]请手动完成以下操作：[/bold yellow]\n"
                "1. 点击对应套餐的 [特惠订阅] 按钮\n"
                "2. 拖动滑块完成验证\n"
                "3. 确认支付完成购买",
                title="人工操作",
                border_style="yellow"
            ))

            # 保持浏览器打开，等待用户操作
            console.print("[dim]浏览器将保持打开，按 Ctrl+C 结束...[/dim]")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass

            await browser.close()

    except Exception as e:
        console.print(f"[red]✗ 浏览器启动失败: {e}[/red]")
        logger.exception("Browser launch failed")


async def main():
    """主入口"""
    # 默认参数
    package = "Max"
    period = "quarterly"
    target_time = "10:00:00"

    await run_semi_auto_buy(package, period, target_time)


if __name__ == "__main__":
    asyncio.run(main())
