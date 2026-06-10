
  /* MEXC Bounce Scanner — dashboard.js */
  'use strict';

  const PAIRS = [
    "ZEC_USDT","SOL_USDT","BTC_USDT","ETH_USDT","XRP_USDT",
    "DOGE_USDT","SUI_USDT","NEAR_USDT","AVAX_USDT","ARB_USDT"
  ];

  let _state = {};
  let _activeTab = 'all';
  let _overlaySymbol = null;
  let _overlayPoll   = null;

  // ── Polling ───────────────────────────────────────────────────────────────────
  async function fetchState() {
    try {
      const r = await fetch('/api/state');
      if (!r.ok) return;
      _state = await r.json();
      render();
    } catch(e) { /* ignore */ }
  }

  async function fetchPairFast(symbol) {
    try {
      const r = await fetch('/api/pair/' + symbol);
      if (!r.ok) return null;
      return await r.json();
    } catch(e) { return null; }
  }

  setInterval(fetchState, 3000);
  fetchState();

  // ── Tab routing ───────────────────────────────────────────────────────────────
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      _activeTab = tab.dataset.tab;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const tabIds = ['all','short','long','alerts','positions','cooldown','log'];
      tabIds.forEach(id => {
        const el = document.getElementById('tab-' + id);
        if (el) el.style.display = (id === _activeTab ? '' : 'none');
      });
      render();
    });
  });

  // ── Main render ───────────────────────────────────────────────────────────────
  function render() {
    if (!_state.pair_data) return;
    renderHeader();
    renderHealth();
    renderMap();
    renderPairGrids();
    renderAlerts();
    renderPositions();
    renderCooldowns();
    renderLog();
  }

  // ── Header ────────────────────────────────────────────────────────────────────
  function renderHeader() {
    const pnl = _state.daily_pnl || 0;
    const pnlEl = document.getElementById('hdr-pnl');
    pnlEl.textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
    pnlEl.style.color = pnl >= 0 ? 'var(--green)' : 'var(--red)';
    setText('hdr-margin', '$' + Math.round(_state.deployed_margin || 0).toLocaleString());
    setText('hdr-pos',    (_state.open_trades || []).length);
    setText('hdr-scans',  _state.scan_count || 0);
    setText('hdr-session', _state.session || '—');
    const badge = document.getElementById('mode-badge');
    if (_state.paper_mode) {
      badge.className = 'paper-badge'; badge.textContent = 'PAPER';
    } else {
      badge.className = 'live-badge'; badge.textContent = 'LIVE';
    }
    // Circuit breaker warning
    if (_state.circuit_breaker) {
      pnlEl.title = 'Circuit breaker active';
    }
  }

  // ── Health ────────────────────────────────────────────────────────────────────
  function renderHealth() {
    const h = _state.market_health || {};
    const ss = h.short_status || 'CAUTION';
    const ls = h.long_status  || 'CAUTION';
    const se = document.getElementById('health-short');
    const le = document.getElementById('health-long');
    se.textContent = 'SHORT: ' + ss;
    se.className   = 'health-pill ' + ss;
    le.textContent = 'LONG: ' + ls;
    le.className   = 'health-pill ' + ls;
    setText('health-short-reason', h.short_reason || '');
    setText('health-long-reason',  h.long_reason  || '');
    setText('health-stats',
      h.total
        ? 'ADX ' + (h.avg_adx||0).toFixed(1) + ' · J15 ' + (h.avg_j15||50).toFixed(1) + ' · SL rate ' + Math.round((h.sl_rate||0)*100) + '%'
        : ''
    );
  }

  // ── J Bounce Map ──────────────────────────────────────────────────────────────
  function renderMap() {
    const pd = _state.pair_data || {};
    renderMapRow('map-15m', pd, 'j15m');
    renderMapRow('map-1h',  pd, 'j1h');
  }

  function renderMapRow(barId, pd, field) {
    const bar = document.getElementById(barId);
    if (!bar) return;
    // Remove old chips
    bar.querySelectorAll('.map-chip').forEach(c => c.remove());
    const chips = {};
    Object.entries(pd).forEach(([sym, d]) => {
      const v = d[field];
      if (v == null) return;
      const clamped = Math.max(0, Math.min(100, v));
      const pct     = clamped.toFixed(0);
      const label   = sym.replace('_USDT','');
      // Stack chips at same position
      const key     = Math.round(clamped / 5) * 5;
      chips[key]    = (chips[key] || []);
      chips[key].push({ label, v: clamped });
    });
    Object.entries(chips).forEach(([key, items]) => {
      const chip = document.createElement('div');
      chip.className = 'map-chip';
      chip.style.left = key + '%';
      const val = parseFloat(key);
      chip.style.color = val >= 80 ? 'var(--red)' : val <= 20 ? 'var(--green)' : 'var(--text)';
      chip.textContent = items.map(i => i.label).join(' ');
      bar.appendChild(chip);
    });
  }

  // ── Pair grids ────────────────────────────────────────────────────────────────
  function renderPairGrids() {
    const pd = _state.pair_data || {};
    const ot = _state.open_trades || [];
    const allCards  = PAIRS.map(sym => buildCard(sym, pd[sym] || {}, ot));

    const gridAll   = document.getElementById('pair-grid');
    const gridShort = document.getElementById('pair-grid-short');
    const gridLong  = document.getElementById('pair-grid-long');

    let shortCount = 0, longCount = 0;

    if (_activeTab === 'all') {
      gridAll.innerHTML = '';
      allCards.forEach(c => gridAll.appendChild(c));
    }
    if (_activeTab === 'short') {
      gridShort.innerHTML = '';
      PAIRS.forEach(sym => {
        const d = pd[sym] || {};
        if ((d.j15m || 50) > 70 || (d.j1h || 50) > 50) {
          gridShort.appendChild(buildCard(sym, d, ot));
          shortCount++;
        }
      });
    }
    if (_activeTab === 'long') {
      gridLong.innerHTML = '';
      PAIRS.forEach(sym => {
        const d = pd[sym] || {};
        if ((d.j15m || 50) < 30 || (d.j1h || 50) < 50) {
          gridLong.appendChild(buildCard(sym, d, ot));
          longCount++;
        }
      });
    }

    // Update badges
    PAIRS.forEach(sym => {
      const d = pd[sym] || {};
      if ((d.j15m || 50) > 70) shortCount++;
      if ((d.j15m || 50) < 30) longCount++;
    });
    setText('badge-short', shortCount);
    setText('badge-long',  longCount);
    setText('badge-pos',   ot.length);
  }

  function buildCard(sym, d, openTrades) {
    const label = sym.replace('_USDT','');
    const price = d.price || _state.prices?.[sym] || 0;
    const j15m  = d.j15m  ?? 50;
    const j1h   = d.j1h   ?? 50;
    const rsi   = d.rsi15m ?? 50;
    const adx   = d.adx1h  ?? 0;
    const bid   = d.bid_pct ?? 50;
    const ask   = d.ask_pct ?? 50;
    const trend = d.trend   || 'Neutral';
    const trade = openTrades.find(t => t.symbol === sym);

    // Gate dots for SHORT / LONG
    const sg = [j15m > 80, j1h > 60, rsi > 65, ask >= 60];
    const lg = [j15m < 20, j1h < 40, rsi < 35, bid >= 60];
    const sgPass = sg.filter(Boolean).length;
    const lgPass = lg.filter(Boolean).length;

    // Trend arrow
    let arrowClass = 'neutral', arrow = '→';
    if (trend.includes('Bear')) { arrowClass = 'bear'; arrow = '↓'; }
    if (trend.includes('Bull')) { arrowClass = 'bull'; arrow = '↑'; }

    // Readiness pill — SHORT direction (highest priority)
    let readLabel = 'SCANNING', readClass = 'scanning';
    if (sgPass === 4) { readLabel = 'READY SHORT'; readClass = 'ready'; }
    else if (sgPass === 3) { readLabel = 'NEAR 3/4 S';  readClass = 'near'; }
    else if (lgPass === 4) { readLabel = 'READY LONG';  readClass = 'ready'; }
    else if (lgPass === 3) { readLabel = 'NEAR 3/4 L';  readClass = 'near'; }
    else if (sgPass === 2) { readLabel = 'PARTIAL 2/4'; readClass = 'partial'; }
    else if (lgPass === 2) { readLabel = 'PARTIAL 2/4'; readClass = 'partial'; }
    else if (sgPass > 0 && lgPass > 0) { readLabel = 'DIVERGENCE'; readClass = 'div'; }
    if (trade)             { readLabel = 'IN TRADE';    readClass = 'ready'; }

    const cardClass = 'pair-card' +
      (sgPass === 4 ? ' signal-short' : lgPass === 4 ? ' signal-long' : '');

    const div = document.createElement('div');
    div.className = cardClass;
    div.dataset.symbol = sym;
    div.onclick = () => openOverlay(sym);

    const priceStr = formatPrice(price);
    const shortDots = sg.map(p => '<div class="gate-dot' + (p ? ' pass' : '') + '"></div>').join('');
    const longDots  = lg.map(p => '<div class="gate-dot' + (p ? ' pass' : '') + '"></div>').join('');

    div.innerHTML =
      '<div class="card-header">' +
        '<span class="card-symbol">' + label + '</span>' +
        '<span class="card-arrow ' + arrowClass + '">' + arrow + '</span>' +
        '<div style="display:flex;gap:2px;align-items:center">' + shortDots + '</div>' +
        '<span style="color:var(--muted);font-size:10px;padding:0 3px">|</span>' +
        '<div style="display:flex;gap:2px;align-items:center">' + longDots  + '</div>' +
        '<span class="card-price">' + priceStr + '</span>' +
      '</div>' +
      '<div class="card-meta">' +
        '<span>ADX ' + adx.toFixed(1) + '</span>' +
        '<span>J15M ' + j15m.toFixed(1) + '</span>' +
        '<span>J1H ' + j1h.toFixed(1) + '</span>' +
        (trade ? '<span style="color:var(--accent)">● IN TRADE</span>' : '') +
      '</div>' +
      '<div class="mini-bar-wrap">' +
        '<div class="mini-bar-label"><span>RSI ' + rsi.toFixed(1) + '</span><span></span></div>' +
        '<div class="mini-bar-track"><div class="mini-bar-fill rsi" style="width:' + rsi.toFixed(1) + '%"></div></div>' +
      '</div>' +
      '<div class="mini-bar-wrap">' +
        '<div class="mini-bar-label"><span>BID ' + bid.toFixed(1) + '%</span><span>ASK ' + ask.toFixed(1) + '%</span></div>' +
        '<div class="mini-bar-track">' +
          '<div class="mini-bar-fill bid" style="width:' + bid.toFixed(1) + '%"></div>' +
        '</div>' +
      '</div>' +
      '<span class="readiness-pill ' + readClass + '">' + readLabel + '</span>';

    return div;
  }

  // ── Alerts table ──────────────────────────────────────────────────────────────
  function renderAlerts() {
    if (_activeTab !== 'alerts') return;
    const tbody = document.getElementById('alerts-tbody');
    const alerts = (_state.alerts || []).slice(0, 100);
    setText('badge-alerts', alerts.length);
    tbody.innerHTML = alerts.map(a => {
      const sym = a.symbol.replace('_USDT','');
      const dir = a.direction;
      const dc  = dir === 'SHORT' ? 'dir-short' : 'dir-long';
      const t   = a.ts ? new Date(a.ts).toLocaleTimeString() : '—';
      return '<tr>' +
        '<td>' + t + '</td>' +
        '<td style="font-weight:700">' + sym + '</td>' +
        '<td class="' + dc + '">' + dir + '</td>' +
        '<td>' + a.tier + ' ' + a.leverage + 'x</td>' +
        '<td>' + formatPrice(a.price) + '</td>' +
        '<td>' + formatPrice(a.sl_price) + '</td>' +
        '<td>' + formatPrice(a.tp1_price) + '</td>' +
        '<td>' + formatPrice(a.tp2_price) + '</td>' +
        '<td>' + (a.adx || 0).toFixed(1) + '</td>' +
        '<td>' + (a.session || '—') + '</td>' +
      '</tr>';
    }).join('');
  }

  // ── Positions ─────────────────────────────────────────────────────────────────
  function renderPositions() {
    if (_activeTab !== 'positions') return;
    const list   = document.getElementById('positions-list');
    const trades = _state.open_trades || [];
    if (!trades.length) {
      list.innerHTML = '<p style="color:var(--muted);padding:20px;text-align:center">No open positions</p>';
      return;
    }
    list.innerHTML = trades.map(t => {
      const sym   = t.symbol;
      const label = sym.replace('_USDT','');
      const d     = t.direction;
      const dc    = d === 'SHORT' ? 'short' : 'long';
      const price = _state.prices?.[sym] || t.entry_price;
      const pnl   = calcUnrealisedPnl(t, price);
      const pnlCls = pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
      const tp1Hit = t.tp1_hit ? '<span class="tp1-badge">TP1 ✓</span> ' : '';
      return '<div class="position-card">' +
        '<div class="position-header">' +
          '<span class="position-symbol">' + label + '</span>' +
          '<span class="position-dir ' + dc + '">' + d + '</span>' +
          '<span class="position-tier">' + t.tier + ' ' + t.leverage + 'x</span>' +
          '<span class="position-pnl ' + pnlCls + '">' + (pnl>=0?'+':'') + '$' + pnl.toFixed(2) + '</span>' +
        '</div>' +
        '<div style="margin-bottom:8px">' + tp1Hit +
          '<span style="font-size:11px;color:var(--muted)">Opened ' + fmtTime(t.opened_at) + ' · Margin $' + (t.margin||2000) + '</span>' +
        '</div>' +
        '<div class="position-levels">' +
          '<div class="level-box"><div class="lbl">ENTRY</div><div class="val">' + formatPrice(t.entry_price) + '</div></div>' +
          '<div class="level-box"><div class="lbl">SL</div><div class="val" style="color:var(--red)">' + formatPrice(t.sl_price) + '</div></div>' +
          '<div class="level-box"><div class="lbl">TP1</div><div class="val" style="color:var(--green)">' + formatPrice(t.tp1_price) + '</div></div>' +
          '<div class="level-box"><div class="lbl">TP2</div><div class="val" style="color:var(--green)">' + formatPrice(t.tp2_price) + '</div></div>' +
        '</div>' +
        '<div class="position-actions">' +
          '<button class="btn btn-close"  onclick="closeTradeBtn('' + t.id + '',false)">CLOSE MEXC</button>' +
          '<button class="btn btn-force"  onclick="closeTradeBtn('' + t.id + '',true)">FORCE CLOSE</button>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  async function closeTradeBtn(tradeId, force) {
    if (!confirm(force ? 'Force close this trade?' : 'Close this trade at market?')) return;
    await fetch('/api/paper/close', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({trade_id: tradeId, force})
    });
    fetchState();
  }

  // ── Cooldowns ─────────────────────────────────────────────────────────────────
  function renderCooldowns() {
    if (_activeTab !== 'cooldown') return;
    const list = document.getElementById('cooldown-list');
    const pd   = _state.pair_data || {};
    const rows = [];
    PAIRS.forEach(sym => {
      ['SHORT','LONG'].forEach(dir => {
        const cd = getCooldown(sym, dir);
        if (cd > 0) rows.push({ sym, dir, cd });
      });
    });
    if (!rows.length) {
      list.innerHTML = '<p style="color:var(--muted);padding:20px;text-align:center">No active cooldowns</p>';
      return;
    }
    list.innerHTML = rows.map(r => {
      const pct  = Math.max(0, Math.min(100, (1 - r.cd / 1800) * 100));
      const mins = Math.ceil(r.cd / 60);
      const dc   = r.dir === 'SHORT' ? 'dir-short' : 'dir-long';
      return '<div class="cooldown-row">' +
        '<span class="cd-sym">' + r.sym.replace('_USDT','') + '</span>' +
        '<span class="cd-dir ' + dc + '">' + r.dir + '</span>' +
        '<div class="cd-bar-wrap"><div class="cd-bar"><div class="cd-fill" style="width:' + pct.toFixed(1) + '%"></div></div></div>' +
        '<span class="cd-time">' + mins + 'm</span>' +
      '</div>';
    }).join('');
  }

  function getCooldown(sym, dir) {
    // cooldown remaining is not directly in state, derive from pair_data or alerts
    // Fall back: check pending in alerts
    const alerts = _state.alerts || [];
    const now = Date.now() / 1000;
    const match = alerts.find(a => a.symbol === sym && a.direction === dir);
    if (match && match.ts) {
      const elapsed = now - new Date(match.ts).getTime() / 1000;
      const remaining = 1800 - elapsed;
      return remaining > 0 ? remaining : 0;
    }
    return 0;
  }

  // ── Trade log ─────────────────────────────────────────────────────────────────
  function renderLog() {
    if (_activeTab !== 'log') return;
    renderPerf();
    const tbody = document.getElementById('log-tbody');
    const trades = (_state.trade_log || []).slice(0, 200);
    tbody.innerHTML = trades.map(t => {
      const sym  = (t.symbol || '').replace('_USDT','');
      const dir  = t.direction || '';
      const dc   = dir === 'SHORT' ? 'dir-short' : 'dir-long';
      const pnl  = t.pnl ?? null;
      const pnlStr = pnl != null ? ((pnl>=0?'+':'') + '$' + pnl.toFixed(2)) : '—';
      const pnlCls = pnl == null ? '' : pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
      return '<tr>' +
        '<td>' + fmtTime(t.opened_at) + '</td>' +
        '<td style="font-weight:700">' + sym + '</td>' +
        '<td class="' + dc + '">' + dir + '</td>' +
        '<td>' + formatPrice(t.entry_price) + '</td>' +
        '<td>' + formatPrice(t.exit_price) + '</td>' +
        '<td>' + (t.close_reason || '—') + '</td>' +
        '<td class="' + pnlCls + '">' + pnlStr + '</td>' +
        '<td>' + (t.session || '—') + '</td>' +
      '</tr>';
    }).join('');
  }

  function renderPerf() {
    const trades  = _state.trade_log || [];
    const closed  = trades.filter(t => t.status === 'CLOSED' && t.pnl != null);
    const wins    = closed.filter(t => t.pnl >= 0);
    const losses  = closed.filter(t => t.pnl < 0);
    const totalPnl = closed.reduce((s, t) => s + (t.pnl || 0), 0);
    const wr      = closed.length ? (wins.length / closed.length * 100) : 0;
    const avgWin  = wins.length   ? wins.reduce((s,t)=>s+t.pnl,0)  / wins.length : 0;
    const avgLoss = losses.length ? losses.reduce((s,t)=>s+t.pnl,0)/ losses.length : 0;
    const panel   = document.getElementById('perf-panel');
    const pnlCls  = totalPnl >= 0 ? 'var(--green)' : 'var(--red)';
    panel.innerHTML =
      '<div class="perf-title">PERFORMANCE SUMMARY</div>' +
      '<div class="perf-grid">' +
        perfStat('Total PnL',    (totalPnl>=0?'+':'') + '$' + totalPnl.toFixed(2), pnlCls) +
        perfStat('Win Rate',     wr.toFixed(1) + '%') +
        perfStat('Trades',       closed.length) +
        perfStat('Wins',         wins.length,   'var(--green)') +
        perfStat('Losses',       losses.length, 'var(--red)') +
        perfStat('Avg Win',      '+$' + avgWin.toFixed(2),  'var(--green)') +
        perfStat('Avg Loss',     '$'  + avgLoss.toFixed(2), 'var(--red)') +
        perfStat('Daily PnL',    ((_state.daily_pnl||0)>=0?'+':'') + '$' + (_state.daily_pnl||0).toFixed(2), pnlCls) +
      '</div>';
  }

  function perfStat(label, val, color) {
    return '<div class="perf-stat"><div class="lbl">' + label + '</div>' +
      '<div class="val"' + (color ? ' style="color:' + color + '"' : '') + '>' + val + '</div></div>';
  }

  // ── Symbol Overlay ────────────────────────────────────────────────────────────
  function openOverlay(sym) {
    _overlaySymbol = sym;
    document.getElementById('overlay').classList.add('open');
    updateOverlay(sym, _state.pair_data?.[sym] || {}, _state.open_trades || []);
    // Start fast poll
    if (_overlayPoll) clearInterval(_overlayPoll);
    _overlayPoll = setInterval(async () => {
      if (!_overlaySymbol) return;
      const d = await fetchPairFast(_overlaySymbol);
      if (d) updateOverlay(_overlaySymbol, d, _state.open_trades || []);
    }, 2000);
  }

  function closeOverlay() {
    _overlaySymbol = null;
    document.getElementById('overlay').classList.remove('open');
    if (_overlayPoll) { clearInterval(_overlayPoll); _overlayPoll = null; }
  }

  function updateOverlay(sym, d, openTrades) {
    const label  = sym.replace('_USDT','');
    const trade  = openTrades.find(t => t.symbol === sym);
    const price  = d.price || _state.prices?.[sym] || 0;
    const trend  = d.trend  || 'Neutral';
    let stateLabel = trade ? 'IN TRADE' : 'WATCHING';

    document.getElementById('ov-sym').textContent = label;
    document.getElementById('ov-state').textContent = stateLabel + ' · MEXC';

    // Trend color for accent
    let accentColor = 'var(--accent)';
    if (trend.includes('Bear')) accentColor = 'var(--red)';
    if (trend.includes('Bull')) accentColor = 'var(--green)';
    document.querySelector('.overlay-sheet').style.borderTopColor = accentColor;

    const grid = document.getElementById('ov-grid');
    grid.innerHTML =
      ovStat('Price',   formatPrice(price)) +
      ovStat('J15M',    (d.j15m  ?? '—').toString()) +
      ovStat('J1H',     (d.j1h   ?? '—').toString()) +
      ovStat('RSI15M',  (d.rsi15m ?? '—').toString()) +
      ovStat('ADX',     (d.adx1h ?? '—').toString()) +
      ovStat('BID%',    (d.bid_pct ?? '—').toString()) +
      ovStat('ASK%',    (d.ask_pct ?? '—').toString()) +
      ovStat('Trend',   trend);

    // Trade info
    const tradeInfo = document.getElementById('ov-trade-info');
    if (trade) {
      const pnl    = calcUnrealisedPnl(trade, price);
      const pnlCls = pnl >= 0 ? 'pnl-pos' : 'pnl-neg';
      tradeInfo.innerHTML =
        '<div style="background:var(--card);border-radius:6px;padding:10px;margin-bottom:12px">' +
          '<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">' +
            '<span style="font-weight:700">' + trade.direction + '</span>' +
            '<span style="color:var(--muted);font-size:11px">' + trade.tier + ' ' + trade.leverage + 'x</span>' +
            '<span class="' + pnlCls + '" style="margin-left:auto;font-weight:700">' + (pnl>=0?'+':'') + '$' + pnl.toFixed(2) + '</span>' +
          '</div>' +
          '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:11px">' +
            '<span>Entry: ' + formatPrice(trade.entry_price) + '</span>' +
            '<span>SL: <span style="color:var(--red)">' + formatPrice(trade.sl_price) + '</span></span>' +
            '<span>TP1: <span style="color:var(--green)">' + formatPrice(trade.tp1_price) + '</span></span>' +
            '<span>TP2: <span style="color:var(--green)">' + formatPrice(trade.tp2_price) + '</span></span>' +
          '</div>' +
          (trade.tp1_hit ? '<div style="margin-top:6px"><span class="tp1-badge">TP1 ✓ — SL moved to BE</span></div>' : '') +
        '</div>';
    } else {
      tradeInfo.innerHTML = '';
    }

    // Actions
    const actions = document.getElementById('ov-actions');
    if (trade) {
      actions.innerHTML =
        '<button class="btn btn-close"  onclick="closeTradeBtn('' + trade.id + '',false)">CLOSE MEXC</button>' +
        '<button class="btn btn-force"  onclick="closeTradeBtn('' + trade.id + '',true)">FORCE CLOSE</button>';
    } else {
      const longStyle  = 'background:var(--green);color:#000';
      const shortStyle = 'background:var(--red);color:#fff';
      actions.innerHTML =
        '<button class="btn" style="' + longStyle  + '" onclick="openTradeBtn('' + sym + '','LONG')" >OPEN MEXC LONG</button>' +
        '<button class="btn" style="' + shortStyle + '" onclick="openTradeBtn('' + sym + '','SHORT')">OPEN MEXC SHORT</button>';
    }
  }

  async function openTradeBtn(sym, dir) {
    if (!confirm('Open paper ' + dir + ' trade on ' + sym.replace('_USDT','') + '?')) return;
    const r = await fetch('/api/paper/open', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({symbol: sym, direction: dir})
    });
    if (r.ok) {
      await fetchState();
      updateOverlay(sym, _state.pair_data?.[sym] || {}, _state.open_trades || []);
    }
  }

  function ovStat(label, val) {
    return '<div class="overlay-stat"><div class="lbl">' + label + '</div><div class="val">' + val + '</div></div>';
  }

  // ── Helpers ───────────────────────────────────────────────────────────────────
  function formatPrice(p) {
    if (!p) return '—';
    const n = parseFloat(p);
    if (isNaN(n)) return '—';
    if (n >= 1000)  return n.toFixed(2);
    if (n >= 10)    return n.toFixed(3);
    if (n >= 1)     return n.toFixed(4);
    if (n >= 0.01)  return n.toFixed(5);
    return n.toFixed(6);
  }

  function calcUnrealisedPnl(trade, currentPrice) {
    const d      = trade.direction;
    const entry  = trade.entry_price;
    const margin = trade.margin || 2000;
    const lev    = trade.leverage || 5;
    const posVal = margin * lev;
    const raw = d === 'LONG'
      ? (currentPrice - entry) / entry * posVal
      : (entry - currentPrice) / entry * posVal;
    return trade.tp1_hit ? raw / 2 : raw;
  }

  function fmtTime(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleString(); } catch(e) { return iso; }
  }

  function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }
  