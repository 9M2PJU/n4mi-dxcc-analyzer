// Suggestions for DX Monitor (D55, D57): what to put in DX Monitor's Needed list.
// Read-only towards DX Monitor; Dan adds entries there himself.
'use strict';

const state = { data: null, busy: false, saving: false, msg: '' };

const join = (a) => a.join(', ');
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
const day = (iso) => `${MONTHS[+iso.slice(5, 7) - 1]} ${+iso.slice(8, 10)}`;   // ADXO dates are plain days

function inDxTag(v) {
  return v ? '<span class="tag indx" title="An entry in DX Monitor\'s Needed list already catches these spots">ALREADY IN DX MONITOR</span>' : '';
}

function copyBtn(name) {
  return `<button type="button" class="btn tiny noprint" data-copy="${esc(name)}" aria-label="Copy ${esc(name)}">Copy</button>`;
}

function why(e) {
  const t = e.dxpedition;
  if (!t) return '<span class="muted small">Easiest remaining</span>';
  const dates = `${t.callsign} · ${day(t.begin)} to ${day(t.end)}`;
  let out = t.kind === 'air'
    ? `<span class="tag air" title="DXpedition on the air: ${esc(dates)}">ON AIR · ${esc(t.callsign)}</span>`
    : `<span class="tag soon" title="DXpedition starting soon: ${esc(dates)}">${day(t.begin)} · ${esc(t.callsign)}</span>`;
  if (!t.watched) out += ` <span class="tag nw" title="${esc(t.callsign)} isn't on DX Monitor's Watched list">NOT WATCHED</span>`;
  return out;
}

function creditsText(s) {
  const b = s.bands.length > 1 ? s.bands.slice(0, -1).join(', ') + ' or ' + s.bands.slice(-1) : s.bands[0];
  const m = s.modes.length > 1 ? s.modes.slice(0, -1).join(', ') + ' or ' + s.modes.slice(-1) : s.modes[0];
  if (b && m) return `${b} with ${m}`;
  return b ? `${b}, any mode` : `${m}, any band`;
}

function chips(list, empty) {
  return list.length ? list.map((x) => `<span class="chip">${esc(x)}</span>`).join('')
    : `<span class="chip any">${empty}</span>`;
}

function strip(d) {
  const x = d.dxmon;
  let dx;
  if (!x.enabled) {
    dx = 'DX Monitor isn\'t connected, so entries already in its Needed list can\'t be flagged. <a href="/settings#dx-h">Add its address in Settings</a>';
  } else if (x.needed_state === 'not_fetched') {
    dx = 'DX Monitor\'s Needed list hasn\'t been read yet. Press Refresh to check which suggestions are already in it.';
  } else if (x.needed_state === 'failed') {
    dx = `<span style="color:var(--amber)">DX Monitor's Needed list couldn't be read (${esc(x.needed_error || x.error || 'no answer')}), so nothing is flagged.</span>`;
  } else {
    const n = d.entities.concat(d.slots).filter((s) => s.in_dx_monitor).length;
    const un = d.dxmon_unmatched.length
      ? ` · <span class="nwtext" title="${esc(join(d.dxmon_unmatched))}">${d.dxmon_unmatched.length} Needed entr${d.dxmon_unmatched.length > 1 ? 'ies don\'t' : 'y doesn\'t'} match a HamAlert entity name: ${esc(join(d.dxmon_unmatched))}</span>` : '';
    const skipped = x.needed_skipped ? ` · ${x.needed_skipped} unreadable entr${x.needed_skipped > 1 ? 'ies' : 'y'} skipped` : '';
    const age = x.needed_state === 'stale'
      ? ` · <span style="color:var(--amber)">Needed list as read ${esc(when(x.needed_fetched_at))}; the last read failed: ${esc(x.needed_error)}</span>`
      : ` · checked ${esc(when(x.needed_fetched_at || x.tried_at))}`;
    dx = `<strong>${n}</strong> of these ${n === 1 ? 'is' : 'are'} already in DX Monitor's Needed list (${d.dxmon_needed_count} entr${d.dxmon_needed_count === 1 ? 'y' : 'ies'})${age}${x.ok ? '' : ` · <span style="color:var(--amber)">DX Monitor's last answer failed: ${esc(x.error)}</span>`}${skipped}${un}`;
  }
  const refresh = x.enabled ? `<button type="button" class="btn noprint" id="refresh"${state.busy ? ' disabled' : ''}>${state.busy ? 'Refreshing…' : 'Refresh'}</button>` : '';
  return `<section class="strip dx" aria-label="About these suggestions"><div class="k">FOR DX MONITOR</div>
    <div style="flex:1 1 520px;display:flex;flex-direction:column;gap:4px">
      <div>Best targets for DX Monitor's Needed list: entities you've never confirmed, then band and mode gaps on entities you have. Easiest first by Club Log Most Wanted; DXpeditions on the air or starting within 30 days go to the top.</div>
      <div class="muted small" role="status">${dx}</div></div>
    <form class="counts noprint" aria-label="How many suggestions">
      <label>Entities <input type="number" id="n-ent" min="1" max="100" value="${d.settings.entities}"${state.saving ? ' disabled' : ''}></label>
      <label>Band slots <input type="number" id="n-slot" min="1" max="100" value="${d.settings.slots}"${state.saving ? ' disabled' : ''}></label>
    </form>${refresh}</section>`;
}

function entitiesTable(d) {
  const rows = d.entities.map((e, i) => `<tr${e.dxpedition ? ' class="dxrow"' : ''}>
    <td class="n">${i + 1}</td>
    <td><div class="nmcell"><span class="ha">${esc(e.hamalert_name)}</span>${copyBtn(e.hamalert_name)}</div></td>
    <td class="px">${esc(e.prefix || '—')}</td>
    <td class="num">${e.mw_rank != null ? '#' + e.mw_rank : '—'}</td>
    <td>${why(e)}</td>
    <td>${inDxTag(e.in_dx_monitor)}</td></tr>`).join('');
  return `<section aria-labelledby="ent-h" class="advsec">
    <div class="head"><h2 id="ent-h">Entities <span class="n">${d.entities.length}</span> <span class="muted hsub">of ${d.entities_available} never confirmed</span></h2>
      <div class="muted small">In DX Monitor: leave band and mode unticked (any band, any mode)</div></div>
    ${d.entities.length ? `<div class="mxwrap"><table class="adv">
      <thead><tr><th scope="col">#</th><th scope="col">HamAlert name</th><th scope="col">Prefix</th><th scope="col">Most Wanted</th><th scope="col">Why</th><th scope="col">DX Monitor</th></tr></thead>
      <tbody>${rows}</tbody></table></div>`
    : '<div class="panel muted">No never-confirmed entity left to suggest.</div>'}</section>`;
}

function filters(st) {
  // Boxes are off while a save runs, so two saves can never cross on the server.
  const dis = state.saving ? ' disabled' : '';
  const b = st.band_choices.map((c) => `<label class="fbox"><input type="checkbox" data-band="${c.code}"${st.bands.includes(c.code) ? ' checked' : ''}${dis}> ${esc(c.label)}</label>`).join('');
  const c = st.continent_choices.map((x) => `<label class="fbox sans"><input type="checkbox" data-cont="${x.code}"${st.continents.includes(x.code) ? ' checked' : ''}${dis}> ${esc(x.label)}</label>`).join('');
  return `<form class="panel filters noprint" aria-label="Band slot filters">
    <fieldset><legend>BANDS</legend>${b}</fieldset>
    <fieldset><legend>CONTINENTS</legend>${c}</fieldset>
    <div class="muted small">Saved for next time. An unticked band is never suggested; an unticked continent's entities are left out of this list. <button type="button" class="linkbtn" id="reset"${state.saving ? ' disabled' : ''}>Reset</button> to 160 m and 6 m off, all continents on.${state.saving ? ' · Saving…' : ''}</div>
  </form>`;
}

function filterSummary(st) {
  const offB = st.band_choices.filter((c) => !st.bands.includes(c.code)).map((c) => c.label);
  const offC = st.continent_choices.filter((c) => !st.continents.includes(c.code)).map((c) => c.label);
  return (offB.length ? `${join(offB)} left out` : 'all bands') + (offC.length ? ` · without ${join(offC)}` : '');
}

function slotsTable(d) {
  const rows = d.slots.map((s, i) => `<tr>
    <td class="n">${i + 1}</td>
    <td><div class="nmcell"><span class="ha">${esc(s.hamalert_name)}</span>${copyBtn(s.hamalert_name)}</div></td>
    <td><div class="chips">${chips(s.dxmon_bands, 'any band')}${chips(s.dxmon_modes.map((m) => m.toUpperCase()), 'any mode')}</div></td>
    <td><span class="cr">${s.credits}</span> <span class="muted small">· ${esc(creditsText(s))}</span></td>
    <td class="num">${s.mw_rank != null ? '#' + s.mw_rank : '—'}</td>
    <td>${inDxTag(s.in_dx_monitor)}</td></tr>`).join('');
  const none = d.settings.bands.length === 0 || d.settings.continents.length === 0
    ? 'Tick at least one band and one continent to see band slots.'
    : 'No band slot matches these filters.';
  return `<section aria-labelledby="slot-h" class="advsec">
    <div class="head"><h2 id="slot-h">Band slots <span class="n">${d.slots.length}</span> <span class="muted hsub">on entities you've confirmed · ${esc(filterSummary(d.settings))}</span></h2>
      <div class="muted small">Most credits for one contact first, then easiest</div></div>
    ${filters(d.settings)}
    ${d.slots.length ? `<div class="mxwrap"><table class="adv">
      <thead><tr><th scope="col">#</th><th scope="col">HamAlert name</th><th scope="col">Tick in DX Monitor</th><th scope="col">One contact credits</th><th scope="col">Most Wanted</th><th scope="col">DX Monitor</th></tr></thead>
      <tbody>${rows}</tbody></table></div>` : `<div class="panel muted">${none}</div>`}</section>`;
}

function render() {
  const d = state.data;
  document.getElementById('main').innerHTML = strip(d) + entitiesTable(d) + slotsTable(d) +
    `<section class="muted small" aria-label="Notes" style="display:flex;flex-direction:column;gap:6px">
      <div>Names are HamAlert's spellings: copy them exactly into DX Monitor and into your HamAlert trigger. If a Needed entry never shows a hit, check its spelling in HamAlert's DXCC picker.</div>
      <div>Modes in DX Monitor's terms: Phone = SSB, Digital = FT8 and FT4 (RTTY can't be selected there). Anything awaiting credit or covered by a paper card is left out; won't-submit marks stay in, since that confirmation will never be credited.</div>
      <div>Club Log Most Wanted ranks${d.most_wanted_fetched_at ? ` from ${esc(when(d.most_wanted_fetched_at))}` : ': not fetched yet, so entities are in name order. <a href="/settings">Refresh them in Settings</a>'}.</div>
      ${state.msg ? `<div role="status" class="err">${esc(state.msg)}</div>` : ''}</section>`;
  wire();
}

function wire() {
  document.querySelectorAll('[data-copy]').forEach((b) => {
    b.onclick = async () => {
      const ok = await copyText(b.dataset.copy);
      b.textContent = ok ? 'Copied' : 'Copy failed';
      setTimeout(() => { b.textContent = 'Copy'; }, 1500);
    };
  });
  const ref = document.getElementById('refresh');
  if (ref) ref.onclick = async () => {
    state.busy = true; render();
    try { await postJSON('/api/dxmon/refresh'); } catch (e) { /* the strip shows the failure */ }
    await load(false);
  };
  const saveCounts = () => {
    const e = +document.getElementById('n-ent').value, s = +document.getElementById('n-slot').value;
    if (!(e >= 1 && e <= 100 && s >= 1 && s <= 100)) { state.msg = 'Enter 1 to 100 for each count.'; render(); return; }
    save({ entities: e, slots: s });
  };
  document.getElementById('n-ent').onchange = saveCounts;
  document.getElementById('n-slot').onchange = saveCounts;
  document.querySelectorAll('[data-band],[data-cont]').forEach((box) => {
    box.onchange = () => save({
      bands: [...document.querySelectorAll('[data-band]:checked')].map((x) => x.dataset.band),
      continents: [...document.querySelectorAll('[data-cont]:checked')].map((x) => x.dataset.cont),
    });
  });
  document.getElementById('reset').onclick = () => save({
    bands: state.data.settings.default_bands.slice(),
    continents: state.data.settings.continent_choices.map((c) => c.code),
  });
}

async function save(change) {
  // Show the change at once and send the whole new state, so a second click
  // while the first save is running builds on it instead of undoing it.
  const st = Object.assign(state.data.settings, change);
  state.saving = true; state.msg = ''; render();
  try {
    await api('/api/settings/advisor', { method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ entities: st.entities, slots: st.slots, bands: st.bands, continents: st.continents }) });
  } catch (err) { state.msg = `Not saved: ${err.message}`; }
  state.saving = false;
  await load(false);
}

async function load(auto = true) {
  try {
    const d = await api(`/api/advisor${auto ? '' : '?auto=false'}`);
    if (d.no_data) { document.getElementById('main').innerHTML = NO_DATA_HTML; return; }
    state.data = d;
    state.busy = false;
    const sub = document.querySelector('header.top .sub');
    if (sub) sub.textContent = `Matrix imported ${when(d.imported_at)} · ${profileText(d.profile)}`;
    render();
  } catch (err) { showError('main', err); }
}

renderChrome({ title: 'Suggestions for DX Monitor', subtitle: '',
  actions: '<button class="btn" onclick="window.print()">Print</button>' });
load();
