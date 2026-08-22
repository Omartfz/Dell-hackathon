/* SafeContext console. No framework, no build step — the box needs Python only. */
'use strict';

const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const api = async (path, opts = {}) => {
  const r = await fetch('/api' + path, {
    headers: { 'content-type': 'application/json' }, ...opts,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const money = v => v == null ? '–' : '$' + Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
const pct = v => v == null ? '–' : (v * 100).toFixed(1) + '%';
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function highlight(obj) {
  return esc(JSON.stringify(obj, null, 2))
    .replace(/&quot;([^&]+?)&quot;(\s*:)/g, '<span class="k">"$1"</span>$2')
    .replace(/:\s*&quot;([^&]*?)&quot;/g, ': <span class="s">"$1"</span>')
    .replace(/:\s*(-?\d+\.?\d*)/g, ': <span class="n">$1</span>')
    .replace(/:\s*(true|false|null)/g, ': <span class="b">$1</span>');
}

function alertBox(msg, kind = 'warn') {
  $('#alert').innerHTML = msg ? `<div class="${kind}-box">${esc(msg)}</div>` : '';
}

/* ---------------------------------------------------------------- tabs */
$$('nav.tabs button').forEach(b => b.onclick = () => {
  $$('nav.tabs button').forEach(x => x.classList.toggle('active', x === b));
  $$('section[data-panel]').forEach(s => s.hidden = s.dataset.panel !== b.dataset.tab);
  if (b.dataset.tab === 'mongo') loadMongo();
  if (b.dataset.tab === 'policy') loadPolicies();
});

/* -------------------------------------------------------------- header */
let ROLE = 'ap_analyst';

function paintCounters(c) {
  if (!c) return;
  $('#m-processed').textContent = c.processed ?? 0;
  $('#m-esc').textContent = c.tier2 ?? 0;
  $('#m-exposed').textContent = c.sensitive_exposed ?? 0;
  $('#m-queued').textContent = c.queued ?? 0;
}

async function health() {
  try {
    const h = await api('/health');
    const model = h.inference.local_model;
    $('#model-badge').textContent = model ? `${model} · ON-BOX` : 'no local model';
    $('#model-badge').className = 'badge ' + (model ? 'on' : 'off');
    $('#mongo-badge').textContent = h.mongo.replica_set ? 'mongo · replica set' : 'mongo · standalone';
    $('#mongo-badge').className = 'badge ' + (h.mongo.replica_set ? 'on' : 'off');
    if (!h.mongo.replica_set) alertBox(h.mongo.detail);
    else if (!model) alertBox('No local model found. Tiers 0 and 2 work; tier 1 reasoning is skipped.');
    else alertBox('');
    paintCounters(h.agent.counters);
    $('#stream-state').textContent = h.agent.running ? 'watching' : 'stopped';
  } catch (e) { alertBox('API unreachable: ' + e.message); }
  try { ROLE = (await api('/policies')) && ROLE; } catch (_) { }
  $('#btn-role').textContent = 'Role: ' + ROLE;
}

/* -------------------------------------------------------------- stream */
const MAX_ROWS = 220;

function pushEvent(m) {
  const box = $('#stream');
  if (box.firstElementChild?.className === 'empty') box.innerHTML = '';
  const v = m.verdict || {};
  const row = document.createElement('div');
  row.className = 'ev';
  row.innerHTML =
    `<span class="tier t-${v.tier ?? 0}"></span>` +
    `<span class="m">${esc(m.merchant || m.kind)}</span>` +
    `<span class="amt">${money(m.amount)}</span>` +
    `<span class="ms">${m.ms}ms</span>`;
  row.title = `${v.headline || ''}\n${(v.reasons || []).join('\n')}`;
  box.prepend(row);
  while (box.children.length > MAX_ROWS) box.lastElementChild.remove();
  paintCounters(m.counters);
  if (v.tier === 2) loadInbox();
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.type === 'event') pushEvent(m);
    else if (m.type === 'status') { paintCounters(m.counters); $('#stream-state').textContent = m.running ? 'watching' : 'stopped'; }
    else if (m.type === 'log') $('#stream-hint').textContent = m.message;
  };
  ws.onclose = () => setTimeout(connect, 1500);
  setInterval(() => { if (ws.readyState === 1) ws.send('.'); }, 20000);
}

/* --------------------------------------------------------------- inbox */
let SELECTED = null;

async function loadInbox() {
  const rows = await api('/inbox?limit=25').catch(() => []);
  const open = rows.filter(r => r.status === 'open');
  $('#inbox-count').textContent = `${open.length} open`;
  const box = $('#inbox');
  if (!rows.length) { box.innerHTML = '<div class="empty">nothing needs a decision</div>'; return; }
  box.innerHTML = rows.map(r => {
    const ex = r.exposure || {};
    const id = r._id?.$oid || r._id;
    return `<div class="item ${SELECTED === r.event_id ? 'sel' : ''}" data-ev="${esc(r.event_id)}" data-id="${esc(id)}">
      <div class="top"><span class="sev ${esc(r.severity)}">${esc(r.severity)}</span>
        <h3>${esc(r.headline)}</h3><span class="amt mono">${money(r.amount)}</span></div>
      <p>${esc((r.reasons || [])[0] || '')}</p>
      <div class="chips">
        <span class="chip">${ex.available_units ?? '?'} → ${ex.sent_units ?? '?'} units</span>
        <span class="chip ${ex.sensitive_exposed === 0 ? 'ok' : ''}">${ex.sensitive_exposed ?? '?'} sensitive exposed</span>
        <span class="chip">${esc(r.escalation_status || '')}</span>
        ${r.status !== 'open' ? `<span class="chip">${esc(r.status)}</span>` : ''}
      </div>
      ${r.status === 'open' ? `<div class="row" style="margin-top:9px">
        <button data-act="hold" data-id="${esc(id)}">Hold &amp; verify</button>
        <button data-act="release" data-id="${esc(id)}">Release</button></div>` : ''}
    </div>`;
  }).join('');

  box.querySelectorAll('.item').forEach(el => el.onclick = ev => {
    if (ev.target.dataset.act) return;
    SELECTED = el.dataset.ev;
    showDetail(el.dataset.ev);
  });
  box.querySelectorAll('button[data-act]').forEach(b => b.onclick = async ev => {
    ev.stopPropagation();
    await api(`/inbox/${b.dataset.id}/${b.dataset.act}`, { method: 'POST' });
    loadInbox();
  });
}

/* -------------------------------------------------------------- detail */
async function showDetail(eventId) {
  $$('nav.tabs button').forEach(x => x.classList.toggle('active', x.dataset.tab === 'detail'));
  $$('section[data-panel]').forEach(s => s.hidden = s.dataset.panel !== 'detail');
  let d;
  try { d = await api('/escalations/' + encodeURIComponent(eventId)); }
  catch { $('#detail-empty').hidden = false; $('#detail').hidden = true; return; }

  $('#detail-empty').hidden = true; $('#detail').hidden = false;
  const m = d.metrics || {}, nb = d.naive_baseline || {};
  $('#d-avail').textContent = m.available_units ?? '–';
  $('#d-sent').textContent = m.sent_units ?? '–';
  $('#d-exposed').textContent = m.sensitive_exposed ?? '–';
  $('#d-exposed').style.color = m.sensitive_exposed ? 'var(--bad)' : 'var(--good)';
  $('#d-red-u').textContent = pct(m.context_reduction_units);
  $('#d-red-b').textContent = pct(m.context_reduction_bytes);
  $('#d-naive').textContent = `${nb.units ?? '?'} units / ${(nb.bytes ?? 0).toLocaleString()} bytes`;
  $('#d-est').textContent = pct(m.estimated_exposure);
  $('#d-swaps').textContent = d.alias_swaps ?? 0;
  $('#d-policy').textContent = `${d.policy_id || ''} · ${d.role || ''}${d.fallback ? ' · FALLBACK SPEC' : ''}`;
  $('#d-bytes').textContent = `${d.payload_bytes} bytes · ${d.external?.status || ''}`;
  $('#d-payload').innerHTML = highlight(d.envelope);
  $('#d-answer').innerHTML = d.answer_reidentified
    ? esc(d.answer_reidentified) : '<span class="hint">no external answer (queued or offline)</span>';
  $('#d-answer-alias').innerHTML = d.answer_aliased
    ? esc(d.answer_aliased) : '<span class="hint">–</span>';

  const decs = (d.decisions || []).slice().sort((a, b) =>
    (a.decision === 'REMOVE') - (b.decision === 'REMOVE') || a.field.localeCompare(b.field));
  $('#d-dec-count').textContent = `${decs.filter(x => x.decision !== 'REMOVE').length} sent · ${decs.filter(x => x.decision === 'REMOVE').length} withheld`;
  $('#d-decisions tbody').innerHTML = decs.map(x => `<tr>
    <td class="mono">${esc(x.field)}</td>
    <td class="dec-${x.decision}">${esc(x.decision)}${x.op ? ` <span class="hint">${esc(x.op)}</span>` : ''}</td>
    <td class="sens-${esc(x.sensitivity)}">${esc(x.sensitivity)}</td>
    <td>${esc(x.reason)} <span class="hint">[${esc(x.source)}]</span></td></tr>`).join('');
}

/* --------------------------------------------------------------- mongo */
async function loadMongo() {
  const [st, idx, rings, risk, spend] = await Promise.all([
    api('/mongo/status').catch(() => null), api('/mongo/indexes').catch(() => []),
    api('/mongo/rings').catch(() => null), api('/mongo/vendor-risk').catch(() => null),
    api('/mongo/spend').catch(() => null),
  ]);
  if (st) {
    const cs = st.change_stream;
    $('#cs-watch').textContent = cs.watching.join(', ');
    $('#cs-check').textContent = cs.checkpoints;
    $('#cs-last').textContent = cs.last_event_id || '–';
    $('#cs-token').textContent = cs.resume_token_stored ? 'yes' : 'no';
    $('#cs-rs').textContent = st.replica_set.detail;
    $('#mg-total').textContent = `${st.total_documents.toLocaleString()} documents`;
    $('#mg-colls tbody').innerHTML = Object.entries(st.collections)
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td class="mono">${v.toLocaleString()}</td></tr>`).join('');
  }
  $('#mg-idx tbody').innerHTML = idx.map(i =>
    `<tr><td class="mono">${esc(i.collection)}<br><span class="hint">${i.live.length} live</span></td>
     <td class="hint">${esc(i.rationale)}</td></tr>`).join('');
  if (rings) $('#mg-rings tbody').innerHTML = (rings.rings || []).map(r =>
    `<tr><td class="mono">${esc(String(r._id).slice(0, 12))}…</td><td>${r.card_count}</td>
     <td>${(r.txns || []).length}</td><td class="mono">${money(r.total)}</td>
     <td>${r.window_hours}h</td></tr>`).join('') || '<tr><td colspan="5" class="hint">none</td></tr>';
  if (risk) $('#mg-risk tbody').innerHTML = (risk.result || []).map(v =>
    `<tr><td>${esc(v.name)}</td><td class="mono">${money(v.pending_total)}</td>
     <td class="mono">${esc(String(v.latest_change?.$date || v.latest_change || '').slice(0, 10))}</td>
     <td>${v.injection_flagged ? '<span class="sev critical">yes</span>' : '–'}</td></tr>`).join('')
    || '<tr><td colspan="4" class="hint">none</td></tr>';
  if (spend) $('#mg-spend').innerHTML = highlight(spend.result);
}

/* ------------------------------------------------------------ policies */
async function loadPolicies() {
  const rows = await api('/policies').catch(() => []);
  $('#pol-table tbody').innerHTML = rows.map(p => `<tr>
    <td class="mono">${esc(p._id)}</td><td>${esc(p.role)}</td><td class="mono">${esc(p.task_type)}</td>
    <td class="hint">${(p.allow_fields || []).length}</td>
    <td class="hint">${(p.deny_fields || []).length}</td>
    <td class="mono hint">${Object.entries(p.transform_required || {}).map(([k, v]) => `${k}→${v}`).join('<br>')}</td>
  </tr>`).join('');
}

/* ----------------------------------------------------------------- ask */
$('#btn-ask').onclick = async () => {
  const task = $('#ask-input').value.trim();
  if (!task) return;
  $('#ask-payload').textContent = 'running on the box…';
  try {
    const r = await api('/ask', { method: 'POST', body: JSON.stringify({ task }) });
    $('#ask-trace tbody').innerHTML = (r.trace || []).map(s =>
      `<tr><td>${s.n}</td><td class="mono">${esc(s.tool)}</td><td>${esc(s.detail)}</td>
       <td class="mono">${s.ms || ''}</td></tr>`).join('');
    $('#ask-sum').textContent = r.summary + (r.fallback ? ' · FALLBACK' : '');
    $('#ask-payload').innerHTML = highlight(r.envelope);
  } catch (e) { $('#ask-payload').textContent = 'error: ' + e.message; }
};
$$('button.q').forEach(b => b.onclick = () => { $('#ask-input').value = b.dataset.q; $('#btn-ask').click(); });

/* ------------------------------------------------------------- actions */
$('#btn-replay').onclick = async () => {
  await api('/stream/replay', { method: 'POST', body: JSON.stringify({ limit: 40 }) });
  $('#stream-hint').textContent = 'replaying seeded events as real inserts…';
};
$('#btn-net').onclick = async () => {
  const goOffline = $('#net-badge').classList.contains('on');
  const r = await api('/network/' + (goOffline ? 'offline' : 'online'), { method: 'POST' });
  $('#net-badge').textContent = 'network · ' + (r.online ? 'online' : 'offline');
  $('#net-badge').className = 'badge ' + (r.online ? 'on' : 'off');
  $('#btn-net').textContent = r.online ? '🔌 Go offline' : '🔌 Go online';
  $('#stream-hint').textContent = r.online
    ? 'online — tier 2 escalates again'
    : 'OFFLINE — tiers 0 and 1 keep running on the box; tier 2 is queueing';
};
$('#btn-drain').onclick = async () => {
  const r = await api('/drain', { method: 'POST' });
  $('#stream-hint').textContent = `drained ${r.sent} queued escalation(s)`;
  loadInbox();
};
$('#btn-role').onclick = async () => {
  ROLE = ROLE === 'ap_analyst' ? 'controller' : 'ap_analyst';
  await api('/role/' + ROLE, { method: 'POST' });
  $('#btn-role').textContent = 'Role: ' + ROLE;
  $('#stream-hint').textContent = `role is now ${ROLE} — the next escalation uses a different policy`;
};
$('#btn-seed').onclick = async () => {
  if (!confirm('Drop and reseed the database?')) return;
  $('#stream-hint').textContent = 'reseeding…';
  const r = await api('/seed', { method: 'POST' });
  $('#stream-hint').textContent = `reseeded ${r.total.toLocaleString()} documents`;
  loadInbox();
};
$('#btn-kill').onclick = async () => {
  await api('/stream/stop', { method: 'POST' });
  $('#cs-check').textContent = 'stream stopped…';
  await new Promise(r => setTimeout(r, 800));
  await api('/stream/start', { method: 'POST' });
  await loadMongo();
  $('#stream-hint').textContent = 'stream restarted from the stored resume token';
};

/* ---------------------------------------------------------------- boot */
health(); loadInbox(); connect();
setInterval(health, 15000);
