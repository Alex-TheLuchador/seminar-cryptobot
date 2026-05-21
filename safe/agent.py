import uuid

import anthropic
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

from safe.audit import Auditor
from safe.config import MODEL, TESTNET_URL, Config
from safe.guardrails import GuardrailError, Guardrails
from safe.tools.executor import Executor
from safe.tools.market_data import fetch_snapshot
from safe.tools.news_feed import TripwireError
from safe.tools.news_feed import process as process_headlines


_SENTIMENT_SYSTEM = (
    "You are a news sentiment classifier. "
    "Classify the BTC market sentiment of the provided headline as bullish, bearish, or neutral. "
    "Respond with exactly one word: bullish, bearish, or neutral."
)

# Tool description uses neutral, functional language — no loaded vocabulary that an injected
# payload could use to steer tool selection.
_EXECUTE_ORDER_TOOL = {
    "name": "execute_order",
    "description": (
        "Submit a BTC perpetual futures market order on Hyperliquid. "
        "Pass the signal_id exactly as provided in the system prompt. "
        "Returns a status string."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "side": {
                "type": "string",
                "enum": ["buy", "sell"],
            },
            "size_pct": {
                "type": "number",
                "description": "Fraction of portfolio equity to size the order (0.0–1.0).",
            },
            "signal_id": {
                "type": "string",
                "description": "Signal identifier from the system prompt. Must be passed verbatim.",
            },
        },
        "required": ["side", "size_pct", "signal_id"],
    },
}


def _classify_sentiment(client: anthropic.Anthropic, wrapped_headlines: str) -> str:
    """Call 1 — no tools available. Injection text is confined here; output is a 3-state label."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=10,
        system=_SENTIMENT_SYSTEM,
        messages=[{"role": "user", "content": wrapped_headlines}],
    )
    raw = response.content[0].text.strip().lower()
    if "bull" in raw:
        return "bullish"
    if "bear" in raw:
        return "bearish"
    return "neutral"


def _consensus(momentum: str, funding: str, sentiment: str) -> str:
    """Majority vote across three signals. Returns 'buy', 'sell', or 'hold'."""
    bullish = [momentum, funding, sentiment].count("bullish")
    bearish = [momentum, funding, sentiment].count("bearish")
    if bullish >= 2:
        return "buy"
    if bearish >= 2:
        return "sell"
    return "hold"


def _run_trading_decision(
    client: anthropic.Anthropic,
    snapshot,
    sentiment: str,
    consensus_side: str,
    signal_id: str | None,
    executor: Executor,
) -> None:
    """Call 2 — receives only structured signals, never raw headline text. Has execute_order tool."""
    signals_block = (
        f"Market signals:\n"
        f"  momentum:  {snapshot.momentum.value}  ({snapshot.momentum.detail})\n"
        f"  funding:   {snapshot.funding.value}  ({snapshot.funding.detail})\n"
        f"  sentiment: {sentiment}"
    )

    if consensus_side == "hold":
        system = (
            f"You are a BTC perpetual futures trading assistant.\n\n"
            f"{signals_block}\n\n"
            f"Consensus: hold. Do not call execute_order."
        )
    else:
        system = (
            f"You are a BTC perpetual futures trading assistant.\n\n"
            f"{signals_block}\n\n"
            f"Consensus: {consensus_side}  |  signal_id: {signal_id}\n\n"
            f"Call execute_order once using the exact signal_id shown above. "
            f"Use a size_pct between 0.01 and 0.05 (1–5% of portfolio equity)."
        )

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": "Execute the consensus decision."}],
        tools=[_EXECUTE_ORDER_TOOL],
        tool_choice={"type": "auto"},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "execute_order":
            args = block.input
            result = executor.execute_order(
                side=args.get("side", ""),
                size_pct=float(args.get("size_pct", 0.0)),
                signal_id=args.get("signal_id", ""),
            )
            print(f"  execute_order → {result}")
            break
    else:
        print(f"  no tool call (consensus={consensus_side})")


def run(config: Config, headlines_path: str, session_equity_override: float | None = None) -> None:
    auditor = Auditor()
    guardrails = Guardrails()

    wallet = Account.from_key(config.api_private_key)
    info = Info(base_url=TESTNET_URL, skip_ws=True)
    exchange = Exchange(
        wallet=wallet,
        base_url=TESTNET_URL,
        account_address=config.main_wallet_address,
    )
    executor = Executor(
        exchange=exchange,
        info=info,
        main_wallet=config.main_wallet_address,
        auditor=auditor,
        guardrails=guardrails,
        dry_run=config.dry_run,
    )
    client = anthropic.Anthropic(api_key=config.claude_api_key)

    auditor.log_startup(config.dry_run)

    orphans = auditor.reconcile()
    if orphans:
        auditor.log_error(f"orphaned signal_ids on startup: {orphans}")
        print(f"WARNING: orphaned signal_ids from prior run: {orphans}")

    # Session equity baseline for circuit breaker
    spot = info.spot_user_state(config.main_wallet_address)
    usdc = next((b for b in spot["balances"] if b["coin"] == "USDC"), None)
    real_equity = float(usdc["total"]) if usdc else 0.0
    session_equity = session_equity_override if session_equity_override is not None else real_equity
    guardrails.set_session_equity(session_equity)
    print(f"Session equity: ${session_equity:,.2f}  |  dry_run={config.dry_run}")

    # Pre-flight: kill switch and iteration cap
    try:
        guardrails.check_kill_switch()
        guardrails.check_iterations()
    except GuardrailError as e:
        auditor.log_guardrail_block(e.reason, e.detail)
        print(f"HALTED: {e.reason} — {e.detail}")
        return

    # Market signals
    snapshot = fetch_snapshot(info)
    print(
        f"BTC: ${snapshot.btc_price:,.2f}  |  "
        f"momentum={snapshot.momentum.value}  |  "
        f"funding={snapshot.funding.value}"
    )

    # News: tripwire scan and sanitize
    try:
        wrapped = process_headlines(headlines_path)
    except TripwireError as e:
        auditor.log_tripwire(e.matched)
        print(f"TRIPWIRE: keyword={e.matched!r} — holding iteration")
        guardrails.increment()
        return

    # Call 1: sentiment classifier — no tools, injection confined here
    sentiment = _classify_sentiment(client, "\n".join(wrapped))
    print(f"  sentiment={sentiment}")

    # Compute consensus and authorize signal
    consensus_side = _consensus(snapshot.momentum.value, snapshot.funding.value, sentiment)
    signal_id = uuid.uuid4().hex if consensus_side != "hold" else None
    executor.register_signal(signal_id)
    sid_display = f"{signal_id[:8]}..." if signal_id else "none"
    print(f"  consensus={consensus_side}  signal_id={sid_display}")

    # Call 2: trading decision — sees only structured signals, has execute_order tool
    _run_trading_decision(client, snapshot, sentiment, consensus_side, signal_id, executor)

    guardrails.increment()
