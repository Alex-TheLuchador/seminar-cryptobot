import uuid
from dataclasses import dataclass, field

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from safe.audit import Auditor
from safe.guardrails import GuardrailError, Guardrails


@dataclass
class Executor:
    exchange: Exchange
    info: Info
    main_wallet: str
    auditor: Auditor
    guardrails: Guardrails
    dry_run: bool

    _current_signal_id: str | None = field(default=None, init=False, repr=False)

    def register_signal(self, signal_id: str | None) -> None:
        """Called by the agent before each Claude invocation to set the valid signal_id."""
        self._current_signal_id = signal_id

    def execute_order(self, side: str, size_pct: float, signal_id: str) -> str:
        """
        Tool implementation called by Claude. Validates, enforces guardrails, places order.
        Always returns a string — errors are returned, not raised, so Claude sees the outcome.
        """
        # Signal validation — reject any call whose signal_id was not pre-registered
        if signal_id != self._current_signal_id:
            reason, detail = "signal_mismatch", f"got={signal_id!r} expected={self._current_signal_id!r}"
            self.auditor.log_guardrail_block(reason, detail)
            return f"BLOCKED:{reason} {detail}"

        if side not in ("buy", "sell"):
            return f"BLOCKED:invalid_side {side!r}"

        # Position cap
        try:
            self.guardrails.check_position_size(size_pct)
        except GuardrailError as e:
            self.auditor.log_guardrail_block(e.reason, e.detail)
            return f"BLOCKED:{e.reason} {e.detail}"

        # Get current equity and run circuit breaker
        spot = self.info.spot_user_state(self.main_wallet)
        usdc = next((b for b in spot["balances"] if b["coin"] == "USDC"), None)
        equity = float(usdc["total"]) if usdc else 0.0

        try:
            self.guardrails.check_daily_loss(equity)
        except GuardrailError as e:
            self.auditor.log_guardrail_block(e.reason, e.detail)
            return f"BLOCKED:{e.reason} {e.detail}"

        # Compute order size
        btc_price = float(self.info.all_mids()["BTC"])
        size_btc = round((equity * size_pct) / btc_price, 6)
        cloid = uuid.uuid4().hex

        self.auditor.log_intent(signal_id, side, size_pct, self.dry_run)

        if self.dry_run:
            self.auditor.log_result(signal_id, "dry_run", f"cloid={cloid} btc={size_btc}")
            return f"DRY_RUN side={side} btc={size_btc:.6f} price~{btc_price:.0f}"

        try:
            result = self.exchange.market_open("BTC", side == "buy", size_btc, cloid=cloid)
            if result.get("status") == "ok":
                self.auditor.log_result(signal_id, "ok", f"cloid={cloid}")
                return f"order placed cloid={cloid} btc={size_btc:.6f}"
            else:
                detail = str(result)
                self.auditor.log_result(signal_id, "error", detail)
                return f"order failed: {detail}"
        except Exception as exc:
            detail = str(exc)
            self.auditor.log_result(signal_id, "error", detail)
            self.auditor.log_error(detail)
            return f"exchange error: {detail}"
