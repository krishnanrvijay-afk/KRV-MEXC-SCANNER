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

def analyze(label, symbol, direction, open_ts, entry_px, duration_s):
    candles = fetch(
        symbol, "Min1",
        open_ts - 60,
        open_ts + 180)

    trade_c = [c for c in candles
        if c["t"] >= open_ts - 30
        and c["t"] <= open_ts + 120]

    print(f"\n{'='*68}")
    print(f"  {label}")
    print(f"  {symbol} {direction}  dur={duration_s}s  entry={entry_px}")
    print(f"  open={fmt(open_ts)} UTC")
    print(f"{'='*68}")
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
        print(f"  no candles in window")
        return

    for c in trade_c:
        p_hi = pnl(entry_px, c["h"], direction)
        p_lo = pnl(entry_px, c["l"], direction)
        note = ""
        if abs(c["t"] - open_ts) < 90:
            note = "ENTRY WINDOW"
        if direction == "LONG":
            if c["l"] <= entry_px:
                note += " \u26a1CR"
        else:
            if c["h"] >= entry_px:
                note += " \u26a1CR"
        print(f"  {fmt(c['t']):>8}"
              f"  {c['o']:10.5f}"
              f"  {c['h']:10.5f}"
              f"  {c['l']:10.5f}"
              f"  {c['c']:10.5f}"
              f"  {p_hi:8.2f}"
              f"  {p_lo:8.2f}"
              f"  {note}")

def ts(iso):
    return int(datetime.fromisoformat(
        iso.replace('+00', '')
    ).replace(
        tzinfo=timezone.utc
    ).timestamp())

TRADES = [
    ("@107 SHORT 18s -$19",
     "HYPE_USDT", "SHORT",
     ts("2026-07-02 13:30:48+00"),
     65.391, 18),

    ("SOL LONG 4s -$9",
     "SOL_USDT", "LONG",
     ts("2026-07-02 13:33:51+00"),
     81.4425, 4),

    ("XRP_USDT SHORT 7s $0",
     "XRP_USDT", "SHORT",
     ts("2026-07-02 13:57:34+00"),
     1.1027, 7),

    ("@107 SHORT 4s -$4",
     "HYPE_USDT", "SHORT",
     ts("2026-07-02 14:20:07+00"),
     65.933, 4),

    ("LINK_USDT SHORT 5s $0",
     "LINK_USDT", "SHORT",
     ts("2026-07-02 14:28:16+00"),
     7.849, 5),

    ("ETH SHORT 6s -$15",
     "ETH_USDT", "SHORT",
     ts("2026-07-02 14:33:17+00"),
     1701.35, 6),

    ("ADA LONG 6s -$1",
     "ADA_USDT", "LONG",
     ts("2026-07-02 15:21:34+00"),
     0.159685, 6),

    ("XRP_USDT LONG 4s -$7",
     "XRP_USDT", "LONG",
     ts("2026-07-02 15:22:01+00"),
     1.0911, 4),

    ("DOGE_USDT LONG 7s $0",
     "DOGE_USDT", "LONG",
     ts("2026-07-02 15:28:38+00"),
     0.07452, 7),

    ("WIF_USDT LONG 0s -$29",
     "WIF_USDT", "LONG",
     ts("2026-07-02 15:35:46+00"),
     0.1727, 0),

    ("HYPE_USDT LONG 1s -$8",
     "HYPE_USDT", "LONG",
     ts("2026-07-02 15:35:46+00"),
     65.667, 1),
]

print("CONFIRM_REVERSAL forensic — exact DB timestamps")
print(f"{len(TRADES)} trades\n")

for t in TRADES:
    try:
        analyze(*t)
    except Exception as e:
        print(f"\n{t[0]}: ERROR {e}")

print("\nDone.")
