"""
Circuit breaker demo script.

Pretends the session started with 10% more equity than the wallet currently holds,
putting the bot 10% in the red — well past the 2% daily loss threshold. Then
attempts a trade directly against the executor, bypassing market signal collection
so the circuit breaker fires regardless of current momentum/funding/sentiment state.

Usage:
    python demo/trip_circuit_breaker.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from safe.audit import Auditor
from safe.config import TESTNET_URL, Config
from safe.guardrails import Guardrails
from safe.tools.executor import Executor

config = Config.load()

info = Info(base_url=TESTNET_URL, skip_ws=True)
spot = info.spot_user_state(config.main_wallet_address)
usdc = next((b for b in spot["balances"] if b["coin"] == "USDC"), None)
real_equity = float(usdc["total"]) if usdc else 0.0

# Pretend the session started 10% higher — current equity is already 10% below that baseline.
inflated_baseline = real_equity * 1.10
loss_pct = (inflated_baseline - real_equity) / inflated_baseline * 100
threshold_pct = Guardrails().max_daily_loss_pct * 100

print(f"Real equity:      ${real_equity:,.2f}")
print(f"Simulated start:  ${inflated_baseline:,.2f}  (10% above real)")
print(f"Simulated loss:   {loss_pct:.1f}%  (threshold: {threshold_pct:.0f}%)")
print("=" * 60)

# Build the executor directly — skip market signal collection so this demo
# fires cleanly regardless of what momentum/funding/sentiment happen to be today.
wallet = Account.from_key(config.api_private_key)
exchange = Exchange(wallet=wallet, base_url=TESTNET_URL, account_address=config.main_wallet_address)
auditor = Auditor()
guardrails = Guardrails()
guardrails.set_session_equity(inflated_baseline)

executor = Executor(
    exchange=exchange,
    info=info,
    main_wallet=config.main_wallet_address,
    auditor=auditor,
    guardrails=guardrails,
    dry_run=True,  # circuit breaker fires before any exchange call, but keep this safe
)

signal_id = "demo-circuit-breaker"
executor.register_signal(signal_id)
result = executor.execute_order("buy", 0.03, signal_id)
print(f"execute_order → {result}")
