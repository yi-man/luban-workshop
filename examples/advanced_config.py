"""
GLM Coding Bot - 高级配置示例

本示例展示如何使用 GLM Coding Bot 的高级功能：
- 自定义配置
- 事件回调
- 错误处理策略
- 性能监控
"""

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.stock_monitor import StockMonitor
from tools.glm_coding_bot.core.browser_controller import BrowserController
from tools.glm_coding_bot.core.captcha_solver import CaptchaSolver
from tools.glm_coding_bot.product_mapping import SubscriptionPeriod, get_product_id


@dataclass
class BotConfig:
    """Bot配置类"""
    # 产品配置
    package: str = "Max"
    period: SubscriptionPeriod = SubscriptionPeriod.quarterly

    # 监控配置
    poll_interval: float = 0.02  # 20ms
    stock_timeout: float = 60.0
    max_stock_retries: int = 3

    # 浏览器配置
    headless: bool = False
    viewport_width: int = 1280
    viewport_height: int = 900
    page_load_timeout: float = 30.0
    max_browser_retries: int = 3

    # 验证码配置
    use_ai_solver: bool = True
    captcha_timeout: float = 15.0
    max_captcha_retries: int = 3
    manual_fallback: bool = True

    # 事件回调
    on_stock_detected: Optional[Callable[[], None]] = None
    on_browser_ready: Optional[Callable[[], None]] = None
    on_purchase_complete: Optional[Callable[[bool], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None


class AdvancedBot:
    """高级Bot类，展示完整的高级功能"""

    def __init__(self, config: BotConfig):
        self.config = config
        self.stats = {
            "start_time": None,
            "stock_detected_time": None,
            "browser_ready_time": None,
            "purchase_complete_time": None,
            "errors": [],
        }

        # 组件实例
        self.monitor: Optional[StockMonitor] = None
        self.browser: Optional[BrowserController] = None
        self.captcha_solver: Optional[CaptchaSolver] = None

    async def run(self) -> bool:
        """运行完整抢购流程"""
        self.stats["start_time"] = time.time()
        console_print("=" * 60)
        console_print("[bold cyan]GLM Coding Bot - 高级模式[/bold cyan]")
        console_print("=" * 60)

        try:
            # 阶段1: 库存监控
            if not await self._phase1_stock_monitoring():
                return False

            # 阶段2: 浏览器执行
            if not await self._phase2_browser_execution():
                return False

            # 阶段3: 完成购买
            return await self._phase3_complete_purchase()

        except Exception as e:
            console_print(f"[red]✗ 抢购流程异常: {e}[/red]")
            self.stats["errors"].append({"time": time.time(), "error": str(e)})

            if self.config.on_error:
                await self._run_callback(self.config.on_error, e)

            return False

        finally:
            await self._cleanup()
            self._print_final_stats()

    async def _phase1_stock_monitoring(self) -> bool:
        """阶段1: 库存监控"""
        console_print("\n[bold]阶段1: 库存监控[/bold]")
        console_print("-" * 40)

        product_id = get_product_id(self.config.package, self.config.period)
        if not product_id:
            console_print(f"[red]✗ 未找到产品ID: {self.config.package} - {self.config.period}[/red]")
            return False

        console_print(f"产品ID: {product_id}")
        console_print(f"轮询间隔: {self.config.poll_interval * 1000:.0f}ms")

        self.monitor = StockMonitor(
            product_id=product_id,
            poll_interval=self.config.poll_interval,
        )

        console_print("开始监控库存...")
        found = await self.monitor.wait_for_stock(timeout=self.config.stock_timeout)

        if found:
            self.stats["stock_detected_time"] = time.time()
            console_print("[green]✓ 检测到库存！[/green]")

            if self.config.on_stock_detected:
                await self._run_callback(self.config.on_stock_detected)

            return True
        else:
            console_print("[red]✗ 未检测到库存（超时）[/red]")
            return False

    async def _phase2_browser_execution(self) -> bool:
        """阶段2: 浏览器执行"""
        console_print("\n[bold]阶段2: 浏览器执行[/bold]")
        console_print("-" * 40)

        self.browser = BrowserController(
            headless=self.config.headless,
            viewport={"width": self.config.viewport_width, "height": self.config.viewport_height},
            page_load_timeout=self.config.page_load_timeout,
            max_retries=self.config.max_browser_retries,
        )

        console_print("初始化浏览器...")
        success = await self.browser.init()

        if not success:
            console_print("[red]✗ 浏览器初始化失败[/red]")
            return False

        console_print("[green]✓ 浏览器初始化成功[/green]")

        # 导航到购买页面
        console_print("导航到购买页面...")
        nav_success = await self.browser.navigate_to_purchase()

        if not nav_success:
            console_print("[red]✗ 页面导航失败[/red]")
            return False

        console_print("[green]✓ 页面导航成功[/green]")

        self.stats["browser_ready_time"] = time.time()

        if self.config.on_browser_ready:
            await self._run_callback(self.config.on_browser_ready)

        return True

    async def _phase3_complete_purchase(self) -> bool:
        """阶段3: 完成购买"""
        console_print("\n[bold]阶段3: 完成购买[/bold]")
        console_print("-" * 40)

        # 点击购买按钮
        console_print(f"点击 [{self.config.package}] 套餐购买按钮...")
        clicked = await self.browser.click_buy_button(self.config.package)

        if not clicked:
            console_print("[red]✗ 点击购买按钮失败[/red]")
            return False

        console_print("[green]✓ 已点击购买按钮[/green]")

        # 处理验证码
        console_print("\n处理验证码...")

        if self.config.use_ai_solver:
            self.captcha_solver = CaptchaSolver(
                max_retries=self.config.max_captcha_retries,
            )

            success = await self.browser.handle_captcha(timeout=self.config.captcha_timeout)
        else:
            # 直接人工处理
            success = await self.captcha_solver._manual_solve(
                self.browser.page,
                timeout=self.config.captcha_timeout
            )

        self.stats["purchase_complete_time"] = time.time()

        if success:
            console_print("\n" + "=" * 60)
            console_print("[green bold]🎉 抢购成功！请尽快完成支付[/green bold]")
            console_print("=" * 60)
        else:
            console_print("\n[yellow]⚠ 验证未完成，请手动检查浏览器[/yellow]")

        if self.config.on_purchase_complete:
            await self._run_callback(self.config.on_purchase_complete, success)

        return success

    async def _cleanup(self):
        """清理资源"""
        if self.browser:
            console_print("\n[dim]清理资源...[/dim]")
            await self.browser.close()

    async def _run_callback(self, callback, *args):
        """运行回调函数"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            console_print(f"[yellow]回调执行失败: {e}[/yellow]")

    def _print_final_stats(self):
        """打印最终统计"""
        console_print("\n" + "=" * 60)
        console_print("[bold]执行统计[/bold]")
        console_print("=" * 60)

        if self.stats["start_time"]:
            console_print(f"开始时间: {datetime.fromtimestamp(self.stats['start_time']).strftime('%Y-%m-%d %H:%M:%S')}")

        if self.stats["stock_detected_time"]:
            elapsed = self.stats["stock_detected_time"] - self.stats["start_time"]
            console_print(f"库存检测耗时: {elapsed:.2f}秒")

        if self.stats["browser_ready_time"] and self.stats["stock_detected_time"]:
            elapsed = self.stats["browser_ready_time"] - self.stats["stock_detected_time"]
            console_print(f"浏览器启动耗时: {elapsed:.2f}秒")

        if self.stats["purchase_complete_time"]:
            elapsed = self.stats["purchase_complete_time"] - self.stats["start_time"]
            console_print(f"总耗时: {elapsed:.2f}秒")

        if self.stats["errors"]:
            console_print(f"\n错误次数: {len(self.stats['errors'])}")


# 辅助函数（用于非Rich环境）
def console_print(message: str):
    """打印消息（支持Rich格式或纯文本）"""
    try:
        from rich import print as rich_print
        rich_print(message)
    except ImportError:
        # 移除Rich格式标记
        import re
        clean = re.sub(r'\[.*?\]', '', message)
        print(clean)


# 示例：自定义事件回调
def on_stock_detected():
    """库存检测回调"""
    print("🎉 回调：检测到库存！")


def on_browser_ready():
    """浏览器就绪回调"""
    print("🔥 回调：浏览器已就绪！")


def on_purchase_complete(success: bool):
    """购买完成回调"""
    if success:
        print("✅ 回调：抢购成功！")
    else:
        print("❌ 回调：抢购失败")


def on_error(error: Exception):
    """错误回调"""
    print(f"⚠️  回调：发生错误 - {error}")


async def main():
    """主函数"""
    # 创建高级配置
    config = BotConfig(
        package="Max",
        period=SubscriptionPeriod.quarterly,
        headless=True,  # 无头模式
        poll_interval=0.02,  # 20ms轮询
        use_ai_solver=False,  # 不使用AI求解器（演示用）
        manual_fallback=True,  # 启用人工回退
        # 事件回调
        on_stock_detected=on_stock_detected,
        on_browser_ready=on_browser_ready,
        on_purchase_complete=on_purchase_complete,
        on_error=on_error,
    )

    # 创建并运行Bot
    bot = AdvancedBot(config)

    # 注意：这只是一个演示，实际运行需要完整的浏览器环境
    print("\n" + "=" * 60)
    print("注意：这是一个演示脚本")
    print("要运行完整流程，需要:")
    print("1. 安装 Chrome/Chromium 浏览器")
    print("2. 运行 playwright install chromium")
    print("3. 先执行登录: python -m tools.glm_coding_bot login --phone <手机号>")
    print("=" * 60 + "\n")

    # 实际运行时取消下面的注释：
    # await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
