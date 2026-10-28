"""The single-page phone UI served by `ballout web` (HTML, CSS and JS inline)."""

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Ball Out Gamba</title>
<meta name="description" content="UFC fight history, live odds and betting analysis">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="BallOut">
<meta name="theme-color" content="#b2182c">
<link rel="apple-touch-icon" href="/icon.png">
<link rel="icon" href="/icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<style>
:root {
  --bg: #f4f4f6; --surface: #ffffff; --surface2: #ececf0; --text: #16171a; --muted: #6b6e76;
  --line: #dcdde2; --accent: #b2182c; --accent-ink: #ffffff; --good: #18864b; --good-bg: #e3f4ea;
  --bad: #b42318; --bad-bg: #fde8e6; --warn: #8a5a00; --warn-bg: #fff3d6; --a: #b2182c; --b: #2f5fb3;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #0f1012; --surface: #1a1b1f; --surface2: #24262b; --text: #f1f1f3; --muted: #9a9ca5;
    --line: #2e3036; --accent: #e0384f; --accent-ink: #ffffff; --good: #4cc68a; --good-bg: #13301f;
    --bad: #ff7b6e; --bad-bg: #3a1714; --warn: #f2c35b; --warn-bg: #352a0c; --a: #e0384f; --b: #6d9bf0;
  }
}
:root[data-theme="dark"] {
  --bg: #0f1012; --surface: #1a1b1f; --surface2: #24262b; --text: #f1f1f3; --muted: #9a9ca5;
  --line: #2e3036; --accent: #e0384f; --accent-ink: #ffffff; --good: #4cc68a; --good-bg: #13301f;
  --bad: #ff7b6e; --bad-bg: #3a1714; --warn: #f2c35b; --warn-bg: #352a0c; --a: #e0384f; --b: #6d9bf0;
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  -webkit-text-size-adjust: 100%; }
header { position: sticky; top: 0; z-index: 5; background: var(--surface); border-bottom: 1px solid var(--line);
  padding: calc(env(safe-area-inset-top) + 10px) 16px 10px; display: flex; align-items: center; gap: 8px; }
header h1 { font-size: 17px; margin: 0; flex: 1; letter-spacing: -0.01em; }
header h1 span { color: var(--accent); }
main { overflow-wrap: break-word; padding: 12px 16px calc(84px + env(safe-area-inset-bottom)); max-width: 760px; margin: 0 auto; }
nav { position: fixed; bottom: 0; left: 0; right: 0; z-index: 5; display: flex; background: var(--surface);
  border-top: 1px solid var(--line); padding-bottom: env(safe-area-inset-bottom); }
nav button { flex: 1; background: none; border: 0; color: var(--muted); padding: 10px 0 8px; font: inherit;
  font-size: 12px; display: flex; flex-direction: column; align-items: center; gap: 2px; }
nav button svg { width: 22px; height: 22px; }
nav button.on { color: var(--accent); font-weight: 600; }
section { display: none; } section.on { display: block; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 14px; margin: 0 0 12px; }
.card h2 { font-size: 16px; margin: 0 0 4px; } .card > h3:first-child { margin-top: 0; } .card h3 { font-size: 14px; margin: 14px 0 6px; color: var(--muted);
  text-transform: uppercase; letter-spacing: .04em; }
.muted { color: var(--muted); } .small { font-size: 13px; } .tiny { font-size: 12px; }
.row { display: flex; align-items: center; gap: 8px; } .row > .grow { flex: 1; min-width: 0; }
.between { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
input, select { font: inherit; font-size: 16px; color: var(--text); background: var(--surface2); border: 1px solid var(--line);
  border-radius: 10px; padding: 10px 12px; width: 100%; min-width: 0; }
label.check { display: flex; gap: 6px; align-items: center; font-size: 14px; color: var(--muted); }
label.check input { width: auto; }
.btn { font: inherit; font-weight: 600; border: 0; border-radius: 10px; padding: 10px 14px; background: var(--accent);
  color: var(--accent-ink); cursor: pointer; white-space: nowrap; }
.btn.ghost { background: var(--surface2); color: var(--text); }
.btn.small { padding: 6px 10px; font-size: 13px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.pill { display: inline-block; white-space: nowrap; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600;
  background: var(--surface2); color: var(--muted); }
.pill.good { background: var(--good-bg); color: var(--good); } .pill.bad { background: var(--bad-bg); color: var(--bad); }
.pill.warn { background: var(--warn-bg); color: var(--warn); }
.bar { display: flex; height: 8px; border-radius: 999px; overflow: hidden; background: var(--surface2); margin: 6px 0; }
.bar i { display: block; height: 100%; } .bar i.a { background: var(--a); } .bar i.b { background: var(--b); }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
table.tight { font-size: 13px; } table.tight td, table.tight th { padding: 6px 3px; }
th, td { padding: 6px 4px; border-bottom: 1px solid var(--line); text-align: right; vertical-align: top; }
th:first-child, td:first-child { text-align: left; } th { color: var(--muted); font-weight: 500; font-size: 12px; }
td.mid, th.mid { text-align: center; }
td:not(:first-child), th:not(:first-child) { white-space: nowrap; }
.scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.fight { border-top: 1px solid var(--line); padding: 10px 0; } .fight:first-of-type { border-top: 0; }
.name { font-weight: 600; } .ca { color: var(--a); } .cb { color: var(--b); }
a { color: var(--accent); text-decoration: none; } a:active { opacity: .6; }
.links { display: flex; flex-wrap: wrap; gap: 4px 14px; } .links a { font-size: 13px; white-space: nowrap; }
.list a.item, .list div.item { display: block; padding: 10px 0; border-bottom: 1px solid var(--line); color: var(--text); }
.err { color: var(--bad); } .spin { color: var(--muted); padding: 16px 0; }
.kv { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 12px; font-size: 14px; }
.kv div { display: flex; justify-content: space-between; border-bottom: 1px solid var(--line); padding: 4px 0; }
.kv div span:first-child { color: var(--muted); }
.big { font-size: 26px; font-weight: 700; letter-spacing: -0.02em; }
.ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.log { background: var(--surface2); border-radius: 10px; padding: 10px; font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  max-height: 220px; overflow-y: auto; white-space: pre-wrap; margin-top: 10px; }
.welcome { max-width: 560px; margin: 8vh auto 0; text-align: center; }
.welcome .logo { width: 72px; height: 72px; border-radius: 18px; }
.welcome h2 { font-size: 26px; margin: 16px 0 8px; letter-spacing: -0.02em; }
.welcome p { color: var(--muted); }
.welcome ul { text-align: left; color: var(--muted); font-size: 14px; padding-left: 20px; }
body.setup nav, body.setup header input, body.setup header .muted { display: none; }
body.setup main { padding-bottom: 24px; }
.bookgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 4px 12px; }
.bookgrid label { display: flex; gap: 8px; align-items: center; padding: 6px 0; font-size: 15px; }
.bookgrid label input { width: auto; }
details.lines { margin-top: 4px; } details.lines summary { cursor: pointer; list-style: none; }
details.lines summary::-webkit-details-marker { display: none; }
details.lines summary::before { content: "▸ "; } details.lines[open] summary::before { content: "▾ "; }
details.lines table { margin-top: 4px; max-width: 420px; }
.meter { position: relative; height: 10px; border-radius: 999px; background: var(--surface2); overflow: hidden; margin: 6px 0 4px; }
.meter i { position: absolute; inset: 0 auto 0 0; border-radius: 999px;
  background: linear-gradient(90deg, #2f9e66 0%, #c9a227 50%, #d9822b 70%, #c0392b 100%); background-size: var(--full, 100%) 100%; }
.hype-pill { font-size: 11px; padding: 1px 7px; margin-left: 6px; vertical-align: 1px; }
select.div { width: auto; padding: 6px 10px; font-size: 14px; }
.url { font: 600 17px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; user-select: all; word-break: break-all; }
@media (min-width: 900px) {
  header { padding-left: 24px; padding-right: 24px; }
  nav { top: 0; bottom: 0; right: auto; width: 200px; flex-direction: column; justify-content: flex-start; gap: 2px;
    border-top: 0; border-right: 1px solid var(--line); padding: 72px 10px 16px; }
  nav button { flex: 0 0 auto; flex-direction: row; gap: 10px; font-size: 15px; padding: 10px 12px; border-radius: 10px; justify-content: flex-start; }
  nav button.on { background: var(--surface2); }
  nav button svg { width: 20px; height: 20px; }
  header { z-index: 6; }
  main { margin-left: 200px; max-width: 980px; padding: 20px 28px 32px; }
  body.setup main { margin-left: auto; }
  .card { padding: 18px; }
}
</style>
</head>
<body>
<header>
  <h1>Ball Out <span>Gamba</span></h1>
  <span class="muted small">Bankroll $</span>
  <input id="bankroll" inputmode="decimal" placeholder="0" style="width:84px;padding:6px 8px">
</header>
<main>
  <section id="tab-cards">
    <div class="card">
      <div class="between"><h2>Upcoming UFC cards</h2><button class="btn small" id="load-cards">Refresh</button></div>
      <div class="row" style="flex-wrap:wrap;gap:14px;margin-top:6px">
        <label class="check"><input type="checkbox" id="opt-news"> Check fighter news</label>
        <label class="check"><input type="checkbox" id="opt-unsched"> Include undated fights</label>
        <select id="c-div" class="div"><option value="">All divisions</option></select>
      </div>
      <p class="muted tiny" style="margin:8px 0 0">Live lines via BestFightOdds. Best prices come from the sportsbooks you
        picked in Settings. "Ours" blends the stats model with the market. Value = 5%+ expected return at your best price.</p>
    </div>
    <div id="cards-out"></div>
  </section>

  <section id="tab-matchup">
    <div class="card">
      <h2>Matchup</h2>
      <div class="grid2" style="margin-top:8px">
        <input id="m-a" list="fighter-list" placeholder="Fighter A" autocomplete="off">
        <input id="m-b" list="fighter-list" placeholder="Fighter B" autocomplete="off">
        <input id="m-oa" placeholder="Odds A (-150)" inputmode="numbers-and-punctuation">
        <input id="m-ob" placeholder="Odds B (+130)" inputmode="numbers-and-punctuation">
      </div>
      <div class="between" style="margin-top:10px">
        <label class="check"><input type="checkbox" id="m-live" checked> Use live odds if booked</label>
        <button class="btn" id="m-go">Analyse</button>
      </div>
    </div>
    <div id="m-out"></div>
  </section>

  <section id="tab-fighters">
    <div class="card">
      <h2>Fighters</h2>
      <div class="row" style="margin-top:8px"><input id="f-q" class="grow" placeholder="Search any UFC fighter" autocomplete="off">
        <select id="f-div" class="div"><option value="">All divisions</option></select></div>
      <div id="f-results" class="list"></div>
    </div>
    <div id="f-out"></div>
    <div class="card">
      <div class="between"><h2>Top active fighters</h2>
        <select id="l-div" class="div"><option value="">All divisions</option></select></div>
      <div id="l-out" class="list"></div>
    </div>
  </section>

  <section id="tab-hype">
    <div class="card">
      <h2>Hype meter</h2>
      <p class="muted small" style="margin:2px 0 8px">How far the betting odds rate a fighter above what their fight stats
        support, weighted up for unbeaten fighters. 60+ is very hyped, 80+ is the fraud-check zone. Historically those fighters
        won 3-4 points less often than their odds implied (after the usual favourite bias). Most still win.</p>
      <div class="row" style="flex-wrap:wrap;gap:14px">
        <label class="check"><input type="checkbox" id="h-live" checked> Score booked fighters on their next fight's odds</label>
        <select id="h-div" class="div"><option value="">All divisions</option></select>
      </div>
      <details style="margin-top:10px"><summary class="small" style="cursor:pointer">The evidence</summary><div id="h-bt" class="scroll"></div></details>
    </div>
    <div id="h-out"></div>
  </section>

  <section id="tab-settings">
    <div class="card">
      <div class="between"><h2>Data</h2><button class="btn small" id="s-update">Update data</button></div>
      <div id="s-data" class="small muted">Loading…</div>
      <div id="s-log" class="log" hidden></div>
    </div>
    <div class="card">
      <h2>Sportsbooks</h2>
      <p class="muted small" style="margin:2px 0 10px">Pick the books you bet with. Best prices, expected return, stakes and value
        bets only use these. "Market %" always uses every sportsbook, because the consensus of all books is the most accurate probability.</p>
      <div id="s-books" class="bookgrid"></div>
      <h3>Prediction markets</h3>
      <div id="s-markets" class="bookgrid"></div>
      <p class="muted tiny" style="margin:6px 0 0">Prediction-market prices can be thin and jumpy, so they're off unless you pick them.</p>
      <div class="tiny" id="s-books-msg" style="margin-top:6px"></div>
    </div>
    <div class="card">
      <div class="between"><h2>Use it on your iPhone</h2><button class="btn small ghost" id="s-phone" hidden>Turn on</button></div>
      <div id="s-phone-out" class="small"></div>
    </div>
    <div class="card small muted">
      <h2 style="color:var(--text)">About</h2>
      Fight data: ufcstats.com (via Greco1899/scrape_ufc_stats). Odds: BestFightOdds and jansen88/ufc-data.
      News: Google News, ESPN, Sherdog. Estimates, not certainties - bet only what you can afford to lose.
      If gambling stops being fun, call 1-800-GAMBLER.
    </div>
  </section>

  <section id="tab-welcome">
    <div class="welcome">
      <img class="logo" src="/icon.png" alt="">
      <h2>Welcome to Ball Out Gamba</h2>
      <p>First, download the fight data: every UFC fight since 1994, round-by-round stats and betting lines
        since 2014. It takes about 10 minutes the first time and a few seconds after that.</p>
      <ul>
        <li>Live odds from every major sportsbook for upcoming cards, with value bets</li>
        <li>Matchup breakdowns, fighter profiles and links to watch their fights</li>
        <li>News checks for injuries, replacements and missed weight</li>
      </ul>
      <button class="btn" id="w-go" style="margin-top:8px">Download fight data</button>
      <div id="w-log" class="log" hidden style="text-align:left"></div>
    </div>
  </section>

  <section id="tab-news">
    <div class="card">
      <h2>News</h2>
      <div class="row" style="margin-top:8px"><input id="n-q" class="grow" list="fighter-list" placeholder="Fighter (blank = latest UFC news)">
        <button class="btn" id="n-go">Go</button></div>
      <p class="muted tiny" style="margin:8px 0 0">Flags: injury, withdrawal / replacement, weight, legal / suspension.</p>
    </div>
    <div id="n-out"></div>
  </section>
</main>
<datalist id="fighter-list"></datalist>

<nav>
  <button data-tab="cards"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M8 4v5M16 4v5"/></svg>Cards</button>
  <button data-tab="matchup"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="7" cy="12" r="4"/><circle cx="17" cy="12" r="4"/></svg>Matchup</button>
  <button data-tab="fighters"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>Fighters</button>
  <button data-tab="hype"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22c4 0 7-2.8 7-7 0-4.5-4-7.5-5-12-2.5 2-4 4.5-4 7-1-.7-1.7-1.8-2-3-2 2-3 4.4-3 7 0 4.4 3 8 7 8z"/></svg>Hype</button>
  <button data-tab="news"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9h10M7 13h10M7 17h6"/></svg>News</button>
  <button data-tab="settings"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>Settings</button>
</nav>

<script>
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct = (x, d = 0) => x == null ? '–' : (x * 100).toFixed(d) + '%';
const num = (x, d = 1) => x == null ? '–' : Number(x).toFixed(d);
const am = dec => dec == null ? '–' : dec >= 2 ? '+' + Math.round((dec - 1) * 100) : String(Math.round(-100 / (dec - 1)));
const fair = p => p == null || p <= 0 || p >= 1 ? '–' : am(1 / p);
const day = iso => iso ? new Date(iso).toLocaleDateString(undefined, {month: 'short', day: 'numeric', year: 'numeric'}) : '';
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
};
async function api(path, params = {}) {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null));
  const r = await fetch(`/api/${path}?${q}`);
  const j = await r.json();
  if (j && j.no_data) { show('welcome'); throw new Error(j.error); }
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const loading = (el, msg) => { el.innerHTML = `<div class="spin">${esc(msg)}</div>`; };
const fail = (el, e) => { el.innerHTML = `<div class="card err">${esc(e.message || e)}</div>`; };
const bankroll = () => parseFloat($('#bankroll').value) || 0;
const stake = k => bankroll() && k ? ` · stake $${(bankroll() * k).toFixed(2)}` : '';
const bar = p => `<div class="bar"><i class="a" style="width:${(p * 100).toFixed(1)}%"></i><i class="b" style="width:${(100 - p * 100).toFixed(1)}%"></i></div>`;
const flagPills = hs => [...new Set((hs || []).flatMap(h => h.flags))].map(f => `<span class="pill warn">${esc(f)}</span>`).join(' ');
const hypeClass = m => m >= 80 ? 'bad' : m >= 60 ? 'warn' : m < 20 ? 'good' : '';
const hypePill = (m, lab) => m == null ? '' : `<span class="pill hype-pill ${hypeClass(m)}" title="${esc(lab)}">hype ${Math.round(m)}</span>`;
const meterBar = m => `<div class="meter"><i style="width:${m}%;--full:${m ? 10000 / m : 100}%"></i></div>`;
let DIVS = [];
async function loadDivisions() {
  try { DIVS = await api('divisions'); } catch (e) { return; }
  for (const id of ['#c-div', '#f-div', '#l-div', '#h-div']) {
    $(id).innerHTML = '<option value="">All divisions</option>' + DIVS.map(d => `<option>${esc(d)}</option>`).join('');
  }
}
const watchLinks = w => `<div class="links">${Object.entries(w).map(([k, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(k)} ↗</a>`).join('')}</div>`;

// ---- tabs ----------------------------------------------------------------
function show(tab) {
  document.body.classList.toggle('setup', tab === 'welcome');
  document.querySelectorAll('section').forEach(s => s.classList.toggle('on', s.id === 'tab-' + tab));
  document.querySelectorAll('nav button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
  if (tab !== 'welcome') store.set('tab', tab);
  if (tab === 'settings') loadSettings();
  if (tab === 'hype' && !$('#h-out').innerHTML) loadHype();
  window.scrollTo(0, 0);
  if (tab === 'cards' && !$('#cards-out').dataset.loaded) loadCards();
  if (tab === 'news' && !$('#n-out').innerHTML) loadNews();
  if (tab === 'fighters' && !$('#l-out').innerHTML) loadLeaders();
}
document.querySelectorAll('nav button').forEach(b => b.onclick = () => show(b.dataset.tab));
$('#bankroll').value = store.get('bankroll', '');
$('#bankroll').oninput = () => store.set('bankroll', $('#bankroll').value);

// ---- fighter autocomplete -----------------------------------------------
let acTimer;
document.addEventListener('input', e => {
  if (!['m-a', 'm-b', 'n-q'].includes(e.target.id)) return;
  clearTimeout(acTimer);
  acTimer = setTimeout(async () => {
    try {
      const hits = await api('search', {q: e.target.value});
      $('#fighter-list').innerHTML = hits.map(h => `<option value="${esc(h.name)}">${esc(h.record)}</option>`).join('');
    } catch (err) {}
  }, 200);
});

// ---- upcoming cards -------------------------------------------------------
$('#load-cards').onclick = () => loadCards();
async function loadCards() {
  const out = $('#cards-out');
  out.dataset.loaded = '1';
  const withNews = $('#opt-news').checked;
  loading(out, withNews ? 'Fetching live lines and checking every fighter\'s news… (about a minute)' : 'Fetching live lines… (about 10 seconds)');
  try {
    window.cardsData = await api('upcoming', {news: withNews ? 1 : '', unscheduled: $('#opt-unsched').checked ? 1 : ''});
    renderCards();
  } catch (e) { fail(out, e); }
}
$('#c-div').onchange = () => { if (window.cardsData) renderCards(); };
function renderCards() {
  const out = $('#cards-out'), d = window.cardsData, div = $('#c-div').value;
  const inDiv = x => !div || x === div;
  {
    let html = '';
    const alerts = (d.fraud_checks || []).filter(a => inDiv(a.division));
    if (alerts.length) {
      html += `<div class="card"><h2>Fraud-check alerts</h2><p class="muted tiny" style="margin:0 0 4px">Favourites the odds rate well above their stats.</p>`;
      for (const a of alerts) {
        html += `<div class="fight"><div class="between"><span class="name">${esc(a.fighter)} <span class="muted small">vs ${esc(a.opponent)}</span></span>
          <span class="pill ${hypeClass(a.meter)}">hype ${a.meter} · ${esc(a.label)}</span></div>
          <div class="small">odds ${pct(a['market %'])} · stats ${pct(a['stats %'])} · ours ${pct(a['our %'])} <span class="muted tiny">${esc(a.event)}</span></div>
          ${a.why.map(w => `<div class="tiny muted">• ${esc(w)}</div>`).join('')}</div>`;
      }
      html += `</div>`;
    }
    const vb = (d.value_bets || []).filter(v => inDiv(v.division));
    html += `<div class="card"><h2>Value bets</h2>`;
    if (!vb.length) html += `<p class="muted small" style="margin:4px 0 0">None right now. Lines move, so check again closer to fight night.</p>`;
    for (const v of vb) {
      html += `<div class="fight"><div class="between"><span class="name">${esc(v.bet)} <span class="muted small">vs ${esc(v.vs)}</span></span>
        <span class="pill good">EV ${v.EV >= 0 ? '+' : ''}${pct(v.EV, 1)}</span></div>
        <div class="small">${esc(v.price)} at ${esc(v.book)} · ours ${pct(v['our %'], 1)} vs market ${pct(v['market %'], 1)}${stake(v['kelly %'])}</div>
        <div class="tiny muted">${esc(v.event)}${v['market only'] ? ' · no UFC history, market price only' : ''}</div>
        ${v.check ? `<div class="tiny"><span class="pill warn">${esc(v.check)}</span></div>` : ''}</div>`;
    }
    html += `<p class="muted tiny" style="margin:8px 0 0">Updated ${new Date(d.fetched_at).toLocaleTimeString()} · tap a fight for the full breakdown.</p></div>`;
    let shown = 0;
    for (const ev of d.events) {
      const fights = ev.fights.filter(f => inDiv(f.weight_class));
      if (!fights.length) continue;
      shown += fights.length;
      html += `<div class="card"><div class="between"><h2>${esc(ev.name)}</h2><span class="muted small">${ev.date ? day(ev.date) : 'date TBA'}</span></div>`;
      for (const f of fights) {
        const p = f.p1_est, n1 = (ev.news || {})[f.fighter1], n2 = (ev.news || {})[f.fighter2];
        const evPill = e => e == null ? '' : `<span class="pill ${e >= 0.05 ? 'good' : e < -0.05 ? 'bad' : ''}">${e >= 0 ? '+' : ''}${pct(e, 0)}</span>`;
        const lines = Object.entries(f.lines || {}).sort((x, y) => x[0].localeCompare(y[0]));
        const last = n => esc(n.split(' ').pop());
        const cell = (d, best) => `<td>${d === best ? '<b>' + am(d) + '</b>' : am(d)}</td>`;
        const linesHtml = lines.length ? `<details class="lines"><summary class="tiny muted">Your books' lines (${lines.length})</summary>
          <table class="tight"><tr><th>Book</th><th>${last(f.fighter1)}</th><th>${last(f.fighter2)}</th></tr>
          ${lines.map(([b, [d1, d2]]) => `<tr><td>${esc(b)}</td>${cell(d1, f.dec1_best)}${cell(d2, f.dec2_best)}</tr>`).join('')}</table></details>` : '';
        const props = f.p_decision != null ? `<div class="tiny muted">Market: decision ${pct(f.p_decision)} · ${esc(f.fighter1.split(' ').pop())} KO ${pct(f.p_1_KO)} SUB ${pct(f.p_1_SUB)} · ${esc(f.fighter2.split(' ').pop())} KO ${pct(f.p_2_KO)} SUB ${pct(f.p_2_SUB)}</div>` : '';
        html += `<div class="fight" data-a="${esc(f.fighter1)}" data-b="${esc(f.fighter2)}" style="cursor:pointer">
          <div class="tiny muted">${esc(f.weight_class || '')}</div>
          <div class="between"><span class="name ca ellipsis">${esc(f.fighter1)}${hypePill(f.hype1, f.hype1_label)}</span><span class="small">${pct(p, 1)} · ${am(f.dec1_best)} <span class="muted tiny">${esc(f.book1_best)}</span> ${evPill(f.ev1)}</span></div>
          ${bar(p)}
          <div class="between"><span class="name cb ellipsis">${esc(f.fighter2)}${hypePill(f.hype2, f.hype2_label)}</span><span class="small">${pct(1 - p, 1)} · ${am(f.dec2_best)} <span class="muted tiny">${esc(f.book2_best)}</span> ${evPill(f.ev2)}</span></div>
          <div class="tiny muted">market ${pct(f.p1_market)} (all ${f.books} books) · model ${f.p1_model == null ? 'no data' : pct(f.p1_model)}${f.move != null ? ` · moved ${(f.move * 100 >= 0 ? '+' : '') + (f.move * 100).toFixed(1)} pts` : ''}</div>
          ${props}
          ${linesHtml}
          ${(n1 || n2) ? `<div class="tiny">${flagPills(n1) ? esc(f.fighter1) + ': ' + flagPills(n1) : ''} ${flagPills(n2) ? esc(f.fighter2) + ': ' + flagPills(n2) : ''}</div>` : ''}
          ${(f.notes || []).map(n => `<div class="tiny muted">• ${esc(n)}</div>`).join('')}
        </div>`;
      }
      html += `</div>`;
      const flagged = Object.entries(ev.news || {}).filter(([, hs]) => hs.some(h => h.flags.length));
      if (flagged.length) {
        html += `<div class="card"><h2>News flags · ${esc(ev.name)}</h2>`;
        for (const [name, hs] of flagged) {
          html += `<h3>${esc(name)}</h3>` + hs.filter(h => h.flags.length).slice(0, 4).map(h =>
            `<div class="small" style="margin:4px 0"><a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a>
             <span class="muted tiny">${esc(h.source)} · ${day(h.published)}</span> ${h.flags.map(x => `<span class="pill warn">${esc(x)}</span>`).join(' ')}</div>`).join('');
        }
        html += `</div>`;
      }
    }
    if (div && !shown) html += `<div class="card muted small">No upcoming ${esc(div)} fights with lines yet.</div>`;
    out.innerHTML = html;
    out.querySelectorAll('.fight[data-a]').forEach(el => el.onclick = ev => {
      if (ev.target.closest('details')) return;  // expanding the lines list, not opening the matchup
      openMatchup(el.dataset.a, el.dataset.b);
    });
  }
}

// ---- matchup --------------------------------------------------------------
function openMatchup(a, b) {
  $('#m-a').value = a; $('#m-b').value = b; $('#m-oa').value = ''; $('#m-ob').value = ''; $('#m-live').checked = true;
  show('matchup'); runMatchup();
}
$('#m-go').onclick = () => runMatchup();
async function runMatchup() {
  const out = $('#m-out');
  if (!$('#m-a').value || !$('#m-b').value) return;
  loading(out, $('#m-live').checked ? 'Crunching the numbers and checking live odds…' : 'Crunching the numbers…');
  try {
    const d = await api('matchup', {a: $('#m-a').value, b: $('#m-b').value, odds_a: $('#m-oa').value, odds_b: $('#m-ob').value,
      live: $('#m-live').checked ? 1 : '', bankroll: bankroll() || ''});
    const A = d.a, B = d.b, m = d.methods;
    const pr = d.priced || [];
    const best = pr.length && pr[0]['blend %'] != null ? pr[0]['blend %'] : d.p_a;
    let html = `<div class="card"><div class="muted small">${esc(m.weight_class)}</div>
      <div class="between" style="margin-top:4px"><span class="name ca">${esc(A.name)}</span><span class="name cb">${esc(B.name)}</span></div>
      <div class="between"><span class="big ca">${pct(best, 1)}</span><span class="big cb">${pct(1 - best, 1)}</span></div>
      ${bar(best)}
      <div class="tiny muted">${pr.length && pr[0]['blend %'] != null ? `Model + market blend. Stats model alone: ${pct(d.p_a, 1)} / ${pct(1 - d.p_a, 1)}.` : 'Stats model. Add odds for both fighters (or live odds) for the market blend.'}</div>
      ${d.live ? `<div class="tiny" style="margin-top:6px"><span class="pill">live</span> ${esc(d.live.event)} · best of your ${d.live.books} book${d.live.books === 1 ? '' : 's'}: ${esc(d.live.book_a)} / ${esc(d.live.book_b)}</div>` : ''}
    </div>`;
    if (pr.length) {
      html += `<div class="card"><h2>Betting value</h2><div class="scroll"><table class="tight"><tr><th>Fighter</th><th>Price</th><th>Ours</th><th>Mkt</th><th>EV</th><th>Stake</th></tr>`;
      for (const r of pr) {
        const ev = r['EV/$100'];
        html += `<tr><td>${esc(r.fighter)}</td><td>${esc(r['book line'] ?? '–')}</td><td>${pct(r['blend %'] ?? r['model %'], 1)}</td>
          <td>${pct(r['market %'], 1)}</td>
          <td><span class="pill ${ev >= 5 ? 'good' : ev < -5 ? 'bad' : ''}">${ev == null ? '–' : (ev >= 0 ? '+' : '') + ev.toFixed(1) + '%'}</span></td>
          <td>${r['kelly %'] ? (bankroll() ? '$' + (bankroll() * r['kelly %']).toFixed(2) : pct(r['kelly %'], 1)) : '–'}</td></tr>`;
      }
      html += `</table></div><p class="muted tiny" style="margin:8px 0 0">${d.vig != null ? `Book margin ${pct(d.vig, 1)}. ` : ''}Stake = quarter Kelly, capped at 5% of bankroll${bankroll() ? '' : ' (set your bankroll at the top for dollar amounts)'}.</p></div>`;
    }
    html += `<div class="card"><h2>How it ends (stats model)</h2><table><tr><th></th><th>KO/TKO</th><th>Sub</th><th>Decision</th></tr>
      <tr><td class="ca">${esc(A.name)}</td><td>${pct(m.A_KO)}</td><td>${pct(m.A_SUB)}</td><td>${pct(m.A_DEC)}</td></tr>
      <tr><td class="cb">${esc(B.name)}</td><td>${pct(m.B_KO)}</td><td>${pct(m.B_SUB)}</td><td>${pct(m.B_DEC)}</td></tr></table>
      <p class="small" style="margin:8px 0 0">Goes the distance: <b>${pct(m.distance)}</b> <span class="muted tiny">(rough guide; the market's props are sharper)</span></p>
      ${d.drivers.length ? `<h3>Biggest factors</h3>${d.drivers.map(x => `<div class="small">${esc(x.factor)} → <b class="${x.favours === A.name ? 'ca' : 'cb'}">${esc(x.favours)}</b></div>`).join('')}` : ''}
    </div>`;
    const rows = [
      ['UFC record', A.record, B.record], ['Elo', A.elo, B.elo], ['Streak', A.streak, B.streak],
      ['Age', num(A.age), num(B.age)], ['Height', A.height ?? '–', B.height ?? '–'], ['Reach', A.reach ?? '–', B.reach ?? '–'],
      ['Stance', A.stance ?? '–', B.stance ?? '–'], ['Days since fight', A.days_since ?? '–', B.days_since ?? '–'],
      ['Wins KO/SUB/DEC', `${A.wins.KO}/${A.wins.SUB}/${A.wins.DEC}`, `${B.wins.KO}/${B.wins.SUB}/${B.wins.DEC}`],
      ['Losses KO/SUB/DEC', `${A.losses.KO}/${A.losses.SUB}/${A.losses.DEC}`, `${B.losses.KO}/${B.losses.SUB}/${B.losses.DEC}`],
      ['Sig. strikes/min', num(A.stats.SLpM, 2), num(B.stats.SLpM, 2)], ['Absorbed/min', num(A.stats.SApM, 2), num(B.stats.SApM, 2)],
      ['Striking acc.', pct(A.stats['Str. Acc']), pct(B.stats['Str. Acc'])], ['Striking def.', pct(A.stats['Str. Def']), pct(B.stats['Str. Def'])],
      ['Takedowns/15', num(A.stats['TD Avg/15'], 2), num(B.stats['TD Avg/15'], 2)], ['TD acc.', pct(A.stats['TD Acc']), pct(B.stats['TD Acc'])],
      ['TD def.', pct(A.stats['TD Def']), pct(B.stats['TD Def'])], ['Subs/15', num(A.stats['Sub Avg/15'], 2), num(B.stats['Sub Avg/15'], 2)],
      ['Knockdowns/15', num(A.stats['KD/15'], 2), num(B.stats['KD/15'], 2)], ['Control time', pct(A.stats['Ctrl %']), pct(B.stats['Ctrl %'])],
      ['Went the distance', pct(A.distance_rate), pct(B.distance_rate)],
      ['Hype meter', A.hype && A.hype.available ? `${A.hype.meter} · ${A.hype.label}` : '–', B.hype && B.hype.available ? `${B.hype.meter} · ${B.hype.label}` : '–'],
    ];
    html += `<div class="card"><h2>Tale of the tape</h2><table><tr><th></th><th class="ca">${esc(A.name)}</th><th class="cb">${esc(B.name)}</th></tr>
      ${rows.map(r => `<tr><td class="muted">${r[0]}</td><td>${esc(r[1])}</td><td>${esc(r[2])}</td></tr>`).join('')}</table></div>`;
    if (d.h2h.length || d.common.length) {
      html += `<div class="card">`;
      if (d.h2h.length) html += `<h2>Previous meetings</h2>` + d.h2h.map(h => `<div class="small" style="margin:4px 0">${day(h.date)} · ${esc(A.name)} <b>${esc(h.result)}</b> by ${esc(h.method)} R${h.round ?? '?'} · <a href="${esc(h.watch['UFC YouTube'])}" target="_blank" rel="noopener">watch ↗</a></div>`).join('');
      if (d.common.length) {
        const keys = Object.keys(d.common[0]);
        html += `<h3>Common opponents</h3><div class="scroll"><table><tr>${keys.map(k => `<th>${esc(k)}</th>`).join('')}</tr>${d.common.map(r => `<tr>${keys.map(k => `<td>${esc(r[k])}</td>`).join('')}</tr>`).join('')}</table></div>`;
      }
      html += `</div>`;
    }
    html += `<div class="card"><h2>Watch</h2><h3>${esc(A.name)}</h3>${watchLinks(d.watch.a)}<h3>${esc(B.name)}</h3>${watchLinks(d.watch.b)}</div>`;
    html += `<div class="card"><div class="between"><h2>News</h2><button class="btn small ghost" id="m-news">Check news</button></div><div id="m-news-out"></div>
      ${d.notes.map(n => `<div class="tiny muted">• ${esc(n)}</div>`).join('')}</div>`;
    out.innerHTML = html;
    $('#m-news').onclick = async () => {
      const box = $('#m-news-out');
      loading(box, 'Checking headlines…');
      try {
        const [na, nb] = await Promise.all([api('news', {fighter: A.name}), api('news', {fighter: B.name})]);
        box.innerHTML = [na, nb].map(n => newsBlock(n.fighter, n.headlines.slice(0, 6))).join('');
      } catch (e) { fail(box, e); }
    };
  } catch (e) { fail(out, e); }
}

// ---- fighters ---------------------------------------------------------------
let fTimer;
$('#f-q').oninput = () => {
  clearTimeout(fTimer);
  fTimer = setTimeout(async () => {
    const box = $('#f-results');
    try {
      const hits = await api('search', {q: $('#f-q').value, division: $('#f-div').value});
      box.innerHTML = hits.map(h => `<a class="item" href="#" data-id="${esc(h.id)}"><span class="name">${esc(h.name)}</span> <span class="muted small">${esc(h.record)} · ${esc(h.division || '')} · last ${day(h.last)}</span></a>`).join('');
      box.querySelectorAll('a.item').forEach(a => a.onclick = ev => { ev.preventDefault(); loadFighter(a.dataset.id); });
    } catch (e) { box.innerHTML = ''; }
  }, 200);
};
async function loadFighter(id) {
  const out = $('#f-out');
  $('#f-results').innerHTML = '';
  loading(out, 'Loading fighter…');
  try {
    const f = await api('fighter', {id});
    const s = f.stats;
    out.innerHTML = `<div class="card"><h2>${esc(f.name)}${f.nickname ? ` <span class="muted small">"${esc(f.nickname)}"</span>` : ''}</h2>
      <div class="small">UFC ${esc(f.record)} · Elo ${f.elo} (peak ${f.peak_elo}) · streak ${f.streak > 0 ? '+' : ''}${f.streak}</div>
      <div class="small muted">Age ${num(f.age)} · ${esc(f.height ?? '–')} · reach ${f.reach ?? '–'}" · ${esc(f.stance ?? '–')} · last fought ${day(f.last_fight)}</div>
      <div class="kv" style="margin-top:10px">
        <div><span>Wins KO/SUB/DEC</span><span>${f.wins.KO}/${f.wins.SUB}/${f.wins.DEC}</span></div>
        <div><span>Losses KO/SUB/DEC</span><span>${f.losses.KO}/${f.losses.SUB}/${f.losses.DEC}</span></div>
        <div><span>Sig. strikes/min</span><span>${num(s.SLpM, 2)}</span></div><div><span>Absorbed/min</span><span>${num(s.SApM, 2)}</span></div>
        <div><span>Striking acc.</span><span>${pct(s['Str. Acc'])}</span></div><div><span>Striking def.</span><span>${pct(s['Str. Def'])}</span></div>
        <div><span>Takedowns/15</span><span>${num(s['TD Avg/15'], 2)}</span></div><div><span>TD def.</span><span>${pct(s['TD Def'])}</span></div>
        <div><span>Subs/15</span><span>${num(s['Sub Avg/15'], 2)}</span></div><div><span>Control time</span><span>${pct(s['Ctrl %'])}</span></div>
        <div><span>Knockdowns/15</span><span>${num(s['KD/15'], 2)}</span></div><div><span>Went the distance</span><span>${pct(f.distance_rate)}</span></div>
      </div>
      ${f.hype && f.hype.available ? `<h3>Hype meter</h3>
        <div class="between small"><span><b>${f.hype.meter}</b>/100 · ${esc(f.hype.label)}</span><span class="muted tiny">${esc(f.hype.basis)}</span></div>
        ${meterBar(f.hype.meter)}
        <div class="tiny muted">odds ${pct(f.hype['market %'])} vs stats ${pct(f.hype['stats %'])}</div>
        ${f.hype.why.map(w => `<div class="tiny muted">• ${esc(w)}</div>`).join('')}` : ''}
      <h3>Watch</h3>${watchLinks(f.watch)}
      <div style="margin-top:10px"><button class="btn small ghost" id="f-news">Check news</button> <button class="btn small ghost" id="f-vs">Compare…</button></div>
      <div id="f-news-out"></div></div>
      <div class="card"><h2>Fight log</h2>${f.log.map(r => `<div class="fight"><div class="between"><span><span class="pill ${r.result === 'W' ? 'good' : r.result === 'L' ? 'bad' : ''}">${esc(r.result)}</span> <span class="name">${esc(r.opponent)}</span></span><span class="muted tiny">${day(r.date)}</span></div>
        <div class="small">${esc(r.method)} · R${r.round ?? '?'} ${esc(r.time ?? '')}${r.sig ? ` · sig. str ${esc(r.sig)}` : ''}${r.td ? ` · TD ${esc(r.td)}` : ''}</div>
        <div class="tiny muted ellipsis">${esc(r.event)}</div>
        <div class="links"><a href="${esc(r.watch['UFC YouTube'])}" target="_blank" rel="noopener">UFC YouTube ↗</a><a href="${esc(r.watch['YouTube'])}" target="_blank" rel="noopener">YouTube ↗</a><a href="${esc(r.watch['UFC Fight Pass'])}" target="_blank" rel="noopener">Fight Pass ↗</a></div></div>`).join('')}</div>`;
    $('#f-news').onclick = async () => {
      const box = $('#f-news-out');
      loading(box, 'Checking headlines…');
      try { const n = await api('news', {fighter: f.name}); box.innerHTML = newsBlock(n.fighter, n.headlines.slice(0, 8)); }
      catch (e) { fail(box, e); }
    };
    $('#f-vs').onclick = () => { $('#m-a').value = f.name.replace(/ \(\d+ lbs\)$/, ''); $('#m-b').value = ''; $('#m-out').innerHTML = ''; show('matchup'); $('#m-b').focus(); };
  } catch (e) { fail(out, e); }
}
$('#l-div').onchange = () => loadLeaders();
$('#f-div').onchange = () => $('#f-q').oninput();
async function loadLeaders() {
  const box = $('#l-out');
  loading(box, 'Loading…');
  try {
    const rows = await api('leaders', {division: $('#l-div').value, limit: 15});
    box.innerHTML = rows.map((r, i) => `<div class="item between"><span><span class="muted small">${i + 1}.</span> <span class="name">${esc(r.fighter)}</span> <span class="muted tiny">${esc(r.division)}</span></span><span class="small">${r.elo} · ${esc(r['ufc record'])}</span></div>`).join('');
  } catch (e) { fail(box, e); }
}

// ---- hype -----------------------------------------------------------------------
$('#h-live').onchange = () => loadHype();
$('#h-div').onchange = () => loadHype();
async function loadHype() {
  const out = $('#h-out');
  loading(out, $('#h-live').checked ? 'Scoring fighters (checking live odds)…' : 'Scoring fighters…');
  try {
    const d = await api('hype', {division: $('#h-div').value, live: $('#h-live').checked ? 1 : ''});
    const bt = d.backtest || [];
    $('#h-bt').innerHTML = `<table class="tight" style="margin-top:6px"><tr><th>Band</th><th>Fights</th><th>Odds said</th><th>Corrected</th><th>Won</th><th>vs corrected</th></tr>
      ${bt.map(r => `<tr><td>${esc(r.band)}</td><td>${r.fights.toLocaleString()}</td><td>${pct(r['odds said'], 1)}</td><td>${pct(r['corrected odds'], 1)}</td>
        <td>${pct(r['actually won'], 1)}</td><td>${(r['vs corrected'] * 100 >= 0 ? '+' : '') + (r['vs corrected'] * 100).toFixed(1)} ± ${(r['± (1 s.e.)'] * 100).toFixed(1)}</td></tr>`).join('')}</table>
      <p class="muted tiny">Every UFC fight with closing odds since ${d.since ? new Date(d.since).getFullYear() : ''}. "Corrected" removes the
      favourite bias (favourites as a group beat their odds); hyped fighters fall short of it. Tested and dropped: padded records,
      win streaks, inexperience, past hype. Young fighters and fighters stepping up tended to beat their odds.</p>`;
    let html = '';
    if ($('#h-live').checked) {
      html += `<div class="card"><h2>Fraud-check alerts</h2>` + (d.alerts.length ? d.alerts.map(a =>
        `<div class="fight"><div class="between"><span class="name">${esc(a.fighter)} <span class="muted small">vs ${esc(a.opponent)}</span></span>
          <span class="pill ${hypeClass(a.meter)}">hype ${a.meter}</span></div>
          <div class="small">${esc(a.label)} · odds ${pct(a['market %'])} vs stats ${pct(a['stats %'])} · ours ${pct(a['our %'])} <span class="muted tiny">${esc(a.event)}</span></div>
          ${a.why.map(w => `<div class="tiny muted">• ${esc(w)}</div>`).join('')}</div>`).join('')
        : `<p class="muted small" style="margin:4px 0 0">No very hyped favourites on the upcoming cards${d.division ? ' at ' + esc(d.division) : ''}.</p>`) + `</div>`;
    }
    html += `<div class="card"><h2>Up-and-comers${d.division ? ' · ' + esc(d.division) : ''}</h2>
      <p class="muted tiny" style="margin:0 0 4px">2-7 UFC fights, 31 or younger, winning and active. Most hyped first.</p>`;
    if (!d.list.length) html += `<p class="muted small">None found.</p>`;
    for (const u of d.list) {
      html += `<div class="fight"><div class="between"><span><span class="name">${esc(u.fighter)}</span>
          <span class="muted small">${esc(u.record)} · ${esc(u.division)}${u.age ? ' · ' + Math.round(u.age) : ''}</span></span>
          <span class="pill ${hypeClass(u.meter)}">${u.meter} · ${esc(u.label)}</span></div>
        ${meterBar(u.meter)}
        <div class="tiny muted">odds ${pct(u['market %'])} vs stats ${pct(u['stats %'])} · ${esc(u.basis)}</div>
        ${u.why ? u.why.split('; ').map(w => `<div class="tiny muted">• ${esc(w)}</div>`).join('') : ''}
        <div class="links" style="margin-top:4px"><a href="#" data-profile="${esc(u.fighter_id)}">Profile</a><a href="#" data-buzz="${esc(u.fighter)}">Media buzz</a><span class="tiny muted" data-buzz-out></span></div>
      </div>`;
    }
    html += `</div>`;
    out.innerHTML = html;
    out.querySelectorAll('[data-profile]').forEach(a => a.onclick = ev => { ev.preventDefault(); show('fighters'); loadFighter(a.dataset.profile); });
    out.querySelectorAll('[data-buzz]').forEach(a => a.onclick = async ev => {
      ev.preventDefault();
      const slot = a.parentElement.querySelector('[data-buzz-out]');
      slot.textContent = 'checking…';
      try { const b = await api('buzz', {name: a.dataset.buzz.replace(/ \(\d+ lbs\)$/, '')}); slot.textContent = `${b.headlines_30d} headlines in 30 days (context only)`; }
      catch (e) { slot.textContent = e.message; }
    });
  } catch (e) { fail(out, e); }
}

// ---- news ---------------------------------------------------------------------
function newsBlock(name, hs) {
  const flags = flagPills(hs);
  return `<h3>${esc(name || 'Latest UFC news')}</h3>${name ? `<div class="small" style="margin-bottom:6px">${flags || '<span class="pill good">no red flags</span>'}</div>` : ''}` +
    (hs.length ? hs.map(h => `<div class="small" style="margin:6px 0"><a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a>
      <span class="muted tiny">${esc(h.source)} · ${day(h.published)}</span> ${h.flags.map(x => `<span class="pill warn">${esc(x)}</span>`).join(' ')}</div>`).join('')
      : '<div class="muted small">No recent headlines.</div>');
}
$('#n-go').onclick = () => loadNews();
$('#n-q').onkeydown = e => { if (e.key === 'Enter') loadNews(); };
async function loadNews() {
  const out = $('#n-out');
  loading(out, 'Fetching headlines…');
  try {
    const n = await api('news', {fighter: $('#n-q').value});
    out.innerHTML = `<div class="card">${newsBlock(n.fighter, n.headlines)}</div>`;
  } catch (e) { fail(out, e); }
}

// ---- data, updates, phone access ---------------------------------------------
let pollTimer = null;
function followUpdate(logEl, onDone) {
  let next = 0;
  logEl.hidden = false;
  clearInterval(pollTimer);
  const tick = async () => {
    try {
      const j = await api('update_status', {since: next});
      next = j.next;
      if (j.lines.length) { logEl.textContent += j.lines.join('\n') + '\n'; logEl.scrollTop = logEl.scrollHeight; }
      if (j.state !== 'running') {
        clearInterval(pollTimer);
        logEl.textContent += j.state === 'done' ? '\nAll set.\n' : `\nFailed: ${j.error}\n`;
        logEl.scrollTop = logEl.scrollHeight;
        onDone(j.state === 'done');
      }
    } catch (e) {}
  };
  pollTimer = setInterval(tick, 1000);
  tick();
}
function resetLoaded() {
  delete $('#cards-out').dataset.loaded;
  ['#cards-out', '#m-out', '#f-out', '#l-out', '#n-out'].forEach(s => $(s).innerHTML = '');
}
$('#w-go').onclick = async () => {
  $('#w-go').disabled = true; $('#w-go').textContent = 'Downloading… (about 10 minutes)';
  try { await api('update'); } catch (e) {}
  followUpdate($('#w-log'), ok => {
    if (ok) { resetLoaded(); show('cards'); }
    else { $('#w-go').disabled = false; $('#w-go').textContent = 'Try again'; }
  });
};
$('#s-update').onclick = async () => {
  $('#s-update').disabled = true; $('#s-update').textContent = 'Updating…';
  $('#s-log').textContent = '';
  try { await api('update'); } catch (e) {}
  followUpdate($('#s-log'), ok => {
    $('#s-update').disabled = false; $('#s-update').textContent = 'Update data';
    if (ok) resetLoaded();
    loadSettings();
  });
};
async function loadSettings() {
  try {
    const s = await api('status');
    const when = s.updated_at ? new Date(s.updated_at).toLocaleString() : 'never';
    $('#s-data').innerHTML = s.has_data
      ? `${(s.fights ?? 0).toLocaleString()} fights and ${(s.fighters ?? 0).toLocaleString()} fighters, ${day(s.first_event)} to ${day(s.latest_event)}.<br>Last updated ${esc(when)}. Update after each event for the newest results.<br><span class="tiny">Stored in ${esc(s.data_dir)}</span>`
      : 'No data yet.';
    if (s.job.state === 'running' && $('#s-log').hidden) {
      $('#s-update').disabled = true; $('#s-update').textContent = 'Updating…';
      followUpdate($('#s-log'), () => { $('#s-update').disabled = false; $('#s-update').textContent = 'Update data'; loadSettings(); });
    }
    renderPhone(s.desktop, s.phone);
  } catch (e) { $('#s-data').textContent = e.message; }
  try { renderBooks(await api('settings')); } catch (e) {}
}
function renderBooks(p) {
  const chosen = new Set(p.books.map(b => b.toLowerCase()));
  const box = name => `<label><input type="checkbox" value="${esc(name)}" ${chosen.has(name.toLowerCase()) ? 'checked' : ''}> ${esc(name)}</label>`;
  $('#s-books').innerHTML = p.sportsbooks.map(box).join('');
  $('#s-markets').innerHTML = p.prediction_markets.map(box).join('');
  document.querySelectorAll('#s-books input, #s-markets input').forEach(cb => cb.onchange = async () => {
    const picked = [...document.querySelectorAll('#s-books input:checked, #s-markets input:checked')].map(x => x.value);
    const msg = $('#s-books-msg');
    if (!picked.length) { cb.checked = true; msg.innerHTML = '<span class="err">Pick at least one sportsbook.</span>'; return; }
    try {
      await api('settings', {books: picked.join(',')});
      delete $('#cards-out').dataset.loaded;
      msg.innerHTML = `<span class="pill good">Saved</span> <span class="muted">Cards and matchups now use ${picked.length} book${picked.length === 1 ? '' : 's'}.</span>`;
    } catch (e) { msg.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  });
}
function renderPhone(desktop, phone) {
  const btn = $('#s-phone'), out = $('#s-phone-out');
  btn.hidden = !desktop;
  btn.textContent = phone.enabled ? 'Turn off' : 'Turn on';
  btn.onclick = async () => {
    btn.disabled = true;
    try { const p = await api('phone', {enable: phone.enabled ? 0 : 1}); renderPhone(desktop, p); }
    catch (e) { out.innerHTML = `<span class="err">${esc(e.message)}</span>`; }
    btn.disabled = false;
  };
  if (phone.enabled && phone.url) {
    out.innerHTML = `<p style="margin:4px 0 8px">On your iPhone (same Wi-Fi), open this address in Safari:</p>
      <div class="url">${esc(phone.url)}</div>
      <p class="muted tiny" style="margin:8px 0 0">Then tap Share → Add to Home Screen. ${desktop ? 'Keep this app open while you use it. Anyone on your network with the address can open it.' : ''}</p>`;
  } else if (desktop) {
    out.innerHTML = `<p class="muted" style="margin:4px 0 0">Turn on to open the same app on your iPhone over Wi-Fi.</p>`;
  } else {
    out.innerHTML = `<p class="muted" style="margin:4px 0 0">Tap Share → Add to Home Screen to keep it on your phone.</p>`;
  }
}

(async () => {
  loadDivisions();
  try {
    const s = await api('status');
    if (!s.has_data) {
      show('welcome');
      if (s.job.state === 'running') { $('#w-go').disabled = true; $('#w-go').textContent = 'Downloading… (about 10 minutes)';
        followUpdate($('#w-log'), ok => { if (ok) { resetLoaded(); show('cards'); } }); }
      return;
    }
  } catch (e) {}
  show(store.get('tab', 'cards'));
})();
</script>
</body>
</html>
"""
