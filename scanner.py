"""
scanner.py — MEXC Bounce Scanner signal logic.
Two-consecutive-scan gate: ALL four hard gates must pass on TWO scans 30s apart.
Score is binary 4/4 or 0 — no partial scoring.
"""

import asyncio
import time
import logging
from datetime import datetime, timezone
from typing import Optional

from config import (
    PAIRS, J15M_SHORT_GATE, J15M_LONG_GATE, J1H_SHORT_MIN, J1H_LONG_MAX,
    RSI15M_SHORT_MIN, RSI15M_LONG_MAX, DEPTH_GATE_PCT, ATR_SL_MULTIPLIER,
    TP1_R, TP2_R, LEVERAGE_HIGH, LEVERAGE_MID, LEVERAGE_LOW,
    COOLDOWN_SECONDS, ADX_FADE_MAX, PAPER_MODE, CONSECUTIVE_LOSS_STOP,
    MIN_SL_PCT, MIN_SL_PCT_DEFAULT, MARGIN_PER_TRADE,
)
from mexc_client import MexcClient, INTERVAL_15M, INTERVAL_1H

log = logging.getLogger("scanner")

# ── Module-level state ─────────────────────────────────────────────────────────
_last_scores: dict[str, int]   = {}
_cooldowns:   dict[str, float] = {}
_scan_count:  int              = 0
_pending:     dict[str, dict]  = {}   # key "SYMBOL_USDTLONG" — awaiting 2nd scan


# ── Indicator helpers ──────────────────────────────────────────────────────────

def _compute_kdj(candles: list[dict], period: int = 9) -> tuple[float, float, float]:
    if len(candles) < period:
        return 50.0, 50.0, 50.0
    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    K, D = 50.0, 50.0
    for i in range(len(closes)):
        if i < period - 1:
            continue
        h_n = max(highs[i - period + 1: i + 1])
        l_n = min(lows[i  - period + 1: i + 1])
        rsv = (closes[i] - l_n) / (h_n - l_n) * 100 if h_n != l_n else 50.0
        K   = 2 / 3 * K + 1 / 3 * rsv
        D   = 2 / 3 * D + 1 / 3 * K
    J = 3 * K - 2 * D
    return K, D, J


def _compute_rsi(candles: list[dict], period: int = 14) -> float:
    closes = [c["close"] for c in candles]
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(0.0, d))
        losses.append(max(0.0, -d))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    return 100 - 100 / (1 + avg_g / avg_l)


def _compute_atr(candles: list[dict], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 0.0
    atr = sum(trs[:period]) / min(period, len(trs))
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    return atr


def _compute_adx(candles: list[dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    plus_dms, minus_dms, trs = [], [], []
    for i in range(1, len(candles)):
        up   = candles[i]["high"]   - candles[i - 1]["high"]
        down = candles[i - 1]["low"] - candles[i]["low"]
        plus_dms.append(max(0.0, up)   if up   > down else 0.0)
        minus_dms.append(max(0.0, down) if down > up   else 0.0)
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return 0.0
    atr_s = sum(trs[:period])
    pdm_s = sum(plus_dms[:period])
    mdm_s = sum(minus_dms[:period])
    dxs   = []
    for i in range(period, len(trs)):
        atr_s = atr_s - atr_s / period + trs[i]
        pdm_s = pdm_s - pdm_s / period + plus_dms[i]
        mdm_s = mdm_s - mdm_s / period + minus_dms[i]
        if atr_s == 0:
            continue
        pdi = pdm_s / atr_s * 100
        mdi = mdm_s / atr_s * 100
        dxs.append(abs(pdi - mdi) / (pdi + mdi) * 100 if pdi + mdi else 0.0)
    if not dxs:
        return 0.0
    adx = sum(dxs[:period]) / min(period, len(dxs))
    for dx in dxs[period:]:
        adx = (adx * (period - 1) + dx) / period
    return adx


def _compute_ma(candles: list[dict], period: int) -> Optional[float]:
    closes = [c["close"] for c in candles]
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _trend_from_ma(price: float, candles_15m: list, candles_1h: list, adx_1h: float = 0.0) -> str:
    def _vote(candles, p):
        ma5  = _compute_ma(candles, 5)
        ma10 = _compute_ma(candles, 10)
        ma30 = _compute_ma(candles, 30)
        if ma5 and ma10 and ma30:
            if ma5 > ma10 > ma30 and p > ma10:
                return "BULL"
            if ma5 < ma10 < ma30 and p < ma10:
                return "BEAR"
        return "NEUTRAL"
    v15m = _vote(candles_15m, price)
    v1h  = _vote(candles_1h,  price)
    if v1h == "BEAR" and v15m == "BEAR" and adx_1h >= 25:
        return "Strong Bear"
    if v1h == "BEAR":
        return "Bearish"
    if v1h == "BULL" and v15m == "BULL" and adx_1h >= 25:
        return "Strong Bull"
    if v1h == "BULL":
        return "Bullish"
    if v15m == "BEAR":
        return "Bearish"
    if v15m == "BULL":
        return "Bullish"
    return "Neutral"


def _depth_pcts(book: dict) -> tuple[float, float]:
    bids = book.get("bids", [])
    asks = book.get("asks", [])
    bid_vol = sum(b["sz"] for b in bids)
    ask_vol = sum(a["sz"] for a in asks)
    total   = bid_vol + ask_vol
    if total == 0:
        return 50.0, 50.0
    return round(bid_vol / total * 100, 1), round(ask_vol / total * 100, 1)


def _leverage_tier(adx: float) -> tuple[str, int]:
    if adx >= 50:
        return "HIGH_PROB", LEVERAGE_HIGH
    if adx >= 25:
        return "STRONG",    LEVERAGE_MID
    return "REGULAR",       LEVERAGE_LOW


# ── Session helpers ────────────────────────────────────────────────────────────

def get_session_name() -> str:
    h = datetime.now(timezone.utc).hour
    # Asia: 22:00-08:00 UTC (17:00-03:00 EST)
    if h >= 22 or h < 8:  return "ASIA"
    # EU: 08:00-13:00 UTC (03:00-08:00 EST)
    if 8  <= h < 13:      return "EU"
    # EU/US overlap: 13:00-17:00 UTC (08:00-12:00 EST)
    if 13 <= h < 17:      return "EU_US"
    # US: 17:00-22:00 UTC (12:00-17:00 EST)
    return "US"


def is_asia_session() -> bool:
    return get_session_name() == "ASIA"


# ── Cooldown helpers ───────────────────────────────────────────────────────────

def set_cooldown(symbol: str, direction: str):
    _cooldowns[f"{symbol}{direction}"] = time.time() + COOLDOWN_SECONDS


def get_cooldown_remaining(symbol: str, direction: str) -> int:
    exp = _cooldowns.get(f"{symbol}{direction}", 0)
    return max(0, int(exp - time.time()))


def clear_cooldown(symbol: str, direction: str):
    _cooldowns.pop(f"{symbol}{direction}", None)


def get_pending() -> dict:
    return dict(_pending)


def get_scan_count() -> int:
    return _scan_count


def clear_all_scanner_state():
    global _scan_count
    _last_scores.clear()
    _cooldowns.clear()
    _pending.clear()
    _scan_count = 0


# ── Market health ──────────────────────────────────────────────────────────────

def compute_market_health(pair_states: list[dict], recent_trades: list[dict]) -> dict:
    total = len(pair_states)
    empty = {"short_status": "CAUTION", "long_status": "CAUTION",
             "bear_count": 0, "bull_count": 0, "total": 0,
             "bear_ratio": 0.0, "bull_ratio": 0.0,
             "avg_adx": 0.0, "avg_j15": 50.0, "sl_rate": 0.0,
             "short_reason": "Insufficient data", "long_reason": "Insufficient data"}
    if total == 0:
        return empty
    bear_count = sum(1 for s in pair_states if s.get("trend") in ("Bearish", "Strong Bear"))
    bull_count = sum(1 for s in pair_states if s.get("trend") in ("Bullish", "Strong Bull"))
    bear_ratio = bear_count / total
    bull_ratio = bull_count / total
    adx_vals   = [s["adx1h"]  for s in pair_states if s.get("adx1h")  is not None]
    j15_vals   = [s["j15m"]   for s in pair_states if s.get("j15m")   is not None]
    avg_adx    = sum(adx_vals) / len(adx_vals) if adx_vals else 0.0
    avg_j15    = sum(j15_vals) / len(j15_vals) if j15_vals else 50.0
    recent6    = [t for t in recent_trades if t.get("close_reason")][-6:]
    sl_rate    = (
        sum(1 for t in recent6 if (t.get("close_reason", "") or "").upper().startswith("SL"))
        / len(recent6)
    ) if recent6 else 0.0

    if bear_ratio >= 0.6 and avg_adx >= 35 and avg_j15 <= 70 and sl_rate < 0.4:
        short_status = "RUN"
        short_reason = f"{bear_count}/{total} pairs bearish, ADX avg {avg_adx:.0f}"
    elif bear_ratio < 0.3 or sl_rate >= 0.6 or (avg_j15 >= 85 and bear_ratio < 0.5):
        short_status = "HALT"
        short_reason = "Low bear conviction or high SL rate"
    else:
        short_status = "CAUTION"
        short_reason = "Mixed conditions"

    if bull_ratio >= 0.6 and avg_adx >= 35 and avg_j15 >= 30 and sl_rate < 0.4:
        long_status = "RUN"
        long_reason = f"{bull_count}/{total} pairs bullish, ADX avg {avg_adx:.0f}"
    elif bull_ratio < 0.3 or sl_rate >= 0.6 or (avg_j15 <= 15 and bull_ratio < 0.5):
        long_status = "HALT"
        long_reason = "Low bull conviction or high SL rate"
    else:
        long_status = "CAUTION"
        long_reason = "Mixed conditions"

    return {
        "short_status": short_status, "long_status": long_status,
        "bear_count": bear_count,     "bull_count": bull_count,
        "total": total,
        "bear_ratio": round(bear_ratio, 3), "bull_ratio": round(bull_ratio, 3),
        "avg_adx":  round(avg_adx, 1),      "avg_j15":  round(avg_j15, 1),
        "sl_rate":  round(sl_rate, 3),
        "short_reason": short_reason,        "long_reason": long_reason,
    }


# ── Main scan ──────────────────────────────────────────────────────────────────

async def _fetch_pair_data(client: MexcClient, symbol: str):
    candles_15m, candles_1h, book, price = await asyncio.gather(
        client.fetch_candles(symbol, INTERVAL_15M, 100),
        client.fetch_candles(symbol, INTERVAL_1H,  100),
        client.fetch_orderbook(symbol, 20),
        client.fetch_price(symbol),
    )
    return candles_15m, candles_1h, book, price


async def run_full_scan(client: MexcClient) -> list[dict]:
    global _scan_count
    _scan_count += 1
    new_alerts: list[dict] = []

    for symbol in PAIRS:
        try:
            await asyncio.sleep(0.4)   # gentle rate-limit: 10 pairs × 0.4s = 4s spread

            # ZEC Asia-session gate — only scan ZEC during Asia session
            if symbol == "ZEC_USDT" and not is_asia_session():
                continue

            candles_15m, candles_1h, book, price = await _fetch_pair_data(client, symbol)

            if not price or price == 0:
                log.warning(f"[SCAN] {symbol} — null price, skipping")
                continue

            # ── Indicators ─────────────────────────────────────────────────────
            _, _, j15m = _compute_kdj(candles_15m)
            _, _, j1h  = _compute_kdj(candles_1h)
            rsi15m     = _compute_rsi(candles_15m)
            atr15m     = _compute_atr(candles_15m)
            adx1h      = _compute_adx(candles_1h)
            trend      = _trend_from_ma(price, candles_15m, candles_1h, adx1h)
            bid_pct, ask_pct = _depth_pcts(book)

            # ── SL distance ────────────────────────────────────────────────────
            _sl_atr      = atr15m * ATR_SL_MULTIPLIER
            _min_sl_pct  = MIN_SL_PCT.get(symbol, MIN_SL_PCT_DEFAULT)
            sl_dist      = max(_sl_atr, price * _min_sl_pct) if _min_sl_pct else _sl_atr

            # ── ADX fade-max gate ──────────────────────────────────────────────
            if adx1h > ADX_FADE_MAX:
                log.debug(f"[SCAN] {symbol} ADX {adx1h:.1f} > {ADX_FADE_MAX} — skipping (fade max)")

            tier, lev = _leverage_tier(adx1h)

            for direction in ("SHORT", "LONG"):
                key = f"{symbol}{direction}"

                if get_cooldown_remaining(symbol, direction) > 0:
                    continue

                # ── ADX fade-max blocks alert firing ──
                if adx1h > ADX_FADE_MAX:
                    continue

                # ── Binary 4/4 gate check ──────────────────────────────────────
                if direction == "SHORT":
                    gates_pass = (
                        j15m  > J15M_SHORT_GATE    and
                        j1h   > J1H_SHORT_MIN      and
                        rsi15m > RSI15M_SHORT_MIN  and
                        ask_pct >= DEPTH_GATE_PCT
                    )
                else:
                    gates_pass = (
                        j15m  < J15M_LONG_GATE     and
                        j1h   < J1H_LONG_MAX       and
                        rsi15m < RSI15M_LONG_MAX   and
                        bid_pct >= DEPTH_GATE_PCT
                    )

                score = 4 if gates_pass else 0
                _last_scores[key] = score

                if not gates_pass:
                    _pending.pop(key, None)
                    continue

                # ── Two-consecutive-scan gate ──────────────────────────────────
                if key not in _pending:
                    _pending[key] = {
                        "symbol": symbol, "direction": direction,
                        "j15m": j15m, "j1h": j1h, "rsi15m": rsi15m,
                        "ask_pct": ask_pct, "bid_pct": bid_pct,
                        "adx": adx1h, "price": price,
                    }
                    log.info(f"[SCAN] {symbol} {direction} — 1st scan confirmed, awaiting 2nd")
                    continue

                # ── 2nd scan confirmed — fire alert ───────────────────────────
                _pending.pop(key, None)
                set_cooldown(symbol, direction)

                # SL / TP calculation
                if direction == "SHORT":
                    sl_price  = round(price + sl_dist, 8)
                    tp1_price = round(price - sl_dist * TP1_R, 8)
                    tp2_price = round(price - sl_dist * TP2_R, 8)
                    be_price  = round(price - price * 0.001, 8)   # ~0.1% fees
                else:
                    sl_price  = round(price - sl_dist, 8)
                    tp1_price = round(price + sl_dist * TP1_R, 8)
                    tp2_price = round(price + sl_dist * TP2_R, 8)
                    be_price  = round(price + price * 0.001, 8)

                session = get_session_name()

                alert = {
                    "symbol":    symbol,
                    "direction": direction,
                    "tier":      tier,
                    "leverage":  lev,
                    "price":     price,
                    "sl_price":  sl_price,
                    "tp1_price": tp1_price,
                    "tp2_price": tp2_price,
                    "be_price":  be_price,
                    "sl_dist":   round(sl_dist, 8),
                    "j15m":      round(j15m,  1),
                    "j1h":       round(j1h,   1),
                    "rsi15m":    round(rsi15m, 1),
                    "ask_pct":   round(ask_pct, 1),
                    "bid_pct":   round(bid_pct, 1),
                    "adx":       round(adx1h, 1),
                    "trend":     trend,
                    "session":   session,
                    "atr15m":    round(atr15m, 8),
                }
                new_alerts.append(alert)
                log.info(f"[ALERT] {symbol} {direction} {tier} {lev}x @ {price}")

        except Exception as e:
            log.error(f"[SCAN] {symbol} error: {e}", exc_info=True)

    return new_alerts


async def scan_pair_fast(client: MexcClient, symbol: str) -> dict:
    """Single-pair data fetch for overlay fast-poll (/api/pair/{symbol})."""
    try:
        candles_15m, candles_1h, book, price = await _fetch_pair_data(client, symbol)
        if not price:
            return {"symbol": symbol, "price": None}
        _, _, j15m = _compute_kdj(candles_15m)
        _, _, j1h  = _compute_kdj(candles_1h)
        rsi15m     = _compute_rsi(candles_15m)
        adx1h      = _compute_adx(candles_1h)
        atr15m     = _compute_atr(candles_15m)
        trend      = _trend_from_ma(price, candles_15m, candles_1h, adx1h)
        bid_pct, ask_pct = _depth_pcts(book)
        return {
            "symbol":  symbol,
            "price":   price,
            "j15m":    round(j15m,   1),
            "j1h":     round(j1h,    1),
            "rsi15m":  round(rsi15m, 1),
            "adx1h":   round(adx1h,  1),
            "atr15m":  round(atr15m, 8),
            "bid_pct": round(bid_pct, 1),
            "ask_pct": round(ask_pct, 1),
            "trend":   trend,
        }
    except Exception as e:
        log.error(f"[FAST] {symbol}: {e}")
        return {"symbol": symbol, "price": None}
