import requests, time
from datetime import datetime, timezone

BASE = (
    "https://contract.mexc.com"
    "/api/v1/contract/kline")

def fetch(symbol, interval, start, end):
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
        raise ValueError(str(d)[:80])
    raw = d["data"]
    out = []
    for i in range(len(raw["time"])):
        out.append({
            "t": int(raw["time"][i]),
            "o": float(raw["open"][i]),
            "h": float(raw["high"][i]),
            "l": float(raw["low"][i]),
            "c": float(raw["close"][i]),
        })
    return sorted(out, key=lambda x: x["t"])

def fmt_et(ts):
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M:%S")

def pnl_short(entry, price, margin=5000, lev=5):
    sz = (margin * lev) / entry
    return round((entry - price) * sz, 2)

def r_val_short(entry, price, sl, margin=5000, lev=5):
    sz = (margin * lev) / entry
    risk = abs(sl - entry) * sz
    if risk == 0:
        return 0
    return round((entry - price) * sz / risk, 3)

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace('+00', '')
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

def simulate_3l(label, symbol,
        entry, sl, tp1,
        open_ts, close_ts,
        exit_reason, exit_pnl,
        mae_r, mfe_r):

    print(f"\n{'='*95}")
    print(f"  {label}")
    print(f"  entry={entry}  SL={sl}  TP1={tp1}")
    print(f"  open={fmt_et(open_ts)} ET  close={fmt_et(close_ts)} ET")
    print(f"  exit={exit_reason}  pnl={exit_pnl:+.2f}  mae={mae_r}R  mfe={mfe_r}R")
    print(f"{'='*95}")

    candles = fetch(symbol, "Min1", open_ts - 300, close_ts + 900)

    if not candles:
        print("  no candle data")
        return

    print(f"\n  {'TIME':>10}"
          f"  {'HIGH':>9}"
          f"  {'LOW':>9}"
          f"  {'CLOSE':>9}"
          f"  {'PNL':>9}"
          f"  {'R':>6}"
          f"  {'AGE':>5}"
          f"  {'BOUNDARY':>10}"
          f"  {'3L_SIG':>8}"
          f"  NOTE")
    print(f"  {'-'*105}")

    boundary_prices = []
    last_candle_ts = 0
    triggered = None
    triggered_pnl = None
    triggered_r = None
    first_profitable_ts = None

    for c in candles:
        if c["t"] < open_ts:
            continue
        if c["t"] > close_ts + 600:
            break

        age = c["t"] - open_ts
        cpnl = pnl_short(entry, c["c"])
        cr = r_val_short(entry, c["c"], sl)

        if cpnl > 0 and first_profitable_ts is None:
            first_profitable_ts = c["t"]

        now_candle = (c["t"] // 60) * 60
        sig = "---"

        if now_candle > last_candle_ts:
            boundary_prices.append(c["c"])
            if len(boundary_prices) > 3:
                boundary_prices = boundary_prices[-3:]
            last_candle_ts = now_candle

            if (age >= 180
                    and cpnl <= 0
                    and len(boundary_prices) >= 3
                    and triggered is None):
                b1 = boundary_prices[-3]
                b2 = boundary_prices[-2]
                b3 = boundary_prices[-1]
                if b3 > b2 > b1:
                    triggered = c["t"]
                    triggered_pnl = cpnl
                    triggered_r = cr
                    sig = "★ FIRE"
                else:
                    sig = "no"
            elif triggered is None:
                sig = "warming"

        note = ""
        if abs(c["t"] - open_ts) < 90:
            note = "ENTRY"
        elif abs(c["t"] - close_ts) < 90:
            note = f"★ {exit_reason}"
        elif c["t"] > close_ts:
            note = "post-exit"
        elif triggered and c["t"] >= triggered:
            note = "3L would exit"
        elif first_profitable_ts and c["t"] >= first_profitable_ts and not note:
            note = "PROFITABLE"

        bp_str = (
            f"{boundary_prices[-1]:.5f}"
            if boundary_prices else "---")

        print(
            f"  {fmt_et(c['t']):>10}"
            f"  {c['h']:9.5f}"
            f"  {c['l']:9.5f}"
            f"  {c['c']:9.5f}"
            f"  {cpnl:9.2f}"
            f"  {cr:6.3f}"
            f"  {age:5}s"
            f"  {bp_str:>10}"
            f"  {sig:>8}"
            f"  {note}")

    print(f"\n  SUMMARY:")
    print(f"  Actual exit: {exit_reason}  pnl={exit_pnl:+.2f}  at {fmt_et(close_ts)}")

    if triggered:
        impact = exit_pnl - triggered_pnl
        print(f"  3L_HIGHER_LOW would fire at: {fmt_et(triggered)} ET")
        print(f"  PnL at 3L exit: {triggered_pnl:.2f} ({triggered_r:.3f}R)")
        if triggered_pnl < 0:
            print(f"  ★ CUTS A LOSER — saves ${abs(triggered_pnl):.2f} vs holding")
        else:
            print(f"  ⚠ CUTS A WINNER early at +${triggered_pnl:.2f} vs actual {exit_pnl:+.2f}")
    else:
        print(f"  3L_HIGHER_LOW did NOT trigger")
        if first_profitable_ts:
            age_to_profit = first_profitable_ts - open_ts
            print(f"  Trade went profitable at {fmt_et(first_profitable_ts)} ET"
                  f" (age {age_to_profit}s) before 3L could arm")

TRADES = [
    ("ARB_USDT SHORT 3C_LOWER_LOW +$102",
     "ARB_USDT",
     0.07874, 0.079941, 0.077579,
     ts("2026-07-07 07:31:13+00"),
     ts("2026-07-07 07:40:06+00"),
     "3C_LOWER_LOW", 101.6,
     -0.02, 0.31),

    ("HYPE_USDT SHORT PEAK_DECAY_20 +$76",
     "HYPE_USDT",
     70.852, 71.772063, 69.929937,
     ts("2026-07-07 07:38:02+00"),
     ts("2026-07-07 07:55:11+00"),
     "PEAK_DECAY_20", 75.51,
     -0.15, 0.31),
]

print("3L_HIGHER_LOW INTERFERENCE CHECK")
print("2 overnight SHORT winners\n")

for t in TRADES:
    try:
        simulate_3l(*t)
    except Exception as e:
        print(f"\n{t[0]}: ERROR {e}")

print("\nAll done.")
