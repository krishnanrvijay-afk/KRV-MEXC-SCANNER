import requests
from datetime import datetime, timezone

BASE = "https://contract.mexc.com/api/v1/contract/kline"

def fetch(symbol, interval, start, end):
    r = requests.get(
        f"{BASE}/{symbol}",
        params={"interval": interval,
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

def pnl(entry, price, direction,
        margin=5000, lev=5):
    sz = (margin * lev) / entry
    if direction == "LONG":
        return round((price - entry) * sz, 2)
    return round((entry - price) * sz, 2)

# NEAR_USDT LONG
# Opened: 2026-07-02 00:09:29 UTC
# Closed: 2026-07-02 00:20:18 UTC
# Entry:  1.814
# be_confirm: 1.812811
# Duration: 649s
# MFE: 0.19R  Final PnL: -$27.56

entry_ts = int(datetime(
    2026,7,2,0,9,29,
    tzinfo=timezone.utc).timestamp())
close_ts = int(datetime(
    2026,7,2,0,20,18,
    tzinfo=timezone.utc).timestamp())
entry_px = 1.814
be_confirm = 1.812811
direction = "LONG"

candles = fetch(
    "NEAR_USDT", "Min1",
    entry_ts - 300,
    close_ts + 120)

trade_c = [c for c in candles
    if c["t"] >= entry_ts - 60
    and c["t"] <= close_ts + 60]

print("NEAR_USDT LONG — 649s forensic")
print(f"Entry: {entry_px}  "
      f"BE_confirm: {be_confirm}")
print(f"{'TIME':>8}  {'O':>7}  "
      f"{'H':>7}  {'L':>7}  "
      f"{'C':>7}  "
      f"{'PnL_lo':>8}  "
      f"{'PnL_hi':>8}  "
      f"{'PnL_c':>8}  NOTE")
print("-" * 80)

peak_pnl = 0
peak_time = None

for c in trade_c:
    p_lo = pnl(entry_px, c["l"],
               direction)
    p_hi = pnl(entry_px, c["h"],
               direction)
    p_c  = pnl(entry_px, c["c"],
               direction)

    if p_hi > peak_pnl:
        peak_pnl = p_hi
        peak_time = c["t"]

    note = ""
    if c["t"] < entry_ts:
        note = "PRE-ENTRY"
    elif c["t"] <= entry_ts + 60:
        note = "ENTRY MIN"
    if c["l"] <= be_confirm:
        note += " ⚡CONFIRM_REVERSAL"

    print(f"{fmt(c['t']):>8}  "
          f"{c['o']:7.4f}  "
          f"{c['h']:7.4f}  "
          f"{c['l']:7.4f}  "
          f"{c['c']:7.4f}  "
          f"{p_lo:8.2f}  "
          f"{p_hi:8.2f}  "
          f"{p_c:8.2f}  "
          f"{note}")

print(f"\nPeak PnL: +${peak_pnl:.2f}"
      f" at {fmt(peak_time)}")
print(f"Exit PnL: approx -$27.56")
print(f"Gap: ${peak_pnl + 27.56:.2f}"
      f" given back after peak")
