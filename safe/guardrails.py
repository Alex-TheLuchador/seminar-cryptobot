from dataclasses import dataclass, field
from pathlib import Path


class GuardrailError(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


@dataclass
class Guardrails:
    kill_switch_path: str = "kill_switch.txt"
    max_position_pct: float = 0.05
    max_daily_loss_pct: float = 0.02
    max_iterations: int = 100

    _iteration_count: int = field(default=0, init=False, repr=False)
    _session_start_equity: float = field(default=0.0, init=False, repr=False)
    _circuit_tripped: bool = field(default=False, init=False, repr=False)

    def set_session_equity(self, equity: float) -> None:
        self._session_start_equity = equity

    def check_kill_switch(self) -> None:
        path = Path(self.kill_switch_path)
        if path.exists() and "STOP" in path.read_text().upper():
            raise GuardrailError("kill_switch")

    def check_iterations(self) -> None:
        if self._iteration_count >= self.max_iterations:
            raise GuardrailError("max_iterations", f"limit={self.max_iterations}")

    def check_position_size(self, size_pct: float) -> None:
        if size_pct > self.max_position_pct:
            raise GuardrailError(
                "position_cap",
                f"{size_pct:.4f} > cap={self.max_position_pct:.4f}",
            )

    def check_daily_loss(self, current_equity: float) -> None:
        if self._circuit_tripped:
            raise GuardrailError("circuit_breaker", "already tripped this session")
        if self._session_start_equity <= 0:
            return
        loss_pct = (self._session_start_equity - current_equity) / self._session_start_equity
        if loss_pct >= self.max_daily_loss_pct:
            self._circuit_tripped = True
            raise GuardrailError(
                "circuit_breaker",
                f"loss={loss_pct:.4f} >= threshold={self.max_daily_loss_pct:.4f}",
            )

    def increment(self) -> None:
        self._iteration_count += 1
