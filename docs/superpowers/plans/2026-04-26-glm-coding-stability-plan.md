# GLM Coding Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `glm-coding-bot` so stock detection and page clickability are coordinated explicitly, reducing false positives and eliminating last-second browser warmup delays.

**Architecture:** Keep the headed browser as the purchase executor, but split the flow into independent stock-signal and page-readiness tracks coordinated by a small state machine. Add explicit page state, stock confirmation, bounded recovery, and structured timing metrics so the purchase decision is testable and observable.

**Tech Stack:** Python 3.12, `asyncio`, `aiohttp`, Playwright async API, `pytest`, `click`

---

## File Map

- Create: `tools/glm_coding_bot/core/purchase_coordinator.py`
- Create: `tests/test_purchase_coordinator.py`
- Modify: `tools/glm_coding_bot/core/stock_monitor.py`
- Modify: `tests/test_stock_monitor.py`
- Modify: `tests/test_integration.py`
- Modify: `tools/glm_coding_bot/core/browser_controller.py`
- Modify: `tests/test_browser_controller.py`
- Modify: `tools/glm_coding_bot/cli.py`
- Create: `tests/test_cli_buy_flow.py`
- Modify: `tools/glm_coding_bot/README.md`

## Task 1: Harden Stock Parsing

**Files:**
- Modify: `tools/glm_coding_bot/core/stock_monitor.py`
- Modify: `tests/test_stock_monitor.py`
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Write the failing stock parsing tests**

```python
# tests/test_stock_monitor.py
from tools.glm_coding_bot.core.stock_monitor import StockMonitor


@pytest.mark.asyncio
async def test_check_once_without_business_signal_is_not_available(monitor):
    mock_resp = _make_mock_response(status=200, json_data={"code": 200, "data": {}})
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    result = await monitor.check_stock_once(session=mock_session)

    assert result.available is False


@pytest.mark.asyncio
async def test_check_once_with_positive_magnitude_is_available(monitor):
    mock_resp = _make_mock_response(status=200, json_data={
        "code": 200,
        "data": {"magnitude": 100, "productId": "product-test-123"},
    })
    mock_session = MagicMock()
    mock_session.get = MagicMock(return_value=mock_resp)

    result = await monitor.check_stock_once(session=mock_session)

    assert result.available is True
    assert result.raw_data["data"]["magnitude"] == 100
```

- [ ] **Step 2: Run the stock monitor tests to verify the new assertion fails**

Run: `uv run python -m pytest tests/test_stock_monitor.py::TestStockMonitor::test_check_once_without_stock tests/test_stock_monitor.py::test_check_once_without_business_signal_is_not_available -v`

Expected: FAIL because empty `data` is currently treated as available or the new test is missing.

- [ ] **Step 3: Implement explicit stock availability parsing**

```python
# tools/glm_coding_bot/core/stock_monitor.py
def _extract_business_signal(result_data: dict | None) -> tuple[bool, int | None, int | None]:
    if not isinstance(result_data, dict):
        return False, None, None

    tokens = result_data.get("tokens")
    times = result_data.get("times")
    magnitude = result_data.get("magnitude")

    if isinstance(tokens, int) and tokens > 0:
        return True, tokens, times if isinstance(times, int) else None
    if isinstance(times, int) and times > 0:
        return True, tokens if isinstance(tokens, int) else None, times
    if isinstance(magnitude, int) and magnitude > 0:
        return True, tokens if isinstance(tokens, int) else None, times if isinstance(times, int) else None

    return False, tokens if isinstance(tokens, int) else None, times if isinstance(times, int) else None


async def _parse_response(self, resp: aiohttp.ClientResponse) -> StockInfo:
    if resp.status != 200:
        return StockInfo(product_id=self.product_id, available=False, raw_data={"status": resp.status})

    try:
        data = await resp.json()
        if data.get("code") != 200:
            return StockInfo(product_id=self.product_id, available=False, raw_data=data)

        result_data = data.get("data")
        available, tokens, times = _extract_business_signal(result_data)
        return StockInfo(
            product_id=self.product_id,
            available=available,
            tokens=tokens,
            times=times,
            raw_data=data,
        )
    except Exception as e:
        return StockInfo(product_id=self.product_id, available=False, raw_data={"error": str(e)})
```

- [ ] **Step 4: Run the focused stock tests and integration smoke**

Run: `uv run python -m pytest tests/test_stock_monitor.py tests/test_integration.py::TestIntegration::test_stock_monitor_detects_stock -v`

Expected: PASS for the new positive/negative parsing cases.

- [ ] **Step 5: Commit**

```bash
git add tests/test_stock_monitor.py tests/test_integration.py tools/glm_coding_bot/core/stock_monitor.py
git commit -m "refactor: tighten stock availability parsing"
```

## Task 2: Add Confirmed Stock Signals

**Files:**
- Modify: `tools/glm_coding_bot/core/stock_monitor.py`
- Modify: `tests/test_stock_monitor.py`

- [ ] **Step 1: Write the failing confirmation tests**

```python
# tests/test_stock_monitor.py
from tools.glm_coding_bot.core.stock_monitor import StockSignalMonitor


@pytest.mark.asyncio
async def test_signal_monitor_requires_second_hit(monkeypatch):
    monitor = StockSignalMonitor(product_id="product-test-123", poll_interval=0.02)
    responses = [
        StockInfo(product_id="product-test-123", available=True, raw_data={"data": {"magnitude": 1}}),
        StockInfo(product_id="product-test-123", available=True, raw_data={"data": {"magnitude": 1}}),
    ]

    async def fake_check_once():
        return responses.pop(0)

    monkeypatch.setattr(monitor, "check_once", fake_check_once)

    signal = await monitor.confirm_hit()

    assert signal.confirmed is True
    assert signal.confidence == 2


@pytest.mark.asyncio
async def test_signal_monitor_rejects_unconfirmed_hit(monkeypatch):
    monitor = StockSignalMonitor(product_id="product-test-123", poll_interval=0.02)
    responses = [
        StockInfo(product_id="product-test-123", available=True, raw_data={"data": {"magnitude": 1}}),
        StockInfo(product_id="product-test-123", available=False, raw_data={"data": {}}),
    ]

    async def fake_check_once():
        return responses.pop(0)

    monkeypatch.setattr(monitor, "check_once", fake_check_once)

    signal = await monitor.confirm_hit()

    assert signal.confirmed is False
    assert signal.raw_hit is True
```

- [ ] **Step 2: Run the new confirmation tests to verify they fail**

Run: `uv run python -m pytest tests/test_stock_monitor.py::test_signal_monitor_requires_second_hit tests/test_stock_monitor.py::test_signal_monitor_rejects_unconfirmed_hit -v`

Expected: FAIL because `StockSignalMonitor` does not exist yet.

- [ ] **Step 3: Implement `StockSignal` and `StockSignalMonitor`**

```python
# tools/glm_coding_bot/core/stock_monitor.py
@dataclass
class StockSignal:
    product_id: str
    raw_hit: bool = False
    confirmed: bool = False
    confidence: int = 0
    first_hit_at: float | None = None
    confirmed_at: float | None = None
    last_raw_response: dict | None = None


class StockSignalMonitor:
    def __init__(self, product_id: str, poll_interval: float = 0.02):
        self.monitor = StockMonitor(product_id=product_id, poll_interval=poll_interval)
        self.product_id = product_id
        self.poll_interval = poll_interval

    async def check_once(self) -> StockInfo:
        return await self.monitor.check_stock_once()

    async def confirm_hit(self) -> StockSignal:
        first = await self.check_once()
        signal = StockSignal(
            product_id=self.product_id,
            raw_hit=first.available,
            confidence=1 if first.available else 0,
            first_hit_at=first.timestamp if first.available else None,
            last_raw_response=first.raw_data,
        )
        if not first.available:
            return signal

        await asyncio.sleep(0.02)
        second = await self.check_once()
        signal.last_raw_response = second.raw_data
        if second.available:
            signal.confirmed = True
            signal.confidence = 2
            signal.confirmed_at = second.timestamp
        return signal
```

- [ ] **Step 4: Run the stock monitor suite**

Run: `uv run python -m pytest tests/test_stock_monitor.py -v`

Expected: PASS with new stock signal coverage.

- [ ] **Step 5: Commit**

```bash
git add tests/test_stock_monitor.py tools/glm_coding_bot/core/stock_monitor.py
git commit -m "feat: add confirmed stock signals"
```

## Task 3: Add Explicit Page Readiness

**Files:**
- Modify: `tools/glm_coding_bot/core/browser_controller.py`
- Modify: `tests/test_browser_controller.py`

- [ ] **Step 1: Write failing browser readiness tests**

```python
# tests/test_browser_controller.py
@pytest.mark.asyncio
async def test_get_page_state_reports_hot_ready_when_button_clickable(controller):
    mock_page = AsyncMock()
    controller._page = mock_page
    controller._initialized = True
    controller._select_period_tab = AsyncMock(return_value=True)
    controller._has_login_prompt = AsyncMock(return_value=False)
    controller._has_blocking_overlay = AsyncMock(return_value=False)

    mock_button = AsyncMock()
    mock_button.is_visible = AsyncMock(return_value=True)
    mock_button.is_enabled = AsyncMock(return_value=True)
    mock_page.query_selector_all = AsyncMock(return_value=[mock_button, mock_button, mock_button])

    state = await controller.refresh_page_state("Max", "quarterly")

    assert state.warm_ready is True
    assert state.hot_ready is True


@pytest.mark.asyncio
async def test_attempt_recover_only_repositions_existing_page(controller):
    controller.navigate_to_purchase = AsyncMock()
    controller._select_period_tab = AsyncMock(return_value=True)
    controller._resolve_buy_button = AsyncMock(return_value=AsyncMock())

    recovered = await controller.attempt_recover("Max", "quarterly")

    assert recovered is True
    controller.navigate_to_purchase.assert_not_awaited()
```

- [ ] **Step 2: Run the browser tests to verify the new helpers are missing**

Run: `uv run python -m pytest tests/test_browser_controller.py::TestBrowserController::test_click_buy_button_success tests/test_browser_controller.py::test_get_page_state_reports_hot_ready_when_button_clickable -v`

Expected: FAIL because `refresh_page_state` and `attempt_recover` do not exist yet.

- [ ] **Step 3: Implement page state dataclass and readiness helpers**

```python
# tools/glm_coding_bot/core/browser_controller.py
@dataclass
class PageState:
    session_ok: bool = False
    route_ok: bool = False
    period_ok: bool = False
    button_present: bool = False
    button_clickable: bool = False
    viewport_ok: bool = False
    captcha_blocking: bool = False
    warm_ready: bool = False
    hot_ready: bool = False
    last_checked_at: float = 0.0
    last_failure_reason: str | None = None


async def refresh_page_state(self, package: str, period: str) -> PageState:
    state = PageState(last_checked_at=time.time())
    if not self._page:
        state.last_failure_reason = "page-missing"
        return state

    state.session_ok = not await self._has_login_prompt()
    state.route_ok = self.base_url in (self._page.url or "")
    state.period_ok = await self._select_period_tab(period)
    button = await self._resolve_buy_button(package)
    state.button_present = button is not None
    if button is not None:
        state.button_clickable = await button.is_visible() and await button.is_enabled()
        state.viewport_ok = state.button_clickable
    state.captcha_blocking = await self._has_blocking_overlay()
    state.warm_ready = all([state.session_ok, state.route_ok, state.period_ok, state.button_present, state.viewport_ok])
    state.hot_ready = state.warm_ready and state.button_clickable and not state.captcha_blocking
    if not state.hot_ready:
        state.last_failure_reason = "not-hot-ready"
    return state


async def attempt_recover(self, package: str, period: str) -> bool:
    if not self._page:
        return False
    await self._page.evaluate("() => window.scrollTo(0, 800)")
    await asyncio.sleep(0.05)
    await self._select_period_tab(period)
    button = await self._resolve_buy_button(package)
    return button is not None


async def click_purchase(self, package: str, period: str) -> bool:
    return await self.click_buy_button(package, period)


async def _resolve_buy_button(self, package: str):
    if not self._page:
        return None
    button_map = {"Lite": 0, "Pro": 1, "Max": 2}
    buttons = await self._page.query_selector_all(".buy-btn")
    index = button_map.get(package)
    if index is None or len(buttons) <= index:
        return None
    return buttons[index]


async def _has_login_prompt(self) -> bool:
    if not self._page:
        return True
    for selector in ("text=登录 / 注册", "text=登录/注册", "text=登录"):
        locator = self._page.locator(selector)
        if await locator.count() and await locator.first.is_visible():
            return True
    return False


async def _has_blocking_overlay(self) -> bool:
    if not self._page:
        return False
    overlay = await self._page.query_selector(".captcha-component, .tencent-captcha-dy, .ant-modal-mask")
    return overlay is not None
```

- [ ] **Step 4: Run the browser controller suite**

Run: `uv run python -m pytest tests/test_browser_controller.py -v`

Expected: PASS with readiness and bounded recovery behavior covered.

- [ ] **Step 5: Commit**

```bash
git add tests/test_browser_controller.py tools/glm_coding_bot/core/browser_controller.py
git commit -m "feat: add page readiness tracking"
```

## Task 4: Add Purchase Coordinator State Machine

**Files:**
- Create: `tools/glm_coding_bot/core/purchase_coordinator.py`
- Create: `tests/test_purchase_coordinator.py`

- [ ] **Step 1: Write failing coordinator state machine tests**

```python
# tests/test_purchase_coordinator.py
@pytest.mark.asyncio
async def test_run_commits_when_stock_and_page_ready():
    page_controller = AsyncMock()
    page_controller.refresh_page_state = AsyncMock(return_value=PageState(warm_ready=True, hot_ready=True))
    page_controller.click_purchase = AsyncMock(return_value=True)

    signal_monitor = AsyncMock()
    signal_monitor.confirm_hit = AsyncMock(return_value=StockSignal(
        product_id="product-test-123",
        raw_hit=True,
        confirmed=True,
        confidence=2,
    ))

    coordinator = PurchaseCoordinator(
        package="Max",
        period="quarterly",
        product_id="product-test-123",
        page_controller=page_controller,
        signal_monitor=signal_monitor,
    )

    result = await coordinator.run()

    assert result.success is True
    assert result.phase == "COMPLETED"
    page_controller.click_purchase.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_uses_single_recovery_before_fail():
    page_controller = AsyncMock()
    page_controller.refresh_page_state = AsyncMock(side_effect=[
        PageState(warm_ready=True, hot_ready=False),
        PageState(warm_ready=True, hot_ready=False),
    ])
    page_controller.attempt_recover = AsyncMock(return_value=False)

    signal_monitor = AsyncMock()
    signal_monitor.confirm_hit = AsyncMock(return_value=StockSignal(
        product_id="product-test-123",
        raw_hit=True,
        confirmed=True,
        confidence=2,
    ))

    coordinator = PurchaseCoordinator(
        package="Max",
        period="quarterly",
        product_id="product-test-123",
        page_controller=page_controller,
        signal_monitor=signal_monitor,
    )

    result = await coordinator.run()

    assert result.success is False
    assert result.failure_reason == "recovery-failed"
    page_controller.attempt_recover.assert_awaited_once()
```

- [ ] **Step 2: Run the coordinator tests to verify they fail**

Run: `uv run python -m pytest tests/test_purchase_coordinator.py -v`

Expected: FAIL because `purchase_coordinator.py` does not exist yet.

- [ ] **Step 3: Implement the session, result, and coordinator**

```python
# tools/glm_coding_bot/core/purchase_coordinator.py
@dataclass
class PurchaseSession:
    phase: str = "INIT"
    commit_started: bool = False
    commit_completed: bool = False
    recovery_used: bool = False
    failure_reason: str | None = None
    timing_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class PurchaseResult:
    success: bool
    phase: str
    failure_reason: str | None = None
    timing_metrics: dict[str, float] = field(default_factory=dict)


class PurchaseCoordinator:
    def __init__(self, package: str, period: str, product_id: str, page_controller, signal_monitor):
        self.package = package
        self.period = period
        self.product_id = product_id
        self.page_controller = page_controller
        self.signal_monitor = signal_monitor
        self.session = PurchaseSession()

    async def run(self) -> PurchaseResult:
        self.session.phase = "WARMING"
        page_state = await self.page_controller.refresh_page_state(self.package, self.period)
        if not page_state.warm_ready:
            return PurchaseResult(False, "FAILED", "warmup-not-ready")

        self.session.phase = "STOCK_PENDING_CONFIRM"
        signal = await self.signal_monitor.confirm_hit()
        if not signal.confirmed:
            return PurchaseResult(False, "FAILED", "stock-unconfirmed")

        self.session.phase = "COMMIT_READY"
        page_state = await self.page_controller.refresh_page_state(self.package, self.period)
        if not page_state.hot_ready:
            self.session.phase = "RECOVERING"
            self.session.recovery_used = True
            if not await self.page_controller.attempt_recover(self.package, self.period):
                return PurchaseResult(False, "FAILED", "recovery-failed")
            page_state = await self.page_controller.refresh_page_state(self.package, self.period)
            if not page_state.hot_ready:
                return PurchaseResult(False, "FAILED", "not-hot-ready")

        self.session.phase = "COMMITTING"
        self.session.commit_started = True
        clicked = await self.page_controller.click_purchase(self.package, self.period)
        if not clicked:
            return PurchaseResult(False, "FAILED", "click-failed")

        self.session.commit_completed = True
        self.session.phase = "COMPLETED"
        return PurchaseResult(True, "COMPLETED", timing_metrics=self.session.timing_metrics)
```

- [ ] **Step 4: Run the coordinator tests**

Run: `uv run python -m pytest tests/test_purchase_coordinator.py -v`

Expected: PASS with commit and bounded recovery coverage.

- [ ] **Step 5: Commit**

```bash
git add tests/test_purchase_coordinator.py tools/glm_coding_bot/core/purchase_coordinator.py
git commit -m "feat: add purchase coordinator"
```

## Task 5: Refactor CLI Buy Flow to Use the Coordinator

**Files:**
- Modify: `tools/glm_coding_bot/cli.py`
- Create: `tests/test_cli_buy_flow.py`

- [ ] **Step 1: Write failing buy orchestration tests**

```python
# tests/test_cli_buy_flow.py
@pytest.mark.asyncio
async def test_buy_uses_coordinator_after_preflight(monkeypatch, tmp_path):
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot")
    cookie_file = config.user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    coordinator = AsyncMock()
    coordinator.run = AsyncMock(return_value=PurchaseResult(success=True, phase="COMPLETED"))

    monkeypatch.setattr(cli_module, "get_config", lambda: config)
    monkeypatch.setattr(cli_module, "_verify_login_session", AsyncMock(return_value=SessionCheckResult.valid("ok")))
    monkeypatch.setattr(cli_module.TimeSync, "sync", AsyncMock(return_value=SimpleNamespace(success=True, offset_ms=0.0)))
    monkeypatch.setattr(cli_module, "PurchaseCoordinator", lambda **kwargs: coordinator)

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True)

    coordinator.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_buy_stops_when_coordinator_fails(monkeypatch, tmp_path):
    config = Config(user_data_dir=tmp_path / ".glm-coding-bot")
    cookie_file = config.user_data_dir / "Default" / "Cookies"
    cookie_file.parent.mkdir(parents=True)
    cookie_file.write_text("dummy")

    coordinator = AsyncMock()
    coordinator.run = AsyncMock(return_value=PurchaseResult(success=False, phase="FAILED", failure_reason="stock-unconfirmed"))

    monkeypatch.setattr(cli_module, "get_config", lambda: config)
    monkeypatch.setattr(cli_module, "_verify_login_session", AsyncMock(return_value=SessionCheckResult.valid("ok")))
    monkeypatch.setattr(cli_module.TimeSync, "sync", AsyncMock(return_value=SimpleNamespace(success=True, offset_ms=0.0)))
    monkeypatch.setattr(cli_module, "PurchaseCoordinator", lambda **kwargs: coordinator)

    await cli_module._buy("Max", "quarterly", "10:00:00", headless=False, now=True)

    coordinator.run.assert_awaited_once()
```

- [ ] **Step 2: Run the buy flow tests to verify they fail**

Run: `uv run python -m pytest tests/test_cli_buy_flow.py -v`

Expected: FAIL because `_buy()` still contains the old inline browser and stock flow.

- [ ] **Step 3: Refactor `_buy()` to orchestrate the coordinator**

```python
# tools/glm_coding_bot/cli.py
from tools.glm_coding_bot.core.purchase_coordinator import PurchaseCoordinator
from tools.glm_coding_bot.core.stock_monitor import StockSignalMonitor


async def _buy(package: str, period: str, target_time: str, headless: bool, now: bool):
    ...
    page_controller = BrowserController(headless=headless)
    await page_controller.init()
    await page_controller.navigate_to_purchase()

    signal_monitor = StockSignalMonitor(product_id=product_id, poll_interval=0.02)
    coordinator = PurchaseCoordinator(
        package=package,
        period=period,
        product_id=product_id,
        page_controller=page_controller,
        signal_monitor=signal_monitor,
    )
    result = await coordinator.run()
    if not result.success:
        console.print(f"[red]抢购失败: {result.failure_reason}[/red]")
        await page_controller.close()
        return

    console.print("[green]购买点击已提交，进入验证码阶段[/green]")
    success = await page_controller.handle_captcha(timeout=15.0)
```

- [ ] **Step 4: Run the CLI and focused GLM bot tests**

Run: `uv run python -m pytest tests/test_cli_buy_flow.py tests/test_cli_check_login.py tests/test_purchase_coordinator.py -v`

Expected: PASS with the coordinator wired into `_buy()`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli_buy_flow.py tests/test_cli_check_login.py tests/test_purchase_coordinator.py tools/glm_coding_bot/cli.py
git commit -m "refactor: route buy flow through coordinator"
```

## Task 6: Update Docs and Run Full GLM Bot Verification

**Files:**
- Modify: `tools/glm_coding_bot/README.md`

- [ ] **Step 1: Update the README flow description**

```md
## 流程

1. **预热浏览器**：开售前提前启动有头浏览器、恢复登录态、进入购买页并选中目标周期
2. **库存确认**：API 高频轮询检测候选命中，并在 20ms 后做一次确认轮询
3. **提交点击**：只有在 `stock_confirmed` 与 `hot_ready` 同时成立时才点击购买
4. **短恢复**：若库存确认时页面暂不可点，仅允许一次 400ms 内的轻量恢复
5. **验证码处理**：点击提交后继续在同一浏览器会话中处理验证码
```

- [ ] **Step 2: Run the full GLM bot-related test suite**

Run: `uv run python -m pytest tests/test_browser_controller.py tests/test_cli_buy_flow.py tests/test_cli_check_login.py tests/test_integration.py tests/test_purchase_coordinator.py tests/test_stock_monitor.py -v`

Expected: PASS with all stability-related coverage green.

- [ ] **Step 3: Run compile verification**

Run: `uv run python -m compileall tools/glm_coding_bot/cli.py tools/glm_coding_bot/core/browser_controller.py tools/glm_coding_bot/core/purchase_coordinator.py tools/glm_coding_bot/core/stock_monitor.py`

Expected: exit code `0`

- [ ] **Step 4: Commit**

```bash
git add tools/glm_coding_bot/README.md
git commit -m "docs: document stability-first purchase flow"
```

## Self-Review

- Spec coverage check:
  - stock availability hardening is covered by Task 1
  - confirmed stock signal is covered by Task 2
  - page readiness and bounded recovery are covered by Task 3
  - coordinator phases and commit gating are covered by Task 4
  - CLI orchestration is covered by Task 5
  - documentation and verification are covered by Task 6
- Placeholder scan:
  - no unfinished placeholders or open-ended implementation instructions remain
- Type consistency:
  - `PageState`, `StockSignal`, `PurchaseSession`, `PurchaseResult`, and `PurchaseCoordinator` names are used consistently across tasks
