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

def compute_kdj(candles, n=9):
    K, D = 50.0, 50.0
    result = []
    for i, c in enumerate(candles):
        w = candles[max(0,i-n+1):i+1]
        hi = max(x["h"] for x in w)
        lo = min(x["l"] for x in w)
        rng = hi - lo
        rsv = ((c["c"]-lo)/rng*100
               if rng > 0 else 50.0)
        K = (2/3)*K + (1/3)*rsv
        D = (2/3)*D + (1/3)*K
        result.append(round(3*K-2*D, 2))
    return result

def fmt_et(ts):
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M")

def pnl_long(entry, price, margin=5000, lev=5):
    sz = (margin * lev) / entry
    return round((price - entry) * sz, 2)

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace('+00','')
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

SYMBOL    = "HYPE_USDT"
ENTRY     = 67.3975
SIGNAL_TS = ts("2026-07-09 16:35:00+00")
START     = ts("2026-07-09 15:00:00+00")
END       = ts("2026-07-09 17:00:00+00")

print("Fetching candles...")
c1m  = fetch(SYMBOL, "Min1",  START, END)
c5m  = fetch(SYMBOL, "Min5",  START, END)
c15m = fetch(SYMBOL, "Min15", START, END)

j1m    = compute_kdj(c1m)
j5m_v  = compute_kdj(c5m)
j15m_v = compute_kdj(c15m)

j5m_map = {}
for i, c in enumerate(c5m):
    for o in range(5):
        j5m_map[c["t"]+o*60] = j5m_v[i]

j15m_map = {}
for i, c in enumerate(c15m):
    for o in range(15):
        j15m_map[c["t"]+o*60] = j15m_v[i]

first_both = None
first_j5m  = None
first_j15m = None

print(f"\n{'='*85}")
print(f"  @107 / HYPE_USDT LONG — OPTION A DIAGNOSTIC")
print(f"  Gate: J5M < 20 AND J15M < 20 simultaneously")
print(f"  Signal fired: {fmt_et(SIGNAL_TS)} ET  Entry: {ENTRY}")
print(f"{'='*85}")
print(f"  {'TIME':>5}  {'CLOSE':>9}  {'PNL':>9}  {'J1M':>7}  {'J5M':>7}  {'J15M':>7}  {'J5<20':>6}  {'J15<20':>7}  {'BOTH':>5}  NOTE")
print(f"  {'-'*85}")

for i, c in enumerate(c1m):
    j1  = j1m[i]
    j5  = j5m_map.get(c["t"], 50)
    j15 = j15m_map.get(c["t"], 50)
    cpnl = pnl_long(ENTRY, c["c"])

    j5_ok  = j5  < 20
    j15_ok = j15 < 20
    both   = j5_ok and j15_ok

    if j5_ok and first_j5m is None:
        first_j5m = c["t"]
    if j15_ok and first_j15m is None:
        first_j15m = c["t"]
    if both and first_both is None:
        first_both = c["t"]

    note = ""
    if abs(c["t"]-SIGNAL_TS) < 90:
        note = "★ SIGNAL FIRED"
    elif both:
        note = "⚡ GATE OPEN"
    elif j5_ok and not j15_ok:
        note = "J5M only"
    elif j15_ok and not j5_ok:
        note = "J15M only"

    print(
        f"  {fmt_et(c['t']):>5}"
        f"  {c['c']:9.3f}"
        f"  {cpnl:9.2f}"
        f"  {j1:7.1f}"
        f"  {j5:7.1f}"
        f"  {j15:7.1f}"
        f"  {'YES' if j5_ok else '---':>6}"
        f"  {'YES' if j15_ok else '---':>7}"
        f"  {'✓' if both else ' ':>5}"
        f"  {note}")

print(f"\n{'='*85}")
print(f"  SUMMARY")
print(f"{'='*85}")

if first_j5m:
    lag = (SIGNAL_TS-first_j5m)//60
    print(f"  J5M first < 20: {fmt_et(first_j5m)} ET ({lag}m before signal)")
if first_j15m:
    lag = (SIGNAL_TS-first_j15m)//60
    print(f"  J15M first < 20: {fmt_et(first_j15m)} ET ({lag}m before signal)")
if first_both:
    lag = (SIGNAL_TS-first_both)//60
    print(f"  BOTH first < 20: {fmt_et(first_both)} ET ({lag}m before signal)")
    print(f"  Gate open {lag}m before signal fired")
else:
    print(f"  BOTH never < 20 simultaneously before signal")
    print(f"  J15M was the bottleneck")

print("\nDone.")
