import requests
from datetime import datetime, timezone

BASE = (
  "https://contract.mexc.com"
  "/api/v1/contract/kline")

def fetch(symbol, interval,
          start, end):
    r = requests.get(
        f"{BASE}/{symbol}",
        params={
          "interval": interval,
          "start": start,
          "end": end},
        timeout=15)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise ValueError(
            str(d)[:80])
    raw = d["data"]
    out = []
    for i in range(
            len(raw["time"])):
        out.append({
          "t": int(raw["time"][i]),
          "h": float(raw["high"][i]),
          "l": float(raw["low"][i]),
          "c": float(raw["close"][i])
        })
    return sorted(
        out, key=lambda x: x["t"])

def calc_kdj(candles, n=9):
    K, D = 50.0, 50.0
    result = []
    for i, c in enumerate(candles):
        w = candles[
            max(0,i-n+1):i+1]
        hi = max(x["h"] for x in w)
        lo = min(x["l"] for x in w)
        rng = hi - lo
        rsv = ((c["c"]-lo)/rng*100
               if rng > 0 else 50.0)
        K = (2/3)*K+(1/3)*rsv
        D = (2/3)*D+(1/3)*K
        result.append(
            round(3*K-2*D, 2))
    return result

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M:%S")

def pnl(entry, price, direction,
        margin=5000, lev=5):
    sz = (margin * lev) / entry
    if direction == "LONG":
        return round(
            (price-entry)*sz, 2)
    return round(
        (entry-price)*sz, 2)

def get_c5m_low(c5m_candles, t):
    # find the last CLOSED 5m
    # candle before timestamp t
    # closed = candle whose end
    # time <= t
    # candle end = c["t"] + 300
    prev = None
    for c in c5m_candles:
        if c["t"] + 300 <= t:
            prev = c
        else:
            break
    return prev["l"] if prev else None

def get_j5m(c5m_candles,
            j5m_vals, t):
    # J5M value of the 5m candle
    # containing timestamp t
    for i, c in enumerate(
            c5m_candles):
        if (c["t"] <= t <
                c["t"] + 300):
            return j5m_vals[i]
    return None

def analyze(label, symbol,
            direction, open_ts,
            close_ts, entry_px,
            be_confirm_px,
            duration_s):
    warmup = 3600
    c1 = fetch(symbol, "Min1",
        open_ts - 60,
        close_ts + 120)
    c5 = fetch(symbol, "Min5",
        open_ts - warmup,
        close_ts + 300)
    j5m_vals = calc_kdj(c5)

    trade_c = [c for c in c1
        if c["t"] >= open_ts - 30
        and c["t"] <= close_ts + 60]

    peak_pnl = 0
    peak_ts = None
    ever_profitable = False
    trail_exit_ts = None
    trail_exit_pnl = None

    print(f"\n{'='*72}")
    print(f"  {label}")
    print(f"  dur={duration_s}s  "
          f"entry={entry_px}")
    print(f"{'='*72}")
    print(f"  {'TIME':>8}  "
          f"{'PnL_hi':>8}  "
          f"{'PnL_c':>8}  "
          f"{'J5M':>7}  "
          f"{'C5M_LOW':>9}  "
          f"NOTE")
    print(f"  {'-'*68}")

    for c in trade_c:
        p_hi = pnl(entry_px,
            c["h"], direction)
        p_lo = pnl(entry_px,
            c["l"], direction)
        p_c = pnl(entry_px,
            c["c"], direction)

        if p_hi > 0:
            ever_profitable = True
        if p_hi > peak_pnl:
            peak_pnl = p_hi
            peak_ts = c["t"]

        c5m_low = get_c5m_low(
            c5, c["t"])
        j5m = get_j5m(
            c5, j5m_vals, c["t"])

        # trail break —
        # price breaks prev 5m low
        # while ever profitable
        trail_broke = (
            ever_profitable and
            c5m_low is not None and
            direction == "LONG" and
            c["l"] < c5m_low and
            trail_exit_ts is None)

        if trail_broke:
            trail_exit_ts = c["t"]
            trail_exit_pnl = p_lo

        note = ""
        if abs(c["t"] -
                open_ts) < 90:
            note = "ENTRY"
        if c["l"] <= be_confirm_px:
            note += " ⚡CR"
        if trail_broke:
            note += " ★TRAIL"

        print(
            f"  {fmt(c['t']):>8}"
            f"  {p_hi:8.2f}"
            f"  {p_c:8.2f}"
            f"  {j5m or 0:7.1f}"
            f"  {c5m_low or 0:9.5f}"
            f"  {note}")

    print(f"\n  Peak: +${peak_pnl:.2f}"
          f" at {fmt(peak_ts)}"
          if peak_ts else
          "\n  No real peak")
    if trail_exit_ts:
        actual = pnl(entry_px,
            be_confirm_px,
            direction)
        saved = (trail_exit_pnl
                 - actual)
        print(
            f"  TRAIL EXIT:"
            f" ~${trail_exit_pnl:.2f}"
            f" at {fmt(trail_exit_ts)}")
        print(
            f"  CR EXIT:   "
            f" ~${actual:.2f}")
        print(
            f"  SAVED:      "
            f"${saved:.2f}")
    else:
        print(
            "  Trail never broke"
            " in candle data")

def ts(y,mo,d,h,mi,s=0):
    return int(datetime(
        y,mo,d,h,mi,s,
        tzinfo=timezone.utc
    ).timestamp())

TRADES = [
    ("NEAR_USDT LONG 649s -$27"
     " mfe=0.19R",
     "NEAR_USDT","LONG",
     ts(2026,7,2,0,9,29),
     ts(2026,7,2,0,20,18),
     1.814, 1.812811, 649),

    ("NEAR_USDT LONG 153s -$15"
     " mfe=0.08R",
     "NEAR_USDT","LONG",
     ts(2026,7,2,0,48,20),
     ts(2026,7,2,0,50,53),
     1.81605, 1.815614, 153),

    ("HYPE_USDT LONG 260s -$28"
     " mfe=0.06R",
     "HYPE_USDT","LONG",
     ts(2026,7,2,1,0,28),
     ts(2026,7,2,1,4,48),
     62.3395, 62.285723, 260),

    ("BTC_USDT LONG 358s -$24"
     " mfe=0.07R",
     "BTC_USDT","LONG",
     ts(2026,7,2,0,55,22),
     ts(2026,7,2,1,1,20),
     59705.6, 59694.635, 358),

    ("HYPE_USDT LONG 84s -$16"
     " mfe=0.01R",
     "HYPE_USDT","LONG",
     ts(2026,7,2,0,22,28),
     ts(2026,7,2,0,23,52),
     62.5075, 62.486924, 84),

    ("DOGE_USDT LONG 110s -$7"
     " mfe=0.11R",
     "DOGE_USDT","LONG",
     ts(2026,7,1,20,49,15),
     ts(2026,7,1,20,51,5),
     0.07279, 0.072763, 110),

    ("HYPE_USDT LONG 43s -$22"
     " mfe=0.09R",
     "HYPE_USDT","LONG",
     ts(2026,7,1,20,50,5),
     ts(2026,7,1,20,50,48),
     62.3395, 62.325763, 43),
]

print("Non-zero MFE CONFIRM_REVERSAL"
      " — J5M + C5M_LOW forensic")
print(f"{len(TRADES)} trades\n")

for t in TRADES:
    try:
        analyze(*t)
    except Exception as e:
        print(f"\n{t[0]}: ERROR {e}")

print("\nDone.")
