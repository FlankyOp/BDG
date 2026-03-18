/* ============================================================
   CONSTANTS
============================================================ */
const RUNTIME_CONFIG = window.BDG_CONFIG || {};
const DRAW_BASE = RUNTIME_CONFIG.drawBase || 'https://draw.ar-lottery01.com';

const NUMBER_COLOR_MAP = {
  0: 'Red',
  1: 'Green',
  2: 'Red',
  3: 'Green',
  4: 'Red',
  5: 'Violet',
  6: 'Red',
  7: 'Green',
  8: 'Red',
  9: 'Green',
};

const DEFAULT_GAME_CONFIGS = {
  WinGo_1M: { name: 'WinGo 1 Min', intervalMs: 60_000 },
  WinGo_3M: { name: 'WinGo 3 Min', intervalMs: 180_000 },
  WinGo_5M: { name: 'WinGo 5 Min', intervalMs: 300_000 },
};

const GAME_CONFIGS = {
  ...DEFAULT_GAME_CONFIGS,
  ...(RUNTIME_CONFIG.gameConfigs || {}),
};

/* ============================================================
   FIREBASE CONFIGURATION
============================================================ */
// IMPORTANT: REPLACE WITH YOUR ACTUAL FIREBASE CONFIG
const firebaseConfig = RUNTIME_CONFIG.firebase || {
  apiKey: "AIzaSyAJBUpptDCAxMOxbX6WjKhiedKmO_zdxH4",
  authDomain: "flankygod-bdg.firebaseapp.com",
  databaseURL: "https://flankygod-bdg-default-rtdb.firebaseio.com",
  projectId: "flankygod-bdg",
  storageBucket: "flankygod-bdg.firebasestorage.app",
  messagingSenderId: "338443538676",
  appId: "1:338443538676:web:bb3463404c8975a22bcea1",
  measurementId: "G-TKTDT0VQTX"
};

// Initialize Firebase
if (typeof firebase !== 'undefined') {
  firebase.initializeApp(firebaseConfig);
  if (typeof firebase.analytics === 'function') {
    firebase.analytics();
  }
}
const db = typeof firebase !== 'undefined' ? firebase.database() : null;

/* ============================================================
   STATE
============================================================ */
let _state = {
  gameCode: 'WinGo_1M',
  liveData: null,
  historyList: [],
  draws: [],
  manualOverride: false,
  countdownTimer: null,
  pollTimer: null,
  endTime: null,
  predictionResult: null,
  lastPeriodSeen: null,
  fallbackMode: false,
  fallbackReason: '',
  apiInFlight: false,
  lastHistoryKey: '',
  firebaseFallbackTimer: null,
  firebaseRecoveryTimer: null,
  firebaseSessionId: 0,
};

/* ============================================================
   UTILITIES
============================================================ */
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function safeDiv(a, b) { return b === 0 ? 0 : a / b; }
function normalizeColorName(value) {
  if (!value) return 'Red';
  const c = String(value).trim().toLowerCase();
  if (c.includes('violet')) return 'Violet';
  if (c.includes('green')) return 'Green';
  return 'Red';
}
function colorBarHex(color) {
  return color === 'Red' ? '#FF4444'
       : color === 'Green' ? '#44CC66'
       : color === 'Violet' ? '#A855F7' : '#7C3AED';
}
function apiColorToJs(apiColor) {
  return normalizeColorName(apiColor);
}

function numberToColor(n) {
  return NUMBER_COLOR_MAP[Number(n)] || 'Red';
}

function numberToSize(n) {
  return Number(n) >= 5 ? 'Big' : 'Small';
}

function toPct(score) {
  return `${(score * 100).toFixed(1)}%`;
}

function issuePlusOne(issue) {
  try {
    if (!issue) return '-';
    return (BigInt(String(issue)) + 1n).toString();
  } catch {
    return '-';
  }
}

function normalizeApiHistory(payload) {
  const rows = payload?.data?.list;
  if (!Array.isArray(rows)) return [];

  return rows
    .map((r) => {
      const number = Number(r?.number);
      if (!Number.isFinite(number) || number < 0 || number > 9) return null;
      return {
        issueNumber: String(r.issueNumber ?? r.period ?? ''),
        number,
        color: normalizeColorName(r.color || numberToColor(number)),
      };
    })
    .filter(Boolean);
}

function buildPredictionFromHistory(history) {
  const counts = {};
  const scores = {};

  for (let i = 0; i <= 9; i += 1) {
    counts[i] = 0;
    scores[i] = 0;
  }

  history.forEach((h, idx) => {
    const n = Number(h.number);
    if (!Number.isFinite(n) || n < 0 || n > 9) return;
    counts[n] += 1;

    // Recency-weighted score so recent rounds influence rank more.
    const weight = Math.max(0.2, 1 - (idx * 0.03));
    scores[n] += weight;
  });

  const totalScore = Object.values(scores).reduce((a, b) => a + b, 0) || 1;
  const rankings = Object.keys(scores)
    .map((k) => {
      const n = Number(k);
      const score = scores[n] / totalScore;
      return {
        number: n,
        score,
        color: numberToColor(n),
        size: numberToSize(n),
      };
    })
    .sort((a, b) => b.score - a.score);

  const p1 = rankings[0];
  const p2 = rankings[1];
  const p3 = rankings[2];

  const recent = history.slice(0, 8);
  const bigCount = recent.filter((h) => numberToSize(h.number) === 'Big').length;
  const sizePattern = bigCount >= 6
    ? 'Big trend active'
    : bigCount <= 2
      ? 'Small trend active'
      : 'No strong pattern detected';

  const colorRecent = recent.map((h) => numberToColor(h.number));
  const greenCount = colorRecent.filter((c) => c === 'Green').length;
  const redCount = colorRecent.filter((c) => c === 'Red').length;
  const colorPattern = greenCount >= 6
    ? 'Green dominant'
    : redCount >= 6
      ? 'Red dominant'
      : 'Mixed';

  return {
    primary_prediction: {
      number: p1.number,
      color: p1.color,
      size: p1.size,
      accuracy: toPct(p1.score),
    },
    alternative_prediction: {
      number: p2.number,
      color: p2.color,
      size: p2.size,
      accuracy: toPct(p2.score),
    },
    backup_prediction: {
      number: p3.number,
      color: p3.color,
      size: p3.size,
      accuracy: toPct(p3.score),
    },
    strong_possibility: {
      number: p3.number,
      color: p3.color,
      size: p3.size,
      accuracy: toPct(p3.score),
    },
    trend_analysis: {
      size_pattern: sizePattern,
      color_pattern: colorPattern,
      active_streak: 'Adaptive from latest rounds',
      detected_cycle: 'No strong cycle detected',
    },
    all_rankings: rankings,
    number_frequency: counts,
    summary: {
      best_bet: `NUMBER ${p1.number} (${p1.color}, ${p1.size})`,
      alternative_bet: `NUMBER ${p2.number} (${p2.color}, ${p2.size})`,
      backup_bet: `NUMBER ${p3.number} (${p3.color}, ${p3.size})`,
      combined_strategy: `Play ${p1.number} first, hedge with ${p2.number} if needed.`,
    },
    probability_explanation: `Generated from ${history.length} latest live rounds (fallback mode).`,
    timestamp: new Date().toISOString(),
  };
}

/* ============================================================
   FIREBASE LISTENERS
============================================================ */
let gameStateRef = null;
let predictionRef = null;

function clearFirebaseTimers() {
  if (_state.firebaseFallbackTimer) {
    clearTimeout(_state.firebaseFallbackTimer);
    _state.firebaseFallbackTimer = null;
  }
  if (_state.firebaseRecoveryTimer) {
    clearInterval(_state.firebaseRecoveryTimer);
    _state.firebaseRecoveryTimer = null;
  }
}

function stopApiPolling() {
  if (_state.pollTimer) {
    clearInterval(_state.pollTimer);
    _state.pollTimer = null;
  }
  _state.apiInFlight = false;
}

async function pollFromApi() {
  if (_state.apiInFlight) return;
  _state.apiInFlight = true;
  const gc = _state.gameCode;
  try {
    const url = `${DRAW_BASE}/WinGo/${gc}/GetHistoryIssuePage.json?pageSize=120&pageNo=1`;
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`API ${res.status}`);

    const payload = await res.json();
    const history = normalizeApiHistory(payload);
    if (!history.length) throw new Error('No history rows');

    const historyKey = history
      .slice(0, 10)
      .map((h) => `${h.issueNumber}:${h.number}`)
      .join('|');

    if (historyKey === _state.lastHistoryKey) {
      setLive(true);
      updateStatusBar('success', `Live via direct API at ${new Date().toLocaleTimeString()}`);
      return;
    }
    _state.lastHistoryKey = historyKey;

    const live = {
      next: { issueNumber: issuePlusOne(history[0].issueNumber) },
      current: { endTime: Date.now() + 45_000 },
    };

    _state.liveData = live;
    _state.historyList = history;
    _state.endTime = live.current.endTime;

    updateGameInfo(live, history);
    setLive(true);
    updateStatusBar('success', `Live via direct API at ${new Date().toLocaleTimeString()}`);

    const pred = buildPredictionFromHistory(history);
    _state.predictionResult = pred;
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('results-section').classList.add('visible');
    renderCards(pred);
    renderTrend(pred);
    renderProbBars(pred.all_rankings);
    renderFreqChart(pred.number_frequency);
    renderSummary(pred);
    renderTimestamp(pred.timestamp);
  } catch (err) {
    setLive(false);
    updateStatusBar('error', `Data fetch failed: ${err.message}`);
  } finally {
    _state.apiInFlight = false;
  }
}

function startApiPolling(reason) {
  if (_state.fallbackMode) return;

  _state.fallbackMode = true;
  _state.fallbackReason = reason || 'Firebase unavailable';
  clearFirebaseTimers();
  if (gameStateRef) gameStateRef.off();
  if (predictionRef) predictionRef.off();
  stopApiPolling();

  updateStatusBar('error', `${_state.fallbackReason}. Switching to direct API...`);
  pollFromApi();

  const interval = Math.min(5_000, Math.max(2_000, Math.floor((GAME_CONFIGS[_state.gameCode]?.intervalMs || 60_000) / 20)));
  _state.pollTimer = setInterval(pollFromApi, interval);

  if (db) {
    _state.firebaseRecoveryTimer = setInterval(() => {
      if (_state.fallbackMode) {
        setupFirebaseListeners();
      }
    }, 60_000);
  }
}

function setupFirebaseListeners() {
  if (!db) {
    console.error("Firebase not initialized. Cannot setup listeners.");
    startApiPolling('Firebase not configured');
    return;
  }

  _state.fallbackMode = false;
  _state.fallbackReason = '';
  _state.lastHistoryKey = '';
  _state.firebaseSessionId += 1;
  const sessionId = _state.firebaseSessionId;
  clearFirebaseTimers();
  stopApiPolling();
  
  const gc = _state.gameCode;
  
  // Cleanup old listeners
  if (gameStateRef) gameStateRef.off();
  if (predictionRef) predictionRef.off();
  
  updateStatusBar('success', 'Connecting to Firebase...');
  _state.firebaseFallbackTimer = setTimeout(() => {
    if (sessionId !== _state.firebaseSessionId) return;
    if (!_state.historyList.length && !_state.predictionResult) {
      startApiPolling('Firebase feed not available');
    }
  }, 1800);
  
  // Listen to Game State (countdown, recent history)
  gameStateRef = db.ref(`/game_state/${gc}`);
  gameStateRef.on('value', (snapshot) => {
    const data = snapshot.val();
    if (!data) {
      startApiPolling('No Firebase game_state data');
      return;
    }

    if (sessionId !== _state.firebaseSessionId) return;
    clearFirebaseTimers();
    
    _state.liveData = data.live;
    _state.historyList = data.recent_history || [];
    _state.endTime = data.live?.current?.endTime || null;
    
    setLive(true);
    updateGameInfo(data.live, _state.historyList);
    updateStatusBar('success', `Synced at ${new Date().toLocaleTimeString()}`);
  }, (error) => {
    setLive(false);
    startApiPolling(`DB error: ${error.message}`);
  });
  
  // Listen to Predictions
  predictionRef = db.ref(`/predictions/${gc}`);
  predictionRef.on('value', (snapshot) => {
    const pred = snapshot.val();
    if (!pred) {
      startApiPolling('No Firebase prediction data');
      return;
    }

    if (sessionId !== _state.firebaseSessionId) return;
    clearFirebaseTimers();
    
    _state.predictionResult = pred;
    
    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('results-section').classList.add('visible');

    renderCards(pred);
    renderTrend(pred);
    renderProbBars(pred.all_rankings);
    renderFreqChart(pred.number_frequency);
    renderSummary(pred);
    renderTimestamp(pred.timestamp);
  });
}

// Deprecated polling mechanics replaced by Firebase listeners.
async function pollData() { }

/* ============================================================
   COUNTDOWN & TIMERS
============================================================ */
function startCountdown() {
  if (_state.countdownTimer) clearInterval(_state.countdownTimer);
  _state.countdownTimer = setInterval(tickCountdown, 250);
}

function tickCountdown() {
  if (!_state.endTime) {
    setCountdown(0, 0);
    return;
  }
  const remaining = Math.max(0, Math.ceil((_state.endTime - Date.now()) / 1000));
  const m = Math.floor(remaining / 60);
  const s = remaining % 60;
  setCountdown(m, s);
}

function setCountdown(m, s) {
  const urgent = m === 0 && s <= 10;
  const digits = [Math.floor(m / 10), m % 10, Math.floor(s / 10), s % 10];
  const ids = ['cd-m1', 'cd-m0', 'cd-s1', 'cd-s0'];
  ids.forEach((id, i) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = digits[i];
    el.classList.toggle('urgent', urgent);
  });
}

function selectGame(gameCode) {
  if (_state.gameCode === gameCode) return;
  _state.gameCode = gameCode;
  _state.lastPeriodSeen = null;
  _state.predictionResult = null;
  _state.manualOverride = false;
  _state.endTime = null;
  _state.historyList = [];
  _state.fallbackMode = false;
  _state.lastHistoryKey = '';
  clearFirebaseTimers();
  stopApiPolling();

  document.querySelectorAll('.game-tab').forEach((t) => {
    t.classList.toggle('active', t.dataset.code === gameCode);
  });

  document.getElementById('recent-chips').innerHTML = '';
  document.getElementById('next-period').textContent = '-';
  document.getElementById('last-result').textContent = '-';

  setupFirebaseListeners();
}

function updateGameInfo(live, history) {
  const nextEl = document.getElementById('next-period');
  if (nextEl) nextEl.textContent = live.next?.issueNumber || '-';

  const lastEl = document.getElementById('last-result');
  if (history.length && lastEl) {
    const lr = history[0];
    const col = normalizeColorName(lr.color);
    lastEl.innerHTML = `<span style="color:${colorBarHex(col)}">${lr.number}</span> <span style="color:var(--text-2);font-size:.7rem">(${col})</span>`;
  }

  _state.endTime = live.current?.endTime || null;
  renderRecentChips(history.slice(0, 10));

  const lbl = document.getElementById('data-source-label');
  if (lbl) lbl.textContent = `${GAME_CONFIGS[_state.gameCode]?.name || _state.gameCode} live`;
}


/* ============================================================
   RENDER
============================================================ */
function renderRecentChips(history) {
  const container = document.getElementById('recent-chips');
  if (!container) return;
  const prevFirst = container.querySelector('.chip')?.textContent;
  const newFirst = String(history[0]?.number);

  container.innerHTML = history.map((r, i) => {
    const col = normalizeColorName(r.color);
    const cls = `chip chip-${col}${i === 0 && newFirst !== prevFirst ? ' chip-new' : ''}`;
    return `<div class="${cls}" title="#${r.issueNumber} · ${r.number} (${col})">${r.number}</div>`;
  }).join('');

  const countEl = document.getElementById('history-count');
  if (countEl) countEl.textContent = `Last ${history.length}`;
}

function renderCards(pred) {
  const backupPrediction = pred.backup_prediction || pred.strong_possibility;
  const defs = [
    { key: 'primary_prediction', label: 'PRIMARY PREDICTION', cls: 'primary' },
    { key: 'alternative_prediction', label: 'ALTERNATIVE PREDICTION', cls: 'alternative' },
    { key: 'backup_prediction', label: 'BACKUP PREDICTION', cls: 'possibility', fallback: backupPrediction },
  ];

  const grid = document.getElementById('cards-grid');
  grid.innerHTML = defs.map(({ key, label, cls, fallback }) => {
    const p = pred[key] || fallback;
    if (!p) return '';
    const pct = parseFloat(p.accuracy);
    const bar = colorBarHex(p.color);
    const colorClass = p.color.toLowerCase();

    return `<div class="pred-card ${cls}">
      <div class="card-label label">${label}</div>
      <div class="number-circle number-hex color-${colorClass}">${p.number}</div>
      <div class="card-meta">
        <span class="badge badge-${p.color}">${p.color}</span>
        <span class="badge badge-${p.size}">${p.size}</span>
      </div>
      <div class="accuracy-row"><span class="label">Accuracy</span><span class="accuracy-pct">${p.accuracy}</span></div>
      <div class="progress-track"><div class="progress-fill" style="background:${bar}" data-pct="${pct}"></div></div>
    </div>`;
  }).join('');

  requestAnimationFrame(() => {
    grid.querySelectorAll('.progress-fill').forEach((el) => { el.style.width = `${el.dataset.pct}%`; });
  });
}

function renderTrend(pred) {
  const t = pred.trend_analysis;
  document.getElementById('trend-panel').innerHTML = [
    ['Size Pattern', t.size_pattern],
    ['Color Pattern', t.color_pattern],
    ['Active Streak', t.active_streak],
    ['Detected Cycle', t.detected_cycle],
  ].map(([k, v]) => `<div class="trend-row"><span class="trend-key">${k}</span><span class="trend-val">${v}</span></div>`).join('');
}

function renderProbBars(rankings) {
  const maxS = rankings[0]?.score || 1;
  const top = rankings.slice(0, 6);
  const panel = document.getElementById('prob-panel');
  panel.innerHTML = `
    <div class="prob-crystal-layout">
      <div class="prob-crystal-bars">
        ${top.map((r) => {
          const hPct = Math.round((r.score / maxS) * 100);
          const color = r.color.toLowerCase();
          return `<div class="prob-crystal-col">
            <span class="prob-crystal-pct">${(r.score * 100).toFixed(1)}%</span>
            <div class="prob-crystal-bar color-${color}" data-height="${Math.max(hPct, 10)}"><span>${r.number}</span></div>
          </div>`;
        }).join('')}
      </div>
      <div class="prob-crystal-list">
        ${top.map((r) => `<div class="prob-crystal-item"><span class="num" style="color:${colorBarHex(r.color)}">${r.number}</span><span class="pct">${(r.score * 100).toFixed(1)}%</span></div>`).join('')}
      </div>
    </div>`;

  requestAnimationFrame(() => {
    panel.querySelectorAll('.prob-crystal-bar').forEach((el) => {
      const h = Number(el.dataset.height || 10);
      el.style.height = `${Math.round((h / 100) * 190)}px`;
    });
  });
}

function renderFreqChart(freq) {
  const vals = Object.values(freq);
  const maxV = Math.max(...vals) || 1;

  document.getElementById('freq-chart').innerHTML = Object.entries(freq).map(([num, cnt]) => {
    const h = Math.round(safeDiv(cnt, maxV) * 52);
    const col = colorBarHex(numberToColor(Number(num)));
    return `<div class="freq-bar-wrap">
      <div class="freq-bar" style="height:${h}px;background:${col};opacity:0.75"></div>
      <span class="freq-label">${num}</span>
    </div>`;
  }).join('');
}

function renderSummary(pred) {
  const s = pred.summary;
  const p = pred.primary_prediction;
  const al = pred.alternative_prediction;
  const st = pred.backup_prediction || pred.strong_possibility;
  const pill = (bet, col) => `<span class="bet-pill" style="border-color:${colorBarHex(col)};color:${colorBarHex(col)}">${bet}</span>`;

  document.getElementById('summary-banner').innerHTML = `
    <div class="panel-title"><span class="panel-title-dot"></span>Final Summary</div>
    <div class="summary-bets">
      <div class="summary-bet-item"><span class="bet-label">Best Bet</span>${pill(s.best_bet, p.color)}</div>
      ${al ? `<div class="summary-bet-item"><span class="bet-label">Alt Bet</span>${pill(s.alternative_bet, al.color)}</div>` : ''}
      ${st ? `<div class="summary-bet-item"><span class="bet-label">Backup</span>${pill(s.backup_bet, st.color)}</div>` : ''}
    </div>
    <div class="summary-strategy">${pred.probability_explanation}<br><strong>Strategy:</strong> ${s.combined_strategy}</div>`;
}

function renderTimestamp(ts) {
  const d = new Date(ts);
  document.getElementById('gen-timestamp').innerHTML = `<span>Predicted at ${d.toLocaleTimeString()} - ${d.toLocaleDateString()}</span>`;
}

/* ============================================================
   STATUS HELPERS
============================================================ */
function setLive(isLive) {
  const badge = document.getElementById('live-badge');
  const label = document.getElementById('live-label');
  const aiStatus = document.getElementById('ai-status');
  const aiSyncText = document.getElementById('ai-sync-text');
  if (!badge || !label) return;
  badge.classList.toggle('offline', !isLive);
  label.textContent = isLive ? 'LIVE' : 'Offline';
  if (aiStatus && aiSyncText) {
    aiStatus.classList.toggle('offline', !isLive);
    aiSyncText.textContent = isLive ? 'FLANKY-V12: SYNCED' : 'FLANKY-V12: LINK LOST';
  }
}

function updateStatusBar(type, msg) {
  const el = document.getElementById('fetch-status');
  if (!el) return;
  el.className = `status-bar ${type}`;
  el.textContent = msg;
}

/* ============================================================
   MANUAL PREDICT / OVERRIDE
============================================================ */
function manualPredict() {
  if (_state.fallbackMode) {
    pollFromApi();
    return;
  }
  updateStatusBar('error', 'Manual trigger disabled while Firebase mode is active.');
}

function toggleManualInput() {
  const body = document.getElementById('input-body');
  const icon = document.getElementById('input-toggle-icon');
  const isOpen = body.classList.toggle('open');
  icon.classList.toggle('open', isOpen);
}

function applyManualDraws() {
  const raw = document.getElementById('draws-input').value.trim();
  const nums = (raw.match(/\d+/g) || [])
    .map((x) => Number(x))
    .filter((x) => Number.isInteger(x) && x >= 0 && x <= 9);
  if (nums.length < 10) {
    document.getElementById('error-msg').classList.add('visible');
    return;
  }
  document.getElementById('error-msg').classList.remove('visible');

  const history = nums.map((n, i) => ({
    issueNumber: String(Date.now() - i),
    number: n,
    color: normalizeColorName(numberToColor(n)),
  }));

  const pred = buildPredictionFromHistory(history);
  _state.predictionResult = pred;
  document.getElementById('empty-state').style.display = 'none';
  document.getElementById('results-section').classList.add('visible');
  renderCards(pred);
  renderTrend(pred);
  renderProbBars(pred.all_rankings);
  renderFreqChart(pred.number_frequency);
  renderSummary(pred);
  renderTimestamp(pred.timestamp);
  updateStatusBar('success', 'Manual prediction generated.');
}

function clearManual() {
  document.getElementById('draws-input').value = '';
  document.getElementById('error-msg').classList.remove('visible');
}

startCountdown();
setupFirebaseListeners();
window.addEventListener('beforeunload', () => {
  clearFirebaseTimers();
  stopApiPolling();
  if (gameStateRef) gameStateRef.off();
  if (predictionRef) predictionRef.off();
});
;
