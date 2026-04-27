# GLM Coding Bot

GLM Coding Plan 抢购工具。高频 API 轮询检测库存 + 浏览器自动化购买 + 滑块验证码识别。

## 安装

```bash
# 在 luban-workshop 根目录
uv sync

# 安装浏览器（首次使用）
playwright install chromium
```

## 使用

### 登录

```bash
uv run python -m tools.glm_coding_bot login
```

自动打开有头浏览器，导航到登录页面，支持扫码或手机验证码登录。登录完成后在终端按回车，浏览器状态自动保存到 `~/.glm-coding-bot`，后续无需重复登录。

### 检查登录状态

```bash
uv run python -m tools.glm_coding_bot check-login
```

### 抢购

```bash
# 默认：Max 套餐 / 连续包季 / 10:00:00
uv run python -m tools.glm_coding_bot buy

# 自定义参数
uv run python -m tools.glm_coding_bot buy --package Pro --period monthly --time 10:00:00

# 立即执行（不等待目标时间）
uv run python -m tools.glm_coding_bot buy --now

# 无头模式
uv run python -m tools.glm_coding_bot buy --headless
```

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--package` | 套餐类型 | `Lite`, `Pro`, `Max` |
| `--period` | 订阅周期 | `monthly`, `quarterly`, `yearly` |
| `--time` | 抢购时间 | `HH:MM:SS` |
| `--headless` | 无头模式（不显示浏览器） | flag |
| `--now` | 立即执行 | flag |

### 仅监控库存

```bash
uv run python -m tools.glm_coding_bot monitor --package Max --period quarterly --duration 120
```

### 功能测试

```bash
uv run python -m tools.glm_coding_bot test
```

## 流程

1. **预热浏览器**：开售前提前启动有头浏览器、恢复登录态、进入购买页并完成预热/就绪检查
2. **库存确认**：API 高频轮询持续等待库存信号，并在每次候选命中后于 20ms 后再确认一次
3. **提交点击**：只有在 `stock_confirmed` 与 `hot_ready` 同时成立时才点击购买
4. **短恢复**：若库存确认时页面暂不可点，仅允许一次轻量恢复尝试
5. **验证码处理**：点击提交后继续在同一浏览器会话中处理验证码

## 产品映射

| 套餐 | 连续包月 | 连续包季 | 连续包年 |
|------|----------|----------|----------|
| **Lite** | product-02434c | product-b8ea38 | product-70a804 |
| **Pro** | product-1df3e1 | product-fef82f | product-5643e6 |
| **Max** | product-2fc421 | product-5d3a03 | product-d46f8b |

## 项目结构

```
tools/glm_coding_bot/
├── cli.py                  # CLI 命令（login, check-login, buy, monitor, test）
├── config.py               # 配置管理
├── product_mapping.py      # 产品 ID 映射
├── product.json            # API 原始产品数据
├── core/
│   ├── stock_monitor.py    # 高频库存监控
│   ├── browser_controller.py  # 浏览器自动化
│   ├── purchase_coordinator.py  # 库存与页面提交协调
│   └── captcha_solver.py   # 滑块验证码识别
└── utils/
    ├── logger.py           # 日志
    └── time_sync.py        # NTP 时间同步
```
