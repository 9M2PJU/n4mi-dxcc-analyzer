// Missing Entities (primary view): never-credited entities, grouped by continent.
'use strict';

const state = { data: null, status: null, marks: [], sort: 'easy', group: 'continent', hideAwaiting: false,
  dx: null, dxBusy: false };

const SORTS = {
  easy: ['Most Wanted, easiest first', (a, b) => rankKey(a, true) - rankKey(b, true) || byName(a, b)],
  rare: ['Most Wanted, rarest first', (a, b) => rankKey(a, false) - rankKey(b, false) || byName(a, b)],
  name: ['Entity name', (a, b) => byName(a, b)],
  prefix: ['Prefix', (a, b) => a.prefix.localeCompare(b.prefix) || byName(a, b)],
  // D54: only offered while DX Monitor is switched on.
  dx: ['DXpeditions first', (a, b) => dxScore(b) - dxScore(a) || rankKey(a, true) - rankKey(b, true) || byName(a, b)],
};
const byName = (a, b) => a.name.localeCompare(b.name);
// Club Log rank 1 = most wanted. Easiest first = highest rank number first.
// Entities without a rank always sort last.
function rankKey(e, easiest) {
  if (e.mw_rank == null) return 1e6;
  return easiest ? -e.mw_rank : e.mw_rank;
}

// ---------- DXpeditions from DX Monitor (D54; optional) ----------
const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
// ADXO dates are plain days ("2026-10-16"); never shift them through a time zone.
const day = (iso) => `${MONTHS[+iso.slice(5, 7) - 1]} ${+iso.slice(8, 10)}`;
const dxOn = () => !!(state.dx && state.dx.enabled && state.dx.tags);
const dxFirst = (e) => (dxOn() && (state.dx.tags[e.dxcc] || [])[0]) || null;
function dxScore(e) {
  const t = dxFirst(e);
  return !t ? 0 : t.kind === 'air' ? 2 : 1;
}

function dxTags(e) {
  const all = dxOn() ? state.dx.tags[e.dxcc] || [] : [];
  if (!all.length) return '';
  const t = all[0];
  const more = all.length > 1 ? ` · also ${all.slice(1).map((x) => `${x.callsign} ${day(x.begin)}–${day(x.end)}`).join(', ')}` : '';
  const dates = `${t.callsign} · ${day(t.begin)} to ${day(t.end)}${more}`;
  let out = t.kind === 'air'
    ? `<span class="tag air" title="DXpedition on the air: ${esc(dates)}">ON AIR · ${esc(t.callsign)}</span>`
    : `<span class="tag soon" title="DXpedition starting soon: ${esc(dates)}">${day(t.begin)} · ${esc(t.callsign)}</span>`;
  if (!t.watched) out += `<span class="tag nw" title="${esc(t.callsign)} isn't on DX Monitor's Watched list">NOT WATCHED</span>`;
  return out;
}

function dxStrip() {
  const d = state.dx;
  if (!d || !d.enabled) return '';
  const unplaced = (d.unplaced || []).length;
  const ask = unplaced ? ` · <a href="/settings#dx-h">${unplaced} ADXO name${unplaced > 1 ? 's' : ''} need${unplaced > 1 ? '' : 's'} your OK in Settings</a>` : '';
  const btn = `<button class="btn noprint" id="dxref"${state.dxBusy ? ' disabled' : ''}>${state.dxBusy ? 'Refreshing…' : 'Refresh'}</button>`;
  if (!d.fetched_at) {
    return `<section class="strip dx stale" aria-label="DXpeditions"><div class="k">DXPEDITIONS</div>
      <div style="flex:1 1 480px" role="status">DX Monitor hasn't answered yet${d.error ? `: ${esc(d.error)}` : '.'} <a href="/settings#dx-h">Check the DX Monitor settings</a></div>${btn}</section>`;
  }
  const s = d.summary;
  const parts = [s.on_air && `<strong>${s.on_air}</strong> needed entit${s.on_air === 1 ? 'y' : 'ies'} on the air`,
    s.soon && `<strong>${s.soon}</strong> starting within ${d.window_days} days`].filter(Boolean);
  const head = parts.length
    ? parts.join(' · ') + (s.not_watched ? `, <span class="nwtext">${s.not_watched} not on DX Monitor's Watched list</span>` : '')
    : `No needed entity has a DXpedition on the air or starting within ${d.window_days} days`;
  const later = s.later ? ` · ${s.later} more needed entit${s.later > 1 ? 'ies have DXpeditions' : 'y has a DXpedition'} starting later than ${d.window_days} days out` : '';
  const fresh = d.ok
    ? `<div class="muted small">From DX Monitor · its list updated ${esc(when(d.adxo_updated))} · checked ${esc(when(d.tried_at))}${later}${ask}</div>`
    : `<div class="small" role="status" style="color:var(--amber)">Last try ${esc(when(d.tried_at))}: ${esc(d.error)} Showing its list as received at ${esc(when(d.fetched_at))}. <a href="/settings#dx-h">Check the DX Monitor settings</a>${ask}</div>`;
  return `<section class="strip dx${d.ok ? '' : ' stale'}" aria-label="DXpeditions"><div class="k">DXPEDITIONS</div>
    <div style="flex:1 1 480px;display:flex;flex-direction:column;gap:4px"><div>${head}</div>${fresh}</div>${btn}</section>`;
}

async function loadDX(refresh) {
  try {
    state.dx = refresh ? await postJSON('/api/dxmon/refresh') : await api('/api/dxmon');
  } catch (err) {
    // The page works fully without DX Monitor. If the app itself can't answer,
    // show no DXpedition strip at all rather than guess the feature is on.
    state.dx = { enabled: false };
  }
  state.dxBusy = false;
  if (state.data) render();
}

function entRow(e) {
  const others = Object.keys(e.marks).filter((c) => c !== 'MIXED').length;
  const tags = dxTags(e) + slotTags(e, 'MIXED')
    + (others ? `<span class="ot" title="Band and mode slots marked for this entity">+${others} slot${others > 1 ? 's' : ''}</span>` : '')
    + (e.sat_credited ? '<span class="tag sat" title="Already credited for Satellite DXCC">SAT</span>' : '');
  const rank = e.mw_rank != null ? `<span class="rk" title="Club Log Most Wanted rank">#${e.mw_rank}</span>` : '';
  return `<button type="button" class="ent me click${dxScore(e) ? ' dx' : ''}" data-dxcc="${e.dxcc}" title="Mark ${esc(e.name)} as awaiting credit or won't submit"><div class="px">${esc(e.prefix || '—')}</div><div class="nm">${esc(e.name)}</div>${rank}${tags ? `<div class="tg">${tags}</div>` : ''}</button>`;
}

function render() {
  const d = state.data;
  const s = d.summary;
  const awaitingEntities = d.entities.filter((e) => (e.marks.MIXED || {}).state === 'awaiting').length;
  const cardEntities = d.entities.filter((e) => (e.cards.MIXED || []).length).length;
  const slotCats = new Set(d.profile.bands.concat(d.profile.modes));
  const slotMarks = state.marks.filter((m) => m.state === 'awaiting' && slotCats.has(m.category)).length;
  const check = state.status && state.status.last_status_check;
  const checkTxt = !check ? 'Mixed · not yet checked against LoTW Account Status'
    : check.snapshot_id !== d.snapshot_id ? 'Mixed · last LoTW check was on an earlier import'
    : check.reconciled ? 'Mixed · matches LoTW Account Status' : '<span class="err">Mixed · does NOT match LoTW Account Status</span>';

  if (state.sort === 'dx' && !dxOn()) state.sort = 'easy';
  let list = d.entities.slice();
  if (state.hideAwaiting) list = list.filter((e) => (e.marks.MIXED || {}).state !== 'awaiting');
  list.sort(SORTS[state.sort][1]);
  let groups;
  if (state.group === 'continent') {
    groups = CONTINENTS.map(([c, name]) => ({ name, items: list.filter((e) => e.continent === c) }))
      .filter((g) => g.items.length);
    // DXpeditions first: continents with an entity on the air come first.
    if (state.sort === 'dx') groups.sort((a, b) => Math.max(0, ...b.items.map(dxScore)) - Math.max(0, ...a.items.map(dxScore)));
  } else {
    groups = [{ name: SORTS[state.sort][0].toUpperCase(), items: list }];
  }

  const since = d.since_last;
  let sinceTxt = 'First import — changes appear here after the next one.';
  if (since) {
    const n1 = since.new_entities.length, n2 = since.new_slots.length, n3 = since.lost.length;
    sinceTxt = (n1 || n2 || n3)
      ? [n1 && `+${n1} entit${n1 === 1 ? 'y' : 'ies'}${n1 <= 5 ? ' (' + since.new_entities.map((x) => esc(x.name)).join(', ') + ')' : ''}`,
         n2 && `+${n2} band and mode slot${n2 === 1 ? '' : 's'}`,
         n3 && `<span class="err">${n3} credit${n3 === 1 ? '' : 's'} lost</span>`].filter(Boolean).join(' · ')
      : 'No change in your profile.';
    sinceTxt += ` <span class="muted small">(compared with the import of ${esc(when(since.previous_saved_at))})</span>`;
  }

  const mw = d.most_wanted_fetched_at
    ? `Club Log Most Wanted ranks from ${esc(when(d.most_wanted_fetched_at))}.`
    : 'No Club Log Most Wanted list yet, so the Most Wanted sorts fall back to name.';

  document.getElementById('main').innerHTML = `
    <section class="stats" aria-label="Summary">
      <div class="panel stat"><div class="k">ENTITIES CREDITED</div>
        <div class="v">${s.entities_credited} <small>/ ${s.entities_current}</small></div>
        <div class="muted small">${checkTxt}</div></div>
      <div class="panel stat hot"><div class="k">NEVER CONFIRMED</div><div class="v">${s.entities_missing}</div>
        <div class="muted small">${awaitingEntities} awaiting credit in LoTW${cardEntities ? ` · ${cardEntities} with a paper card` : ''}</div></div>
      <div class="panel stat"><div class="k">MISSING BAND SLOTS</div><div class="v">${num(s.slots_missing + s.slots_missing_new)}</div>
        <div class="muted small">${num(s.slots_missing)} on credited entities, ${num(s.slots_missing_new)} on never-confirmed · ${slotMarks} awaiting credit</div></div>
      <div class="panel stat"><div class="k">COMPLETE IN PROFILE</div><div class="v">${s.complete}</div>
        <div class="muted small">${s.one_slot_away} more are one slot away</div></div>
    </section>
    ${s.satellite_missing != null ? `<div class="strip"><div class="k">SATELLITE</div><div>${s.satellite_missing} entities still needed for Satellite DXCC (a separate award) · see Missing Band Slots</div></div>` : ''}
    <section class="strip" aria-label="Since last import"><div class="k">SINCE LAST IMPORT</div><div>${sinceTxt}</div></section>
    ${dxStrip()}
    <section aria-labelledby="me-h" style="display:flex;flex-direction:column;gap:16px">
      <div class="head">
        <h2 id="me-h">Missing entities <span class="n">${list.length}</span></h2>
        <div class="controls noprint">
          <label>Sort <select id="sort">${Object.entries(SORTS).filter(([k]) => k !== 'dx' || dxOn()).map(([k, [t]]) =>
            `<option value="${k}"${k === state.sort ? ' selected' : ''}>${t}</option>`).join('')}</select></label>
          <label>Show <select id="group">
            <option value="continent"${state.group === 'continent' ? ' selected' : ''}>By continent</option>
            <option value="list"${state.group === 'list' ? ' selected' : ''}>One list</option></select></label>
          <label class="chk"><input type="checkbox" id="hide"${state.hideAwaiting ? ' checked' : ''}> Hide entities awaiting credit</label>
        </div>
      </div>
      <div class="legend"><span class="li"><span class="tag await">AWAITING</span> confirmed in LoTW, not yet credited</span>
        <span class="li"><span class="tag card">${CARD_ICON}CARD</span> paper QSL, not yet credited</span>
        ${dxOn() ? `<span class="li"><span class="tag air">ON AIR</span> DXpedition active now</span>
        <span class="li"><span class="tag soon">START DATE</span> starts within ${state.dx.window_days} days</span>
        <span class="li"><span class="tag nw">NOT WATCHED</span> not on DX Monitor's Watched list</span>` : ''}</div>
      <div class="groups${state.group === 'list' ? ' one' : ''}">
        ${groups.map((g) => `<div class="group"><div class="gh"><span>${esc(g.name)}</span><span class="n">${g.items.length}</span></div>
          ${g.items.map(entRow).join('')}</div>`).join('') || '<div class="muted">Nothing to show.</div>'}
      </div>
      <div class="muted small">${mw} <a class="noprint" href="/settings">Refresh in Settings</a> · Select an entity to mark it and the bands and modes its confirmation covers.</div>
    </section>`;

  document.getElementById('sort').onchange = (e) => { state.sort = e.target.value; render(); };
  document.getElementById('group').onchange = (e) => { state.group = e.target.value; render(); };
  document.getElementById('hide').onchange = (e) => { state.hideAwaiting = e.target.checked; render(); };
  const dxref = document.getElementById('dxref');
  if (dxref) dxref.onclick = () => { state.dxBusy = true; render(); loadDX(true); };
  document.querySelectorAll('.ent.click').forEach((b) => (b.onclick = () => {
    const ent = state.data.entities.find((e) => e.dxcc === +b.dataset.dxcc);
    openMarkMenu(ent, state.data.profile, load);
  }));
}

async function load() {
  try {
    const [data, status, marks] = await Promise.all([api('/api/view/entities'), api('/api/status'), api('/api/marks')]);
    if (data.no_data) {
      renderChrome({ title: 'What\'s still needed', subtitle: 'No matrix imported yet' });
      document.getElementById('main').innerHTML = NO_DATA_HTML;
      return;
    }
    Object.assign(state, { data, status, marks: marks.marks });
    renderChrome({
      title: `${data.callsign || 'DXCC'} · What's still needed`,
      subtitle: `Matrix imported ${esc(when(data.saved_at || data.imported_at))} · ${esc(profileText(data.profile))}`,
      actions: '<a class="btn primary" href="/import">Paste new matrix</a>' + EXPORT_MENU + '<button class="btn" onclick="window.print()">Print</button>',
    });
    render();
    // DXpeditions arrive after the page is drawn, so a slow or stopped
    // DX Monitor never holds up Missing Entities (D54).
    if (state.dx === null) loadDX(false);
  } catch (err) {
    renderChrome({ title: 'What\'s still needed' });
    showError('main', err);
  }
}
load();
