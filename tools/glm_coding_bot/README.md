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
uv run glm-coding-bot login --phone 13800138000
```

按提示输入短信验证码，cookies 会保存到 `cookies.json`。

### 检查登录状态

```bash
uv run glm-coding-bot check-login
```

### 抢购

```bash
# 默认：Max 套餐 / 连续包季 / 10:00:00
uv run glm-coding-bot buy

# 自定义参数
uv run glm-coding-bot buy --package Pro --period monthly --time 10:00:00

# 立即执行（不等待目标时间）
uv run glm-coding-bot buy --now

# 无头模式
uv run glm-coding-bot buy --headless
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
uv run glm-coding-bot monitor --package Max --period quarterly --duration 120
```

### 功能测试

```bash
uv run glm-coding-bot test
```

## 流程

```
API 高频轮询 (50次/秒)  →  检测到库存  →  自动打开浏览器  →  点击购买  →  处理滑块验证  →  完成
```

1. **库存检测**：每 20ms 轮询一次 API，NTP 时间同步确保精度
2. **浏览器执行**：加载已保存的 cookies 自动登录，导航到购买页面，点击购买按钮
3. **验证码处理**：优先尝试 OpenCV 边缘检测定位滑块，模拟人类拖拽轨迹；失败 3 次后提示人工操作

## 产品映射

| 套餐 | 连续包月 | 连续包季 | 连续包年 |
|------|----------|----------|----------|
| **Lite** | product-02434c | product-b8ea38 | product-70a804 |
| **Pro** | product-1df3e1 | product-fef82f | product-5643e6 |
| **Max** | product-2fc421 | product-5d3a03 | product-d46f8b |

## 项目结构

```
tools/glm_coding_bot/
├── cli.py                  # CLI 命令（login, buy, monitor, test）
├── config.py               # 配置管理
├── product_mapping.py      # 产品 ID 映射
├── product.json            # API 原始产品数据
├── core/
│   ├── stock_monitor.py    # 高频库存监控
│   ├── browser_controller.py  # 浏览器自动化
│   └── captcha_solver.py   # 滑块验证码识别
└── utils/
    ├── logger.py           # 日志
    └── time_sync.py        # NTP 时间同步
```
