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
          "o": float(raw["open"][i]),
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

entry_ts = int(datetime(
    2026,7,2,0,9,29,
    tzinfo=timezone.utc
).timestamp())
close_ts = int(datetime(
    2026,7,2,0,20,18,
    tzinfo=timezone.utc
).timestamp())
entry_px = 1.814
be_confirm = 1.812811
direction = "LONG"

# Min1 price candles
c1 = fetch("NEAR_USDT", "Min1",
    entry_ts-300, close_ts+120)

# Min15 for J15M KDJ
c15 = fetch("NEAR_USDT", "Min15",
    entry_ts-7200, close_ts+900)
j15_vals = calc_kdj(c15)

# Build J15M lookup by 15m bucket
j15_map = {}
for i, c in enumerate(c15):
    j15_map[c["t"]] = j15_vals[i]

def get_j15m(t):
    # find the Min15 candle that
    # contains timestamp t
    bucket = (t // 900) * 900
    if bucket in j15_map:
        return j15_map[bucket]
    # try adjacent
    for d in [-900, 900, -1800]:
        if bucket+d in j15_map:
            return j15_map[bucket+d]
    return None

trade_c = [c for c in c1
    if c["t"] >= entry_ts-60
    and c["t"] <= close_ts+60]

print("NEAR_USDT LONG — J15M forensic")
print(f"Entry: {entry_px}  "
      f"BE_confirm: {be_confirm}")
print(f"{'TIME':>8}  {'PnL_hi':>8}"
      f"  {'PnL_c':>8}  "
      f"{'J15M':>7}  "
      f"{'PEAK_J15M':>10}  "
      f"{'DECAY':>7}  NOTE")
print("-"*72)

peak_pnl = 0
peak_j15m = None
j15m_se_fire_ts = None
j15m_se_fire_pnl = None
ever_profitable = False

for c in trade_c:
    p_hi = pnl(entry_px, c["h"],
               direction)
    p_c  = pnl(entry_px, c["c"],
               direction)
    j15m = get_j15m(c["t"])

    if p_hi > 0:
        ever_profitable = True
    if p_hi > peak_pnl:
        peak_pnl = p_hi

    # track J15M peak
    if (ever_profitable and
            j15m is not None):
        if (peak_j15m is None or
                j15m > peak_j15m):
            peak_j15m = j15m

    # SE fire condition —
    # J15M decayed 10pts from peak
    decay = 0
    if peak_j15m is not None and j15m:
        decay = peak_j15m - j15m

    se_fires = (
        ever_profitable and
        decay >= 10 and
        j15m_se_fire_ts is None)
    if se_fires:
        j15m_se_fire_ts = c["t"]
        j15m_se_fire_pnl = p_c

    note = ""
    if c["t"] < entry_ts:
        note = "PRE"
    elif c["t"] <= entry_ts+60:
        note = "ENTRY"
    if c["l"] <= be_confirm:
        note += " ⚡CR"
    if se_fires:
        note += " ★J15M_SE FIRES"

    print(f"{fmt(c['t']):>8}"
          f"  {p_hi:8.2f}"
          f"  {p_c:8.2f}"
          f"  {j15m or 0:7.1f}"
          f"  {peak_j15m or 0:10.1f}"
          f"  {decay:7.1f}"
          f"  {note}")

print(f"\nPeak PnL:    +${peak_pnl:.2f}"
      f" at 00:13")
if j15m_se_fire_ts:
    print(
        f"J15M SE exit: {fmt(j15m_se_fire_ts)}"
        f" PnL={j15m_se_fire_pnl:+.2f}")
    print(
        f"CR exit:      00:20:00"
        f" PnL≈-$27.56")
    print(
        f"SE vs CR:     "
        f"${j15m_se_fire_pnl+27.56:.2f}"
        f" better with J15M SE")
else:
    print("J15M SE never fired"
          " (decay never >= 10)")
