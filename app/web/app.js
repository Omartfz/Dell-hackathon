'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const api=async(p,o={})=>{const r=await fetch('/api'+p,{headers:{'content-type':'application/json'},...o});
  if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.statusText);return r.json();};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money=v=>v==null?'—':'$'+Number(v).toLocaleString(undefined,{maximumFractionDigits:0});
const compact=v=>{if(v==null)return'—';const n=Number(v);
  return n>=1e6?'$'+(n/1e6).toFixed(2)+'M':n>=1e3?'$'+(n/1e3).toFixed(1)+'K':'$'+n.toFixed(0);};
const pct=v=>v==null?'—':(v*100).toFixed(1)+'%';
const bytes=n=>n==null?'0 B':n<1024?n+' B':(n/1024).toFixed(1)+' KB';
const hl=o=>esc(JSON.stringify(o,null,2))
  .replace(/&quot;([^&]+?)&quot;(\s*:)/g,'<span class="k">"$1"</span>$2')
  .replace(/:\s*&quot;([^&]*?)&quot;/g,': <span class="st">"$1"</span>')
  .replace(/:\s*(-?\d+\.?\d*)/g,': <span class="nm2">$1</span>')
  .replace(/:\s*(true|false|null)/g,': <span class="bo">$1</span>');
const banner=(m,ok)=>$('#banner').innerHTML=m?`<div class="banner${ok?' ok':''}">${esc(m)}</div>`:'';

/* nav */
$$('aside a').forEach(a=>a.onclick=()=>go(a.dataset.page));
function go(p){
  $$('aside a').forEach(x=>x.classList.toggle('active',x.dataset.page===p));
  $$('.page').forEach(s=>s.classList.toggle('on',s.dataset.page===p));
  window.scrollTo(0,0);
  ({automation:loadInbox,mongo:loadMongo,controls:loadControls,payables:loadPayables,
    expenses:loadExpenses,cards:loadCards,treasury:loadTreasury}[p]||(()=>{}))();
}

/* header + tiles */
let ROLE='ap_analyst', ONLINE=true;
function paint(c){ if(!c)return;
  $('#k-proc').textContent=c.processed??0; $('#k-esc').textContent=c.tier2??0;
  $('#k-exposed').textContent=c.sensitive_exposed??0;
  $('#k-queued').textContent=(c.queued??0)+' queued offline';
  const red=$('#k-red'); if(red&&c.processed)red.textContent='—';
  $('#egress').textContent=bytes(c.bytes_out??0);
}
async function health(){
  try{
    const h=await api('/health'); const m=h.inference.local_model;
    $('#model-name').textContent=m?m+' · ON-BOX':'no local model';
    $('#modelsel').className='modelsel'+(m?'':' off');
    paint(h.agent.counters);
    $('#stream-state').textContent=h.agent.running?'watching':'stopped';
    if(!h.mongo.replica_set)banner('MongoDB unreachable — serving the seeded dataset from '
      +'memory so the console still renders. Run scripts/setup_mongo.sh for change '
      +'streams, $graphLookup and the live agent.');
    else if(!m)banner('No local model — tiers 0 and 2 work, tier 1 reasoning is skipped.');
    else banner('');
  }catch(e){banner('API unreachable: '+e.message);}
}
function sparkline(el,vals){
  if(!el||!vals||vals.length<2)return;
  const mn=Math.min(...vals),mx=Math.max(...vals),rg=(mx-mn)||1;
  const pts=vals.map((v,i)=>[i/(vals.length-1)*100,24-((v-mn)/rg)*20]);
  const d=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
  el.innerHTML=`<path class="fillp" d="${d} L100 26 L0 26 Z"/><path d="${d}"/>`;
}

function drawForecast(fc){
  const el=$('#fc'); if(!el||!fc)return;
  const W=720,H=200,P=26;
  const all=[...fc.history.map(h=>({t:h.t,v:h.v})),...fc.forecast.map(f=>({t:f.t,v:f.v}))];
  const los=fc.forecast.map(f=>f.lo),his=fc.forecast.map(f=>f.hi);
  const mn=Math.min(...all.map(a=>a.v),...los),mx=Math.max(...all.map(a=>a.v),...his);
  const rg=(mx-mn)||1, n=all.length-1;
  const X=i=>P+(i/n)*(W-P*2), Y=v=>H-P-((v-mn)/rg)*(H-P*2);
  const hi=fc.history.length;
  const hp=fc.history.map((h,i)=>`${i?'L':'M'}${X(i).toFixed(1)} ${Y(h.v).toFixed(1)}`).join(' ');
  const fp=fc.forecast.map((f,i)=>`${i?'L':'M'}${X(hi+i).toFixed(1)} ${Y(f.v).toFixed(1)}`).join(' ');
  const up=fc.forecast.map((f,i)=>`${i?'L':'M'}${X(hi+i).toFixed(1)} ${Y(f.hi).toFixed(1)}`).join(' ');
  const dn=fc.forecast.slice().reverse().map((f,i)=>
    `L${X(hi+fc.forecast.length-1-i).toFixed(1)} ${Y(f.lo).toFixed(1)}`).join(' ');
  const ticks=[mn,mn+rg/2,mx].map(v=>
    `<text x="4" y="${(Y(v)+3).toFixed(1)}">${compact(v)}</text>`).join('');
  el.innerHTML=`<path class="band" d="${up} ${dn} Z"/>
    <line class="today" x1="${X(hi).toFixed(1)}" y1="${P-8}" x2="${X(hi).toFixed(1)}" y2="${H-P}"/>
    <text x="${(X(hi)+4).toFixed(1)}" y="${P-11}">today</text>
    <path class="line" d="${hp}"/><path class="line fut" d="${fp}"/>${ticks}`;
}

async function loadHome(){
  try{
    const s=await api('/mongo/spend?months=3'); const r=s.result||{};
    const tot=(r.totals||[{}])[0]||{};
    $('#g-total').textContent=compact(tot.total);
    $('#k-txn').textContent=(tot.count??0).toLocaleString();
    $('#k-flag').textContent=tot.flagged??0;
    const cols=['#3b6ef5','#0f9d58','#e8890c','#8b5cf6','#e5484d','#0ea5b7'];
    const cats=(r.by_category||[]).slice(0,5),mx=Math.max(...cats.map(c=>c.total),1);
    $('#g-cats').innerHTML=cats.map((c,i)=>`<div class="catrow"><span class="nm">${esc(c._id)}</span>
      <span class="tr"><i style="width:${(c.total/mx*100).toFixed(0)}%;background:${cols[i%6]}"></i></span>
      <span class="vv">${money(c.total)}</span></div>`).join('');
    const allc=(r.by_category||[]),ct=allc.reduce((a,c)=>a+c.total,0);
    $('#sc-total').textContent='total '+compact(ct);
    $('#sc-list').innerHTML=allc.slice(0,6).map((c,i)=>`<div class="catrow">
      <span class="nm">${esc(c._id)}</span>
      <span class="tr"><i style="width:${(c.total/ct*100).toFixed(0)}%;background:${cols[i%6]}"></i></span>
      <span class="vv">${compact(c.total)}</span></div>`).join('');
    const mo=(r.by_month||[]).slice(-3),mmx=Math.max(...mo.map(m=>m.total),1);
    $('#c-bars').innerHTML=mo.map((m,i)=>`<div class="b ${i===mo.length-1?'now':''}">
      <b>${compact(m.total)}</b><i style="height:${Math.max(10,m.total/mmx*118).toFixed(0)}px"></i>
      <span>${esc(m._id)}</span></div>`).join('')||'<div class="blank">no data</div>';
    if(mo.length){$('#k-mtd').textContent=compact(mo[mo.length-1].total);
      sparkline($('#sp-mtd'),mo.map(m=>m.total));}
    $('#m-rows').innerHTML=(r.top_merchants||[]).slice(0,7).map(m=>
      `<tr><td>${esc(m._id)}</td><td class="num">${money(m.total)}</td></tr>`).join('');
    $('#asof').textContent='Northwind · '+new Date().toISOString().slice(0,10);
  }catch(_){}
  try{
    const fc=await api('/forecast'); drawForecast(fc);
    $('#k-cash').textContent=compact(fc.balance);
    $('#k-burn').textContent=compact(fc.burn);
    $('#k-runway').textContent=(fc.runway_months??'—')+' mo';
    sparkline($('#sp-cash'),fc.history.map(h=>h.v));
    $('#fc-note').textContent=`no shortfall in horizon · ${fc.runway_months} mo runway`;
  }catch(_){}
  try{
    const c=await api('/cards'); $('#k-cards').textContent=c.length;
  }catch(_){}
  try{
    const f=await api('/flagged?limit=12');
    $('#fl-count').textContent=f.length+' rows';
    $('#fl-rows').innerHTML=f.map(t=>`<tr>
      <td class="mono">${esc(String(t.ts?.$date||t.ts||'').slice(0,10))}</td>
      <td>${esc(t.merchant)}</td><td>${esc(t.employee_name||'')}</td>
      <td class="muted">${esc(t.category)}</td><td class="num">${money(t.amount)}</td>
      <td class="muted">${(t.flags||[]).join(', ')||'–'}</td>
      <td class="num"><span class="tag ${t.fraud_score>=.8?'r':t.fraud_score>=.6?'a':'g'}">${(t.fraud_score*100).toFixed(0)}%</span></td></tr>`).join('');
  }catch(_){}
}

/* stream */
function row(m){
  const v=m.verdict||{}, t=v.tier??0;
  return `<tr><td class="mono">${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})}</td>
    <td>${esc(m.merchant||m.kind)}</td>
    <td><span class="tier t${t}"><i></i>${['rules','local','escalated'][t]}</span></td>
    <td class="num">${money(m.amount)}</td><td class="num muted">${m.ms}</td></tr>`;
}
function connect(){
  const ws=new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage=e=>{const m=JSON.parse(e.data);
    if(m.type==='event'){
      const tb=$('#stream-rows'); if(tb.querySelector('.blank'))tb.innerHTML='';
      tb.insertAdjacentHTML('afterbegin',row(m));
      while(tb.children.length>120)tb.lastElementChild.remove();
      paint(m.counters); if((m.verdict||{}).tier===2){loadInbox();}
    } else if(m.type==='status'){paint(m.counters);
      $('#stream-state').textContent=m.running?'watching':'stopped';}
  };
  ws.onclose=()=>setTimeout(connect,1500);
  setInterval(()=>{if(ws.readyState===1)ws.send('.')},20000);
}

/* inbox */
let SEL=null;
function attHTML(r,compactMode){
  const ex=r.exposure||{}, id=r._id?.$oid||r._id;
  return `<div class="att" data-ev="${esc(r.event_id)}" data-id="${esc(id)}">
    <span class="sevdot sev-${esc(r.severity)}"></span>
    <div class="bd"><p class="t">${esc(r.headline)}</p>
      <p class="d">${esc((r.reasons||[])[0]||'')}</p>
      <div class="chips"><span class="chip">${ex.available_units??'?'} → ${ex.sent_units??'?'} units</span>
        <span class="chip ${ex.sensitive_exposed===0?'ok':''}">${ex.sensitive_exposed??'?'} sensitive out</span>
        <span class="chip">${esc(r.escalation_status||'')}</span>
        ${r.status!=='open'?`<span class="chip">${esc(r.status)}</span>`:''}</div></div>
    <div style="text-align:right"><div style="font-weight:600">${money(r.amount)}</div>
      ${r.status==='open'?`<button class="lk" data-act="hold" data-id="${esc(id)}">Hold &amp; verify →</button>`:''}</div>
  </div>`;
}
async function loadInbox(){
  const rows=await api('/inbox?limit=25').catch(()=>[]);
  const open=rows.filter(r=>r.status==='open');
  $('#pill-auto').textContent=open.length; $('#bell').textContent=open.length;
  $('#att-count').textContent=`${open.length} open`; $('#auto-count').textContent=`${open.length} open`;
  const html=rows.length?rows.map(r=>attHTML(r)).join(''):'<div class="blank">nothing needs a decision</div>';
  $('#att-list').innerHTML=html; $('#auto-list').innerHTML=html;
  $$('.att').forEach(el=>el.onclick=ev=>{
    if(ev.target.dataset.act){act(ev.target.dataset.id,ev.target.dataset.act);return;}
    SEL=el.dataset.ev; go('automation'); detail(el.dataset.ev);
  });
}
async function act(id,a){await api(`/inbox/${id}/${a}`,{method:'POST'});loadInbox();}

async function detail(ev){
  let d; try{d=await api('/escalations/'+encodeURIComponent(ev));}
  catch{$('#det-blank').hidden=false;$('#det').hidden=true;return;}
  $('#det-blank').hidden=true;$('#det').hidden=false;
  const m=d.metrics||{},nb=d.naive_baseline||{};
  $('#d-avail').textContent=m.available_units??'–'; $('#d-sent').textContent=m.sent_units??'–';
  $('#d-exp').textContent=m.sensitive_exposed??'–';
  $('#d-exp').style.color=m.sensitive_exposed?'var(--red)':'var(--green)';
  $('#d-red').textContent=`${pct(m.context_reduction_units)} / ${pct(m.context_reduction_bytes)}`;
  $('#d-naive').textContent=`${nb.units??'?'} units · ${(nb.bytes??0).toLocaleString()} bytes`;
  $('#d-est').textContent=pct(m.estimated_exposure); $('#d-swaps').textContent=d.alias_swaps??0;
  $('#d-policy').textContent=`${d.policy_id||''} · ${d.role||''}${d.fallback?' · FALLBACK':''}`;
  $('#d-bytes').textContent=`${d.payload_bytes} bytes · ${d.external?.status||''}`;
  $('#d-pre').innerHTML=hl(d.envelope);
  $('#d-ans').innerHTML=d.answer_reidentified?esc(d.answer_reidentified):'<span class="muted">no external answer (queued or offline)</span>';
  $('#d-ans-a').innerHTML=d.answer_aliased?esc(d.answer_aliased):'<span class="muted">–</span>';
  const dec=(d.decisions||[]).slice().sort((a,b)=>(a.decision==='REMOVE')-(b.decision==='REMOVE')||a.field.localeCompare(b.field));
  $('#d-cnt').textContent=`${dec.filter(x=>x.decision!=='REMOVE').length} sent · ${dec.filter(x=>x.decision==='REMOVE').length} withheld`;
  $('#d-rows').innerHTML=dec.map(x=>`<tr><td class="mono">${esc(x.field)}</td>
    <td class="dec-${x.decision}">${esc(x.decision)}${x.op?` <span class="muted">${esc(x.op)}</span>`:''}</td>
    <td class="s-${esc(x.sensitivity)}">${esc(x.sensitivity)}</td>
    <td>${esc(x.reason)} <span class="muted">[${esc(x.source)}]</span></td></tr>`).join('');
}

/* mongo */
async function loadMongo(){
  const [st,idx,rings,risk]=await Promise.all([api('/mongo/status').catch(()=>null),
    api('/mongo/indexes').catch(()=>[]),api('/mongo/rings').catch(()=>null),
    api('/mongo/vendor-risk').catch(()=>null)]);
  if(st){const cs=st.change_stream;
    $('#cs-w').textContent=cs.watching.join(', '); $('#cs-c').textContent=cs.checkpoints;
    $('#cs-l').textContent=cs.last_event_id||'–'; $('#cs-t').textContent=cs.resume_token_stored?'yes':'no';
    $('#cs-r').textContent=st.replica_set.detail;
    $('#mg-tot').textContent=st.total_documents.toLocaleString()+' documents';
    $('#mg-colls').innerHTML=Object.entries(st.collections).sort((a,b)=>b[1]-a[1])
      .map(([k,v])=>`<tr><td class="mono">${esc(k)}</td><td class="num mono">${v.toLocaleString()}</td></tr>`).join('');}
  $('#mg-idx').innerHTML=idx.map(i=>`<tr><td class="mono">${esc(i.collection)}<br>
    <span class="muted">${i.live.length} live</span></td><td class="muted">${esc(i.rationale)}</td></tr>`).join('');
  $('#mg-rings').innerHTML=(rings?.rings||[]).map(r=>`<tr><td class="mono">${esc(String(r._id).slice(0,14))}…</td>
    <td class="num">${r.card_count}</td><td class="num">${(r.txns||[]).length}</td>
    <td class="num">${money(r.total)}</td><td class="num">${r.window_hours}h</td></tr>`).join('')
    ||'<tr><td colspan="5" class="blank">none</td></tr>';
  $('#mg-risk').innerHTML=(risk?.result||[]).map(v=>`<tr><td>${esc(v.name)}</td>
    <td class="num">${money(v.pending_total)}</td>
    <td class="mono">${esc(String(v.latest_change?.$date||v.latest_change||'').slice(0,10))}</td>
    <td>${v.injection_flagged?'<span class="tag r">yes</span>':'–'}</td></tr>`).join('')
    ||'<tr><td colspan="4" class="blank">none</td></tr>';
}
async function loadControls(){
  const p=await api('/policies').catch(()=>[]);
  $('#pol-rows').innerHTML=p.map(x=>`<tr><td class="mono">${esc(x._id)}</td><td>${esc(x.role)}</td>
    <td class="mono">${esc(x.task_type)}</td><td class="num">${(x.allow_fields||[]).length}</td>
    <td class="num">${(x.deny_fields||[]).length}</td>
    <td class="mono muted">${Object.entries(x.transform_required||{}).map(([k,v])=>k+'→'+v).join('<br>')}</td></tr>`).join('');
  const c=await api('/catalog').catch(()=>[]);
  $('#cat-rows').innerHTML=c.map(x=>`<tr><td class="mono">${esc(x.field_id)}</td>
    <td class="s-${esc(x.sensitivity)}">${esc(x.sensitivity)}</td>
    <td class="mono muted">${(x.allowed_ops||[]).join(', ')}</td></tr>`).join('');
}
async function loadPayables(){
  const r=await api('/payables').catch(()=>[]);
  $('#pay-rows').innerHTML=r.map(i=>`<tr><td class="mono">${esc(i._id)}</td><td>${esc(i.vendor_name||i.vendor_id)}</td>
    <td class="num">${money(i.amount)}</td><td class="mono">${esc(String(i.scheduled_at?.$date||'').slice(0,10))}</td>
    <td>${i.injection_detected?'<span class="tag r">detected</span>':'–'}</td>
    <td>${esc(i.status)}</td></tr>`).join('')||'<tr><td colspan="6" class="blank">—</td></tr>';
}
async function loadExpenses(){
  const r=await api('/transactions?limit=80').catch(()=>[]);
  $('#exp-rows').innerHTML=r.map(t=>`<tr><td class="mono">${esc(String(t.ts?.$date||'').slice(0,10))}</td>
    <td>${esc(t.merchant)}</td><td class="muted">${esc(t.category)}</td>
    <td class="num">${money(t.amount)}</td><td class="muted">${(t.flags||[]).join(', ')||'–'}</td>
    <td class="num">${(t.fraud_score*100).toFixed(0)}%</td></tr>`).join('')||'<tr><td colspan="6" class="blank">—</td></tr>';
}
async function loadCards(){
  const r=await api('/cards').catch(()=>[]);
  $('#card-rows').innerHTML=r.map(c=>`<tr><td class="mono">•••• ${esc(c.last4)}
    <span class="tag r" style="margin-left:6px">PAN never leaves</span></td>
    <td>${esc(c.holder_name||c.holder_id)}</td><td class="num">${money(c.txn_limit)}</td>
    <td>${esc(c.status)}</td></tr>`).join('')||'<tr><td colspan="4" class="blank">—</td></tr>';
}
async function loadTreasury(){
  const r=await api('/treasury').catch(()=>null); if(!r)return;
  $('#tre-tiles').innerHTML=`
    <div class="tile"><div class="lbl">Cash on hand</div><div class="val">${compact(r.balance_exact)}</div>
      <div class="foot"><span class="tag a">MNPI</span></div></div>
    <div class="tile"><div class="lbl">Monthly burn</div><div class="val">${compact(r.monthly_burn)}</div>
      <div class="foot"><span class="tag a">MNPI</span></div></div>
    <div class="tile"><div class="lbl">Runway</div><div class="val">${r.runway_months} mo</div>
      <div class="foot"><span class="tag g">healthy</span></div></div>
    <div class="tile good"><div class="lbl">Sent to external models</div><div class="val">banded</div>
      <div class="foot">exact figures never leave</div></div>`;
}

/* ask */
$('#ask-go').onclick=async()=>{
  const task=$('#ask-in').value.trim(); if(!task)return;
  $('#ask-out').hidden=false; $('#ask-pre').textContent='running on the box…';
  try{
    const r=await api('/ask',{method:'POST',body:JSON.stringify({task})});
    $('#ask-sum').textContent=r.summary+(r.fallback?' · FALLBACK':'');
    $('#ask-pre').innerHTML=hl(r.envelope);
    $('#ask-trace').querySelector('tbody').innerHTML=(r.trace||[]).map(s=>
      `<tr><td class="num muted">${s.n}</td><td class="mono">${esc(s.tool)}</td>
       <td>${esc(s.detail)}</td><td class="num muted">${s.ms||''}</td></tr>`).join('');
  }catch(e){$('#ask-pre').textContent='error: '+e.message;}
};
$$('.q').forEach(b=>b.onclick=()=>{$('#ask-in').value=b.dataset.q;$('#ask-go').click();});

/* actions */
const replay=async()=>{await api('/stream/replay',{method:'POST',body:JSON.stringify({limit:40})});
  $('#stream-state').textContent='replaying…';};
$('#a-replay').onclick=replay; $('#btn-replay').onclick=replay;
$('#a-net').onclick=async()=>{ONLINE=!ONLINE;
  await api('/network/'+(ONLINE?'online':'offline'),{method:'POST'});
  $('#a-net').textContent=ONLINE?'🔌 Go offline':'🔌 Go online';
  banner(ONLINE?'':'OFFLINE — tiers 0 and 1 keep running on the box; tier 2 is queueing.',ONLINE?0:0);
  if(ONLINE)banner('');};
$('#a-drain').onclick=async()=>{const r=await api('/drain',{method:'POST'});
  banner(`drained ${r.sent} queued escalation(s)`,true);loadInbox();};
$('#a-role').onclick=async()=>{ROLE=ROLE==='ap_analyst'?'controller':'ap_analyst';
  await api('/role/'+ROLE,{method:'POST'});$('#a-role').textContent='Role: '+ROLE;
  $('#who-role').textContent=ROLE==='controller'?'Controls / Manager':'Finance / Admin';
  banner(`role is now ${ROLE} — the next escalation uses a different policy`,true);};
$('#a-seed').onclick=async()=>{if(!confirm('Drop and reseed the database?'))return;
  const r=await api('/seed',{method:'POST'});banner(`reseeded ${r.total.toLocaleString()} documents`,true);
  loadHome();loadInbox();};
$('#a-kill').onclick=async()=>{await api('/stream/stop',{method:'POST'});
  await new Promise(r=>setTimeout(r,800));await api('/stream/start',{method:'POST'});
  await loadMongo();banner('stream restarted from the stored resume token',true);};

/* boot */
health();loadHome();loadInbox();connect();setInterval(health,15000);
