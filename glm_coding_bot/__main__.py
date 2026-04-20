"""CLI入口

提供命令行接口：
- login: 登录并保存 cookies
- check-login: 检查登录状态
- buy: 执行抢购（半自动）
- monitor: 监控库存变化
"""

import sys

from glm_coding_bot.cli import cli

if __name__ == "__main__":
    cli()
