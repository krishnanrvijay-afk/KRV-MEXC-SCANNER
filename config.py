import os
from datetime import datetime, timezone

# MEXC perpetual futures — symbols use _USDT suffix
PAIRS = [
    "ZEC_USDT", "SOL_USDT", "BTC_USDT", "ETH_USDT", "XRP_USDT",
    "DOGE_USDT", "SUI_USDT", "NEAR_USDT", "AVAX_USDT", "ARB_USDT",
]

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

SCAN_INTERVAL_SECONDS  = 30
PRICE_INTERVAL_SECONDS = 8
PAPER_MODE             = os.environ.get("PAPER_MODE", "true").lower() == "true"
LIVE_MANUAL_ENTRY_ONLY = os.environ.get("LIVE_MANUAL_ENTRY_ONLY", "true").lower() == "true"

# ── Four hard gates ────────────────────────────────────────────────────────────
J15M_SHORT_GATE  = 80
J15M_LONG_GATE   = 20
J1H_SHORT_MIN    = 60
J1H_LONG_MAX     = 40
RSI15M_SHORT_MIN = 65
RSI15M_LONG_MAX  = 35
DEPTH_GATE_PCT   = 60   # ask%>=60 SHORT / bid%>=60 LONG

# ── Signal tiers by ADX ────────────────────────────────────────────────────────
LEVERAGE_HIGH = 10   # ADX >= 50 — HIGH PROB
LEVERAGE_MID  = 7    # ADX 25-49 — STRONG
LEVERAGE_LOW  = 5    # ADX < 25  — REGULAR

ATR_SL_MULTIPLIER = 1.0
TP1_R = 1.0
TP2_R = 1.5

MARGIN_PER_TRADE = 2000.0
MARGIN_HARD_CAP  = 25000.0

COOLDOWN_SECONDS      = 1800
CONSECUTIVE_LOSS_STOP = 3
DAILY_LOSS_LIMIT      = -500.0
ADX_FADE_MAX          = 60

# ── Minimum SL distance per symbol ────────────────────────────────────────────
MIN_SL_PCT: dict = {
    "ZEC_USDT":  0.030,   # 3% minimum
}
MIN_SL_PCT_DEFAULT = 0.0   # all others: ATR-only, no floor

# ── Session definitions (EST = UTC-5) ─────────────────────────────────────────
# EU: 03:00-08:00 EST  =  08:00-13:00 UTC
# EU/US overlap: 08:00-12:00 EST  =  13:00-17:00 UTC
# US: 12:00-17:00 EST  =  17:00-22:00 UTC
# Asia: 17:00-03:00 EST  =  22:00-08:00 UTC
