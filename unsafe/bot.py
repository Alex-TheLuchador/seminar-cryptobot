"""
BTC perpetual futures trading bot.

Reads news headlines, asks Claude what to do, places orders on Hyperliquid.

This file is deliberately written the way a "vibe-coded" agent looks in practice.
Every bad practice is visible. The contrast with the safe version is the lesson.
"""
import json
import time
import anthropic
from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from eth_account import Account


# Secrets hardcoded in source. Anyone who can read this file (or scrape the
# repo from GitHub) gets the keys. Bots scrape new public repos within minutes
# of a push; once leaked, a private key cannot be revoked.
# (These are placeholder values — replace with real testnet credentials to run.)
#
# Hyperliquid uses two separate addresses:
#   HYPERLIQUID_API_PRIVATE_KEY     — private key of the API sub-wallet (signs orders)
#   HYPERLIQUID_API_WALLET_ADDRESS  — address of the API sub-wallet (authorised signer)
#   HYPERLIQUID_MAIN_WALLET_ADDRESS — your main Hyperliquid account (holds USDC balance)
# If you use your main wallet key directly (not an API sub-wallet), set
# HYPERLIQUID_MAIN_WALLET_ADDRESS and HYPERLIQUID_API_WALLET_ADDRESS to the same value.
HYPERLIQUID_API_PRIVATE_KEY = "0xa1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890a1b2c3d4e5f67890"
HYPERLIQUID_API_WALLET_ADDRESS = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
HYPERLIQUID_MAIN_WALLET_ADDRESS = "0x0000000000000000000000000000000000000001"
CLAUDE_API_KEY = "sk-ant-api03-PLACEHOLDER_REPLACE_TO_RUN"

# Defaults to live mode against testnet. No DRY_RUN flag. No paper trading.
TESTNET_URL = constants.TESTNET_API_URL
MODEL = "claude-sonnet-4-6"

wallet = Account.from_key(HYPERLIQUID_API_PRIVATE_KEY)
info = Info(base_url=TESTNET_URL, skip_ws=True)
exchange = Exchange(wallet=wallet, base_url=TESTNET_URL, account_address=HYPERLIQUID_MAIN_WALLET_ADDRESS)
claude = anthropic.Anthropic(api_key=CLAUDE_API_KEY)


def run_once(headlines_path="demo/headlines_clean.json"):
    # Reads the whole file as a raw string. No JSON parsing. No sanitisation.
    # Whatever is in this file ends up directly inside the model's system prompt.
    news = open(headlines_path).read()

    price = float(info.all_mids()["BTC"])
    print(f"BTC price: ${price:,.2f}")

    # Untrusted external content is concatenated straight into the system prompt.
    # This is the prompt injection door: any "instructions" hidden in the news
    # file are read as operator instructions.
    response = claude.messages.create(
        model=MODEL,
        max_tokens=200,
        system=(
            f"You are a crypto trading bot. Latest news: {news}. "
            f"Current BTC price: {price}. "
            f"Respond with exactly one word: buy, sell, or hold."
        ),
        messages=[{"role": "user", "content": "What should I do with BTC right now?"}],
    )

    decision = response.content[0].text.strip().lower()
    print(f"Claude decision: {decision}")

    # 100% of account value sized into a single trade. No position limits.
    # No daily loss limit. One bad decision = total loss.
    # Unified account: USDC lives in spot state, not perp margin summary.
    spot = info.spot_user_state(HYPERLIQUID_MAIN_WALLET_ADDRESS)
    usdc = next(b for b in spot["balances"] if b["coin"] == "USDC")
    balance = float(usdc["total"])
    size = round(balance / price, 5)
    print(f"Sizing: balance=${balance:,.2f}, size={size} BTC")

    # No client order ID. If the network drops between submit and confirmation,
    # the naive retry below would place the same order twice.
    if "buy" in decision:
        result = exchange.market_open("BTC", True, size)
        print(f"BUY placed: {result}")
    elif "sell" in decision:
        result = exchange.market_open("BTC", False, size)
        print(f"SELL placed: {result}")
    else:
        print("Hold.")


def run():
    # while True with no kill switch, no max-iteration cap, no drawdown tracking.
    # The only way to stop this is Ctrl+C. Errors are swallowed and the loop
    # retries immediately with no backoff.
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"Error: {e} -- retrying")
        time.sleep(3600)


if __name__ == "__main__":
    run()
