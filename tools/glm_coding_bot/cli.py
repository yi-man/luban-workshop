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
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.status import Status

from tools.glm_coding_bot.config import get_config
from tools.glm_coding_bot.core.browser_controller import BrowserController
from tools.glm_coding_bot.core.stock_monitor import StockMonitor
from tools.glm_coding_bot.product_mapping import (
    SubscriptionPeriod,
    get_product_id,
)
from tools.glm_coding_bot.utils.logger import get_logger
from tools.glm_coding_bot.utils.time_sync import TimeSync, sync_time

console = Console()
logger = get_logger()

LOGIN_SELECTORS = (
    "text=登录 / 注册",
    "text=登录/注册",
    "text=登录",
)
AUTH_UI_SELECTORS = (
    "text=个人中心",
    "text=我的套餐",
    "text=我的订单",
    "text=退出登录",
)
ANONYMOUS_COOKIE_NAMES = {
    "acw_tc",
    "_ga",
    "_gid",
    "_gat",
}
ANONYMOUS_COOKIE_PREFIXES = (
    "acw_",
    "hm_",
    "_ga",
    "_gid",
    "_gat",
    "sensorsdata",
)
AUTH_COOKIE_HINTS = (
    "auth",
    "login",
    "passport",
    "refresh",
    "session",
    "token",
    "uid",
    "user",
)


@dataclass(frozen=True)
class SessionCheckResult:
    status: Literal["valid", "invalid", "error"]
    detail: str

    @classmethod
    def valid(cls, detail: str) -> "SessionCheckResult":
        return cls("valid", detail)

    @classmethod
    def invalid(cls, detail: str) -> "SessionCheckResult":
        return cls("invalid", detail)

    @classmethod
    def error(cls, detail: str) -> "SessionCheckResult":
        return cls("error", detail)


# ============== 验证函数 ==============

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
def login():
    """打开浏览器登录（扫码/手机验证码），登录状态自动保存"""

    config = get_config()
    user_data_dir = config.user_data_dir
    user_data_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        "[bold cyan]GLM Coding Bot - 登录[/bold cyan]\n"
        f"[dim]浏览器数据目录: {user_data_dir}[/dim]",
        border_style="cyan",
    ))

    async def do_login():
        from playwright.async_api import async_playwright

        console.print("[blue]正在启动浏览器（有头模式）...[/blue]")

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=False,
                viewport={"width": 1280, "height": 900},
                args=[
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            page = context.pages[0] if context.pages else await context.new_page()

            with Status("[blue]正在打开登录页面...", console=console):
                await page.goto("https://bigmodel.cn/glm-coding")

            console.print("[bold yellow]请在浏览器中完成登录（扫码/手机验证码）[/bold yellow]")
            console.print("[dim]登录完成后，按回车键继续...[/dim]")
            input()

            with Status("[blue]正在验证登录状态...", console=console):
                await page.goto("https://bigmodel.cn/glm-coding", wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(1200)
                session_result = await _inspect_login_session(page, context)

            if session_result.status == "valid":
                console.print(f"[green]登录成功！{session_result.detail}[/green]")
                console.print(f"[dim]  浏览器数据目录: {user_data_dir}[/dim]")
                console.print("[dim]  下次运行将自动使用此登录状态[/dim]")
            elif session_result.status == "invalid":
                console.print("[yellow]未检测到有效登录状态，请确认是否已成功登录[/yellow]")
                console.print(f"[dim]  {session_result.detail}[/dim]")
                console.print("[dim]  你可以重新运行 login 命令[/dim]")
            else:
                console.print("[yellow]暂时无法确认登录状态[/yellow]")
                console.print(f"[dim]  {session_result.detail}[/dim]")
                console.print("[dim]  你可以重新运行 login 命令[/dim]")

            await context.close()

    asyncio.run(do_login())


@cli.command("check-login")
def check_login():
    """检查登录状态"""
    config = get_config()
    user_data_dir = config.user_data_dir

    console.print(Panel.fit(
        "[bold cyan]登录状态检查[/bold cyan]",
        border_style="cyan",
    ))

    if not user_data_dir.exists():
        console.print("[red]未找到登录信息[/red]")
        console.print("[dim]请先运行: glm-coding-bot login[/dim]")
        return

    # 检查浏览器数据目录是否存在且有内容
    cookie_files = list(user_data_dir.glob("Default/Cookies")) + list(user_data_dir.glob("Profile*/Cookies"))

    detail = "no-cookie-files"
    if cookie_files:
        console.print("[blue]正在验证会话有效性...[/blue]")
        session_result = asyncio.run(_verify_login_session(user_data_dir))
        detail = session_result.detail
        if session_result.status == "valid":
            console.print("[green]登录状态: 有效[/green]")
        elif session_result.status == "invalid":
            console.print("[yellow]登录状态: 无效[/yellow]")
            console.print("[dim]请重新运行: glm-coding-bot login[/dim]")
        else:
            console.print("[yellow]登录状态检查失败[/yellow]")
            console.print(f"[dim]{session_result.detail}[/dim]")
    else:
        console.print("[yellow]登录状态: 无效[/yellow]")
        console.print("[dim]请重新运行: glm-coding-bot login[/dim]")

    # 调试信息（仅日志，不在 CLI 展示）
    logger.debug("check-login detail: %s", detail if cookie_files else "no-cookie-files")

    # 兼容旧版 cookies.json
    cookies_file = Path("cookies.json")
    if cookies_file.exists():
        console.print(f"\n[yellow]检测到旧版 cookies.json 文件[/yellow]")
        console.print("[dim]新版本使用浏览器持久化存储，该文件不再需要[/dim]")


def _is_unexpired_cookie(cookie: dict) -> bool:
    expires = cookie.get("expires")
    return expires in (None, -1) or expires > time.time()


def _looks_like_auth_cookie(name: str) -> bool:
    lowered = name.lower()
    if lowered in ANONYMOUS_COOKIE_NAMES:
        return False
    if any(lowered.startswith(prefix) for prefix in ANONYMOUS_COOKIE_PREFIXES):
        return False
    return any(hint in lowered for hint in AUTH_COOKIE_HINTS)


def _classify_login_session(
    cookies: list[dict],
    login_visible: bool,
    auth_ui_visible: bool,
) -> SessionCheckResult:
    if login_visible:
        return SessionCheckResult.invalid("页面显示登录入口，当前会话不可用")

    valid_cookies = [
        cookie
        for cookie in cookies
        if "bigmodel" in cookie.get("domain", "") and _is_unexpired_cookie(cookie)
    ]
    auth_cookies = [
        cookie for cookie in valid_cookies if _looks_like_auth_cookie(cookie.get("name", ""))
    ]

    if auth_ui_visible:
        return SessionCheckResult.valid("检测到已登录页面元素")
    if auth_cookies:
        return SessionCheckResult.valid(f"检测到 {len(auth_cookies)} 个认证Cookie")
    if valid_cookies:
        return SessionCheckResult.error("检测到站点Cookie，但缺少可确认的登录信号")
    return SessionCheckResult.error("未检测到可确认的登录信号")


async def _has_visible_selector(page, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector)
            if await locator.count() and await locator.first.is_visible():
                return True
        except Exception:
            continue
    return False


async def _inspect_login_session(page, context) -> SessionCheckResult:
    cookies = await context.cookies("https://bigmodel.cn")
    login_visible = await _has_visible_selector(page, LOGIN_SELECTORS)
    auth_ui_visible = await _has_visible_selector(page, AUTH_UI_SELECTORS)
    return _classify_login_session(cookies, login_visible, auth_ui_visible)


async def _verify_login_session(user_data_dir: Path) -> SessionCheckResult:
    """通过实际打开页面验证会话是否仍有效。"""
    from playwright.async_api import async_playwright

    context = None
    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=True,
                viewport={"width": 1280, "height": 900},
                args=["--disable-blink-features=AutomationControlled"],
            )

            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto("https://bigmodel.cn/glm-coding", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(1200)
            return await _inspect_login_session(page, context)
    except Exception as e:
        return SessionCheckResult.error(f"会话验证失败: {e}")
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                # 可能已由 Playwright 连接生命周期自动关闭
                pass


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

    config = get_config()
    if not config.user_data_dir.exists():
        console.print("[red]未登录，请先运行:[/red]")
        console.print("[dim]  glm-coding-bot login[/dim]")
        return

    cookie_files = list(config.user_data_dir.glob("Default/Cookies")) + list(config.user_data_dir.glob("Profile*/Cookies"))
    if not cookie_files:
        console.print("[red]登录状态无效，请先运行:[/red]")
        console.print("[dim]  glm-coding-bot login[/dim]")
        return

    with Status("[blue]检查登录状态...", console=console):
        session_result = await _verify_login_session(config.user_data_dir)
    if session_result.status == "error":
        console.print("[red]登录状态校验失败，请稍后重试[/red]")
        console.print(f"[dim]  {session_result.detail}[/dim]")
        return
    if session_result.status != "valid":
        console.print("[red]登录状态无效，请先运行:[/red]")
        console.print("[dim]  glm-coding-bot login[/dim]")
        return

    console.print(f"[green]使用浏览器登录数据: {config.user_data_dir}[/green]")

    with Status("[blue]同步NTP时间...", console=console):
        time_sync_result = await TimeSync().sync()
    ntp_offset_ms = time_sync_result.offset_ms if time_sync_result.success else 0.0
    if time_sync_result.success:
        console.print(f"[green]时间同步成功 (偏移 {ntp_offset_ms:+.0f}ms)[/green]")
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
        # 使用 NTP 偏移修正当前时间，减少本机时钟误差造成的抢购偏移
        now_dt = datetime.now() + timedelta(milliseconds=ntp_offset_ms)
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

    bot = BrowserController(headless=headless)

    try:
        console.print("\n" + "=" * 60)
        console.print("[bold cyan]阶段1: 浏览器预热[/bold cyan]")
        console.print("=" * 60)
        await bot.init()
        nav_ok = await bot.navigate_to_purchase()
        if not nav_ok:
            console.print("[red]浏览器预热失败，抢购结束[/red]")
            return

        console.print("\n" + "=" * 60)
        console.print("[bold cyan]阶段2: 高频库存检测[/bold cyan]")
        console.print("=" * 60)
        monitor = StockMonitor(product_id=product_id, poll_interval=0.02)
        found = await monitor.wait_for_stock(timeout=60.0)
        if not found:
            console.print("[red]未检测到库存，抢购结束[/red]")
            return

        console.print("\n" + "=" * 60)
        console.print("[bold cyan]阶段3: 快速执行购买[/bold cyan]")
        console.print("=" * 60)

        clicked = await bot.click_buy_button(package, period)
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
