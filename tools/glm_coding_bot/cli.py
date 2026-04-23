"""
CLI 命令行接口 - GLM Coding Bot 用户交互

提供命令：
- login: 登录并保存 cookies
- check-login: 检查登录状态
- buy: 执行抢购
- monitor: 仅监控库存
- test: 快速测试
"""

import asyncio
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.status import Status

from tools.glm_coding_bot.config import get_config
from tools.glm_coding_bot.core.browser_controller import BrowserController
from tools.glm_coding_bot.core.stock_monitor import StockMonitor
from tools.glm_coding_bot.product_mapping import (
    SubscriptionPeriod,
    get_product_id,
)
from tools.glm_coding_bot.utils.logger import get_logger
from tools.glm_coding_bot.utils.time_sync import sync_time

console = Console()
logger = get_logger()


# ============== 验证函数 ==============

def validate_phone(phone: str) -> bool:
    """验证手机号格式"""
    pattern = r"^1[3-9]\d{9}$"
    return bool(re.match(pattern, phone))


def validate_time(time_str: str) -> bool:
    """验证时间格式 (HH:MM:SS)"""
    try:
        datetime.strptime(time_str, "%H:%M:%S")
        return True
    except ValueError:
        return False


def validate_package_period(package: str, period: str) -> bool:
    """验证套餐和周期组合是否有效"""
    valid_packages = ["Lite", "Pro", "Max"]
    valid_periods = ["monthly", "quarterly", "yearly"]

    if package not in valid_packages:
        return False
    if period not in valid_periods:
        return False

    try:
        period_enum = SubscriptionPeriod(period)
        product_id = get_product_id(package, period_enum)
        return product_id is not None
    except ValueError:
        return False


# ============== CLI命令 ==============

@click.group()
@click.version_option(version="0.1.0", prog_name="glm-coding-bot")
def cli():
    """GLM Coding 抢购 Bot - 极速抢购工具"""
    pass


@cli.command()
@click.option("--phone", prompt="手机号", help="登录手机号")
@click.option("--headless", is_flag=True, help="无头模式")
def login(phone: str, headless: bool):
    """登录并保存 cookies"""
    if not validate_phone(phone):
        console.print("[red]手机号格式不正确，请输入11位手机号[/red]")
        return

    console.print(Panel.fit(
        "[bold cyan]GLM Coding Bot - 登录[/bold cyan]\n"
        f"[dim]手机号: {phone}[/dim]",
        border_style="cyan",
    ))

    async def do_login():
        from playwright.async_api import async_playwright

        console.print("[blue]正在启动浏览器...[/blue]")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            with Status("[blue]正在加载登录页面...", console=console):
                await page.goto("https://bigmodel.cn/glm-coding")
                await page.click("text=登录 / 注册")
                await asyncio.sleep(1)

            console.print("[blue]正在输入手机号...[/blue]")
            await page.fill('[placeholder="请输入手机号"]', phone)

            console.print("[yellow]正在获取验证码...[/yellow]")
            await page.click("text=获取验证码")

            console.print("[green]验证码已发送到手机，请输入:[/green]")
            code = Prompt.ask("验证码")

            if not code or len(code) != 6:
                console.print("[red]验证码格式不正确[/red]")
                await browser.close()
                return

            await page.fill('[placeholder="请输入验证码"]', code)

            with Status("[blue]正在登录...", console=console):
                await page.click("button:has-text('登录 / 注册')")
                await asyncio.sleep(3)

            # 保存 cookies
            cookies = await context.cookies()
            cookies_file = Path("cookies.json")
            with open(cookies_file, "w") as f:
                json.dump(cookies, f, indent=2)

            console.print(f"[green]Cookies已保存到: {cookies_file}[/green]")
            console.print(f"[dim]  共 {len(cookies)} 个cookies[/dim]")

            await browser.close()

    asyncio.run(do_login())


@cli.command("check-login")
def check_login():
    """检查登录状态"""
    cookies_file = Path("cookies.json")

    console.print(Panel.fit(
        "[bold cyan]登录状态检查[/bold cyan]",
        border_style="cyan",
    ))

    if not cookies_file.exists():
        console.print("[red]未找到登录信息[/red]")
        console.print("[dim]请先运行: glm-coding-bot login --phone <手机号>[/dim]")
        return

    try:
        with open(cookies_file) as f:
            cookies = json.load(f)

        if not cookies:
            console.print("[yellow]Cookies文件为空[/yellow]")
            return

        total = len(cookies)
        expired = [c for c in cookies if (c.get("expires") or float("inf")) < time.time()]
        valid = total - len(expired)

        if expired:
            console.print(f"[yellow]登录已过期 ({len(expired)}/{total} cookies过期)[/yellow]")
            console.print("[dim]请重新运行: glm-coding-bot login --phone <手机号>[/dim]")
        else:
            console.print(f"[green]登录状态有效[/green]")
            console.print(f"[dim]  有效cookies: {valid}/{total}[/dim]")

        domains: dict[str, int] = {}
        for c in cookies:
            domain = c.get("domain", "unknown")
            domains[domain] = domains.get(domain, 0) + 1

        console.print("\n[bold]Cookie域名分布:[/bold]")
        for domain, count in sorted(domains.items(), key=lambda x: -x[1])[:5]:
            console.print(f"  [dim]{domain}: {count}[/dim]")

    except json.JSONDecodeError as e:
        console.print(f"[red]Cookies文件格式错误: {e}[/red]")
        console.print("[dim]建议删除cookies.json后重新登录[/dim]")
    except Exception as e:
        console.print(f"[red]检查失败: {e}[/red]")


@cli.command()
@click.option("--package", default="Max", type=click.Choice(["Lite", "Pro", "Max"]), help="套餐类型")
@click.option("--period", default="quarterly", type=click.Choice(["monthly", "quarterly", "yearly"]), help="订阅周期")
@click.option("--time", "target_time", default="10:00:00", help="目标时间 (HH:MM:SS)")
@click.option("--headless", is_flag=True, help="无头模式")
@click.option("--now", is_flag=True, help="立即执行（不等待目标时间）")
def buy(package: str, period: str, target_time: str, headless: bool, now: bool):
    """执行抢购"""
    if not validate_time(target_time):
        console.print("[red]时间格式不正确，请使用 HH:MM:SS 格式[/red]")
        return

    if not validate_package_period(package, period):
        console.print(f"[red]无效的套餐组合: {package} - {period}[/red]")
        return

    asyncio.run(_buy(package, period, target_time, headless, now))


async def _buy(package: str, period: str, target_time: str, headless: bool, now: bool):
    """抢购实现"""
    console.print(Panel.fit(
        f"[bold cyan]GLM Coding Bot - 抢购[/bold cyan]\n"
        f"[dim]套餐: {package} | 周期: {period} | 目标时间: {target_time}[/dim]\n"
        f"[dim]模式: {'立即执行' if now else '定时等待'} | 浏览器: {'无头' if headless else '可视'}[/dim]",
        border_style="cyan",
    ))

    cookies_file = Path("cookies.json")
    if not cookies_file.exists():
        console.print("[red]未登录，请先运行:[/red]")
        console.print("[dim]  glm-coding-bot login --phone <手机号>[/dim]")
        return

    try:
        with open(cookies_file) as f:
            cookies = json.load(f)
        valid_cookies = [c for c in cookies if (c.get("expires") or float("inf")) > time.time()]
        console.print(f"[green]登录状态有效 ({len(valid_cookies)}/{len(cookies)} cookies)[/green]")
    except Exception as e:
        console.print(f"[yellow]读取登录状态失败: {e}[/yellow]")

    with Status("[blue]同步NTP时间...", console=console):
        sync_success = await sync_time()
    if sync_success:
        console.print("[green]时间同步成功[/green]")
    else:
        console.print("[yellow]时间同步失败，使用本地时间[/yellow]")

    try:
        period_enum = SubscriptionPeriod(period)
        product_id = get_product_id(package, period_enum)
    except Exception as e:
        console.print(f"[red]获取产品ID失败: {e}[/red]")
        return

    if not product_id:
        console.print(f"[red]未找到产品ID: {package} - {period}[/red]")
        return

    console.print(f"[green]目标产品: {product_id}[/green]")

    if not now:
        now_dt = datetime.now()
        target = datetime.strptime(target_time, "%H:%M:%S")
        target = now_dt.replace(hour=target.hour, minute=target.minute, second=target.second)

        if target < now_dt:
            target = target + timedelta(days=1)
            console.print(f"[blue]目标时间是明天 {target.strftime('%Y-%m-%d %H:%M:%S')}[/blue]")

        start_time = target - timedelta(seconds=10)

        if start_time > now_dt:
            wait_seconds = (start_time - now_dt).total_seconds()
            hours = int(wait_seconds // 3600)
            minutes = int((wait_seconds % 3600) // 60)
            seconds = int(wait_seconds % 60)

            parts = []
            if hours > 0:
                parts.append(f"{hours}小时")
            if minutes > 0:
                parts.append(f"{minutes}分钟")
            parts.append(f"{seconds}秒")

            console.print(f"[blue]等待到 {start_time.strftime('%H:%M:%S')} (还有 {''.join(parts)})[/blue]")
            await asyncio.sleep(wait_seconds)
        else:
            console.print("[yellow]目标时间已过，立即开始[/yellow]")

    console.print("\n" + "=" * 60)
    console.print("[bold cyan]阶段1: 高频库存检测[/bold cyan]")
    console.print("=" * 60)

    monitor = StockMonitor(product_id=product_id, poll_interval=0.02)

    found = await monitor.wait_for_stock(timeout=60.0)
    if not found:
        console.print("[red]未检测到库存，抢购结束[/red]")
        return

    console.print("\n" + "=" * 60)
    console.print("[bold cyan]阶段2: 浏览器执行购买[/bold cyan]")
    console.print("=" * 60)

    bot = BrowserController(headless=headless)

    try:
        await bot.init()
        await bot.navigate_to_purchase()

        clicked = await bot.click_buy_button(package)
        if not clicked:
            console.print("[red]点击购买按钮失败[/red]")
            return

        console.print("\n[bold yellow]处理验证码...[/bold yellow]")
        success = await bot.handle_captcha(timeout=15.0)

        if success:
            console.print("\n" + "=" * 60)
            console.print("[green bold]抢购成功！请尽快完成支付[/green bold]")
            console.print("=" * 60)
        else:
            console.print("\n[yellow]验证未完成，请手动检查浏览器[/yellow]")

    except Exception as e:
        console.print(f"[red]浏览器操作失败: {e}[/red]")
        logger.exception("Browser operation failed")

    finally:
        stats = bot.get_stats()
        console.print(f"\n[dim]浏览器统计:[/dim]")
        console.print(f"[dim]  导航: {stats['navigation_count']}次[/dim]")
        console.print(f"[dim]  点击: {stats['click_count']}次[/dim]")
        console.print(f"[dim]  错误: {stats['error_count']}次[/dim]")

        console.print("\n[dim]10秒后关闭浏览器...[/dim]")
        await asyncio.sleep(10)
        await bot.close()


@cli.command("monitor")
@click.option("--package", default="Max", type=click.Choice(["Lite", "Pro", "Max"]), help="套餐类型")
@click.option("--period", default="quarterly", type=click.Choice(["monthly", "quarterly", "yearly"]), help="订阅周期")
@click.option("--duration", default=60, type=int, help="监控时长（秒）")
def monitor(package: str, period: str, duration: int):
    """仅监控库存变化，不执行购买"""
    if not validate_package_period(package, period):
        console.print(f"[red]无效的套餐组合: {package} - {period}[/red]")
        return

    asyncio.run(_monitor(package, period, duration))


async def _monitor(package: str, period: str, duration: int):
    """监控库存"""
    console.print(Panel.fit(
        f"[bold cyan]库存监控[/bold cyan]\n"
        f"[dim]套餐: {package} | 周期: {period} | 时长: {duration}秒[/dim]",
        border_style="cyan",
    ))

    try:
        period_enum = SubscriptionPeriod(period)
        product_id = get_product_id(package, period_enum)
    except Exception as e:
        console.print(f"[red]获取产品ID失败: {e}[/red]")
        return

    if not product_id:
        console.print(f"[red]未找到产品ID: {package} - {period}[/red]")
        return

    monitor = StockMonitor(product_id=product_id, poll_interval=0.02)

    found = await monitor.wait_for_stock(timeout=float(duration))

    if found:
        console.print("\n[green bold]检测到库存！[/green bold]")
    else:
        console.print("\n[yellow]监控结束，未检测到库存[/yellow]")


@cli.command("test")
@click.option("--headless", is_flag=True, help="无头模式")
def test_cmd(headless: bool):
    """快速测试各组件功能"""
    asyncio.run(_test(headless))


async def _test(headless: bool):
    """运行功能测试"""
    console.print(Panel.fit(
        "[bold cyan]GLM Coding Bot - 功能测试[/bold cyan]",
        border_style="cyan",
    ))

    results: list[tuple[str, bool | None, str | None]] = []

    with Status("[blue]测试时间同步...", console=console) as status:
        try:
            success = await sync_time()
            if success:
                status.update("[green]时间同步测试通过")
                results.append(("时间同步", True, None))
            else:
                status.update("[yellow]时间同步失败，但继续测试")
                results.append(("时间同步", False, "同步失败"))
        except Exception as e:
            status.update(f"[red]时间同步测试失败: {e}")
            results.append(("时间同步", False, str(e)))

    await asyncio.sleep(0.5)

    with Status("[blue]测试产品ID查询...", console=console) as status:
        try:
            test_cases = [
                ("Max", SubscriptionPeriod.QUARTERLY),
                ("Pro", SubscriptionPeriod.MONTHLY),
                ("Lite", SubscriptionPeriod.YEARLY),
            ]
            all_found = all(get_product_id(pkg, per) for pkg, per in test_cases)

            if all_found:
                status.update("[green]产品ID查询测试通过")
                results.append(("产品ID查询", True, None))
            else:
                status.update("[yellow]部分产品ID未找到")
                results.append(("产品ID查询", False, "部分ID未找到"))
        except Exception as e:
            status.update(f"[red]产品ID查询测试失败: {e}")
            results.append(("产品ID查询", False, str(e)))

    await asyncio.sleep(0.5)

    if not headless:
        console.print("\n[yellow]是否测试浏览器启动？这将打开浏览器窗口。[/yellow]")
        if not Confirm.ask("测试浏览器", default=False):
            results.append(("浏览器启动", None, "用户跳过"))
            _print_test_results(results)
            return

    with Status("[blue]测试浏览器启动...", console=console) as status:
        try:
            bot = BrowserController(headless=headless)
            success = await bot.init()

            if success:
                status.update("[green]浏览器启动测试通过")
                results.append(("浏览器启动", True, None))

                status.update("[blue]测试页面导航...")
                nav_success = await bot.navigate_to_purchase()
                if nav_success:
                    status.update("[green]页面导航测试通过")
                    results.append(("页面导航", True, None))
                else:
                    status.update("[yellow]页面导航失败")
                    results.append(("页面导航", False, "导航失败"))
            else:
                status.update("[red]浏览器启动失败")
                results.append(("浏览器启动", False, "启动失败"))

            await bot.close()

        except Exception as e:
            status.update(f"[red]浏览器测试失败: {e}")
            results.append(("浏览器启动", False, str(e)))

    _print_test_results(results)


def _print_test_results(results: list[tuple[str, bool | None, str | None]]):
    console.print("\n" + "=" * 60)
    console.print("[bold cyan]测试结果汇总[/bold cyan]")
    console.print("=" * 60)

    passed = failed = skipped = 0
    for name, result, detail in results:
        if result is True:
            console.print(f"[green]✓ {name}[/green]")
            passed += 1
        elif result is False:
            msg = f" ({detail})" if detail else ""
            console.print(f"[red]✗ {name}[/red][dim]{msg}[/dim]")
            failed += 1
        else:
            console.print(f"[yellow]⊘ {name}[/yellow] [dim]({detail})[/dim]")
            skipped += 1

    console.print("\n" + "=" * 60)
    console.print(f"[bold]总计:[/bold] {passed}通过, {failed}失败, {skipped}跳过")

    if failed == 0:
        console.print("\n[green bold]所有测试通过！[/green bold]")
    else:
        console.print(f"\n[yellow]{failed}项测试未通过，请检查相关组件[/yellow]")


if __name__ == "__main__":
    cli()
