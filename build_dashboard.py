"""
============================================================================
 build_dashboard.py  -  renders Packsize_Dashboard.html
 Power Stop LLC / HK1

 Two axes of navigation:
   scope   Combined | MG1 (705164) | MG2 (706614)
   period  Daily | Monthly | Quarterly | Yearly

 Every scope carries its own target: the overview is scored against both
 machines (2 x 175 x 8 = 2,800/day); each machine tab against its own
 (1 x 175 x 8 = 1,400/day). All twelve combinations have a full history.
============================================================================
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from packsize_etl import _MdLog, load_config, resolve, run as etl_run


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Packsize Production &middot; HK1</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<script src="{{CHARTJS}}"></script>
<style>
:root{
  --bg:#0f0f11; --surface:#18181c; --surface-2:#1f1f25; --line:#2a2a32;
  --text:#e8e6e3; --muted:#8b8b96; --dim:#5f5f6b;
  --amber:#f2b705; --green:#4ade80; --red:#f4704f; --blue:#5aa9e6;
  --display:'Fraunces',Georgia,serif; --mono:'JetBrains Mono',ui-monospace,monospace;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--mono);font-size:14px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1500px;margin:0 auto;padding:26px 26px 64px}

header{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-end;justify-content:space-between;padding-bottom:18px;border-bottom:1px solid var(--line)}
h1{font-family:var(--display);font-size:32px;font-weight:700;margin:0;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:12.5px;margin-top:5px}
.meta{text-align:right;font-size:11.5px;color:var(--dim);line-height:1.75}
.meta b{color:var(--muted);font-weight:500}

.scopes{display:flex;gap:7px;margin:20px 0 0;flex-wrap:wrap}
.scopes button{
  font-family:var(--mono);font-size:12.5px;font-weight:500;letter-spacing:.04em;
  background:var(--surface);color:var(--muted);border:1px solid var(--line);
  padding:10px 20px;border-radius:7px;cursor:pointer;transition:.14s;text-align:left;
}
.scopes button:hover{color:var(--text);border-color:#3a3a44}
.scopes button.on{background:var(--surface-2);color:var(--text);border-color:var(--amber);box-shadow:inset 0 -2px 0 var(--amber)}
.scopes button small{display:block;font-size:10px;color:var(--dim);margin-top:3px;letter-spacing:.02em}
.scopes button.on small{color:var(--amber)}
.scopes button:focus-visible{outline:2px solid var(--amber);outline-offset:2px}

nav{display:flex;gap:6px;margin:14px 0 22px;flex-wrap:wrap;align-items:center}
nav button{
  font-family:var(--mono);font-size:11px;font-weight:500;letter-spacing:.07em;text-transform:uppercase;
  background:transparent;color:var(--muted);border:1px solid var(--line);
  padding:7px 15px;border-radius:5px;cursor:pointer;transition:.14s;
}
nav button:hover{color:var(--text);border-color:#3a3a44}
nav button.on{background:var(--amber);color:#16161a;border-color:var(--amber);font-weight:700}
nav button:focus-visible{outline:2px solid var(--amber);outline-offset:2px}
nav .tgt{margin-left:auto;font-size:11px;color:var(--dim)}
nav .tgt b{color:var(--amber);font-weight:700}

.shead{display:flex;align-items:baseline;gap:12px;margin:26px 0 13px;flex-wrap:wrap}
.shead h2{font-family:var(--display);font-size:17px;font-weight:700;margin:0;color:var(--text)}
.shead span{font-size:11.5px;color:var(--dim)}

.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:13px}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:15px 16px 14px;position:relative;overflow:hidden}
.kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--dim)}
.kpi.ok::before{background:var(--green)} .kpi.warn::before{background:var(--amber)} .kpi.bad::before{background:var(--red)}
.kpi .lbl{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:9px}
.kpi .val{font-family:var(--display);font-size:33px;font-weight:700;line-height:1;letter-spacing:-.02em}
.kpi .val small{font-family:var(--mono);font-size:12px;font-weight:400;color:var(--muted);margin-left:5px;letter-spacing:0}
.kpi .std{font-size:11px;color:var(--dim);margin-top:9px;display:flex;justify-content:space-between;gap:8px;align-items:center}
.kpi .std>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kpi .pill{font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px;letter-spacing:.04em;flex:none}
.pill.ok{background:rgba(74,222,128,.14);color:var(--green)}
.pill.warn{background:rgba(242,183,5,.16);color:var(--amber)}
.pill.bad{background:rgba(244,112,79,.15);color:var(--red)}
.pill.flat{background:var(--surface-2);color:var(--muted)}
.bar{height:4px;background:var(--surface-2);border-radius:3px;margin-top:11px;overflow:hidden}
.bar i{display:block;height:100%;border-radius:3px}

.kpi.click{cursor:pointer;transition:border-color .14s}
.kpi.click:hover{border-color:#3a3a44}
.kpi .tog{margin-top:10px;padding-top:9px;border-top:1px solid var(--line);display:flex;gap:5px}
.kpi .tog button{flex:1;font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.06em;
  background:var(--surface-2);color:var(--muted);border:1px solid var(--line);border-radius:4px;
  padding:5px 4px;cursor:pointer;transition:.12s}
.kpi .tog button:hover{color:var(--text);border-color:#3a3a44}
.kpi .tog button.on{background:var(--amber);color:#16161a;border-color:var(--amber)}
.kpi .more{margin-top:10px;padding-top:9px;border-top:1px solid var(--line);font-size:10.5px;
  letter-spacing:.06em;text-transform:uppercase;color:var(--amber);display:flex;justify-content:space-between;align-items:center}
.kpi .more span:last-child{color:var(--dim);font-size:13px;line-height:1}

.ovl{position:fixed;inset:0;background:rgba(8,8,10,.76);display:none;align-items:center;justify-content:center;z-index:50;padding:24px}
.ovl.on{display:flex}
.modal{background:var(--surface);border:1px solid var(--line);border-radius:11px;width:min(620px,100%);
  max-height:82vh;display:flex;flex-direction:column;box-shadow:0 22px 60px rgba(0,0,0,.6)}
.modal header{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;
  padding:18px 20px 14px;border-bottom:1px solid var(--line)}
.modal h3{font-family:var(--display);font-size:17px;margin:0}
.modal .hint{font-size:11.5px;color:var(--dim);margin-top:4px}
.modal .x{background:none;border:1px solid var(--line);color:var(--muted);border-radius:6px;
  width:28px;height:28px;cursor:pointer;font-size:15px;line-height:1;flex:none}
.modal .x:hover{color:var(--text);border-color:#3a3a44}
.modal.wide{width:min(900px,100%)}
.modal .body{padding:14px 20px 20px;overflow-y:auto}
.mnav{display:flex;gap:5px;margin-bottom:14px;flex-wrap:wrap}
.mnav button{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;
  background:var(--surface-2);color:var(--muted);border:1px solid var(--line);border-radius:4px;
  padding:6px 13px;cursor:pointer;transition:.12s}
.mnav button:hover{color:var(--text);border-color:#3a3a44}
.mnav button.on{background:var(--amber);color:#16161a;border-color:var(--amber)}
.mstats{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:9px;margin-top:16px}
.mstats div{background:var(--surface-2);border:1px solid var(--line);border-radius:6px;padding:10px 12px}
.mstats b{display:block;font-family:var(--display);font-size:20px;font-weight:700;line-height:1.1}
.mstats small{display:block;font-size:9.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin-top:5px}
.modal .body::-webkit-scrollbar{width:8px}
.modal .body::-webkit-scrollbar-thumb{background:#2e2e38;border-radius:4px}
.sku{position:relative;display:grid;grid-template-columns:1fr auto auto;gap:9px;align-items:center;
     padding:7px 9px;margin-bottom:3px;font-size:12.5px;border-radius:4px;overflow:hidden}
.sku .fill{position:absolute;left:0;top:0;bottom:0;background:rgba(242,183,5,.16);z-index:0}
.sku .nm,.sku .ct,.sku .pc{position:relative;z-index:1}
.sku .nm{color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sku .ct{color:var(--text);font-variant-numeric:tabular-nums}
.sku .pc{color:var(--muted);font-size:11.5px;width:46px;text-align:right}
.skutot{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-top:12px;padding-top:10px;border-top:1px solid var(--line)}

.grid{display:grid;gap:14px}
.g2{grid-template-columns:2fr 1fr}
.g2e{grid-template-columns:1fr 1fr}
.card{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:16px 18px 14px}
.card h3{font-family:var(--display);font-size:14.5px;font-weight:700;margin:0 0 3px}
.card .hint{font-size:11px;color:var(--dim);margin-bottom:13px}
.chart{position:relative;height:288px}
.chart.tall{height:330px}
.nochart{display:flex;align-items:center;justify-content:center;height:100%;text-align:center;
  color:var(--dim);font-size:12px;line-height:1.7;border:1px dashed var(--line);border-radius:7px}

table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:right;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:500;padding:0 9px 9px 0;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:left;padding-left:0}
th:last-child,td:last-child{padding-right:0}
td{text-align:right;padding:8px 9px 8px 0;border-bottom:1px solid #212128;white-space:nowrap}
tbody tr:hover td{background:#1c1c22}
td.k{color:var(--text);font-weight:500}
td.d{color:var(--muted)}
.tag{font-size:10px;font-weight:700;padding:2px 7px;border-radius:20px}
.tag.ok{background:rgba(74,222,128,.14);color:var(--green)}
.tag.warn{background:rgba(242,183,5,.16);color:var(--amber)}
.tag.bad{background:rgba(244,112,79,.15);color:var(--red)}
.scroll{max-height:430px;overflow-y:auto}
.scroll::-webkit-scrollbar{width:8px}
.scroll::-webkit-scrollbar-thumb{background:#2e2e38;border-radius:4px}

.note{background:var(--surface-2);border-left:3px solid var(--amber);border-radius:0 7px 7px 0;padding:13px 17px;font-size:12px;color:var(--muted);line-height:1.65;margin-top:14px}
.note b{color:var(--text);font-weight:500}
.hidden{display:none}
@media(max-width:1050px){.g2,.g2e{grid-template-columns:1fr}}
@media print{body{background:#fff;color:#111}.card,.kpi{background:#fff;border-color:#ccc}.scopes,nav{display:none}.scroll{max-height:none}}
</style>
</head>
<body>
<div class="wrap">

  <header>
    <div>
      <h1 id="ttl">Packsize Production</h1>
      <div class="sub" id="sub"></div>
    </div>
    <div class="meta" id="meta"></div>
  </header>

  <div class="scopes" id="scopeTabs"></div>
  <nav id="periodTabs">
    <button data-view="daily">Daily</button>
    <button data-view="monthly">Monthly</button>
    <button data-view="quarterly">Quarterly</button>
    <button data-view="yearly">Yearly</button>
    <span class="tgt" id="tgtNote"></span>
  </nav>

  <section id="v-daily">
    <div class="shead"><h2 id="dayTitle">Latest production day</h2><span id="daySpan"></span></div>
    <div class="kpis" id="dayKpis"></div>

    <div class="grid g2" style="margin-top:22px">
      <div class="card">
        <h3 id="trendTitle">Cartons per day vs target</h3>
        <div class="hint" id="trendHint"></div>
        <div class="chart tall"><canvas id="cTrend"></canvas></div>
      </div>
      <div class="card">
        <h3>Where the shift went</h3>
        <div class="hint" id="shiftHint"></div>
        <div class="chart tall"><canvas id="cShift"></canvas></div>
      </div>
    </div>

    <div class="grid g2e" style="margin-top:14px">
      <div class="card">
        <h3>Fault pareto</h3>
        <div class="hint">Genuine faults only. Shift-boundary e-stops excluded.</div>
        <div class="chart"><canvas id="cPareto"></canvas></div>
      </div>
      <div class="card">
        <h3>Recent days</h3>
        <div class="hint">Most recent first. Green = at or above target.</div>
        <div class="scroll"><table id="tDaily"></table></div>
      </div>
    </div>
  </section>

  <section id="v-period" class="hidden">
    <div class="shead"><h2 id="pTitle"></h2><span id="pSpan"></span></div>
    <div class="kpis" id="pKpis"></div>

    <div class="grid g2" style="margin-top:22px">
      <div class="card">
        <h3 id="pChartTitle"></h3>
        <div class="hint">Bars = cartons per day. Line = % of days that met target.</div>
        <div class="chart tall"><canvas id="cPeriod"></canvas></div>
      </div>
      <div class="card">
        <h3>Utilization &amp; availability</h3>
        <div class="hint">Availability = machine healthy. Utilization = machine running.</div>
        <div class="chart tall"><canvas id="cUtil"></canvas></div>
      </div>
    </div>

    <div class="card" style="margin-top:14px">
      <h3 id="pTableTitle"></h3>
      <div class="hint">Rates are recomputed from period totals, not averaged across days.</div>
      <div class="scroll"><table id="tPeriod"></table></div>
    </div>
  </section>
</div>

<div class="ovl" id="metOvl">
  <div class="modal wide" role="dialog" aria-modal="true" aria-labelledby="metTitle">
    <header>
      <div><h3 id="metTitle">Metric</h3><div class="hint" id="metSub"></div></div>
      <button class="x" id="metX" aria-label="Close">&times;</button>
    </header>
    <div class="body">
      <nav class="mnav" id="metTabs">
        <button data-p="daily">Daily</button>
        <button data-p="monthly">Monthly</button>
        <button data-p="quarterly">Quarterly</button>
        <button data-p="yearly">Yearly</button>
      </nav>
      <div class="chart" style="height:250px"><canvas id="cMetric"></canvas></div>
      <div class="mstats" id="metStats"></div>
      <div id="metExtra"></div>
    </div>
  </div>
</div>

<div class="ovl" id="skuOvl">
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="skuTitle">
    <header>
      <div><h3 id="skuTitle">Box SKUs produced</h3><div class="hint" id="skuSub"></div></div>
      <button class="x" id="skuX" aria-label="Close">&times;</button>
    </header>
    <div class="body" id="skuBody"></div>
  </div>
</div>

<script>
const DATA = {{PAYLOAD}};
const S = DATA.standard, TH = DATA.thresholds, M = DATA.machine;
const SCOPES = DATA.scopes;

let SCOPE = SCOPES[0];
let VIEW = DATA.default_view || 'daily';
let ASSOC = SCOPES[0].associates;

const n1 = v => v==null ? '\u2014' : Number(v).toFixed(1);
const n0 = v => v==null ? '\u2014' : Math.round(v).toLocaleString();
const CSS = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();

const HAS_CHART = (typeof Chart !== 'undefined');
const CHARTS = {};
function mkChart(id, spec){
  const cv = document.getElementById(id);
  if(!cv) return null;
  if(CHARTS[id] && CHARTS[id].destroy){ CHARTS[id].destroy(); CHARTS[id]=null; }
  if(!HAS_CHART){
    cv.parentElement.innerHTML = '<div class="nochart">Chart library unavailable offline.<br>Figures are in the tables below.</div>';
    return null;
  }
  try { CHARTS[id] = new Chart(cv, spec); return CHARTS[id]; }
  catch(e){ cv.parentElement.innerHTML = '<div class="nochart">Chart failed to render.</div>'; console.error(id,e); return null; }
}

function status(val, target, higher=true){
  if(val==null||target==null||!target) return 'flat';
  const r = higher ? val/target : target/val;
  if(r >= TH.on_target) return 'ok';
  if(r >= TH.watch) return 'warn';
  return 'bad';
}
function tile(lbl, val, unit, target, higher, targetLabel, extra, clickId){
  const st = status(val, target, higher);
  const ratio = (val!=null && target) ? (higher ? val/target : target/val) : 0;
  const w = Math.max(2, Math.min(100, ratio*100));
  const col = st==='ok'?CSS('--green'):st==='warn'?CSS('--amber'):CSS('--red');
  const pct = (val!=null&&target)? Math.round(ratio*100)+'%' : '\u2014';
  return `<div class="kpi ${st}${clickId?' click':''}"${clickId?` id="${clickId}" tabindex="0" role="button"`:''}>
    <div class="lbl">${lbl}</div>
    <div class="val">${val==null?'\u2014':(Number.isInteger(val)||Math.abs(val)>=1000?n0(val):n1(val))}<small>${unit||''}</small></div>
    <div class="bar"><i style="width:${w}%;background:${col}"></i></div>
    <div class="std"><span>${targetLabel}</span><span class="pill ${st}">${pct}</span></div>
    ${extra||''}
  </div>`;
}

document.getElementById('ttl').textContent = DATA.title;
document.getElementById('sub').textContent = DATA.subtitle;
document.getElementById('meta').innerHTML =
  `<b>Refreshed</b> ${DATA.generated_at}<br>`+
  `<b>Hours</b> ${DATA.shift.count} shift &middot; ${DATA.shift.start}\u2013${DATA.shift.end} &middot; ${DATA.shift.paid_hours} hrs<br>`+
  `<b>Spec</b> ${M.rated_bph} cartons/hr &middot; 1 associate per machine<br>`+
  `<b>Coverage</b> ${DATA.coverage.days} production days to ${DATA.coverage.last}`;

document.getElementById('scopeTabs').innerHTML = SCOPES.map(sc=>
  `<button data-scope="${sc.key}">${sc.label}<small>${sc.sublabel} \u00b7 ${n0(sc.target_day)}/day</small></button>`
).join('');

/* ================= DAILY ================= */
function renderDaily(){
  const L = SCOPE.latest;
  const T = SCOPE.trend || [];

  if(!L){
    document.getElementById('dayTitle').textContent = 'No production recorded';
    document.getElementById('daySpan').textContent = SCOPE.sublabel;
    document.getElementById('dayKpis').innerHTML = '<div class="kpi"><div class="lbl">No data</div></div>';
    document.getElementById('tDaily').innerHTML = '';
    return;
  }

  document.getElementById('dayTitle').textContent = `${L.weekday} ${L.date}`;
  document.getElementById('daySpan').textContent =
    `${SCOPE.label} \u00b7 first ${L.first} \u00b7 last ${L.last}` +
    (L.overrun_h>0.05 ? ` \u00b7 ran ${n1(L.overrun_h)} h past shift end` : '');

  const skus = L.skus || [];
  const skuHtml = skus.length
    ? `<div class="more"><span>${L.sku_count} box SKUs</span><span>&rsaquo;</span></div>` : '';

  const capLabel = (SCOPE.n_machines>1 && L.multi_machine)
    ? `both machines ran ${L.concurrent_min}m`
    : `${M.rated_bph}/hr \u00d7 ${SCOPE.n_machines} \u00d7 ${DATA.shift.paid_hours} hrs`;

  document.getElementById('dayKpis').innerHTML = [
    tile('Cartons produced', L.cartons, '', SCOPE.target_day, true,
         `target ${n0(SCOPE.target_day)}`, skuHtml, 't_cartons'),
    '<div id="laborSlot"></div>',
    tile('Capacity used', L.capacity_pct, '%', 100, true, capLabel, '', 't_capacity_pct'),
    tile('Availability', L.availability_pct, '%', S.availability_pct, true,
         `standard ${S.availability_pct}%`, '', 't_availability_pct'),
    tile('Fault events', L.fault_events, '', S.max_fault_events, false,
         `max ${S.max_fault_events}`, '', 't_fault_events'),
    tile('Trim waste', L.trim_pct, '%', S.max_trim_pct, false,
         `max ${S.max_trim_pct}%`, '', 't_trim_pct')
  ].join('');
  renderLabor();
  ['cartons','capacity_pct','availability_pct','fault_events','trim_pct']
    .forEach(k => wireMetric('t_'+k, k));

  document.getElementById('trendTitle').textContent = `Cartons per day vs target \u2014 ${SCOPE.label}`;
  document.getElementById('trendHint').textContent =
    `Last ${T.length} production days. Line = ${n0(SCOPE.target_day)}/day target.`;
  mkChart('cTrend', {
    type:'bar',
    data:{ labels:T.map(d=>d.date.slice(5)), datasets:[
      { label:'Cartons', data:T.map(d=>d.cartons),
        backgroundColor:T.map(d=> d.cartons>=SCOPE.target_day ? 'rgba(74,222,128,.72)'
          : d.cartons>=SCOPE.target_day*TH.watch ? 'rgba(242,183,5,.72)' : 'rgba(244,112,79,.6)'),
        borderRadius:3, barPercentage:.86, categoryPercentage:.9, order:2 },
      { label:'Target', type:'line', data:T.map(()=>SCOPE.target_day),
        borderColor:'#e8e6e3', borderWidth:1.6, pointRadius:0, order:1 }
    ]},
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ labels:{ color:'#8b8b96', font:{family:'JetBrains Mono',size:11}, boxWidth:11 } } },
      scales:{ x:{ ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:9.5},maxRotation:0,autoSkip:true,maxTicksLimit:16}, grid:{display:false} },
               y:{ beginAtZero:true, ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:10}}, grid:{color:'#232329'} } }}
  });

  document.getElementById('shiftHint').textContent =
    `${SCOPE.sched_h} scheduled machine-hours, latest day.`;
  const other = Math.max(0, SCOPE.sched_h - L.run_h - L.fault_h - L.starve_h);
  mkChart('cShift', {
    type:'doughnut',
    data:{ labels:['Running','Fault downtime','Starved / idle','Short gaps & setup'],
      datasets:[{ data:[L.run_h, L.fault_h, L.starve_h, other],
        backgroundColor:['#2d7d5a','#f4704f','#f2b705','#2a2a32'], borderColor:'#18181c', borderWidth:2 }]},
    options:{ responsive:true, maintainAspectRatio:false, cutout:'56%',
      plugins:{ legend:{ position:'bottom', labels:{color:'#8b8b96',font:{family:'JetBrains Mono',size:10.5},boxWidth:10,padding:9} },
        tooltip:{ callbacks:{ label:c=>` ${c.label}: ${c.raw.toFixed(2)} h` } } } }
  });

  const P = SCOPE.pareto || [];
  if(P.length){
    mkChart('cPareto', {
      type:'bar',
      data:{ labels:P.map(p=>p.message), datasets:[{ data:P.map(p=>p.count), backgroundColor:'rgba(90,169,230,.72)', borderRadius:3 }]},
      options:{ indexAxis:'y', responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{display:false} },
        scales:{ x:{ beginAtZero:true, ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:10}}, grid:{color:'#232329'} },
                 y:{ ticks:{color:'#8b8b96',font:{family:'JetBrains Mono',size:10}}, grid:{display:false} } } }
    });
  } else {
    const cv=document.getElementById('cPareto');
    if(cv && cv.parentElement) cv.parentElement.innerHTML = '<div class="nochart">No fault events in the loaded window.</div>';
  }

  const rows = (SCOPE.daily||[]).slice(-40).reverse();
  let h = `<thead><tr><th>Date</th><th>Cartons</th><th>SKUs</th><th>Cap</th><th>Per lab-hr</th><th>Avail</th><th>Faults</th><th>Trim</th><th>Last</th><th></th></tr></thead><tbody>`;
  rows.forEach(d=>{
    const st = status(d.cartons, SCOPE.target_day, true);
    const twoM = (SCOPE.n_machines>1 && d.multi_machine)
      ? `<span title="both machines ran concurrently for ${d.concurrent_min} min" style="color:var(--blue)">&nbsp;2M</span>` : '';
    h += `<tr><td class="k">${d.weekday} ${d.date.slice(5)}</td>`+
         `<td>${n0(d.cartons)}</td><td class="d">${d.sku_count||'\u2014'}</td>`+
         `<td class="d">${n1(d.capacity_pct)}%${twoM}</td><td class="k">${n1(d.cph)}</td>`+
         `<td class="d">${n1(d.availability_pct)}%</td><td class="d">${d.fault_events}</td>`+
         `<td class="d">${n1(d.trim_pct)}%</td><td class="d">${d.last}</td>`+
         `<td><span class="tag ${st}">${st==='ok'?'MET':st==='warn'?'NEAR':'MISS'}</span></td></tr>`;
  });
  document.getElementById('tDaily').innerHTML = h+'</tbody>';
}

/* Per labour-hour: the spec is a flat 175 per associate, so the toggle changes
   attainment. That is what makes a short-staffed day readable. */
function renderLabor(){
  const L = SCOPE.latest;
  const slot = document.getElementById('laborSlot');
  if(!slot || !L) return;
  const paid = DATA.shift.paid_hours || 8;
  const val = L.cartons / (ASSOC * paid);
  const tgt = S.throughput_cph;
  const st = status(val, tgt, true);
  const ratio = tgt ? val/tgt : 0;
  const w = Math.max(2, Math.min(100, ratio*100));
  const col = st==='ok'?CSS('--green'):st==='warn'?CSS('--amber'):CSS('--red');
  // One machine is run by one associate, so the machine tabs have nothing to
  // toggle. The choice only exists on the combined view, where it reads a
  // short-staffed day honestly.
  const multi = SCOPE.n_machines > 1;
  const tog = multi
    ? `<div class="tog">${[1,2].map(a=>
        `<button data-a="${a}" class="${ASSOC===a?'on':''}">${a} ASSOC</button>`).join('')}</div>`
    : '';
  slot.innerHTML = `<div class="kpi ${st} click" id="t_cph" tabindex="0" role="button">
    <div class="lbl">Per labor-hour</div>
    <div class="val">${n1(val)}<small>&nbsp;/ ${ASSOC} assoc</small></div>
    <div class="bar"><i style="width:${w}%;background:${col}"></i></div>
    <div class="std"><span>spec ${n1(tgt)} / associate</span><span class="pill ${st}">${Math.round(ratio*100)}%</span></div>
    ${tog}
  </div>`;
  slot.querySelectorAll('.tog button').forEach(b=>
    b.addEventListener('click', e=>{ e.stopPropagation(); ASSOC = Number(b.dataset.a); renderLabor(); }));
  wireMetric('t_cph','cph');
}

function wireSkuModal_unused(){
  const L = SCOPE.latest;
  const tileEl = document.getElementById('skuTile');
  if(!tileEl || !L || !(L.skus||[]).length) return;
  const ovl = document.getElementById('skuOvl');
  const top = L.skus[0].cartons || 1;
  const total = L.skus.reduce((a,k)=>a+k.cartons,0);
  document.getElementById('skuTitle').textContent = `Box SKUs \u2014 ${SCOPE.label}`;
  document.getElementById('skuSub').textContent =
    `${L.weekday} ${L.date} \u00b7 ${L.sku_count} SKUs \u00b7 ${n0(L.cartons)} cartons`;
  document.getElementById('skuBody').innerHTML =
    L.skus.map(k=>`<div class="sku">
        <span class="fill" style="width:${Math.max(3,(k.cartons/top)*100)}%"></span>
        <span class="nm" title="${k.sku}">${k.sku}</span>
        <span class="ct">${n0(k.cartons)}</span>
        <span class="pc">${n1(k.pct)}%</span>
      </div>`).join('') +
    `<div class="skutot"><span>${L.sku_count} SKUs on this day</span><span>${n0(total)} cartons</span></div>`;
  const open = ()=>{ ovl.classList.add('on'); document.getElementById('skuX').focus(); };
  const close = ()=> ovl.classList.remove('on');
  tileEl.addEventListener('click', open);
  tileEl.addEventListener('keydown', e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); open(); }});
  document.getElementById('skuX').onclick = close;
  ovl.onclick = e=>{ if(e.target===ovl) close(); };
}
document.addEventListener('keydown', e=>{ if(e.key==='Escape'){
  document.getElementById('skuOvl').classList.remove('on');
  document.getElementById('metOvl').classList.remove('on'); } });


/* ================= metric history modal =================
   Every tile clicks into the same panel: the metric's own history for the
   current scope, at daily / monthly / quarterly / yearly granularity, with
   the target drawn on it. Targets follow the scope, so MG1 charts against
   1,400/day while the overview charts against 2,800.                      */
const METRICS = {
  cartons: {label:'Cartons produced', dKey:'cartons', pKey:'cartons_per_day',
            target:()=>SCOPE.target_day, higher:true, unit:'', fmt:n0,
            note:'Daily output. Period views show cartons per day, not period totals.'},
  cph: {label:'Per labor-hour', dKey:'cph', pKey:'cph',
        target:()=>S.throughput_cph, higher:true, unit:'', fmt:n1,
        note:'Cartons per labour-hour against the flat 175 per-associate spec.'},
  capacity_pct: {label:'Capacity used', dKey:'capacity_pct', pKey:'capacity_pct',
        target:()=>100, higher:true, unit:'%', fmt:n1,
        note:'Output as a share of the engineered rate for this scope.'},
  availability_pct: {label:'Availability', dKey:'availability_pct', pKey:'availability_pct',
        target:()=>S.availability_pct, higher:true, unit:'%', fmt:n1,
        note:'Scheduled time less fault downtime. Machine health only.'},
  fault_events: {label:'Fault events', dKey:'fault_events', pKey:'faults_per_day',
        target:()=>S.max_fault_events, higher:false, unit:'', fmt:n1,
        note:'Genuine faults per day. Shift-boundary e-stops excluded.'},
  trim_pct: {label:'Trim waste', dKey:'trim_pct', pKey:'trim_pct',
        target:()=>S.max_trim_pct, higher:false, unit:'%', fmt:n1,
        note:'Trim area as a share of z-Fold consumed. Tracks box mix more than effort.'}
};
let MET_KEY = 'cartons', MET_PERIOD = 'daily';

function metSeries(key, period){
  const m = METRICS[key];
  if(period === 'daily'){
    const rows = (SCOPE.daily || []).slice(-60);
    return {labels: rows.map(r=>r.date.slice(5)), values: rows.map(r=>r[m.dKey]),
            caption: `last ${rows.length} production days`};
  }
  const rows = SCOPE[period] || [];
  return {labels: rows.map(r=>r.label), values: rows.map(r=>r[m.pKey]),
          caption: `${rows.length} ${period.replace('ly','')} period${rows.length===1?'':'s'}`};
}

function renderMetric(){
  const m = METRICS[MET_KEY];
  const tgt = m.target();
  const {labels, values, caption} = metSeries(MET_KEY, MET_PERIOD);
  const clean = values.filter(v=>v!=null && !isNaN(v));

  document.getElementById('metTitle').textContent = `${m.label} \u2014 ${SCOPE.label}`;
  document.getElementById('metSub').textContent =
    `${m.note} \u00b7 ${caption} \u00b7 target ${m.fmt(tgt)}${m.unit}`;
  document.querySelectorAll('#metTabs button').forEach(b=>
    b.classList.toggle('on', b.dataset.p===MET_PERIOD));

  const ok = 'rgba(74,222,128,.72)', wn = 'rgba(242,183,5,.72)', bd = 'rgba(244,112,79,.6)';
  const colour = v => {
    if(v==null||isNaN(v)) return '#2a2a32';
    const st = status(v, tgt, m.higher);
    return st==='ok'?ok:st==='warn'?wn:bd;
  };

  mkChart('cMetric', {
    type:'bar',
    data:{ labels, datasets:[
      { label:m.label, data:values, backgroundColor:values.map(colour), borderRadius:3,
        barPercentage:.88, categoryPercentage:.9, order:2 },
      { label:`target ${m.fmt(tgt)}${m.unit}`, type:'line', data:values.map(()=>tgt),
        borderColor:'#e8e6e3', borderWidth:1.6, pointRadius:0, borderDash:[6,4], order:1 }
    ]},
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ labels:{color:'#8b8b96',font:{family:'JetBrains Mono',size:10.5},boxWidth:11} } },
      scales:{ x:{ ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:9},maxRotation:0,autoSkip:true,maxTicksLimit:18}, grid:{display:false} },
               y:{ beginAtZero:true, ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:10}}, grid:{color:'#232329'} } }}
  });

  if(clean.length){
    const avg = clean.reduce((a,b)=>a+b,0)/clean.length;
    const best = m.higher ? Math.max(...clean) : Math.min(...clean);
    const worst = m.higher ? Math.min(...clean) : Math.max(...clean);
    const met = clean.filter(v=> m.higher ? v>=tgt : v<=tgt).length;
    document.getElementById('metStats').innerHTML = [
      [m.fmt(clean[clean.length-1])+m.unit, 'latest'],
      [m.fmt(avg)+m.unit, 'average'],
      [m.fmt(best)+m.unit, 'best'],
      [m.fmt(worst)+m.unit, 'worst'],
      [`${met} / ${clean.length}`, 'met target'],
      [Math.round(met/clean.length*100)+'%', 'hit rate']
    ].map(x=>`<div><b>${x[0]}</b><small>${x[1]}</small></div>`).join('');
  } else {
    document.getElementById('metStats').innerHTML = '<div><b>\u2014</b><small>no data</small></div>';
  }

  // The cartons panel carries the SKU split for the latest day as well.
  const extra = document.getElementById('metExtra');
  const L = SCOPE.latest;
  if(MET_KEY==='cartons' && L && (L.skus||[]).length){
    const top = L.skus[0].cartons || 1;
    extra.innerHTML = `<div style="margin-top:20px;padding-top:14px;border-top:1px solid var(--line)">
        <div class="hint" style="margin-bottom:10px">Box SKUs on ${L.weekday} ${L.date} \u00b7 ${L.sku_count} lines</div>` +
      L.skus.map(k=>`<div class="sku">
          <span class="fill" style="width:${Math.max(3,(k.cartons/top)*100)}%"></span>
          <span class="nm" title="${k.sku}">${k.sku}</span>
          <span class="ct">${n0(k.cartons)}</span>
          <span class="pc">${n1(k.pct)}%</span>
        </div>`).join('') + '</div>';
  } else { extra.innerHTML = ''; }
}

function openMetric(key, period){
  MET_KEY = key;
  if(period) MET_PERIOD = period;
  document.getElementById('metOvl').classList.add('on');
  renderMetric();
  document.getElementById('metX').focus();
}
function wireMetric(elId, key){
  const el = document.getElementById(elId);
  if(!el) return;
  const per = elId.startsWith('p_') ? VIEW : 'daily';
  el.addEventListener('click', ()=>openMetric(key, per));
  el.addEventListener('keydown', e=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); openMetric(key, per); }});
}
document.getElementById('metX').onclick = ()=> document.getElementById('metOvl').classList.remove('on');
document.getElementById('metOvl').onclick = e=>{
  if(e.target===document.getElementById('metOvl')) e.target.classList.remove('on'); };
document.querySelectorAll('#metTabs button').forEach(b=>
  b.addEventListener('click', ()=>{ MET_PERIOD = b.dataset.p; renderMetric(); }));

/* ================= PERIOD ================= */
const PERIOD_LABEL = {monthly:'Monthly', quarterly:'Quarterly', yearly:'Yearly'};
function renderPeriod(view){
  const rows = SCOPE[view] || [];
  document.getElementById('pTitle').textContent = `${PERIOD_LABEL[view]} \u2014 ${SCOPE.label}`;
  document.getElementById('pSpan').textContent =
    `${rows.length} period${rows.length===1?'':'s'} \u00b7 target ${n0(SCOPE.target_day)} cartons/day`;
  document.getElementById('pChartTitle').textContent = `${PERIOD_LABEL[view]} output vs target`;
  document.getElementById('pTableTitle').textContent = `${PERIOD_LABEL[view]} detail`;

  const last = rows[rows.length-1];
  document.getElementById('pKpis').innerHTML = last ? [
    tile('Cartons per day', last.cartons_per_day, '', SCOPE.target_day, true,
         `target ${n0(SCOPE.target_day)}`, '', 'p_cartons'),
    tile('Capacity used', last.capacity_pct, '%', 100, true,
         `${M.rated_bph}/hr \u00d7 ${SCOPE.n_machines}`, '', 'p_capacity_pct'),
    tile('Per labor-hour', last.cph, '', S.throughput_cph, true,
         `spec ${S.throughput_cph}`, '', 'p_cph'),
    tile('Days met target', last.pct_days_met, '%', 100, true, `${last.days_met_standard} of ${last.days}`),
    tile('Availability', last.availability_pct, '%', S.availability_pct, true,
         `standard ${S.availability_pct}%`, '', 'p_availability_pct'),
    tile('Faults / day', last.faults_per_day, '', S.max_fault_events, false,
         `max ${S.max_fault_events}`, '', 'p_fault_events'),
    tile('Trim waste', last.trim_pct, '%', S.max_trim_pct, false,
         `max ${S.max_trim_pct}%`, '', 'p_trim_pct'),
    tile('Best single day', last.best_day, '', SCOPE.target_day, true, `target ${n0(SCOPE.target_day)}`)
  ].join('') : '<div class="kpi"><div class="lbl">No data</div></div>';
  ['cartons','capacity_pct','cph','availability_pct','fault_events','trim_pct']
    .forEach(k => wireMetric('p_'+k, k));

  const labels = rows.map(r=>r.label);
  mkChart('cPeriod', {
    data:{ labels, datasets:[
      { type:'bar', label:'Cartons / day', data:rows.map(r=>r.cartons_per_day),
        backgroundColor:rows.map(r=> r.cartons_per_day>=SCOPE.target_day?'rgba(74,222,128,.72)'
          :r.cartons_per_day>=SCOPE.target_day*TH.watch?'rgba(242,183,5,.72)':'rgba(244,112,79,.6)'),
        borderRadius:3, yAxisID:'y', order:3 },
      { type:'line', label:'Target', data:rows.map(()=>SCOPE.target_day),
        borderColor:'#e8e6e3', borderWidth:1.6, pointRadius:0, yAxisID:'y', order:2 },
      { type:'line', label:'% days met', data:rows.map(r=>r.pct_days_met),
        borderColor:'#5aa9e6', borderWidth:2, pointRadius:3, pointBackgroundColor:'#5aa9e6',
        tension:.25, yAxisID:'y1', order:1 }
    ]},
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ labels:{color:'#8b8b96',font:{family:'JetBrains Mono',size:11},boxWidth:11} } },
      scales:{ x:{ ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:10}}, grid:{display:false} },
        y:{ beginAtZero:true, position:'left', title:{display:true,text:'cartons / day',color:'#5f5f6b',font:{family:'JetBrains Mono',size:10}},
            ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:10}}, grid:{color:'#232329'} },
        y1:{ beginAtZero:true, max:100, position:'right', title:{display:true,text:'% days met',color:'#5aa9e6',font:{family:'JetBrains Mono',size:10}},
            ticks:{color:'#5aa9e6',font:{family:'JetBrains Mono',size:10}}, grid:{display:false} } }}
  });

  mkChart('cUtil', {
    type:'bar',
    data:{ labels, datasets:[
      { label:'Availability %', data:rows.map(r=>r.availability_pct), backgroundColor:'rgba(74,222,128,.62)', borderRadius:3 },
      { label:'Utilization %', data:rows.map(r=>r.utilization_pct), backgroundColor:'rgba(90,169,230,.72)', borderRadius:3 }
    ]},
    options:{ responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ labels:{color:'#8b8b96',font:{family:'JetBrains Mono',size:11},boxWidth:11} } },
      scales:{ x:{ ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:10}}, grid:{display:false} },
               y:{ beginAtZero:true, max:100, ticks:{color:'#5f5f6b',font:{family:'JetBrains Mono',size:10}}, grid:{color:'#232329'} } }}
  });

  let h = `<thead><tr><th>Period</th><th>Days</th><th>Cartons</th><th>Per day</th><th>Capacity</th><th>Per lab-hr</th><th>% days met</th><th>Avail</th><th>Util</th><th>Faults/day</th><th>Trim</th><th>Best day</th></tr></thead><tbody>`;
  rows.slice().reverse().forEach(r=>{
    const st = status(r.cartons_per_day, SCOPE.target_day, true);
    h += `<tr><td class="k">${r.label}</td><td class="d">${r.days}</td><td>${n0(r.cartons)}</td>`+
         `<td class="k"><span class="tag ${st}">${n0(r.cartons_per_day)}</span></td>`+
         `<td class="d">${n1(r.capacity_pct)}%</td><td class="d">${n1(r.cph)}</td>`+
         `<td class="d">${n1(r.pct_days_met)}%</td><td class="d">${n1(r.availability_pct)}%</td>`+
         `<td class="d">${n1(r.utilization_pct)}%</td><td class="d">${n1(r.faults_per_day)}</td>`+
         `<td class="d">${n1(r.trim_pct)}%</td><td class="d">${n0(r.best_day)}</td></tr>`;
  });
  document.getElementById('tPeriod').innerHTML = h+'</tbody>';
}

/* ================= routing ================= */
function render(){
  document.querySelectorAll('.scopes button').forEach(b=>b.classList.toggle('on', b.dataset.scope===SCOPE.key));
  document.querySelectorAll('#periodTabs button').forEach(b=>b.classList.toggle('on', b.dataset.view===VIEW));
  document.getElementById('tgtNote').innerHTML =
    `${SCOPE.label} target <b>${n0(SCOPE.target_day)}</b> cartons/day &nbsp;\u00b7&nbsp; ${SCOPE.n_machines} machine${SCOPE.n_machines>1?'s':''} \u00d7 ${M.rated_bph}/hr \u00d7 ${DATA.shift.paid_hours} hrs`;
  const daily = VIEW==='daily';
  document.getElementById('v-daily').classList.toggle('hidden', !daily);
  document.getElementById('v-period').classList.toggle('hidden', daily);
  if(daily) renderDaily(); else renderPeriod(VIEW);
}
document.querySelectorAll('.scopes button').forEach(b=> b.addEventListener('click', ()=>{
  SCOPE = SCOPES.find(s=>s.key===b.dataset.scope); ASSOC = SCOPE.associates; render(); }));
document.querySelectorAll('#periodTabs button').forEach(b=> b.addEventListener('click', ()=>{
  VIEW = b.dataset.view; render(); }));

if(!HAS_CHART){
  const b=document.createElement('div'); b.className='note'; b.style.borderLeftColor='#f4704f';
  b.innerHTML='<b>Charts unavailable.</b> The Chart.js library could not be loaded (no internet access, or the CDN is blocked by network policy). Every figure is still shown in the tiles and tables.';
  document.getElementById('periodTabs').after(b);
}
render();
</script>
</body>
</html>
"""


def build(payload: dict, cfg: dict, log: _MdLog) -> Path:
    html = (TEMPLATE
            .replace("{{PAYLOAD}}", json.dumps(payload, separators=(",", ":")))
            .replace("{{CHARTJS}}", cfg["dashboard"]["chart_js_cdn"]))

    out = resolve(cfg, "output_html")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Direct write, then verify. OneDrive breaks tmp -> rename.
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    size = out.stat().st_size
    if size < 8000:
        log.err(f"{out.name} is only {size:,} bytes - write likely truncated")
    else:
        log.ok(f"wrote {out.name} ({size:,} bytes)")

    arch = resolve(cfg, "archive")
    arch.mkdir(parents=True, exist_ok=True)
    snap = arch / f"dashboard_{datetime.now():%Y%m%d}.html"
    with open(snap, "w", encoding="utf-8") as fh:
        fh.write(html)
    log.info(f"archived snapshot -> {snap.name}")
    return out


def main(config_path=None):
    cfg = load_config(config_path)
    log = _MdLog(echo_file=resolve(cfg, "log"))
    res = etl_run(config_path, log=log)
    log.h("Dashboard")
    out = build(res["payload"], res["cfg"], log)
    log.close()
    return out


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
