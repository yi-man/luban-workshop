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
    def __init__(
        self,
        package: str,
        period: str,
        product_id: str,
        page_controller,
        signal_monitor,
        stock_timeout: float = 60.0,
    ):
        self.package = package
        self.period = period
        self.product_id = product_id
        self.page_controller = page_controller
        self.signal_monitor = signal_monitor
        self.stock_timeout = stock_timeout
        self.session = PurchaseSession()

    async def run(self) -> PurchaseResult:
        self.session = PurchaseSession()
        self.session.phase = "WARMING"
        page_state = await self.page_controller.refresh_page_state(self.package, self.period)
        if not page_state.warm_ready:
            return self._fail("warmup-not-ready")

        self.session.phase = "STOCK_PENDING_CONFIRM"
        signal = await self.signal_monitor.wait_for_confirmed_hit(timeout=self.stock_timeout)
        if not signal.confirmed:
            return self._fail("stock-unconfirmed")
        if signal.product_id != self.product_id:
            return self._fail("stock-product-mismatch")

        self.session.phase = "COMMIT_READY"
        page_state = await self.page_controller.refresh_page_state(self.package, self.period)
        if not page_state.hot_ready:
            self.session.phase = "RECOVERING"
            self.session.recovery_used = True
            if not await self.page_controller.attempt_recover(self.package, self.period):
                return self._fail("recovery-failed")
            page_state = await self.page_controller.refresh_page_state(self.package, self.period)
            if not page_state.hot_ready:
                return self._fail("not-hot-ready")

        self.session.phase = "COMMITTING"
        self.session.commit_started = True
        clicked = await self.page_controller.click_purchase(self.package, self.period)
        if not clicked:
            return self._fail("click-failed")

        self.session.commit_completed = True
        self.session.phase = "COMPLETED"
        return PurchaseResult(True, "COMPLETED", timing_metrics=self.session.timing_metrics)

    def _fail(self, reason: str) -> PurchaseResult:
        self.session.phase = "FAILED"
        self.session.failure_reason = reason
        return PurchaseResult(False, "FAILED", reason)
