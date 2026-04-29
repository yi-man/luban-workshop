"""
GLM Coding Bot - 基本使用示例

本示例展示如何使用 GLM Coding Bot 进行基本的抢购操作。
"""

import asyncio
from pathlib import Path

# 添加项目根目录到路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.glm_coding_bot.core.stock_monitor import StockMonitor
from tools.glm_coding_bot.core.browser_controller import BrowserController
from tools.glm_coding_bot.product_mapping import SubscriptionPeriod, get_product_id


async def basic_stock_monitoring_example():
    """
    示例1: 基本库存监控

    演示如何使用 StockMonitor 监控产品库存。
    """
    print("=" * 60)
    print("示例1: 基本库存监控")
    print("=" * 60)

    # 获取产品ID
    package = "Max"
    period = SubscriptionPeriod.quarterly
    product_id = get_product_id(package, period)

    print(f"监控产品: {package} - {period.value}")
    print(f"产品ID: {product_id}")

    # 创建监控器
    monitor = StockMonitor(
        product_id=product_id,
        poll_interval=0.1,  # 100ms轮询间隔（示例用，实际可更快）
    )

    # 监控库存（10秒超时）
    print("开始监控库存（10秒超时）...")
    found = await monitor.wait_for_stock(timeout=10.0)

    if found:
        print("✓ 检测到库存！")
    else:
        print("✗ 未检测到库存（超时）")

    print()


async def basic_browser_example():
    """
    示例2: 基本浏览器操作

    演示如何使用 BrowserController 进行浏览器自动化。
    """
    print("=" * 60)
    print("示例2: 基本浏览器操作")
    print("=" * 60)

    # 创建浏览器控制器（无头模式）
    browser = BrowserController(
        headless=True,  # 无头模式，不显示浏览器窗口
        max_retries=2,
    )

    try:
        # 初始化浏览器
        print("初始化浏览器...")
        success = await browser.init()

        if not success:
            print("✗ 浏览器初始化失败")
            return

        print("✓ 浏览器初始化成功")

        # 导航到购买页面
        print("导航到购买页面...")
        nav_success = await browser.navigate_to_purchase()

        if nav_success:
            print("✓ 导航成功")
        else:
            print("✗ 导航失败")

        # 显示统计信息
        stats = browser.get_stats()
        print(f"\n浏览器统计:")
        print(f"  导航次数: {stats['navigation_count']}")
        print(f"  点击次数: {stats['click_count']}")
        print(f"  错误次数: {stats['error_count']}")

    except Exception as e:
        print(f"✗ 浏览器操作失败: {e}")

    finally:
        # 关闭浏览器
        print("\n关闭浏览器...")
        await browser.close()
        print("✓ 浏览器已关闭")

    print()


async def combined_workflow_example():
    """
    示例3: 组合工作流程

    演示如何组合使用 StockMonitor 和 BrowserController 完成完整抢购流程。
    """
    print("=" * 60)
    print("示例3: 组合工作流程（演示模式）")
    print("=" * 60)

    # 配置
    package = "Max"
    period = SubscriptionPeriod.quarterly
    product_id = get_product_id(package, period)

    print(f"抢购配置:")
    print(f"  套餐: {package}")
    print(f"  周期: {period.value}")
    print(f"  产品ID: {product_id}")

    # 阶段1: 库存监控
    print("\n[阶段1] 库存监控")
    print("-" * 40)

    monitor = StockMonitor(
        product_id=product_id,
        poll_interval=0.1,
    )

    # 这里仅演示，实际应该等待真实库存
    print("（演示模式：模拟检测到库存）")
    print("✓ 库存已检测到")

    # 阶段2: 浏览器执行
    print("\n[阶段2] 浏览器执行")
    print("-" * 40)

    print("（演示模式：浏览器操作步骤）")
    print("1. 初始化浏览器 ✓")
    print("2. 导航到购买页面 ✓")
    print("3. 点击购买按钮 ✓")
    print("4. 处理验证码 ✓")

    print("\n[完成] 抢购流程演示结束")
    print("=" * 60)


async def main():
    """主函数 - 运行所有示例"""
    print("\n" + "=" * 60)
    print("GLM Coding Bot - 使用示例")
    print("=" * 60 + "\n")

    # 运行示例1: 库存监控
    await basic_stock_monitoring_example()
    await asyncio.sleep(1)

    # 运行示例2: 浏览器操作（跳过实际浏览器启动）
    # await basic_browser_example()  # 取消注释以运行
    print("（跳过示例2: 浏览器操作 - 需要实际Chrome环境）\n")
    await asyncio.sleep(1)

    # 运行示例3: 组合工作流程
    await combined_workflow_example()

    print("\n" + "=" * 60)
    print("所有示例运行完毕！")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
