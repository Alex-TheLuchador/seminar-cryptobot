import pytest

from safe.guardrails import GuardrailError, Guardrails


def test_position_cap_at_limit_passes():
    g = Guardrails()
    g.check_position_size(0.05)  # exactly at cap — not over


def test_position_cap_blocks():
    g = Guardrails()
    with pytest.raises(GuardrailError) as exc_info:
        g.check_position_size(0.06)
    assert exc_info.value.reason == "position_cap"


def test_circuit_breaker_under_threshold_passes():
    g = Guardrails()
    g.set_session_equity(1000.0)
    g.check_daily_loss(990.0)  # 1% loss — under 2% threshold


def test_circuit_breaker_at_threshold_trips():
    g = Guardrails()
    g.set_session_equity(1000.0)
    with pytest.raises(GuardrailError) as exc_info:
        g.check_daily_loss(979.0)  # 2.1% loss — over threshold
    assert exc_info.value.reason == "circuit_breaker"


def test_circuit_breaker_stays_tripped_after_recovery():
    g = Guardrails()
    g.set_session_equity(1000.0)
    with pytest.raises(GuardrailError):
        g.check_daily_loss(979.0)
    with pytest.raises(GuardrailError) as exc_info:
        g.check_daily_loss(1010.0)  # equity recovered — still blocked
    assert exc_info.value.reason == "circuit_breaker"


def test_circuit_breaker_skips_check_when_no_equity_set():
    g = Guardrails()
    # session equity never set — should not raise
    g.check_daily_loss(500.0)


def test_kill_switch_no_file_passes(tmp_path):
    g = Guardrails(kill_switch_path=str(tmp_path / "kill.txt"))
    g.check_kill_switch()


def test_kill_switch_empty_file_passes(tmp_path):
    ks = tmp_path / "kill.txt"
    ks.write_text("")
    g = Guardrails(kill_switch_path=str(ks))
    g.check_kill_switch()


def test_kill_switch_fires_on_stop(tmp_path):
    ks = tmp_path / "kill.txt"
    ks.write_text("STOP")
    g = Guardrails(kill_switch_path=str(ks))
    with pytest.raises(GuardrailError) as exc_info:
        g.check_kill_switch()
    assert exc_info.value.reason == "kill_switch"


def test_kill_switch_case_insensitive(tmp_path):
    ks = tmp_path / "kill.txt"
    ks.write_text("stop")
    g = Guardrails(kill_switch_path=str(ks))
    with pytest.raises(GuardrailError) as exc_info:
        g.check_kill_switch()
    assert exc_info.value.reason == "kill_switch"


def test_max_iterations_blocks_after_limit():
    g = Guardrails(max_iterations=3)
    for _ in range(3):
        g.check_iterations()
        g.increment()
    with pytest.raises(GuardrailError) as exc_info:
        g.check_iterations()
    assert exc_info.value.reason == "max_iterations"


def test_max_iterations_passes_before_limit():
    g = Guardrails(max_iterations=3)
    g.check_iterations()  # count=0 — should pass
