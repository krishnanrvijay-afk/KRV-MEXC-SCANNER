import requests
from datetime import datetime, timezone

BASE = (
  "https://contract.mexc.com"
  "/api/v1/contract/kline")

def fetch(symbol, interval, start, end):
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
        raise ValueError(str(d)[:80])
    raw = d["data"]
    out = []
    for i in range(len(raw["time"])):
        out.append({
          "t": int(raw["time"][i]),
          "o": float(raw["open"][i]),
          "h": float(raw["high"][i]),
          "l": float(raw["low"][i]),
          "c": float(raw["close"][i])
        })
    return sorted(out, key=lambda x: x["t"])

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M:%S")

def pnl(entry, price, direction, margin=5000, lev=5):
    sz = (margin * lev) / entry
    if direction == "LONG":
        return round((price - entry) * sz, 2)
    return round((entry - price) * sz, 2)

def analyze(label, symbol, direction, open_ts,
            close_ts, entry_px, be_confirm_px, duration_s):
    candles = fetch(
        symbol, "Min1",
        open_ts - 120,
        open_ts + 300)

    trade_c = [c for c in candles
        if c["t"] >= open_ts - 30
        and c["t"] <= open_ts + 180]

    print(f"\n{'='*64}")
    print(f"  {label}")
    print(f"  {symbol} {direction}  dur={duration_s}s")
    print(f"  entry={entry_px}  be_confirm={be_confirm_px}")
    print(f"{'='*64}")
    print(f"  {'TIME':>8}  "
          f"{'O':>10}  "
          f"{'H':>10}  "
          f"{'L':>10}  "
          f"{'C':>10}  "
          f"{'PNL_HI':>8}  "
          f"{'PNL_LO':>8}  "
          f"NOTE")
    print(f"  {'-'*76}")

    if not trade_c:
        print(f"  no candles — "
              f"window {fmt(open_ts-120)}"
              f" to {fmt(open_ts+300)}")
        return

    for c in trade_c:
        p_hi = pnl(entry_px, c["h"], direction)
        p_lo = pnl(entry_px, c["l"], direction)

        note = ""
        if abs(c["t"] - open_ts) < 90:
            note = "ENTRY WINDOW"
        if direction == "LONG":
            if c["l"] <= entry_px:
                note += " CR_FIRES"
            if c["l"] <= be_confirm_px:
                note += " BELOW_CONFIRM"
        else:
            if c["h"] >= entry_px:
                note += " CR_FIRES"
            if c["h"] >= be_confirm_px:
                note += " ABOVE_CONFIRM"

        print(f"  {fmt(c['t']):>8}"
              f"  {c['o']:10.5f}"
              f"  {c['h']:10.5f}"
              f"  {c['l']:10.5f}"
              f"  {c['c']:10.5f}"
              f"  {p_hi:8.2f}"
              f"  {p_lo:8.2f}"
              f"  {note}")

def ts(y, mo, d, h, mi, s=0):
    return int(datetime(
        y, mo, d, h, mi, s,
        tzinfo=timezone.utc
    ).timestamp())

TRADES = [
    # @107 SHORT 18s -$19
    # 09:31 AM ET = 13:31 UTC
    ("@107 SHORT 18s -$19",
     "HYPE_USDT", "SHORT",
     ts(2026,7,2,13,31,0),
     ts(2026,7,2,13,31,18),
     65.4705, 65.405029, 18),

    # SOL LONG 4s -$9
    # 09:33 AM ET = 13:33 UTC
    ("SOL LONG 4s -$9",
     "SOL_USDT", "LONG",
     ts(2026,7,2,13,33,0),
     ts(2026,7,2,13,33,4),
     81.2895, 81.370790, 4),

    # @107 SHORT 4s -$4
    # 10:20 AM ET = 14:20 UTC
    ("@107 SHORT 4s -$4",
     "HYPE_USDT", "SHORT",
     ts(2026,7,2,14,20,0),
     ts(2026,7,2,14,20,4),
     66.065, 65.998935, 4),

    # XRP_USDT SHORT 7s $0
    # 09:57 AM ET = 13:57 UTC
    ("XRP_USDT SHORT 7s $0",
     "XRP_USDT", "SHORT",
     ts(2026,7,2,13,57,0),
     ts(2026,7,2,13,57,7),
     1.1042, 1.103096, 7),

    # ETH SHORT 6s -$15
    # 10:33 AM ET = 14:33 UTC
    ("ETH SHORT 6s -$15",
     "ETH_USDT", "SHORT",
     ts(2026,7,2,14,33,0),
     ts(2026,7,2,14,33,6),
     1702.25, 1700.5478, 6),

    # ADA LONG 6s -$1
    # 11:21 AM ET = 15:21 UTC
    ("ADA LONG 6s -$1",
     "ADA_USDT", "LONG",
     ts(2026,7,2,15,21,0),
     ts(2026,7,2,15,21,6),
     0.159365, 0.159524, 6),
]

print("US session CONFIRM_REVERSAL forensic — entry_price fix")
print(f"{len(TRADES)} trades\n")

for t in TRADES:
    try:
        analyze(*t)
    except Exception as e:
        print(f"\n{t[0]}: ERROR {e}")

print("\nDone.")
