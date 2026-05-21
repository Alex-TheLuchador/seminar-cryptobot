import time
from dataclasses import dataclass

from hyperliquid.info import Info


@dataclass(frozen=True)
class Signal:
    value: str  # "bullish" | "bearish" | "neutral"
    detail: str


@dataclass(frozen=True)
class MarketSnapshot:
    btc_price: float
    momentum: Signal
    funding: Signal


_CANDLE_COUNT = 5
_CANDLE_INTERVAL = "1h"
_MOMENTUM_THRESHOLD = 0.001   # 0.1% deviation from mean
_FUNDING_THRESHOLD = 0.0001   # 0.01%/hr — positive means longs pay shorts


def _momentum_signal(info: Info, current_price: float) -> Signal:
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - _CANDLE_COUNT * 3600 * 1000
    candles = info.candles_snapshot("BTC", _CANDLE_INTERVAL, start_ms, now_ms)
    if not candles:
        return Signal("neutral", "no candle data")
    closes = [float(c["c"]) for c in candles]
    mean = sum(closes) / len(closes)
    deviation = (current_price - mean) / mean
    label = "bullish" if deviation > _MOMENTUM_THRESHOLD else "bearish" if deviation < -_MOMENTUM_THRESHOLD else "neutral"
    return Signal(label, f"price={current_price:.0f} mean={mean:.0f} dev={deviation:.4f}")


def _funding_signal(info: Info) -> Signal:
    meta, asset_ctxs = info.meta_and_asset_ctxs()
    btc_idx = next(i for i, a in enumerate(meta["universe"]) if a["name"] == "BTC")
    rate = float(asset_ctxs[btc_idx]["funding"])
    if rate > _FUNDING_THRESHOLD:
        return Signal("bearish", f"funding={rate:.6f} (longs pay, market overbought)")
    elif rate < -_FUNDING_THRESHOLD:
        return Signal("bullish", f"funding={rate:.6f} (shorts pay, market oversold)")
    else:
        return Signal("neutral", f"funding={rate:.6f}")


def fetch_snapshot(info: Info) -> MarketSnapshot:
    btc_price = float(info.all_mids()["BTC"])
    return MarketSnapshot(
        btc_price=btc_price,
        momentum=_momentum_signal(info, btc_price),
        funding=_funding_signal(info),
    )
