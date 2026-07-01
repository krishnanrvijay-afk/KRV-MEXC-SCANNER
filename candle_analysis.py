import requests, csv
from datetime import datetime, timezone

BASE = "https://contract.mexc.com/api/v1/contract/kline"

def fetch_klines(symbol, interval,
                 start_ts, end_ts):
    r = requests.get(
        f"{BASE}/{symbol}",
        params={"interval": interval,
                "start": start_ts,
                "end": end_ts},
        timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise ValueError(str(d)[:120])
    raw = d["data"]
    out = []
    for i in range(len(raw["time"])):
        out.append({
            "t": int(raw["time"][i]),
            "h": float(raw["high"][i]),
            "l": float(raw["low"][i]),
            "c": float(raw["close"][i]),
        })
    return sorted(out, key=lambda x: x["t"])

def calc_kdj(candles, n=9):
    K, D = 50.0, 50.0
    result = []
    for i, c in enumerate(candles):
        w = candles[max(0,i-n+1):i+1]
        hi = max(x["h"] for x in w)
        lo = min(x["l"] for x in w)
        rng = hi - lo
        rsv = (c["c"]-lo)/rng*100 \
            if rng>0 else 50.0
        K = (2/3)*K + (1/3)*rsv
        D = (2/3)*D + (1/3)*K
        result.append(round(3*K-2*D, 2))
    return result

def zone(j):
    if j < 30: return "BEARISH"
    if j < 70: return "UNDECIDED"
    return "BULLISH"

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M")

def analyze(label, symbol, direction,
            entry_ts, close_ts):
    warmup = 3 * 3600
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  {symbol} {direction}")
    print(f"  Entry: {fmt(entry_ts)} UTC  "
          f"Close: {fmt(close_ts)} UTC")
    print(f"{'='*60}")

    c15 = fetch_klines(symbol, "Min15",
        entry_ts-warmup, close_ts+900)
    c1h = fetch_klines(symbol, "Min60",
        entry_ts-6*3600, close_ts+3600)

    j15 = calc_kdj(c15)
    j1h_all = calc_kdj(c1h)

    hmap = {}
    for i,c in enumerate(c1h):
        hmap[c["t"]] = j1h_all[i]
    def gj1h(t):
        h=(t//3600)*3600
        if h in hmap: return hmap[h]
        for d in [-3600,3600]:
            if h+d in hmap:
                return hmap[h+d]
        return None

    entry_c = [(c,j15[i])
               for i,c in enumerate(c15)
               if c["t"]>=entry_ts]
    exit_c  = [(c,j15[i])
               for i,c in enumerate(c15)
               if c["t"]<=close_ts]

    if not entry_c:
        print("  No candles in window")
        return

    j15_in  = entry_c[0][1]
    j15_out = exit_c[-1][1] \
        if exit_c else None
    j1h_in  = gj1h(entry_c[0][0]["t"])
    j1h_out = gj1h(exit_c[-1][0]["t"]) \
        if exit_c else None

    # J1H direction — compare current
    # to 2 hours prior
    j1h_2h_ago = gj1h(
        entry_c[0][0]["t"] - 7200)
    if j1h_in and j1h_2h_ago:
        j1h_chg = j1h_in - j1h_2h_ago
        j1h_dir = (
            "FALLING" if j1h_chg < -5
            else "RISING" if j1h_chg > 5
            else "FLAT")
    else:
        j1h_dir = "UNKNOWN"
        j1h_chg = 0

    print(f"  J15M entry: {j15_in:.1f} "
          f"({zone(j15_in)})")
    print(f"  J1H  entry: "
          f"{j1h_in:.1f} ({zone(j1h_in)})"
          if j1h_in else
          "  J1H  entry: N/A")
    print(f"  J1H  2h ago: "
          f"{j1h_2h_ago:.1f}"
          if j1h_2h_ago else
          "  J1H  2h ago: N/A")
    print(f"  J1H  direction: "
          f"{j1h_dir} "
          f"(chg={j1h_chg:+.1f})")
    print(f"  J15M exit:  "
          f"{j15_out:.1f} ({zone(j15_out)})"
          if j15_out else "")
    print(f"  J1H  exit:  "
          f"{j1h_out:.1f} ({zone(j1h_out)})"
          if j1h_out else "")
    print(f"  GATE VERDICT: "
          f"{'BLOCK' if j1h_dir == 'FALLING' else 'ALLOW'}"
          f" (J1H falling = block LONG)")

# ── TRADE DEFINITIONS ─────────────
# July 1 2026, times in UTC
# All closes at 06:35-06:36 UTC
# Durations: @107=4m LTC_USDT=5m
#            LTC=8m  NEAR_USDT=4m

CLOSE_107  = int(datetime(
    2026,7,1,6,36,0,
    tzinfo=timezone.utc).timestamp())
ENTRY_107  = CLOSE_107 - 240

CLOSE_LTC_MX = int(datetime(
    2026,7,1,6,36,0,
    tzinfo=timezone.utc).timestamp())
ENTRY_LTC_MX = CLOSE_LTC_MX - 300

CLOSE_LTC_HL = int(datetime(
    2026,7,1,6,36,0,
    tzinfo=timezone.utc).timestamp())
ENTRY_LTC_HL = CLOSE_LTC_HL - 480

CLOSE_NEAR = int(datetime(
    2026,7,1,6,35,0,
    tzinfo=timezone.utc).timestamp())
ENTRY_NEAR = CLOSE_NEAR - 240

print("Fetching candles for "
      "4 trades...")

analyze(
    "CASE 1 — @107 LONG ASIA KILL",
    "HYPE_USDT", "LONG",
    ENTRY_107, CLOSE_107)

analyze(
    "CASE 2 — LTC_USDT LONG ASIA KILL",
    "LTC_USDT", "LONG",
    ENTRY_LTC_MX, CLOSE_LTC_MX)

analyze(
    "CASE 3 — LTC LONG ASIA KILL "
    "(HL, using LTC_USDT proxy)",
    "LTC_USDT", "LONG",
    ENTRY_LTC_HL, CLOSE_LTC_HL)

analyze(
    "CASE 4 — NEAR_USDT LONG ASIA KILL",
    "NEAR_USDT", "LONG",
    ENTRY_NEAR, CLOSE_NEAR)

print("\nDone.")
