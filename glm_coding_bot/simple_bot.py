#!/usr/bin/env python3
"""
GLM Coding 抢购 Bot - 简化版 (MVP)

功能：
1. 高频API轮询检测库存 (50次/秒)
2. 检测到库存后：
   - 播放提示音
   - 自动打开浏览器
   - 自动登录
   - 导航到购买页面
3. 用户手动完成：
   - 点击"特惠订阅"
   - 完成滑块验证
   - 确认支付

使用方法:
    python simple_bot.py --phone 13800138000

作者: Assistant
日期: 2026-04-20
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import aiohttp
from playwright.async_api import async_playwright
from rich.console import Console
from rich.panel import Panel

# 导入项目模块
from glm_coding_bot.product_mapping import (
    SubscriptionPeriod,
    get_product_id,
)

console = Console()

# ============ 配置 ============
BASE_URL = "https://bigmodel.cn"
API_ENDPOINT = "/api/biz/customer/getTokenMagnitude"
COOKIES_FILE = Path("cookies.json")

# ============ 工具函数 ============
def beep():
    """播放提示音（跨平台）"""
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

async def sync_time():
    """同步NTP时间"""
    from glm_coding_bot.utils.time_sync import TimeSync

    console.print("[blue]同步NTP时间...[/blue]")
    sync = TimeSync()
    result = await sync.sync()

    if result.success:
        console.print(f"[green]✓ 时间同步成功[/green]")
        console.print(f"[dim]  偏移量: {result.offset_ms:+.2f} ms[/dim]")
    else:
        console.print(f"[yellow]⚠ 时间同步失败: {result.error}[/yellow]")

    return result.success

# ============ 核心类 ============
class SimpleStockMonitor:
    """简化版库存监控器""

    def __init__(
        self,
        product_id: str,
        poll_interval: float = 0.02,  # 20ms = 50次/秒
    ):
        self.product_id = product_id
        self.poll_interval = poll_interval
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
                    return {"has_stock": has_stock, "data": data}
                return {"has_stock": False, "error": f"HTTP {resp.status}"}
        except asyncio.TimeoutError:
            return {"has_stock": False, "error": "timeout"}
        except Exception as e:
            return {"has_stock": False, "error": str(e)}

    async def wait_for_stock(self, timeout: float = 120.0) -> bool:
        """等待库存释放"""
        start_time = time.time()
        attempts = 0

        # 加载cookies
        cookies = {}
        if COOKIES_FILE.exists():
            with open(COOKIES_FILE) as f:
                cookies = {c["name"]: c["value"] for c in json.load(f)}

        timeout_obj = aiohttp.ClientTimeout(total=2, connect=0.5)

        async with aiohttp.ClientSession(
            cookies=cookies, timeout=timeout_obj
        ) as session:
            console.print(
                f"[blue]开始轮询库存，产品: {self.product_id}[/blue]"
            )
            console.print(f"[dim]轮询间隔: {self.poll_interval*1000:.0f}ms ({1/self.poll_interval:.0f}次/秒)[/dim]")

            while (time.time() - start_time) < timeout and not self._stop:
                attempts += 1
                result = await self.check_once(session)

                if result.get("has_stock"):
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



# ============ 命令行接口 ============
@click.command()
@click.option("--phone", prompt="手机号", help="登录手机号")
@click.option("--headless", is_flag=True, help="无头模式（不显示浏览器）")
def login(phone: str, headless: bool):
    """登录并保存cookies"""

    async def do_login():
        from playwright.async_api import async_playwright

        console.print(f"[blue]启动登录流程: {phone}[/blue]")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(viewport={"width": 1280, "height": 900})
            page = await context.new_page()

            # 访问登录页面
            await page.goto("https://bigmodel.cn/glm-coding")
            await page.click("text=登录 / 注册")

            # 输入手机号
            await page.fill('[placeholder="请输入手机号"]', phone)

            # 获取验证码
            await page.click("text=获取验证码")
            console.print("[yellow]验证码已发送，请查看短信并输入:[/yellow]")

            # 等待用户输入验证码
            code = input("验证码: ").strip()

            # 输入验证码
            await page.fill('[placeholder="请输入验证码"]', code)

            # 点击登录
            await page.click("button:has-text('登录 / 注册')")

            # 等待登录完成
            await asyncio.sleep(3)

            # 保存cookies
            cookies = await context.cookies()
            cookies_file = Path("cookies.json")
            with open(cookies_file, "w") as f:
                json.dump(cookies, f, indent=2)

            console.print(f"[green]✓ 登录成功！cookies已保存到: {cookies_file}[/green]")

            await browser.close()

    asyncio.run(do_login())
def check_login():
    """检查登录状态"""

    cookies_file = Path("cookies.json")

    if not cookies_file.exists():
        console.print("[red]✗ 未找到登录信息[/red]")
        console.print("[dim]请先运行: python simple_bot.py login --phone <手机号>[/dim]")
        return

    try:
        with open(cookies_file) as f:
            cookies = json.load(f)

        # 简单检查
        if cookies and len(cookies) > 0:
            console.print("[green]✓ 登录状态有效[/green]")
            console.print(f"[dim]  cookies数量: {len(cookies)}[/dim]")
        else:
            console.print("[yellow]⚠ cookies为空，可能需要重新登录[/yellow]")

    except Exception as e:
        console.print(f"[red]✗ 检查失败: {e}[/red]")



if __name__ == "__main__":
    # 默认参数
    package = "Max"
    period = "quarterly"
    target_time = "10:00:00"
    asyncio.run(run_semi_auto_buy(package, period, target_time))
