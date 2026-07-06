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
        raise ValueError(str(d)[:80])
    raw = d["data"]
    out = []
    for i in range(
            len(raw["time"])):
        out.append({
          "t": int(raw["time"][i]),
          "o": float(raw["open"][i]),
          "h": float(raw["high"][i]),
          "l": float(raw["low"][i]),
          "c": float(raw["close"][i]),
          "v": float(raw["vol"][i])
            if "vol" in raw else 0,
        })
    return sorted(
        out, key=lambda x: x["t"])

def fmt(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone.utc
    ).strftime("%H:%M:%S")

def fmt_et(ts):
    # UTC-4 for EDT
    return datetime.fromtimestamp(
        ts - 14400,
        tz=timezone.utc
    ).strftime("%H:%M:%S ET")

def pnl_short(entry, price,
        margin=5000, lev=5):
    sz = (margin * lev) / entry
    return round(
        (entry - price) * sz, 2)

def r_val(entry, price,
          sl, margin=5000, lev=5):
    sz = (margin * lev) / entry
    risk = abs(entry - sl) * sz
    if risk == 0:
        return 0
    return round(
        (entry - price) * sz
        / risk, 3)

def ts(iso):
    return int(
        datetime.fromisoformat(
            iso.replace('+00','')
        ).replace(
            tzinfo=timezone.utc
        ).timestamp())

# HYPE_USDT SHORT
SYMBOL   = "HYPE_USDT"
ENTRY    = 72.26
SL       = 73.1629
TP1      = 71.2851
OPEN_TS  = ts(
    "2026-07-06 01:26:03+00")
CLOSE_TS = ts(
    "2026-07-06 01:32:15+00")
EXIT_PX  = 72.269
EXIT_PNL = -1.25
MFE_R    = 0.17
MAE_R    = -0.01

# Fetch 60 min before open
# to 60 min after close
START = OPEN_TS - 3600
END   = CLOSE_TS + 3600

print("Fetching Min1 candles...")
candles = fetch(
    SYMBOL, "Min1", START, END)

print(f"\n{'='*80}")
print(f"  HYPE_USDT SHORT FORENSIC")
print(f"  Entry: {ENTRY}"
      f"  SL: {SL}"
      f"  TP1: {TP1}")
print(f"  Open:  {fmt_et(OPEN_TS)}"
      f"  Close: {fmt_et(CLOSE_TS)}")
print(f"  Exit PX: {EXIT_PX}"
      f"  PnL: {EXIT_PNL}"
      f"  MFE: {MFE_R}R"
      f"  MAE: {MAE_R}R")
print(f"{'='*80}")
print(f"  {'TIME ET':>10}"
      f"  {'OPEN':>10}"
      f"  {'HIGH':>10}"
      f"  {'LOW':>10}"
      f"  {'CLOSE':>10}"
      f"  {'PNL_C':>9}"
      f"  {'PNL_H':>9}"
      f"  {'PNL_L':>9}"
      f"  {'R_C':>6}"
      f"  {'NOTE'}")
print(f"  {'-'*110}")

peak_pnl = None
peak_ts  = None
post_peak_low_pnl = None

for c in candles:
    p_close = pnl_short(ENTRY, c["c"])
    p_high  = pnl_short(ENTRY, c["h"])
    p_low   = pnl_short(ENTRY, c["l"])
    r_close = r_val(ENTRY, c["c"], SL)

    # track peak (best SHORT = lowest price)
    if (c["t"] >= OPEN_TS and
            c["t"] <= CLOSE_TS):
        if (peak_pnl is None or
                p_low > peak_pnl):
            peak_pnl = p_low
            peak_ts  = c["t"]

    note = ""
    if abs(c["t"] - OPEN_TS) < 90:
        note = "ENTRY"
    elif abs(c["t"] - CLOSE_TS) < 90:
        note = "★ CR EXIT"
    elif c["t"] > CLOSE_TS:
        note = "POST-EXIT"
        if (post_peak_low_pnl is None
                or p_low >
                post_peak_low_pnl):
            post_peak_low_pnl = p_low

    # flag BE cross
    if (c["t"] >= OPEN_TS and
            c["h"] >= ENTRY and
            not note):
        note += " ⚡BE_CROSS"

    # flag TP1 reach
    if c["l"] <= TP1:
        note += " ★TP1"

    # flag SL proximity
    if c["h"] >= SL * 0.998:
        note += " ⚠SL_NEAR"

    print(
        f"  {fmt_et(c['t']):>10}"
        f"  {c['o']:10.4f}"
        f"  {c['h']:10.4f}"
        f"  {c['l']:10.4f}"
        f"  {c['c']:10.4f}"
        f"  {p_close:9.2f}"
        f"  {p_high:9.2f}"
        f"  {p_low:9.2f}"
        f"  {r_close:6.3f}"
        f"  {note}")

print(f"\n{'='*80}")
print(f"  TRADE SUMMARY")
print(f"{'='*80}")
print(f"  Entry:        {ENTRY}")
print(f"  Exit:         {EXIT_PX}"
      f"  ({EXIT_PNL})")
print(f"  Duration:     372s"
      f" (6m 12s)")
print(f"  MAE:          {MAE_R}R")
print(f"  MFE:          {MFE_R}R")
if peak_pnl:
    print(f"  Peak PnL:     "
          f"+${peak_pnl:.2f}"
          f" at {fmt_et(peak_ts)}")
if post_peak_low_pnl:
    print(f"  Post-exit"
          f" best PnL:  "
          f"+${post_peak_low_pnl:.2f}"
          f" (if held)")
print(f"\n  CONFIRM_REVERSAL fired"
      f" when price rose back"
      f" to entry {ENTRY}"
      f" at {fmt_et(CLOSE_TS)}")
_mfe_usd = round(0.17 * abs(ENTRY - SL) * (25000 / ENTRY), 2)
print(f"  MFE was 0.17R ="
      f" approximately"
      f" +${_mfe_usd}"
      f" at best point")

print("\nDone.")
