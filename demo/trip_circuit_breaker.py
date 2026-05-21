"""
Circuit breaker demo script.

Pretends the session started with 10% more equity than the wallet currently holds,
putting the bot 10% in the red — well past the 2% daily loss threshold.

Usage:
    python demo/trip_circuit_breaker.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hyperliquid.info import Info

from safe.agent import run
from safe.config import TESTNET_URL, Config

config = Config.load()

info = Info(base_url=TESTNET_URL, skip_ws=True)
spot = info.spot_user_state(config.main_wallet_address)
usdc = next((b for b in spot["balances"] if b["coin"] == "USDC"), None)
real_equity = float(usdc["total"]) if usdc else 0.0

# Pretend the session started 10% higher — current equity is already 10% below that baseline.
inflated_baseline = real_equity * 1.10

print(f"Real equity:      ${real_equity:,.2f}")
print(f"Simulated start:  ${inflated_baseline:,.2f}  (10% above real)")
print(f"Simulated loss:   {((inflated_baseline - real_equity) / inflated_baseline) * 100:.1f}%  (threshold: 2%)")
print("=" * 60)

run(config, "demo/headlines_clean.json", session_equity_override=inflated_baseline)
