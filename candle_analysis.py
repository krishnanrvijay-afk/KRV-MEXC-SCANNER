import requests, time
from datetime import datetime, timezone

BASE = (
  "https://contract.mexc.com"
  "/api/v1/contract/kline")

def fetch(symbol, interval,
          start, end):
    time.sleep(0.5)
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
          "c": float(
              raw["close"][i]),
        })
    return sorted(
        out, key=lambda x: x["t"])

def fmt_et(ts):
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M:%S")

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace(
                '+00','')
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

def analyze(symbol, direction,
            entry, open_ts,
            close_ts, margin=5000,
            lev=5):
    sz = (margin * lev) / entry
    start = open_ts - 120
    end = close_ts + 120
    candles = fetch(
        symbol, "Min1",
        start, end)

    peak_pnl = 0.0
    peak_ts = None
    decay_threshold = 0.80
    decay_fired_ts = None
    decay_fired_pnl = None

    print(f"\n{'='*75}")
    print(f"  {symbol} {direction}"
          f"  entry={entry}"
          f"  open={fmt_et(open_ts)}"
          f"  close={fmt_et(close_ts)}")
    print(f"{'='*75}")
    print(f"  {'TIME':>10}"
          f"  {'CLOSE':>10}"
          f"  {'PNL':>10}"
          f"  {'PEAK':>10}"
          f"  {'DECAY%':>8}"
          f"  NOTE")
    print(f"  {'-'*65}")

    for c in candles:
        if c["t"] < open_ts - 60:
            continue
        if c["t"] > close_ts + 120:
            break

        if direction == "SHORT":
            cpnl = round(
                (entry - c["c"])
                * sz, 2)
        else:
            cpnl = round(
                (c["c"] - entry)
                * sz, 2)

        if cpnl > peak_pnl:
            peak_pnl = cpnl
            peak_ts = c["t"]

        decay_pct = 0.0
        if peak_pnl > 0:
            decay_pct = round(
                (1 - cpnl /
                 peak_pnl)
                * 100, 1)

        fired = ""
        if (peak_pnl > 0
                and cpnl <
                peak_pnl *
                decay_threshold
                and decay_fired_ts
                is None):
            decay_fired_ts = c["t"]
            decay_fired_pnl = cpnl
            fired = "★ 20% DECAY"

        note = ""
        if abs(c["t"] -
               open_ts) < 90:
            note = "ENTRY"
        elif abs(c["t"] -
                 close_ts) < 90:
            note = "EXIT"
        elif c["t"] == peak_ts:
            note = "PEAK"

        if fired:
            note = fired

        print(
            f"  {fmt_et(c['t']):>10}"
            f"  {c['c']:10.4f}"
            f"  {cpnl:10.2f}"
            f"  {peak_pnl:10.2f}"
            f"  {decay_pct:7.1f}%"
            f"  {note}")

    print(f"\n  SUMMARY:")
    if peak_ts:
        print(f"  Peak PnL:"
              f" ${peak_pnl:.2f}"
              f" at"
              f" {fmt_et(peak_ts)}")
    if decay_fired_ts:
        print(f"  20% decay"
              f" breached at:"
              f" {fmt_et(decay_fired_ts)}"
              f" PnL="
              f"${decay_fired_pnl:.2f}")
        gap = (decay_fired_ts
               - peak_ts) // 60
        print(f"  Gap from peak"
              f" to decay fire:"
              f" {gap} minutes")
    else:
        print(f"  20% decay"
              f" never breached"
              f" in window")

# AVAX SHORT
analyze(
    "AVAX_USDT", "SHORT",
    6.777,
    ts("2026-07-11 15:26:10+00"),
    ts("2026-07-11 15:43:04+00"))

# LINK SHORT
analyze(
    "LINK_USDT", "SHORT",
    8.081,
    ts("2026-07-11 15:31:18+00"),
    ts("2026-07-11 15:42:32+00"))

print("\nDone.")
