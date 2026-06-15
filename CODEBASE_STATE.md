# MEXC-BOUNCE-SCANNER — Codebase State
  # Generated 2025-06-15 from HEAD 04a3b2f3d0eba6911a39d26f3e381fdc4acf0b4a

  ## File sizes
  | File | Lines |
  |------|-------|
  | config.py | 70 |
  | scanner.py | 684 |
  | main.py | 1829 |
  | static/dashboard.js | 2711 |
  | templates/dashboard.html | (contains script tag below) |

  ---

  ## CARDINAL RULES (never break)
  1. No non-ASCII bytes — grep -P '[^\x00-\x7F]' must return EMPTY before every commit.
  2. Cache-bust tag must exist: `<script src="/static/dashboard.js?v={{ cache_bust }}">`
  3. py_compile + AST parse on every changed .py file before commit.
  4. Print changed function BEFORE and AFTER every edit.
  5. Read full file before any edit.

  ---

  ## config.py key constants
  ```
  PAIRS = ["ZEC_USDT","SOL_USDT","BTC_USDT","ETH_USDT","XRP_USDT","DOGE_USDT",
           "SUI_USDT","NEAR_USDT","AVAX_USDT","ARB_USDT","WIF_USDT","HYPE_USDT",
           "XAUT_USDT","PEPE_USDT"]   # 14 pairs

  SCAN_INTERVAL_SECONDS  = 30
  PRICE_INTERVAL_SECONDS = 8
  PAPER_MODE             = True
  LIVE_MANUAL_ENTRY_ONLY = True   # human must click to open live trades

  J15M_SHORT_GATE = 80   J15M_LONG_GATE = 20
  J1H_SHORT_MIN   = 60   J1H_LONG_MAX   = 40
  RSI15M_SHORT_MIN = 60  RSI15M_LONG_MAX = 40
  DEPTH_GATE_PCT  = 55

  ATR_SL_MULTIPLIER      = 1.0
  TP1_R                  = 1.0
  TP1_CLOSE_PCT          = 0.70   # Trailblazer: close 70% at TP1, runner 30% stays
  TP2_R                  = 1.5
  TRAIL_ATR_MULTIPLIER   = 0.5

  LEVERAGE_HIGH = 10  LEVERAGE_MID = 7  LEVERAGE_LOW = 5
  COOLDOWN_SECONDS      = 1800
  CONSECUTIVE_LOSS_STOP = 3
  DAILY_LOSS_LIMIT      = -800.0
  MARGIN_PER_TRADE      = 2000.0
  MARGIN_HARD_CAP       = 25000.0
  ADX_FADE_MAX          = 60
  SESSION_FILTER_ENABLED = False
  PLACE_EXCHANGE_SL      = True

  SUPABASE_URL  = os.environ.get("SUPABASE_URL", "")
  SUPABASE_KEY  = os.environ.get("SUPABASE_KEY", "")
  ```

  ### MIN_SL_PCT per base asset
  BTC=0.008, ETH=0.006, SOL=0.008, XRP=0.007, DOGE=0.007, SUI=0.010,
  NEAR=0.010, LINK=0.008, ARB=0.012, ZEC=0.030; default=0.010

  ---

  ## scanner.py key lines
  | Item | Line |
  |------|------|
  | _last_stoch dict | L25 |
  | _last_stoch_fast dict | L26 |
  | _btc_j1h global (default 50.0) | L32 |
  | BTC_CORRELATION global | L33 |
  | _compute_stochastic (14,3,3 default) | L80 |
  | compute_market_health | L300 |
  | run_full_scan | L353 |
  | BTC_USDT price capture | L405 |
  | regime gate block | L425 |
  | run_full_scan alert result dict | L539 |
  | scan_pair_state | L585 |
  | _fetch_pair_data | L662 |

  ### scan_pair_state per-symbol result dict (L625-655)
  ```python
  {
    "symbol", "price",
    "j5m", "j15m", "j1h",
    "rsi15m", "rsi1h",
    "stoch_k", "stoch_d", "stoch_k_prev", "stoch_d_prev",
    "stoch_k_fast", "stoch_d_fast", "stoch_k_prev_fast", "stoch_d_prev_fast",
    "atr15m", "adx1h",
    "bid_pct", "ask_pct",
    "trend",
    "ma10", "ma30", "ma60",
    "short_score", "short_tier",
    "long_score",  "long_tier",
    "cooldown_short", "cooldown_long",
  }
  ```

  ### run_full_scan alert dict (L539-570)
  ```python
  {
    "symbol", "direction", "score", "tier", "leverage",
    "entry_price", "sl_price", "sl_dist", "tp1_price", "tp2_price",
    "dollar_risk",
    "j15m", "j1h", "j5m", "rsi15m",
    "stoch_k", "stoch_d", "rsi1h", "atr15m", "adx1h",
    "bid_pct", "ask_pct", "trend",
    "ma10", "ma30", "ma60",
    "fired_at", "is_in_trade", "is_score10",
    "margin", "partial_price", "session",
  }
  ```

  ### compute_market_health return (L337-348)
  ```python
  {
    "short_status", "long_status",       # "RUN" | "CAUTION" | "HALT"
    "bear_count", "bull_count", "total",
    "bear_ratio", "bull_ratio",
    "avg_adx", "avg_j5", "sl_rate",
  }
  ```

  ### _compute_stochastic signature (L80)
  ```python
  def _compute_stochastic(candles, k_period=14, d_period=3, smooth=3) -> tuple[float,float]
  ```
  - 8,3,3 fast stoch: called with k_period=8

  ---

  ## main.py key lines
  | Item | Line |
  |------|------|
  | AppState class | ~L70 |
  | AppState.pair_states list | L74 |
  | _load_state / Supabase restore | L255 |
  | mexc_trade_log restore loop | L264 |
  | _save_state | L231 |
  | scan_pair_state call | L885 |
  | /api/state endpoint | L1403 |
  | /api/account endpoint | L1408 |
  | /api/mexc-balance endpoint | L1418 |
  | /api/pair/{symbol} endpoint | L1427 |
  | /api/trade/open | L1565 |
  | /api/trade/close | L1620 |
  | /api/circuit-breaker/reset | L1677 |
  | /api/reset-session | L1686 |
  | /api/reset-day | L1704 |
  | /api/tradelog | L1715 |
  | /api/tradelog/csv | L1720 |
  | cache_bust injection | L1399 |
  | template render | L1393 |

  ### /api/pair/{symbol} response fields (L1510-1554)
  ```
  symbol, price, change_24h,
  j15m, j1h, rsi15m, adx, atr, bid_pct, ask_pct,
  stoch_k, stoch_d, stoch_k_prev, stoch_d_prev,
  stoch_k_fast, stoch_d_fast, stoch_k_prev_fast, stoch_d_prev_fast,
  gate_long [4 bools], gate_short [4 bools],
  score_long, score_short,
  alert, alert_state, alert_age_seconds,
  in_trade_long, in_trade_short,
  last_scan_summaries, recent_alerts,
  confluence_long, confluence_short,
  trend,
  session_halted_long, session_halted_short,
  large_sl_cooldown_long_remaining, large_sl_cooldown_short_remaining,
  session_halt_reason,
  ```

  ### Gate order for long  (L1453)
  `[j15m < 20, j1h < 40, stoch_gate_long, bid_pct >= 55]`
  ### Gate order for short (L1454)
  `[j15m > 80, j1h > 60, stoch_gate_short, ask_pct >= 55]`

  ### stoch gates (L1451-1452)
  ```python
  stoch_gate_long  = stoch_k < 25 and stoch_k_prev <= stoch_d_prev and stoch_k > stoch_d
  stoch_gate_short = stoch_k > 75 and stoch_k_prev >= stoch_d_prev and stoch_k < stoch_d
  ```

  ### trade_log entry columns (L278-299)
  ```
  timestamp_opened, timestamp_closed, symbol, direction, tier,
  adx1h, score, entry_price, sl_price, tp1_price, tp2_price, exit_price,
  exit_reason, pnl_usd, r_value, duration_seconds,
  exchange, session_opened, mae_r, mfe_r, paper
  ```

  ### Supabase tables
  - `mexc_trade_log` — Supabase columns (DB side): pair, direction, tier, entry_price, sl, tp1, tp2,
    exit_price, exit_reason, pnl_dollars, r_value, duration_seconds, exchange, session_opened,
    mae_r, mfe_r, open_time, close_time, created_at
  - `mexc_scanner_state` — id=1 row: daily_pnl, trading_halted_today, consecutive_losses,
    circuit_breaker_active, margin_deployed, saved_date

  ---

  ## dashboard.js key function lines
  | Function | Line |
  |----------|------|
  | BTC_CORRELATION const | L12 |
  | openPairOverlay | L1552 |
  | _ovVerdictHtml | L1782 |
  | _ovStochHtml | L1850 |
  | _ovScanConfHtml | L1989 |
  | _ovActionsHtml | L2006 |
  | _ovRender | L2091 |
  | _btcRegime | L2496 |

  ### _ovStochHtml call signature (L1850)
  Returns: `_ovGateRowHtml('STOCH K/D', pass, note, track) + shadowRow`
  - 4 args: label, pass_bool, note_string, track_string
  - gradient ruler for 14,3,3 slow stoch: green/red linear-gradient with orange 8,3,3 shadow
  - Orange shadow gradients: gradOrangGreen / gradOrangRed

  ---

  ## Template / static serving
  ```html
  <script src="/static/dashboard.js?v={{ cache_bust }}">
  ```
  - cache_bust = int(time.time()) injected at L1399 of main.py

  ---

  ## MEXC API / Environment variables
  | Var | Source |
  |-----|--------|
  | MEXC_API_KEY | mexc_api.py L3: `os.environ.get("MEXC_API_KEY", "")` |
  | MEXC_SECRET_KEY | mexc_api.py L4: `os.environ.get("MEXC_SECRET_KEY", "")` |
  | SUPABASE_URL | config.py `os.environ.get("SUPABASE_URL", "")` |
  | SUPABASE_KEY | config.py `os.environ.get("SUPABASE_KEY", "")` |

  - MEXC exchange API base: `https://contract.mexc.com`
  - Symbol format: `BTC_USDT` (underscore, not hyphen)

  ---

  ## Session / theme notes
  - Dashboard shadow theme: ORANGE (#ff8c00)
  - bounce-scanner-deux (HL) shadow: PURPLE (#b388ff)
  - Overlay stoch ruler: slow 14,3,3 green/red gradient + fast 8,3,3 orange shadow
  