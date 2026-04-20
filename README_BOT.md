# GLM Coding 抢购 Bot

一个高性能的 GLM Coding Plan 抢购工具，采用 API 高频轮询 + 预热浏览器 + 本地AI滑块识别架构，能够在库存释放后 3 秒内完成从检测到锁单的全流程。

## 特性

- ⚡ **极速检测**: API 轮询 50次/秒，延迟 <50ms
- 🎯 **精准时机**: NTP 时间同步，毫秒级精度
- 🔥 **预热浏览器**: 提前登录就位，点击延迟 <500ms
- 🤖 **AI 验证码**: 本地 OpenCV 识别滑块，<1s 完成验证
- 🛡️ **失败兜底**: AI 失败3次后人工介入

## 快速开始

### 1. 安装依赖

```bash
# 克隆项目
git clone <repo-url>
cd glm-coding-bot

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装 playwright 浏览器
playwright install chromium
```

### 2. 登录账号

```bash
python -m glm_coding_bot login --phone 13800138000
```

按提示输入短信验证码，登录成功后会保存 cookies 到 `cookies.json`。

### 3. 检查登录状态

```bash
python -m glm_coding_bot check-login
```

### 4. 执行抢购

```bash
# 默认抢购 Max 套餐，连续包季，10:00:00 开始
python -m glm_coding_bot buy

# 指定参数
python -m glm_coding_bot buy \
  --package Max \
  --period quarterly \
  --time 10:00:00 \
  --headless
```

参数说明：
- `--package`: 套餐类型 (Lite/Pro/Max)
- `--period`: 订阅周期 (monthly/quarterly/yearly)
- `--time`: 抢购时间 (HH:MM:SS)
- `--headless`: 无头模式（不显示浏览器窗口）

## 产品映射

基于真实 API 数据的产品ID映射：

| 套餐 | 连续包月 | 连续包季 | 连续包年 |
|------|----------|----------|----------|
| **Lite** | product-02434c | product-b8ea38 | product-70a804 |
| **Pro** | product-1df3e1 | product-fef82f | product-5643e6 |
| **Max** | product-2fc421 | product-5d3a03 | product-d46f8b |

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│  第一阶段：极速库存检测（API轮询）                        │
│  - 速度：50次/秒（20ms间隔）                             │
│  - 延迟：<50ms/次                                        │
│  - 检测到有库存 → 立即触发第二阶段                        │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  第二阶段：浏览器极速执行（预热实例）                       │
│  - 浏览器已提前启动、登录、滚动到购买区域                   │
│  - 只需：点击"特惠订阅" → 自动处理滑块                   │
│  - 目标：2-3秒内完成购买流程                             │
└─────────────────────────────────────────────────────────┘
```

## 技术栈

- **Python 3.10+**: 主语言
- **asyncio + aiohttp**: 异步HTTP客户端
- **Playwright**: 浏览器自动化
- **OpenCV + ONNX**: AI滑块识别
- **Click**: CLI框架
- **Rich**: 终端美化

## 开发计划

- [x] 项目初始化与依赖配置
- [x] TCP连接池与基础工具
- [x] StockMonitor（库存监控器）
- [x] 产品映射（基于真实API数据）
- [x] BrowserController（浏览器控制器）
- [ ] CaptchaSolver（AI滑块识别）
- [ ] CLI接口完善
- [ ] 测试与文档

## 许可证

MIT License
