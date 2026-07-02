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

def calc_kdj(candles, n=9):
    K, D = 50.0, 50.0
    result = []
    for i, c in enumerate(candles):
        w = candles[max(0, i-n+1):i+1]
        hi = max(x["h"] for x in w)
        lo = min(x["l"] for x in w)
        rng = hi - lo
        rsv = ((c["c"]-lo)/rng*100
               if rng > 0 else 50.0)
        K = (2/3)*K + (1/3)*rsv
        D = (2/3)*D + (1/3)*K
        result.append(round(3*K-2*D, 2))
    return result

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M")

def pnl(entry, price, margin=5000, lev=5):
    sz = (margin * lev) / entry
    return round((price - entry) * sz, 2)

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace('+00', '')
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

# ZEC HL LONG
# Entry:  436.4050
# Exit:   442.0900  +$325.67
# J1H at entry: 39.2
# J15M at entry: 19.5
# Duration: 2h 15m = 8100s
# Open:  ~12:45 PM ET = 16:45 UTC
# Close: ~3:00 PM ET  = 19:00 UTC

ENTRY_PX = 436.4050
EXIT_PX = 442.0900
ENTRY_TS = ts("2026-07-02 16:45:00+00")
EXIT_TS = ts("2026-07-02 19:00:00+00")
AFTER_TS = ts("2026-07-02 20:00:00+00")
SYMBOL = "ZEC_USDT"

print("Fetching J1H candles...")
c1h_warm = fetch(SYMBOL, "Min60",
    ENTRY_TS - 7200,
    AFTER_TS + 3600)
j1h_vals = calc_kdj(c1h_warm)
j1h_map = {c["t"]: j1h_vals[i]
    for i, c in enumerate(c1h_warm)}

def get_j1h(t):
    bucket = (t // 3600) * 3600
    for d in [0, -3600, 3600]:
        if bucket+d in j1h_map:
            return j1h_map[bucket+d]
    return None

print("Fetching Min1 candles...")
c1 = fetch(SYMBOL, "Min1",
    ENTRY_TS - 60,
    AFTER_TS + 60)

trade_c = [c for c in c1
    if c["t"] >= ENTRY_TS - 30
    and c["t"] <= AFTER_TS]

print(f"\n{'='*80}")
print(f"  ZEC LONG — SIGNAL EXHAUSTION FORENSIC")
print(f"  Entry: {ENTRY_PX}  "
      f"Exit: {EXIT_PX}  "
      f"+$325.67")
print(f"  J1H at entry: 39.2  "
      f"J15M at entry: 19.5")
print(f"{'='*80}")
print(f"  {'TIME':>5}  "
      f"{'PRICE':>9}  "
      f"{'J1H':>7}  "
      f"{'J1H_PK':>7}  "
      f"{'DECAY':>7}  "
      f"{'PNL':>9}  "
      f"NOTE")
print(f"  {'-'*72}")

j1h_peak = None
se_fired_ts = None
se_fired_pnl = None
post_exit_high = None
post_exit_low = None
in_trade = True

for c in trade_c:
    j1h = get_j1h(c["t"])
    cpnl = pnl(ENTRY_PX, c["c"])
    p_hi = pnl(ENTRY_PX, c["h"])
    p_lo = pnl(ENTRY_PX, c["l"])

    if (in_trade and
            j1h is not None and
            cpnl > 0):
        if (j1h_peak is None or
                j1h > j1h_peak):
            j1h_peak = j1h

    decay = 0
    if (j1h_peak is not None
            and j1h is not None):
        decay = j1h_peak - j1h

    se_would_fire = (
        j1h_peak is not None and
        decay >= 10 and
        cpnl > 0 and
        se_fired_ts is None)

    if se_would_fire:
        se_fired_ts = c["t"]
        se_fired_pnl = cpnl

    is_after_exit = (
        c["t"] > EXIT_TS)
    if is_after_exit:
        in_trade = False
        if (post_exit_high is None
                or c["h"] >
                post_exit_high):
            post_exit_high = c["h"]
        if (post_exit_low is None
                or c["l"] <
                post_exit_low):
            post_exit_low = c["l"]

    note = ""
    if abs(c["t"]-ENTRY_TS) < 90:
        note = "ENTRY"
    if abs(c["t"]-EXIT_TS) < 90:
        note = "★ SE EXIT"
    if se_would_fire:
        note = "★ SE FIRES"
    if is_after_exit and not note:
        note = "POST-EXIT"

    print(f"  {fmt(c['t']):>5}"
          f"  {c['c']:9.3f}"
          f"  {j1h or 0:7.1f}"
          f"  {j1h_peak or 0:7.1f}"
          f"  {decay:7.1f}"
          f"  {cpnl:9.2f}"
          f"  {note}")

print(f"\n{'='*80}")
print(f"  SIGNAL EXHAUSTION SEQUENCE")
print(f"{'='*80}")
print(f"  Entry J1H:      39.2")
if j1h_peak:
    print(f"  J1H peak:       "
          f"{j1h_peak:.1f}")
if se_fired_ts:
    print(f"  SE fired at:    "
          f"{fmt(se_fired_ts)}"
          f" PnL={se_fired_pnl:+.2f}")
print(f"  Actual exit:    "
      f"{fmt(EXIT_TS)}"
      f" price={EXIT_PX}"
      f" PnL=+$325.67")
print(f"\n  AFTER EXIT (60 min):")
if post_exit_high:
    post_hi_pnl = pnl(ENTRY_PX, post_exit_high)
    print(f"  Price high:     "
          f"{post_exit_high:.3f}"
          f" (would have been"
          f" +${post_hi_pnl:.2f})")
if post_exit_low:
    post_lo_pnl = pnl(ENTRY_PX, post_exit_low)
    print(f"  Price low:      "
          f"{post_exit_low:.3f}"
          f" (would have been"
          f" +${post_lo_pnl:.2f})")

print("\nDone.")
