// Settings: operating profile, Club Log Most Wanted, LoTW Account Status check,
// and DX Monitor (D54, optional).
'use strict';

const BANDS = ['160M', '80M', '40M', '30M', '20M', '17M', '15M', '12M', '10M', '6M', '2M'];
const MODES = ['CW', 'PHONE', 'DIGITAL', 'SAT'];
const DEFAULT = { bands: BANDS.slice(0, 10), modes: ['CW', 'PHONE', 'DIGITAL'] };
const state = { mx: null, saved: null, draft: null, check: null, mwMsg: '', profMsg: '', asMsg: '',
  dx: null, dxDraft: null, dxMsg: '', dxBusy: false };

// Missing count per category, independent of the profile: band/mode slots on
// Mixed-credited entities; Satellite across every current entity (a separate award).
function missingCounts() {
  const out = {};
  const ents = state.mx.entities;
  for (const c of BANDS.concat(MODES)) {
    out[c] = c === 'SAT'
      ? ents.filter((e) => !e.credited.includes('SAT')).length
      : ents.filter((e) => e.credited.includes('MIXED') && !e.credited.includes(c)).length;
  }
  return out;
}

const same = (a, b) => a.bands.join() === b.bands.join() && a.modes.join() === b.modes.join();

function profileSection() {
  const n = missingCounts(), d = state.draft;
  const box = (c, on, group) => `<label><input type="checkbox" data-${group}="${c}"${on ? ' checked' : ''}>
    <span>${esc(label(c))}</span><span class="cnt">${n[c]} missing</span></label>`;
  const slots = d.bands.concat(d.modes.filter((m) => m !== 'SAT')).reduce((t, c) => t + n[c], 0);
  const dirty = !same(d, state.saved);
  return `<section class="panel" aria-labelledby="prof-h" style="display:flex;flex-direction:column;gap:18px">
    <div><h2 id="prof-h">Operating profile</h2>
      <div class="muted small">What counts as “needed” in every view and export</div></div>
    <fieldset class="plain"><legend>BANDS</legend><div class="checks">${BANDS.map((b) => box(b, d.bands.includes(b), 'band')).join('')}</div></fieldset>
    <fieldset class="plain"><legend>MODES</legend><div class="checks">${MODES.map((m) => box(m, d.modes.includes(m), 'mode')).join('')}</div></fieldset>
    <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap">
      <div><div><span class="mono" style="font-size:22px;font-weight:700">${num(slots)}</span> missing band and mode slots with this profile${d.modes.includes('SAT') ? ` · plus ${n.SAT} for Satellite` : ''}</div>
        <div class="muted small" style="max-width:720px">Mixed (new entities) is always tracked. 2 m and Satellite are off by default; tick them if you chase them. Satellite DXCC is a separate award, so its count covers every entity. Changing the profile recalculates every view; nothing is re-imported. 70 cm can't be tracked: LoTW's matrix has no 70 cm column.</div></div>
      <div style="display:flex;gap:10px;align-items:center">
        <span class="small ${dirty ? 'err' : 'muted'}" role="status">${dirty ? 'Not saved' : state.profMsg}</span>
        <button class="btn" id="reset">Reset to 160–6 m</button>
        <button class="btn primary" id="saveprof"${dirty ? '' : ' disabled'}>Save profile</button>
      </div>
    </div>
  </section>`;
}

function clubLogSection() {
  const ranked = state.mx.entities.filter((e) => e.mw_rank != null);
  const top = ranked.find((e) => e.mw_rank === 1);
  const fetched = state.mwFetched;
  return `<section class="panel" aria-labelledby="cl-h" style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap">
    <div><h2 id="cl-h">Club Log Most Wanted</h2>
      <div class="muted small">Used for the <strong>Easiest first</strong> and <strong>Rarest first</strong> sorts. Public list; no Club Log account is used.</div>
      <div class="small" style="margin-top:6px">${fetched ? `Rankings from <span class="mono">${esc(when(fetched))}</span> · ${ranked.length} entities${top ? ` · #1 ${esc(top.name)}` : ''}` : 'Not fetched yet.'}</div>
      <div class="small" role="status">${state.mwMsg}</div></div>
    <button class="btn" id="mw">Refresh rankings</button>
  </section>`;
}

// ---------- DX Monitor (D54) ----------
const OK_ICON = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#5fd39a" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';

function dxEntityOptions() {
  return state.mx.entities.slice().sort((a, b) => a.name.localeCompare(b.name))
    .map((e) => `<option value="${e.dxcc}">${esc(e.name)} (${esc(e.prefix || '—')})</option>`).join('');
}

function dxmonSection() {
  const d = state.dx || { enabled: false };
  const draft = state.dxDraft ?? (d.url || '');
  let status;
  if (!d.enabled) {
    status = '<div class="muted">Off: no address saved. No DXpedition tags; the For DX Monitor export is hidden.</div>';
  } else if (d.ok) {
    status = `<div class="notice ok">${OK_ICON}<div><div class="t">Connected</div>
      <div class="muted small">ADXO list updated by DX Monitor ${esc(when(d.adxo_updated))} · ${d.entry_count} DXpeditions · ${d.watched_count} on your Watched list · checked ${esc(when(d.tried_at))} · refreshed automatically when Missing Entities opens, if older than 15 minutes${d.skipped ? ` · ${d.skipped} malformed entr${d.skipped === 1 ? 'y' : 'ies'} skipped` : ''}</div></div></div>`;
  } else {
    status = `<div class="notice held" role="alert"><div><div class="t">${esc(d.error || 'DX Monitor did not answer.')}</div>
      <div>${d.fetched_at ? `Missing Entities keeps showing the list checked at ${esc(when(d.fetched_at))}, labelled with that time.` : 'No list has been received yet.'} Check that the dxmon stack is running in Portainer and the address is right.</div></div></div>`;
  }
  let names = '';
  if (d.enabled && d.names) {
    const n = d.names, placed = n.direct + n.builtin + n.approved;
    const unplaced = d.unplaced || [];
    const decided = d.decisions || [];
    const canPick = state.mx.entities.length > 0;
    names = `<div style="display:flex;flex-direction:column;gap:12px;border-top:1px solid var(--line);padding-top:16px">
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap">
        <h3 style="margin:0;font:700 16px var(--mono)">Entity names</h3>
        <div class="muted small">${placed} of ${n.names} ADXO names placed: ${n.direct} match the entity table, ${n.builtin} from the built-in list${n.approved ? `, ${n.approved} approved by you` : ''}${n.ignored ? ` · ${n.ignored} ignored` : ''}${unplaced.length ? ` · <span style="color:var(--amber)">${unplaced.length} need${unplaced.length === 1 ? 's' : ''} your OK</span>` : ''}</div>
      </div>
      ${unplaced.length ? `<div class="mono small" style="letter-spacing:.1em;color:var(--amber)">NEEDS YOUR OK</div>
        ${unplaced.map((u, i) => `<div class="panel" style="background:var(--bg);padding:14px 16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap">
          <div style="flex:1 1 300px"><div><span class="mono">“${esc(u.name)}”</span> <span class="muted small">in ADXO for ${esc(u.example)}</span></div>
            <div class="small">${u.suggestion ? `Suggested: <strong>${esc(u.suggestion.name)}</strong> <span class="muted">· ${esc(u.suggestion.prefix || '—')} · DXCC ${u.suggestion.dxcc} · check it before approving</span>` : '<span class="muted">No close match found; choose the entity yourself or ignore it.</span>'}</div></div>
          ${u.suggestion ? `<button class="btn" data-approve="${i}">Approve suggestion</button>` : ''}
          ${canPick ? `<label class="small muted" style="display:flex;flex-direction:column;gap:2px">Or choose
            <select data-pick="${i}" aria-label="Choose the entity for ${esc(u.name)}"><option value="">Another entity…</option>${dxEntityOptions()}</select></label>
            <button class="btn" data-use="${i}">Use</button>` : ''}
          <button class="btn" data-ignore="${i}">Ignore</button>
        </div>`).join('')}` : ''}
      <div class="mono small muted" style="letter-spacing:.1em">YOUR DECISIONS</div>
      ${decided.length ? decided.map((x, i) => `<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;border-bottom:1px solid var(--line);padding:6px 0">
          <div style="flex:1 1 300px"><span class="mono">“${esc(x.name)}”</span> → ${x.dxcc ? `<strong>${esc(x.entity)}</strong>` : '<span class="muted">ignored (its DXpeditions get no tag)</span>'} <span class="muted small">· ${esc(when(x.decided_at))}</span></div>
          <button class="btn" data-forget="${i}">Remove</button></div>`).join('')
        : '<div class="muted small">None yet.</div>'}
      <div class="muted small" style="max-width:900px">Suggestions are never applied on their own. A name the app can't place is never dropped: it stays listed here and its DXpedition simply has no tag until you decide. Your decisions are kept in the database and survive redeploys; the built-in list of known ADXO spellings ships with the app.</div>
    </div>`;
  }
  return `<section class="panel" aria-labelledby="dx-h" style="display:flex;flex-direction:column;gap:18px">
    <div style="max-width:900px"><h2 id="dx-h">DX Monitor <span class="muted" style="font-size:14px;font-weight:500">optional</span></h2>
      <div class="muted small">Adds DXpedition tags to Missing Entities from DX Monitor's ADXO list, flags any that aren't on its Watched list, and offers the <strong>For DX Monitor</strong> export. Leave the address blank to turn every DX Monitor feature off; the analyzer works fully without it.</div></div>
    <div style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">
      <div style="display:flex;flex-direction:column;gap:6px;flex:1 1 320px;max-width:520px">
        <label for="dx-url" class="mono small muted" style="letter-spacing:.1em">DX MONITOR ADDRESS</label>
        <input id="dx-url" type="text" class="txt mono" value="${esc(draft)}" placeholder="http://192.168.6.29:8083" spellcheck="false" autocomplete="off"></div>
      <button class="btn" id="dx-test"${state.dxBusy ? ' disabled' : ''}>Test connection</button>
      <button class="btn primary" id="dx-save"${state.dxBusy ? ' disabled' : ''}>Save</button>
      ${d.enabled ? `<button class="btn" id="dx-refresh"${state.dxBusy ? ' disabled' : ''}>Refresh now</button>` : ''}
    </div>
    <div class="small" role="status">${state.dxMsg}</div>
    ${status}
    ${names}
  </section>`;
}

function checkResult(r) {
  if (!r || r.none) return '';
  const bad = r.reconciliation.filter((x) => !x.ok);
  const okIcon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#5fd39a" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';
  const warnIcon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f5a524" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>';
  const stale = r.is_current_import === false ? '<div class="err small">This check was made against an earlier import. Paste a fresh Account Status table to check the current data.</div>' : '';
  const recon = bad.length
    ? `<div class="notice bad" role="alert"><div><div class="t">${bad.length} categor${bad.length === 1 ? 'y does' : 'ies do'} not match LoTW</div>
        <ul>${bad.map((x) => `<li>${esc(x.label)}: this app counts ${x.app}, LoTW shows ${x.lotw} credits awarded.</li>`).join('')}</ul>
        <div class="muted">Usually the matrix and the Account Status table came from different days. Paste both from the same LoTW session.</div></div></div>`
    : `<div class="notice ok">${okIcon}<div><div class="t">Credits match LoTW in all ${r.reconciliation.length} categories</div><div class="muted small">Checked ${esc(when(r.checked_at))}</div></div></div>`;
  const pend = r.pending.filter((x) => !x.ok);
  const marked = r.pending.reduce((t, x) => t + x.app, 0), lotw = r.pending.reduce((t, x) => t + x.lotw, 0);
  const pending = pend.length
    ? `<div class="notice held" role="alert">${warnIcon}<div style="display:flex;flex-direction:column;gap:6px">
        ${pend.map((x) => `<div><span class="t">${esc(x.label)}: LoTW shows ${x.lotw} pending, you have marked ${x.app}.</span>
          <span class="muted">${x.lotw > x.app ? 'A confirmation is missing a mark: open LoTW\'s pending list for this category and mark the slot.'
            : 'You have an extra mark: it may be for a QSO not yet confirmed in LoTW, or one LoTW has already processed.'}</span></div>`).join('')}
        <div class="muted"><a href="/slots">Go to Missing Band Slots</a> to add or clear marks.</div></div></div>`
    : `<div class="notice ok">${okIcon}<div class="t">Your pending marks match LoTW (${marked} marked · ${lotw} new or in process)</div></div>`;
  return `${stale}${recon}
    <div class="recon">${r.reconciliation.map((x) => `<div><span>${esc(x.label)}</span><span class="${x.ok ? '' : 'down'}">${x.app} ${x.ok ? '<span class="muted">= LoTW</span>' : '≠ ' + x.lotw}</span></div>`).join('')}</div>
    ${pending}
    ${r.not_checked.length ? `<div class="muted small">Not checked: ${r.not_checked.map((c) => esc(c === 'SAT' ? 'Satellite (not listed by LoTW)' : c === 'CHALLENGE' ? 'Challenge' : c === '70CM' ? '70 cm (no matrix column)' : c)).join(' · ')}. Paper cards are never part of this check.</div>` : ''}`;
}

function statusSection() {
  return `<section class="panel" aria-labelledby="as-h" style="display:flex;flex-direction:column;gap:14px">
    <div><h2 id="as-h">Check against LoTW Account Status</h2>
      <div class="muted small">Optional. Copy the <strong>Account Status</strong> table from LoTW's DXCC page and paste it here. The app checks its credit counts against “DXCC Credits Awarded”, and your pending marks against “New LoTW QSLs” plus “LoTW QSLs in Process”.</div></div>
    <label for="as-box" class="mono small muted" style="letter-spacing:.1em">ACCOUNT STATUS TABLE</label>
    <textarea id="as-box" rows="5" spellcheck="false" style="min-height:120px" placeholder="Award&#9;New LoTW QSLs&#9;LoTW QSLs in Process&#9;DXCC Credits Awarded&#9;Total&#10;Mixed *&#9;…"></textarea>
    <div style="display:flex;gap:12px;align-items:center"><button class="btn primary" id="check">Check</button><span class="small" role="status">${state.asMsg}</span></div>
    <div id="result" style="display:flex;flex-direction:column;gap:12px">${checkResult(state.check)}</div>
  </section>`;
}

function render() {
  const box = document.getElementById('as-box');
  const text = box ? box.value : '';
  document.getElementById('main').innerHTML = profileSection() + clubLogSection() + statusSection() + dxmonSection();
  document.getElementById('as-box').value = text;
  wire();
}

function wire() {
  const $ = (id) => document.getElementById(id);
  const d = state.draft;
  const toggle = (list, c, on) => { const s = new Set(list); on ? s.add(c) : s.delete(c); return [...s]; };
  document.querySelectorAll('[data-band]').forEach((b) => (b.onchange = () => {
    d.bands = BANDS.filter((x) => toggle(d.bands, b.dataset.band, b.checked).includes(x)); state.profMsg = ''; render();
  }));
  document.querySelectorAll('[data-mode]').forEach((b) => (b.onchange = () => {
    d.modes = MODES.filter((x) => toggle(d.modes, b.dataset.mode, b.checked).includes(x)); state.profMsg = ''; render();
  }));
  $('reset').onclick = () => { state.draft = { bands: DEFAULT.bands.slice(), modes: DEFAULT.modes.slice() }; render(); };
  $('saveprof').onclick = async () => {
    try {
      const p = await api('/api/settings/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(state.draft) });
      state.saved = { bands: p.bands, modes: p.modes }; state.draft = { bands: p.bands.slice(), modes: p.modes.slice() };
      state.profMsg = '<span class="up">Saved — every view now uses this profile.</span>';
      renderChrome({ title: 'Settings', subtitle: esc(profileText(state.saved)) });
      render();
    } catch (err) { state.profMsg = `<span class="err">${esc(err.message)}</span>`; render(); }
  };
  $('mw').onclick = async () => {
    state.mwMsg = 'Fetching from Club Log…'; render();
    try {
      const r = await postJSON('/api/clublog/refresh');
      state.mwMsg = `<span class="up">Updated: ${r.entities_ranked} entities ranked.</span>`;
      await loadData(); render();
    } catch (err) { state.mwMsg = `<span class="err">${esc(err.message)}</span>`; render(); }
  };
  $('check').onclick = async () => {
    const text = $('as-box').value;
    if (!text.trim()) { state.asMsg = '<span class="err">Paste the Account Status table first.</span>'; render(); return; }
    state.asMsg = 'Checking…'; render();
    try {
      const r = await postJSON('/api/status-check', { text });
      state.check = Object.assign(r, { checked_at: new Date().toISOString(), is_current_import: true });
      state.asMsg = ''; $('as-box').value = ''; render();
    } catch (err) { state.asMsg = `<span class="err">${esc(err.message)}</span>`; render(); }
  };
  wireDX();
}

function wireDX() {
  const $ = (id) => document.getElementById(id);
  const url = () => $('dx-url').value;
  $('dx-url').oninput = (e) => { state.dxDraft = e.target.value; };
  const busy = async (msg, fn) => {
    state.dxBusy = true; state.dxMsg = msg; render();
    try { await fn(); } catch (err) { state.dxMsg = `<span class="err">${esc(err.message)}</span>`; }
    state.dxBusy = false; render();
  };
  $('dx-test').onclick = () => busy('Trying DX Monitor…', async () => {
    const r = await postJSON('/api/dxmon/test', { url: url() });
    state.dxMsg = r.ok ? `<span class="up">DX Monitor answered: ${r.entry_count} DXpeditions, ${r.watched_count} watched. Not saved yet.</span>`
      : `<span class="err">${esc(r.error)}</span>`;
  });
  $('dx-save').onclick = () => busy('Saving…', async () => {
    state.dx = await api('/api/settings/dxmon', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: url() }) });
    state.dxDraft = null;
    state.dxMsg = state.dx.enabled ? '<span class="up">Saved.</span>' : '<span class="up">Saved: DX Monitor features are off.</span>';
  });
  if ($('dx-refresh')) $('dx-refresh').onclick = () => busy('Refreshing from DX Monitor…', async () => {
    state.dx = await postJSON('/api/dxmon/refresh'); state.dxMsg = '';
  });
  const d = state.dx || {};
  const decide = (name, dxcc, what) => busy('Saving…', async () => {
    state.dx = await postJSON('/api/dxmon/names', { name, dxcc });
    state.dxMsg = `<span class="up">${esc(what)}</span>`;
  });
  document.querySelectorAll('[data-approve]').forEach((b) => (b.onclick = () => {
    const u = d.unplaced[+b.dataset.approve];
    decide(u.name, u.suggestion.dxcc, `“${u.name}” is now ${u.suggestion.name}.`);
  }));
  document.querySelectorAll('[data-use]').forEach((b) => (b.onclick = () => {
    const u = d.unplaced[+b.dataset.use];
    const sel = document.querySelector(`[data-pick="${b.dataset.use}"]`);
    if (!sel.value) { state.dxMsg = '<span class="err">Choose an entity from the list first.</span>'; render(); return; }
    decide(u.name, +sel.value, `“${u.name}” is now ${sel.options[sel.selectedIndex].text}.`);
  }));
  document.querySelectorAll('[data-ignore]').forEach((b) => (b.onclick = () => {
    const u = d.unplaced[+b.dataset.ignore];
    decide(u.name, null, `“${u.name}” will be ignored.`);
  }));
  document.querySelectorAll('[data-forget]').forEach((b) => (b.onclick = () => {
    const x = d.decisions[+b.dataset.forget];
    busy('Removing…', async () => {
      state.dx = await api(`/api/dxmon/names?name_norm=${encodeURIComponent(x.name_norm)}`, { method: 'DELETE' });
      state.dxMsg = `<span class="up">Removed: “${esc(x.name)}” needs your OK again if it still appears in ADXO.</span>`;
    });
  }));
}

async function loadData() {
  const [mx, prof, status, check] = await Promise.all([api('/api/view/matrix'), api('/api/settings/profile'),
    api('/api/status'), api('/api/status-check/latest')]);
  state.mx = mx.no_data ? { entities: [] } : mx;
  state.saved = { bands: prof.bands, modes: prof.modes };
  if (!state.draft) state.draft = { bands: prof.bands.slice(), modes: prof.modes.slice() };
  state.mwFetched = status.most_wanted_fetched_at;
  state.check = check;
  state.noData = !!mx.no_data;
  // Settings shows the stored DX Monitor state and never waits on DX Monitor
  // itself (auto=false); a problem here must not break the rest of Settings.
  try {
    state.dx = await api('/api/dxmon?auto=false');
  } catch (err) {
    let url = '';
    try { url = (await api('/api/settings/dxmon')).url; } catch (e) { /* unknown */ }
    state.dx = { enabled: !!url, url, ok: false, error: err.message };
  }
}

async function load() {
  try {
    await loadData();
    renderChrome({ title: 'Settings', subtitle: esc(profileText(state.saved)) });
    render();
    // Links such as /settings#dx-h land on their section once it is drawn.
    if (location.hash.length > 1) {
      const el = document.getElementById(location.hash.slice(1));
      if (el) el.scrollIntoView();
    }
    if (state.noData) {
      document.getElementById('main').insertAdjacentHTML('afterbegin',
        '<div class="notice held"><div><div class="t">No matrix imported yet</div><div>The missing counts appear after your first import. <a href="/import">Import now</a></div></div></div>');
    }
  } catch (err) {
    renderChrome({ title: 'Settings' });
    showError('main', err);
  }
}
load();
