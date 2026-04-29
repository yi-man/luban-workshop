# GLM Coding Bot Stability-First Purchase Flow Design

## Goal

Improve purchase success rate and timing stability for `glm-coding-bot` when using a headed browser. The design prioritizes:

- reducing false stock positives
- ensuring the purchase page is already clickable when stock appears
- avoiding last-second browser startup delays
- keeping operator behavior understandable and observable

This design explicitly does **not** optimize for maximum raw trigger speed at the cost of stability, and it does **not** switch the primary execution path to headless mode.

## Current Problems

### 1. Stock detection is too permissive

Current stock parsing treats a successful API response as stock availability. That is too weak as a business signal and can trigger false commits.

### 2. Browser preparation is too late

The current flow delays browser warmup until close to the target time, then starts polling after warmup-related work. This risks missing the first valid stock window because browser startup, navigation, or page repair consumes the critical seconds.

### 3. Page readiness is implicit instead of explicit

The current browser logic assumes that if the page was opened and a button was found once, it remains actionable. In practice, route changes, overlays, tab state drift, lazy layout shifts, or login interruptions can make the page non-clickable at the exact commit moment.

### 4. Purchase coordination is embedded in `_buy()`

Login verification, time sync, waiting, browser setup, stock polling, click timing, and captcha follow-up are all mixed together. That makes race conditions and recovery rules hard to reason about and hard to test.

## Design Principles

- Use a **headed browser** for the actual purchase path.
- Treat stock availability and page clickability as **independent signals**.
- Allow a click only when both signals are valid at the same time.
- Prefer **short, bounded recovery** over broad rebuilds during the purchase window.
- Make the execution path observable through explicit state and timing logs.

## Proposed Architecture

### Components

#### `PurchaseCoordinator`

Owns the overall purchase state machine and final commit decision.

Responsibilities:

- start browser warmup
- start stock polling in the active window
- track shared runtime state
- decide when click is allowed
- stop redundant work once commit starts

#### `PageWarmupController`

Owns browser-side readiness.

Responsibilities:

- launch or attach to the persistent headed browser context
- navigate to the target purchase page
- select the desired subscription period
- resolve and track the target purchase button
- maintain page readiness signals
- perform one short bounded recovery if the page becomes temporarily unready
- perform the actual click when authorized

#### `StockSignalMonitor`

Owns stock confidence logic.

Responsibilities:

- reuse the existing stock API polling path
- convert raw poll results into a stock signal
- require a short confirmation sequence before reporting confirmed stock
- expose raw responses for diagnosis

#### `PurchaseSession`

Owns shared runtime state.

Recommended as a dataclass with small nested state records instead of loose booleans.

Fields:

- `page_state`
- `stock_state`
- `phase`
- `commit_started`
- `commit_completed`
- `recovery_used`
- `timing_metrics`
- `failure_reason`

## State Model

### Coordinator Phases

- `INIT`
- `WARMING`
- `HOT_STANDBY`
- `STOCK_PENDING_CONFIRM`
- `COMMIT_READY`
- `COMMITTING`
- `RECOVERING`
- `COMPLETED`
- `FAILED`
- `TIMEOUT`

### Transition Rules

- `INIT -> WARMING` when the run starts
- `WARMING -> HOT_STANDBY` when `warm_ready` becomes true
- `HOT_STANDBY -> STOCK_PENDING_CONFIRM` when the first valid stock hit appears
- `STOCK_PENDING_CONFIRM -> COMMIT_READY` when stock confirmation succeeds
- `COMMIT_READY -> COMMITTING` when `hot_ready` is true
- `COMMIT_READY -> RECOVERING` when stock is confirmed but page is not hot-ready
- `RECOVERING -> COMMITTING` when recovery succeeds within budget
- `RECOVERING -> FAILED` when recovery budget is exhausted
- any phase -> `FAILED` on unrecoverable login, route, or browser errors
- any pre-commit phase -> `TIMEOUT` when the purchase window expires

Only one transition path may lead to the actual click. Once `COMMITTING` starts, no second click attempt may begin.

## Page Readiness Model

### `warm_ready`

Represents pre-positioning success. It means the page has been prepared well enough to wait for stock.

Required conditions:

- `session_ok`
- `route_ok`
- `period_ok`
- `button_present`
- `viewport_ok`

### `hot_ready`

Represents immediate clickability. It must be refreshed continuously during the critical window.

Required conditions:

- all `warm_ready` conditions
- `button_clickable`
- `captcha_blocking == false`
- no blocking overlay or modal
- button point remains within a valid viewport hit target

### Page State Shape

Recommended fields:

- `session_ok: bool`
- `route_ok: bool`
- `period_ok: bool`
- `button_present: bool`
- `button_clickable: bool`
- `viewport_ok: bool`
- `captcha_blocking: bool`
- `warm_ready: bool`
- `hot_ready: bool`
- `last_checked_at: float`
- `last_failure_reason: str | None`

### Refresh Timing

- build `warm_ready` no later than `T-45s`
- refresh `hot_ready` every `1000ms` before the final window
- refresh `hot_ready` every `250ms` in the final `2s` window

The page task reports state continuously. It does not block on stock events.

## Stock Signal Model

### Raw Polling

`StockMonitor` continues to poll frequently, but its raw `available` field no longer means "safe to buy now".

### Signal Semantics

Introduce a higher-level stock signal record with fields like:

- `raw_hit: bool`
- `first_hit_at: float | None`
- `confirmed: bool`
- `confirmed_at: float | None`
- `confidence: int`
- `last_raw_response: dict | None`

### Confirmation Rule

The first iteration uses a simple bounded rule:

- first candidate hit marks `raw_hit`
- immediately perform exactly one additional confirmation poll after a `20ms` delay
- only mark `confirmed=true` if both the initial hit and the confirmation hit succeed

This intentionally favors stability over absolute earliest reaction.

### Availability Criteria

The implementation must stop treating `code == 200` alone as stock availability. Availability is derived from explicit business fields in the response when they exist. If those fields are absent or unstable, the system treats the response as a candidate signal only and still requires the confirmation rule above.

The parser contract must be covered by tests with representative positive and negative payloads.

## Timing Strategy

### Pre-Window

- verify login before entering the purchase window
- perform NTP sync
- launch headed browser early
- navigate to the target page
- select the target period
- resolve the target package button
- establish `warm_ready`

### Active Window

- keep the browser parked and refreshed
- start high-frequency stock polling independently
- update `hot_ready` continuously
- commit only when `stock_confirmed` and `hot_ready` are both true

### Post-Commit

- stop or sharply reduce stock polling
- proceed to captcha handling
- continue using the same headed browser session

## Recovery Rules

### Recoverable Errors

- target button moved out of viewport
- period tab lost selected state
- button covered by a transient overlay
- single API timeout
- single API 5xx
- confirmed stock arrives while `hot_ready` is false

### Recovery Policy

- allow exactly one short `attempt_recover()` during the commit window
- recovery may include re-scroll, button re-resolution, and period re-selection
- recovery must complete within a strict `400ms` budget
- recovery must not rebuild the entire browser context

### Unrecoverable Errors

- login becomes invalid
- route changes to login, anti-bot, or unknown intermediate page
- repeated API failures make the signal untrustworthy
- the click path enters an unknown page after commit and cannot be classified

These should fail fast with explicit logging.

## Concurrency Model

Run two independent async tasks coordinated by shared session state:

- `page_task`
- `stock_task`

The coordinator reads both states and performs transitions. The tasks do not directly click and do not decide final commit.

Rules:

- browser task reports page readiness only
- stock task reports stock confidence only
- coordinator is the sole authority for entering `COMMITTING`
- once `commit_started` is true, further commit attempts are blocked

## Code Organization

### New or Expanded Modules

- add `tools/glm_coding_bot/core/purchase_coordinator.py`
- expand `tools/glm_coding_bot/core/browser_controller.py` with readiness and bounded recovery helpers
- add `StockSignalMonitor` in `tools/glm_coding_bot/core/stock_monitor.py`
- keep `tools/glm_coding_bot/cli.py` as orchestration entry only

### Recommended Public Methods

`PageWarmupController`

- `warm_up(package: str, period: str) -> None`
- `refresh_hot_ready() -> PageState`
- `attempt_recover() -> bool`
- `click_purchase() -> bool`

`StockSignalMonitor`

- `poll_until_window() -> None`
- `check_once() -> StockSignal`
- `confirm_hit() -> bool`

`PurchaseCoordinator`

- `run() -> PurchaseResult`

### `_buy()` Refactor

`_buy()` retains:

- CLI argument interpretation
- login validation
- time sync
- product resolution
- purchase window calculation

`_buy()` delegates purchase execution to the coordinator instead of directly managing browser and polling loops.

## Logging and Metrics

Capture at least these timestamps:

- `browser_warm_ready_at`
- `hot_ready_at`
- `stock_first_hit_at`
- `stock_confirmed_at`
- `recovery_started_at`
- `click_started_at`
- `click_finished_at`

Capture at least these outcome fields:

- `phase_at_failure`
- `failure_reason`
- `api_confirmation_attempts`
- `recovery_used`

This data is required for post-run diagnosis.

## Testing Strategy

### Unit Tests

Cover:

- stock confirmation rules
- page readiness computation
- coordinator state transitions
- single-use recovery budget enforcement
- no double-click after `commit_started`

### Integration Tests

Cover:

- page becomes ready before stock
- stock appears before page becomes hot-ready
- one false positive hit followed by failed confirmation
- confirmed stock plus transient page drift with successful recovery
- confirmed stock plus failed recovery

### Manual Validation

Use a real headed browser session to validate:

- login persistence
- route stability on the target page
- target period selection
- button hit testing after long idle warmup
- captcha handoff after commit

For non-sale hours, a mock or injected stock signal is used to test the click path without relying on live inventory.

## Acceptance Criteria

- a single positive API response does not immediately trigger a click
- stock confirmation is required before commit
- browser startup is completed before the active polling window
- the page must be hot-ready at commit time
- only one bounded recovery is allowed in the commit window
- the system never initiates a second click after commit has started

## Out of Scope

- replacing the headed browser with headless execution
- redesigning captcha solving behavior beyond existing handoff boundaries
- multi-account orchestration
- proxy rotation or anti-bot evasion strategy
- UI redesign of CLI commands
