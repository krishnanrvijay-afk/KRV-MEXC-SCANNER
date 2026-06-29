import csv
import requests
from datetime import datetime, timezone

SYMBOL = "WIF_USDT"
BASE = "https://contract.mexc.com/api/v1/contract/kline"

def fetch_klines(symbol, interval, start_ts, end_ts):
    """Fetch candles from MEXC futures API.
    interval: Min15 or Min60
    start_ts / end_ts: Unix seconds"""
    url = f"{BASE}/{symbol}"
    params = {
        "interval": interval,
        "start": start_ts,
        "end": end_ts,
    }
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise ValueError(f"API error: {data}")
    d = data["data"]
    candles = []
    for i in range(len(d["time"])):
        candles.append({
            "t": d["time"][i],
            "o": float(d["open"][i]),
            "h": float(d["high"][i]),
            "l": float(d["low"][i]),
            "c": float(d["close"][i]),
        })
    return sorted(candles, key=lambda x: x["t"])

def calc_kdj(candles, n=9):
    K, D = 50.0, 50.0
    result = []
    for i, c in enumerate(candles):
        window = candles[max(0, i-n+1):i+1]
        hi = max(x["h"] for x in window)
        lo = min(x["l"] for x in window)
        rng = hi - lo
        rsv = 50.0 if rng < 1e-10 else (c["c"] - lo) / rng * 100
        K = (2/3) * K + (1/3) * rsv
        D = (2/3) * D + (1/3) * K
        J = 3*K - 2*D
        result.append({
            "K": round(K, 2),
            "D": round(D, 2),
            "J": round(J, 2)
        })
    return result

def calc_pnl(entry, close, direction, margin=5000, lev=5):
    size = (margin * lev) / entry
    if direction == "LONG":
        return round((close - entry) * size, 2)
    else:
        return round((entry - close) * size, 2)

def zone(j):
    if j < 30:  return "BEARISH"
    if j < 70:  return "UNDECIDED"
    return "BULLISH"

def fmt_ts(ts):
    return datetime.fromtimestamp(ts,
        tz=timezone.utc).strftime("%H:%M")

def print_table(title, candles, kdj15, kdj1h_map,
                trade, entry_ts, exit_ts, csv_path):
    print()
    print("=" * 72)
    print(f"  {title}")
    print(f"  Entry {trade['entry']:.5f} | "
          f"Exit {trade['exit']:.5f} | "
          f"Dir {trade['dir']}")
    print("=" * 72)
    print(f"{'TIME':>6}  {'PRICE':>8}  "
          f"{'J15M':>7}  {'ZONE15':>9}  "
          f"{'J1H':>6}  {'ZONE1H':>9}  "
          f"{'PnL':>8}  {'STATUS'}")
    print("-" * 72)

    prev_zone15 = None
    csv_rows = []
    for i, c in enumerate(candles):
        t = c["t"]
        if t < entry_ts - 30*60:
            continue
        if t > exit_ts + 15*60:
            break

        j15 = kdj15[i]["J"]
        j1h = kdj1h_map.get(
            (t // 3600) * 3600, None)
        z15 = zone(j15)
        z1h = zone(j1h) if j1h is not None else ""
        pnl = calc_pnl(
            trade["entry"], c["c"],
            trade["dir"]) if t >= entry_ts else None

        # Detect zone transitions
        csv_status = ""
        txt_status = ""
        if prev_zone15 and zone(j15) != prev_zone15:
            csv_status = f"ZONE_CROSS:{prev_zone15}->{zone(j15)}"
            txt_status = f"<-- ZONE CROSS {prev_zone15} -> {zone(j15)}"
        if t == entry_ts:
            csv_status = "ENTRY"
            txt_status = "<-- ENTRY"
        if t >= exit_ts and t < exit_ts + 15*60:
            csv_status = "EXIT"
            txt_status = "<-- EXIT"
        prev_zone15 = zone(j15)

        pnl_str = f"${pnl:+.2f}" if pnl is not None else "      "
        j1h_str = f"{j1h:6.1f}" if j1h is not None else "   —  "
        z1h_pad = z1h.ljust(9) if z1h else "   —     "
        z15_pad = z15.ljust(9)

        print(f"{fmt_ts(t):>6}  "
              f"{c['c']:8.5f}  "
              f"{j15:7.1f}  "
              f"{z15_pad:>9}  "
              f"{j1h_str}  "
              f"{z1h_pad:>9}  "
              f"{pnl_str:>8}  "
              f"{txt_status}")

        csv_rows.append({
            "time_utc":   fmt_ts(t),
            "price":      f"{c['c']:.5f}",
            "j15m":       f"{j15:.2f}",
            "zone15":     z15,
            "j1h":        f"{j1h:.2f}" if j1h is not None else "",
            "zone1h":     z1h,
            "pnl_dollars": f"{pnl:.2f}" if pnl is not None else "",
            "status":     csv_status,
        })

    print("-" * 72)
    print()

    # Write CSV
    fieldnames = ["time_utc", "price", "j15m", "zone15",
                  "j1h", "zone1h", "pnl_dollars", "status"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    return len(csv_rows)

if __name__ == "__main__":

    # -- TRADE DEFINITIONS --
    WINNER = {
        "dir": "LONG",
        "entry": 0.17500,
        "exit":  0.18340,
        "entry_ts": int(datetime(
            2026,6,29,5,17,14,
            tzinfo=timezone.utc).timestamp()),
        "exit_ts": int(datetime(
            2026,6,29,10,3,44,
            tzinfo=timezone.utc).timestamp()),
    }
    LOSER = {
        "dir": "LONG",
        "entry": 0.18040,
        "exit":  0.17640,
        "entry_ts": int(datetime(
            2026,6,29,14,6,0,
            tzinfo=timezone.utc).timestamp()),
        "exit_ts": int(datetime(
            2026,6,29,15,5,0,
            tzinfo=timezone.utc).timestamp()),
    }

    print("Fetching WIF_USDT candles from MEXC...")

    w15 = fetch_klines(
        SYMBOL, "Min15",
        WINNER["entry_ts"] - 3*3600,
        WINNER["exit_ts"] + 3600)

    l15 = fetch_klines(
        SYMBOL, "Min15",
        LOSER["entry_ts"] - 3*3600,
        LOSER["exit_ts"] + 3600)

    h1 = fetch_klines(
        SYMBOL, "Min60",
        WINNER["entry_ts"] - 24*3600,
        LOSER["exit_ts"] + 3600)

    print(f"Fetched {len(w15)} x 15m candles (winner)")
    print(f"Fetched {len(l15)} x 15m candles (loser)")
    print(f"Fetched {len(h1)} x 1h candles")

    kdj_w15 = calc_kdj(w15)
    kdj_l15 = calc_kdj(l15)
    kdj_h1  = calc_kdj(h1)

    h1_map = {
        c["t"]: kdj_h1[i]["J"]
        for i, c in enumerate(h1)
    }

    n_winner = print_table(
        "ASIA WINNER +$1,200 — J15M JOURNEY",
        w15, kdj_w15, h1_map,
        WINNER,
        WINNER["entry_ts"],
        WINNER["exit_ts"],
        "winner_candles.csv")

    n_loser = print_table(
        "US LOSER -$554 — J15M JOURNEY",
        l15, kdj_l15, h1_map,
        LOSER,
        LOSER["entry_ts"],
        LOSER["exit_ts"],
        "loser_candles.csv")

    print(f"Wrote winner_candles.csv — {n_winner} rows")
    print(f"Wrote loser_candles.csv — {n_loser} rows")

    print("Zone definitions:")
    print("  BEARISH   = J < 30")
    print("  UNDECIDED = J 30 - 70")
    print("  BULLISH   = J > 70")
    print()
