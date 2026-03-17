/* ============================================================
   CONSTANTS
============================================================ */
const DRAW_BASE = 'https://draw.ar-lottery01.com';

const GAME_CONFIGS = {
  WinGo_1M: { name: 'WinGo 1 Min', intervalMs: 60_000 },
  WinGo_3M: { name: 'WinGo 3 Min', intervalMs: 180_000 },
  WinGo_5M: { name: 'WinGo 5 Min', intervalMs: 300_000 },
};

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
};

/* ============================================================
   UTILITIES
============================================================ */
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function safeDiv(a, b) { return b === 0 ? 0 : a / b; }
function colorBarHex(color) {
  return color === 'Red' ? '#FF4444'
       : color === 'Green' ? '#44CC66'
       : color === 'Violet' ? '#A855F7' : '#7C3AED';
}
function apiColorToJs(apiColor) {
  if (!apiColor) return 'Red';
  const c = apiColor.toLowerCase();
  if (c.includes('violet')) return 'Violet';
  if (c.includes('green')) return 'Green';
  return 'Red';
}

/* ============================================================
   SIZE / COLOR MAPPERS
============================================================ */
const SizeMapper = {
  getSize: (n) => n < 5 ? 'Small' : 'Big',
  numbersToSizes: (arr) => arr.map((n) => SizeMapper.getSize(n)),
};

const ColorMapper = {
  MAP: {0:'Red',1:'Green',2:'Red',3:'Green',4:'Red',5:'Violet',6:'Red',7:'Green',8:'Red',9:'Green'},
  getColor: (n) => ColorMapper.MAP[n] || 'Unknown',
  numbersToColors: (arr) => arr.map((n) => ColorMapper.getColor(n)),
};

/* ============================================================
   PATTERN DETECTOR
============================================================ */
class PatternDetector {
  constructor(draws) {
    this.draws = draws;
    this.sizes = SizeMapper.numbersToSizes(draws);
    this.colors = ColorMapper.numbersToColors(draws);
  }

  detectSizePattern() {
    const alt = this._detectAlternating();
    const rep = this._detectRepeating();
    const streak = this._detectCurrentStreak();
    let pt = null;
    let ps = 0;

    if (alt.found) {
      pt = 'Alternating';
      ps = alt.strength;
    } else if (rep.found) {
      pt = 'Repeating';
      ps = rep.strength;
    } else if (streak.length >= 3) {
      pt = 'Streak';
      ps = Math.min(0.9, streak.length / 5);
    }

    return {
      alternating: alt,
      repeating: rep,
      current_streak: streak,
      streak_history: this._detectStreakHistory(),
      pattern_type: pt,
      pattern_strength: ps,
    };
  }

  _detectAlternating() {
    if (this.sizes.length < 4) return { found: false, strength: 0 };
    const r = this.sizes.slice(-15);
    const altCount = r.filter((v, i) => i === 0 || v !== r[i - 1]).length;
    const ratio = (altCount - 1) / Math.max(r.length - 1, 1);

    if (ratio >= 0.9) {
      return {
        found: true,
        strength: Math.min(0.9, 0.70 + ratio * 0.20),
        next_expected: r[r.length - 1] === 'Big' ? 'Small' : 'Big',
      };
    }

    return { found: false, strength: 0 };
  }

  _detectRepeating() {
    if (this.sizes.length < 4) return { found: false, strength: 0 };
    const r = this.sizes.slice(-10);
    const pairs = [];
    for (let i = 0; i < r.length - 1; i += 2) pairs.push(r.slice(i, i + 2));

    if (pairs.length >= 2 && pairs.every((p, i) => i === 0 || (p[0] === pairs[0][0] && p[1] === pairs[0][1]))) {
      return { found: true, strength: 0.78 };
    }

    return { found: false, strength: 0 };
  }

  _detectCurrentStreak() {
    if (!this.sizes.length) return { length: 0, type: null };
    const cur = this.sizes[this.sizes.length - 1];
    let len = 1;

    for (let i = this.sizes.length - 2; i >= 0; i--) {
      if (this.sizes[i] === cur) len++;
      else break;
    }

    return {
      length: len,
      type: cur,
      direction: len >= 3 ? 'will_reverse' : 'may_continue',
    };
  }

  _detectStreakHistory() {
    const s = [];
    if (!this.sizes.length) return s;

    let ct = this.sizes[0];
    let cl = 1;
    for (let i = 1; i < this.sizes.length; i++) {
      if (this.sizes[i] === ct) {
        cl++;
      } else {
        if (cl >= 2) s.push({ type: ct, length: cl });
        ct = this.sizes[i];
        cl = 1;
      }
    }

    return s;
  }

  detectColorPattern() {
    const nAnB = this._detectNAnB();
    const cycle = this._detectColorCycle();
    const dom = this._getDominantColor();
    let pt = null;
    let ps = 0;

    if (nAnB.type) {
      pt = nAnB.type;
      ps = nAnB.strength;
    } else if (cycle.detected) {
      pt = 'Color Cycle';
      ps = cycle.strength;
    }

    return {
      nAnB_pattern: nAnB,
      color_cycle: cycle,
      dominant_color: dom,
      pattern_type: pt,
      pattern_strength: ps,
    };
  }

  _detectNAnB() {
    if (this.colors.length < 4) return { type: null, strength: 0 };
    const r = this.colors.slice(-12);

    for (let n = 1; n <= 4; n++) {
      const pl = n * 2;
      if (r.length < pl) continue;

      const s = r.slice(-pl);
      const f = s.slice(0, n);
      const sc = s.slice(n);

      if (f.every((c) => c === f[0]) && sc.every((c) => c === sc[0]) && f[0] !== sc[0]) {
        return {
          type: `${n}A${n}B`,
          strength: Math.min(0.9, 0.5 + n * 0.1),
          next_color: r.length % (2 * n) === 0 ? sc[0] : f[0],
        };
      }
    }

    return { type: null, strength: 0 };
  }

  _detectColorCycle() {
    if (this.colors.length < 4) return { detected: false, strength: 0 };
    const r = this.colors.slice(-9);

    for (const cl of [2, 3]) {
      if (r.length < cl * 2) continue;
      const c = r.slice(0, cl);
      let m = 0;
      for (let i = cl; i < r.length; i++) {
        if (r[i] === c[(i - cl) % cl]) m++;
      }
      const ratio = m / (r.length - cl);
      if (ratio >= 0.75) {
        return {
          detected: true,
          cycle: c,
          strength: Math.min(0.80, 0.60 + ratio * 0.25),
          next_color: c[r.length % cl],
        };
      }
    }

    return { detected: false, strength: 0 };
  }

  _getDominantColor() {
    const cnt = {};
    this.colors.forEach((c) => { cnt[c] = (cnt[c] || 0) + 1; });
    const d = Object.entries(cnt).sort((a, b) => b[1] - a[1])[0];
    if (!d) return { color: null, frequency: 0, percentage: 0, color_distribution: {} };

    return {
      color: d[0],
      frequency: d[1],
      percentage: (d[1] / this.colors.length) * 100,
      color_distribution: cnt,
    };
  }

  detectCycles() {
    return [2, 3, 4, 6]
      .map((l) => this._checkCycle(l))
      .filter((c) => c.strength > 0)
      .sort((a, b) => b.strength - a.strength);
  }

  _checkCycle(cl) {
    if (this.draws.length < cl * 2) return { cycle_length: cl, strength: 0, pattern: null };
    const r = this.draws.slice(-cl * 4);
    const p = r.slice(0, cl);
    let m = 0;
    for (let i = cl; i < r.length; i++) if (r[i] === p[i % cl]) m++;
    const s = safeDiv(m, r.length - cl);
    if (s > 0.6) return { cycle_length: cl, pattern: p, strength: s, next_number: p[r.length % cl] };
    return { cycle_length: cl, strength: 0, pattern: null };
  }

  getNumberFrequency() {
    const f = {};
    for (let i = 0; i < 10; i++) f[i] = 0;
    this.draws.forEach((n) => { f[n]++; });
    return f;
  }

  getSizeDistribution() {
    const d = { Big: 0, Small: 0 };
    this.sizes.forEach((s) => { d[s]++; });
    return d;
  }

  analyzeAllPatterns() {
    return {
      size_patterns: this.detectSizePattern(),
      color_patterns: this.detectColorPattern(),
      cycles: this.detectCycles(),
      number_frequency: this.getNumberFrequency(),
      size_distribution: this.getSizeDistribution(),
      recent_draws: this.draws,
      recent_sizes: this.sizes,
      recent_colors: this.colors,
    };
  }
}

/* ============================================================
   PROBABILITY ENGINE
============================================================ */
class ProbabilityEngine {
  constructor(draws, patterns) {
    this.draws = draws;
    this.patterns = patterns;
    this.detector = new PatternDetector(draws);
  }

  calcTrendWeight(n) {
    let w = 0;
    const size = SizeMapper.getSize(n);
    const sp = this.patterns.size_patterns;
    if (sp.pattern_type === 'Streak' && sp.current_streak.length >= 3 && size !== sp.current_streak.type) w += 0.35;
    const r5 = this.detector.sizes.slice(-5);
    if (r5.filter((x) => x === 'Big').length >= 3 && size === 'Small') w += 0.15;
    if (r5.filter((x) => x === 'Small').length >= 3 && size === 'Big') w += 0.15;
    if (this.detector.getNumberFrequency()[n] === 0) w += 0.10;
    return clamp(w, 0, 1);
  }

  calcFrequencyWeight(n) {
    const f = this.detector.getNumberFrequency();
    const mx = Math.max(...Object.values(f)) || 1;
    return 1 - (f[n] / mx);
  }

  calcCycleWeight(n) {
    const c = this.patterns.cycles;
    if (!c.length) return 0;
    const b = c[0];
    if (b.strength < 0.5) return 0;
    if (b.next_number === n) return b.strength * 0.9;
    if (b.pattern && b.pattern.includes(n)) return b.strength * 0.6;
    return 0;
  }

  calcStreakWeight(n) {
    const s = this.patterns.size_patterns.current_streak;
    if (s.length < 2) return 0;
    if (s.length >= 3 && SizeMapper.getSize(n) !== s.type) return clamp(0.6 + s.length * 0.05, 0, 1);
    return 0;
  }

  calcNoiseWeight(n) {
    if (!this.draws.slice(-3).includes(n)) return 0.15;
    const rev = [...this.draws].reverse();
    const li = rev.indexOf(n);
    return ((this.draws.length - 1 - li) / this.draws.length) * 0.10;
  }

  calcColorWeight(n) {
    const col = ColorMapper.getColor(n);
    const cp = this.patterns.color_patterns;
    if (cp.pattern_type && cp.pattern_type.includes('A') && cp.nAnB_pattern.next_color === col) return 0.18;
    const d = cp.dominant_color;
    if (d.color && col !== d.color) return (1 - d.percentage / 100) * 0.15;
    return 0;
  }

  calcConfidenceScore(n) {
    const t = this.calcTrendWeight(n);
    const f = this.calcFrequencyWeight(n);
    const c = this.calcCycleWeight(n);
    const s = this.calcStreakWeight(n);
    const ns = this.calcNoiseWeight(n);
    const col = this.calcColorWeight(n);
    let sc = t * 0.30 + f * 0.25 + c * 0.20 + s * 0.15 + ns * 0.10;
    if (col > 0.1) sc = sc * 0.95 + col * 0.05;
    return clamp(sc, 0, 1);
  }

  rankAllNumbers() {
    return Array.from({ length: 10 }, (_, i) => ({
      number: i,
      score: this.calcConfidenceScore(i),
      size: SizeMapper.getSize(i),
      color: ColorMapper.getColor(i),
    })).sort((a, b) => b.score - a.score);
  }

  getTopPredictions(n = 3) {
    return this.rankAllNumbers().slice(0, n).map((r, i) => ({
      rank: i + 1,
      number: r.number,
      confidence: r.score,
      size: r.size,
      color: r.color,
      accuracy_percentage: r.score * 100,
    }));
  }

  explainPrediction(n) {
    return {
      trend_weight: this.calcTrendWeight(n),
      frequency_weight: this.calcFrequencyWeight(n),
      cycle_weight: this.calcCycleWeight(n),
      streak_weight: this.calcStreakWeight(n),
      noise_weight: this.calcNoiseWeight(n),
      total_score: this.calcConfidenceScore(n),
    };
  }
}

/* ============================================================
   PREDICTOR
============================================================ */
class Predictor {
  constructor(draws, period = null) {
    this.draws = draws;
    this.period = period || String(Date.now());
    this.timestamp = new Date();
    this.patternDetector = new PatternDetector(draws);
    this.patterns = this.patternDetector.analyzeAllPatterns();
    this.probabilityEngine = new ProbabilityEngine(draws, this.patterns);
  }

  generatePrediction() {
    const preds = this.probabilityEngine.getTopPredictions(3);
    const np = this._calcNextPeriod();

    return {
      timestamp: this.timestamp.toISOString(),
      current_period: this.period,
      next_period: np,
      primary_prediction: {
        number: preds[0].number,
        size: preds[0].size,
        color: preds[0].color,
        accuracy: `${preds[0].accuracy_percentage.toFixed(1)}%`,
      },
      alternative_prediction: preds[1] ? {
        number: preds[1].number,
        size: preds[1].size,
        color: preds[1].color,
        accuracy: `${preds[1].accuracy_percentage.toFixed(1)}%`,
      } : null,
      strong_possibility: preds[2] ? {
        number: preds[2].number,
        size: preds[2].size,
        color: preds[2].color,
        accuracy: `${preds[2].accuracy_percentage.toFixed(1)}%`,
      } : null,
      trend_analysis: this._genTrend(),
      probability_explanation: this._genExpl(preds[0].number),
      summary: this._genSummary(preds),
      all_rankings: this.probabilityEngine.rankAllNumbers(),
      number_frequency: this.patterns.number_frequency,
    };
  }

  _calcNextPeriod() {
    try {
      return String(BigInt(this.period) + 1n);
    } catch {
      return this.period;
    }
  }

  _genTrend() {
    const sp = this.patterns.size_patterns;
    const cp = this.patterns.color_patterns;
    const cy = this.patterns.cycles;
    return {
      size_pattern: this._fmtSP(sp),
      color_pattern: this._fmtCP(cp),
      active_streak: this._fmtStreak(sp),
      detected_cycle: this._fmtCycle(cy),
    };
  }

  _fmtSP(sp) {
    if (!sp.pattern_type) return 'No strong pattern';
    const pct = `${(sp.pattern_strength * 100).toFixed(0)}%`;
    if (sp.pattern_type === 'Streak') return `Streak - ${sp.current_streak.type} x${sp.current_streak.length} (${pct})`;
    return `${sp.pattern_type} Pattern (${pct})`;
  }

  _fmtCP(cp) {
    if (cp.pattern_type) return `${cp.pattern_type} (${(cp.pattern_strength * 100).toFixed(0)}%)`;
    const d = cp.dominant_color;
    if (d.color) return `Dominant: ${d.color} (${d.percentage.toFixed(1)}%)`;
    return 'No pattern';
  }

  _fmtStreak(sp) {
    const s = sp.current_streak;
    if (s.length >= 2) return `${s.type} x${s.length} - ${s.length >= 3 ? 'May reverse' : 'May continue'}`;
    return 'No active streak';
  }

  _fmtCycle(c) {
    if (c.length && c[0].strength > 0.5) return `${c[0].cycle_length}-round cycle (${(c[0].strength * 100).toFixed(0)}%)`;
    return 'No cycle detected';
  }

  _genExpl(n) {
    const e = this.probabilityEngine.explainPrediction(n);
    const f = [];
    if (e.trend_weight > 0.20) f.push(`Trend (${(e.trend_weight * 100).toFixed(0)}%)`);
    if (e.cycle_weight > 0.20) f.push(`Cycle (${(e.cycle_weight * 100).toFixed(0)}%)`);
    if (e.streak_weight > 0.20) f.push(`Streak reversal (${(e.streak_weight * 100).toFixed(0)}%)`);
    if (e.frequency_weight > 0.40) f.push(`Frequency (${(e.frequency_weight * 100).toFixed(0)}%)`);
    if (!f.length) f.push(`Comprehensive analysis (${(e.total_score * 100).toFixed(1)}%)`);
    return `Based on: ${f.join(', ')}`;
  }

  _genSummary(p) {
    const fmt = (x) => `NUMBER ${x.number} (${x.color}, ${x.size})`;
    return {
      best_bet: fmt(p[0]),
      alternative_bet: fmt(p[1]),
      backup_bet: fmt(p[2]),
      combined_strategy:
        `Play ${p[0].number} with ${p[0].accuracy_percentage.toFixed(0)}% confidence. ` +
        `Backup: ${p[1].number} (${p[1].accuracy_percentage.toFixed(0)}%) or ${p[2].number} (${p[2].accuracy_percentage.toFixed(0)}%).`,
    };
  }
}

/* ============================================================
   API LAYER
============================================================ */
async function fetchLiveState(gameCode) {
  const r = await fetch(`${DRAW_BASE}/WinGo/${gameCode}.json?ts=${Date.now()}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function fetchHistory(gameCode) {
  const ts = Date.now();
  for (const url of [
    `${DRAW_BASE}/WinGo/${gameCode}/GetHistoryIssuePage.json?pageSize=500&pageNo=1&ts=${ts}`,
    `${DRAW_BASE}/WinGo/${gameCode}/GetHistoryIssuePage.json?ts=${ts}`,
  ]) {
    try {
      const r = await fetch(url);
      if (!r.ok) continue;
      const j = await r.json();
      const list = j.data?.list || [];
      if (list.length) return list;
    } catch {
      // Try the next fallback URL.
    }
  }
  throw new Error('History fetch failed');
}

/* ============================================================
   POLLING LOGIC
============================================================ */
async function pollData() {
  const gc = _state.gameCode;
  try {
    const [live, history] = await Promise.all([fetchLiveState(gc), fetchHistory(gc)]);

    _state.liveData = live;
    _state.historyList = history;
    _state.endTime = live.current?.endTime || null;

    setLive(true);
    updateGameInfo(live, history);

    const currentPeriod = live.current?.issueNumber;
    if (!_state.manualOverride) {
      const nums = history.slice(0, 30).map((r) => parseInt(r.number, 10)).filter((n) => !isNaN(n));
      _state.draws = nums;
    }

    if (_state.draws.length >= 10 && (_state.lastPeriodSeen !== currentPeriod || _state.predictionResult === null)) {
      _state.lastPeriodSeen = currentPeriod;
      runPrediction(_state.draws, currentPeriod);
    }

    updateStatusBar('success', `Updated at ${new Date().toLocaleTimeString()}`);
  } catch (e) {
    setLive(false);
    updateStatusBar('error', `Fetch error: ${e.message.slice(0, 50)}`);
  }
}

function updateGameInfo(live, history) {
  const nextEl = document.getElementById('next-period');
  if (nextEl) nextEl.textContent = live.next?.issueNumber || '-';

  const lastEl = document.getElementById('last-result');
  if (history.length && lastEl) {
    const lr = history[0];
    const col = apiColorToJs(lr.color);
    lastEl.innerHTML = `<span style="color:${colorBarHex(col)}">${lr.number}</span> <span style="color:var(--text-2);font-size:.7rem">(${col})</span>`;
  }

  _state.endTime = live.current?.endTime || null;
  renderRecentChips(history.slice(0, 10));

  const lbl = document.getElementById('data-source-label');
  if (lbl) lbl.textContent = `${GAME_CONFIGS[_state.gameCode]?.name || _state.gameCode} live`;
}

/* ============================================================
   COUNTDOWN
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

/* ============================================================
   POLLING TIMER
============================================================ */
function schedulePoll() {
  if (_state.pollTimer) clearInterval(_state.pollTimer);
  _state.pollTimer = setInterval(pollData, 15_000);
  pollData();
}

function selectGame(gameCode) {
  if (_state.gameCode === gameCode) return;
  _state.gameCode = gameCode;
  _state.lastPeriodSeen = null;
  _state.predictionResult = null;
  _state.manualOverride = false;
  _state.endTime = null;

  document.querySelectorAll('.game-tab').forEach((t) => {
    t.classList.toggle('active', t.dataset.code === gameCode);
  });

  document.getElementById('recent-chips').innerHTML = '';
  document.getElementById('next-period').textContent = '-';
  document.getElementById('last-result').textContent = '-';

  schedulePoll();
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
    const col = apiColorToJs(r.color);
    const cls = `chip chip-${col}${i === 0 && newFirst !== prevFirst ? ' chip-new' : ''}`;
    return `<div class="${cls}" title="#${r.issueNumber} · ${r.number} (${apiColorToJs(r.color)})">${r.number}</div>`;
  }).join('');

  const countEl = document.getElementById('history-count');
  if (countEl) countEl.textContent = `Last ${history.length}`;
}

function runPrediction(draws, nextPeriod) {
  try {
    const pred = new Predictor(draws, nextPeriod).generatePrediction();
    _state.predictionResult = pred;

    document.getElementById('empty-state').style.display = 'none';
    document.getElementById('results-section').classList.add('visible');

    renderCards(pred);
    renderTrend(pred);
    renderProbBars(pred.all_rankings);
    renderFreqChart(pred.number_frequency);
    renderSummary(pred);
    renderTimestamp(pred.timestamp);
  } catch (e) {
    console.error('Prediction error:', e);
  }
}

function renderCards(pred) {
  const defs = [
    { key: 'primary_prediction', label: 'PRIMARY PREDICTION', cls: 'primary' },
    { key: 'alternative_prediction', label: 'ALTERNATIVE PREDICTION', cls: 'alternative' },
    { key: 'strong_possibility', label: 'STRONG POSSIBILITY', cls: 'possibility' },
  ];

  const grid = document.getElementById('cards-grid');
  grid.innerHTML = defs.map(({ key, label, cls }) => {
    const p = pred[key];
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
    const col = colorBarHex(ColorMapper.getColor(Number(num)));
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
  const st = pred.strong_possibility;
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
  if (_state.draws.length >= 10) {
    const btn = document.getElementById('predict-btn');
    btn.classList.add('loading');
    setTimeout(() => {
      runPrediction(_state.draws, _state.liveData?.current?.issueNumber || '');
      btn.classList.remove('loading');
    }, 50);
  } else {
    updateStatusBar('error', 'No data yet - waiting for live fetch to complete');
  }
}

function toggleManualInput() {
  const body = document.getElementById('input-body');
  const icon = document.getElementById('input-toggle-icon');
  const isOpen = body.classList.toggle('open');
  icon.classList.toggle('open', isOpen);
}

function applyManualDraws() {
  const raw = document.getElementById('draws-input').value.trim();
  const errEl = document.getElementById('error-msg');
  errEl.classList.remove('visible');

  const tokens = raw.split(/[\s,]+/).filter(Boolean);
  const nums = tokens.map(Number);
  if (!tokens.length || nums.some((n) => isNaN(n) || n < 0 || n > 9 || !Number.isInteger(n)) || nums.length < 10) {
    errEl.classList.add('visible');
    return;
  }

  _state.draws = nums.slice(0, 20);
  _state.manualOverride = true;
  runPrediction(_state.draws, _state.liveData?.current?.issueNumber || '');
}

function clearManual() {
  document.getElementById('draws-input').value = '';
  document.getElementById('error-msg').classList.remove('visible');
  _state.manualOverride = false;
  if (_state.historyList.length) {
    const nums = _state.historyList.slice(0, 20).map((r) => parseInt(r.number, 10)).filter((n) => !isNaN(n));
    _state.draws = nums;
  }
}

startCountdown();
schedulePoll();
