"""Purchase coordinator state machine."""

from dataclasses import dataclass, field


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
            self.session.phase = "FAILED"
            self.session.failure_reason = "warmup-not-ready"
            return PurchaseResult(False, "FAILED", "warmup-not-ready")

        self.session.phase = "STOCK_PENDING_CONFIRM"
        signal = await self.signal_monitor.confirm_hit()
        if not signal.confirmed:
            self.session.phase = "FAILED"
            self.session.failure_reason = "stock-unconfirmed"
            return PurchaseResult(False, "FAILED", "stock-unconfirmed")

        self.session.phase = "COMMIT_READY"
        page_state = await self.page_controller.refresh_page_state(self.package, self.period)
        if not page_state.hot_ready:
            self.session.phase = "RECOVERING"
            self.session.recovery_used = True
            if not await self.page_controller.attempt_recover(self.package, self.period):
                self.session.phase = "FAILED"
                self.session.failure_reason = "recovery-failed"
                return PurchaseResult(False, "FAILED", "recovery-failed")
            page_state = await self.page_controller.refresh_page_state(self.package, self.period)
            if not page_state.hot_ready:
                self.session.phase = "FAILED"
                self.session.failure_reason = "not-hot-ready"
                return PurchaseResult(False, "FAILED", "not-hot-ready")

        self.session.phase = "COMMITTING"
        self.session.commit_started = True
        clicked = await self.page_controller.click_purchase(self.package, self.period)
        if not clicked:
            self.session.phase = "FAILED"
            self.session.failure_reason = "click-failed"
            return PurchaseResult(False, "FAILED", "click-failed")

        self.session.commit_completed = True
        self.session.phase = "COMPLETED"
        return PurchaseResult(True, "COMPLETED", timing_metrics=self.session.timing_metrics)
