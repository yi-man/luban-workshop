# GLM Coding Bot

GLM Coding Plan 抢购工具。固定浏览器 profile + 提前预热页面 + 浏览器自动化点击 + 仅余额结算判定。

## 安装

```bash
# 在 luban-workshop 根目录
uv sync
```

要求：

- 本机已安装 Google Chrome
- 首次使用前不需要额外执行 `playwright install chromium`

## 使用

### 登录

```bash
uv run python -m tools.glm_coding_bot login
```

自动打开有头浏览器，导航到登录页面，支持扫码或手机验证码登录。登录完成后在终端按回车，浏览器状态自动保存到固定 profile `~/.glm-coding-bot`，后续无需重复登录。

说明：

- 登录、`check-login`、`buy` 都会复用同一个固定 profile
- 同一时刻只能有一个进程占用这个 profile，不要并行跑多个 `buy` / `check-login`

### 检查登录状态

```bash
uv run python -m tools.glm_coding_bot check-login
```

### 抢购

```bash
# 推荐：用于 10:00 抢购
# 命令会自动在目标时间前 10 分钟预热页面，并在目标时间前 10 秒进入抢购窗口
uv run python -m tools.glm_coding_bot buy

# 自定义参数
uv run python -m tools.glm_coding_bot buy --package Pro --period monthly --time 10:00:00

# 立即执行（调试用，不推荐用于 10:00 首次开页）
uv run python -m tools.glm_coding_bot buy --now

# 真实页面探针：按当前时间策略预热页面，但不点击购买
uv run python -m tools.glm_coding_bot buy --dry-run

# 立即探针：立刻打开页面并输出当前就绪状态
uv run python -m tools.glm_coding_bot buy --now --dry-run

# 无头模式
uv run python -m tools.glm_coding_bot buy --headless
```

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--package` | 套餐类型 | `Lite`, `Pro`, `Max` |
| `--period` | 订阅周期 | `monthly`, `quarterly`, `yearly` |
| `--time` | 抢购时间 | `HH:MM:SS` |
| `--headless` | 无头模式（不显示浏览器） | flag |
| `--now` | 立即执行；跳过定时预热窗口 | flag |
| `--dry-run` | 只验证页面预热与就绪状态，不执行库存轮询与购买点击 | flag |

### 推荐操作流程

针对 `10:00:00` 开售，推荐流程：

```bash
# 1. 抢购前先确认登录态
uv run python -m tools.glm_coding_bot check-login

# 2. 在 09:49 左右启动正式抢购
uv run python -m tools.glm_coding_bot buy --time 10:00:00
```

这条 `buy` 命令会自动：

1. 在目标时间前 10 分钟打开固定 profile 并预热 `/glm-coding`
2. 在目标时间前 10 秒进入抢购窗口
3. 刷新页面状态并等待按钮变为可点
4. 点击购买后继续做仅余额结算判定

不要在正式抢购时并行执行第二个 `buy` 或 `check-login`。

### 仅监控库存

```bash
uv run python -m tools.glm_coding_bot monitor --package Max --period quarterly --duration 120
```

### 功能测试

```bash
uv run python -m tools.glm_coding_bot test
```

## 流程

1. **固定 profile 预热**：提前打开本机 Chrome，恢复登录态，进入 `/glm-coding`
2. **页面状态探针**：检查当前 URL、周期 tab、按钮存在性、按钮可点状态
3. **页面刷新与热轮询**：低频刷新页面状态，同时用高频浏览器轮询等待按钮从不可点变可点
4. **提交点击**：只有在页面达到 `hot_ready` 时才点击购买
5. **验证码处理**：点击后继续在同一浏览器会话中处理验证码
6. **仅余额结算判定**：读取 `preview` 结果；若仍需第三方支付则直接报错退出

### 支付限制

当前实现是 `balance_only` 模式：

- 允许使用赠金 / 账户余额抵扣
- 若 `preview.thirdPartyAmount > 0`，会直接报余额不足并退出
- 第三方支付链路当前未自动执行

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
│   ├── stock_monitor.py    # 库存信号监控
│   ├── browser_controller.py  # 固定 profile 浏览器自动化 / 余额结算判定
│   ├── purchase_coordinator.py  # 页面预热与点击协调
│   └── captcha_solver.py   # 滑块验证码识别
└── utils/
    ├── logger.py           # 日志
    └── time_sync.py        # NTP 时间同步
```
