"""Single-file interactive plant view: layout map, animated entities, resources, live charts and a parameter panel.
The page re-runs the simulation (plantsim/engine.js, a port of model.py) whenever a parameter changes. Own code, no network."""
from __future__ import annotations
import dataclasses, html, json, os
from .model import Plant

HERE = os.path.dirname(__file__)

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
<title>__TITLE__</title><style>
body{font:14px/1.4 system-ui,sans-serif;margin:0;color:#070f26;background:#f4f6f9}
header{background:#070f26;color:#fff;padding:12px 20px}h1{margin:0;font-size:19px}
main{padding:10px 20px 24px;max-width:1180px}
.note{margin:10px 0;padding:8px 12px;border-left:4px solid #c98a00;background:#fff6d6}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}
button{background:#005b96;color:#fff;border:0;border-radius:4px;padding:6px 14px;font-size:14px;cursor:pointer}
button.sec{background:#fff;color:#005b96;border:1px solid #005b96}
input[type=range]{flex:1;min-width:200px}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0}.card{background:#fff;border:1px solid #d5dce4;border-radius:6px;padding:6px 12px}
.card small{display:block;color:#4a5668}.card b{font-size:18px}
svg{background:#fff;border:1px solid #d5dce4;border-radius:6px}
.lg span{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px 0 12px}
.grid{display:grid;grid-template-columns:1fr 250px;gap:12px}@media(max-width:900px){.grid{grid-template-columns:1fr}}
.panel{background:#fff;border:1px solid #d5dce4;border-radius:6px;padding:8px 12px;font-size:13px}
.panel h3{margin:6px 0;font-size:13px;color:#005b96}.panel label{display:flex;justify-content:space-between;align-items:center;gap:6px;margin:3px 0}
.panel input[type=number]{width:62px}
#log{border-collapse:collapse;width:100%;font:12px ui-monospace,monospace;background:#fff}#log th{background:#070f26;color:#fff;text-align:left;padding:4px 6px}#log td{padding:3px 6px;border-top:1px solid #e3e8ee;vertical-align:top}.chip{color:#fff;border-radius:3px;padding:0 5px;font-size:11px}
.foot{margin-top:18px;font-size:12px;color:#4a5668}.foot a,.foot span.u{color:#005b96}h2{color:#005b96;font-size:16px;margin:16px 0 6px}
</style></head><body><header><h1>__TITLE__</h1></header><main>
<div class="note"><b>Fictitious plant, illustrative numbers.</b> Generic oral-solid-dose process. Simulated, not measured, not validated against any real site. A small browser tool, not a replacement for a full simulation package.</div>
<div class="cards"><div class="card"><small>Throughput (steady state)</small><b id="k_tp"></b></div>
<div class="card"><small>Mean lead time</small><b id="k_lt"></b></div><div class="card"><small>Busiest stage</small><b id="k_bn"></b></div>
<div class="card"><small>Forklift pool busy</small><b id="k_fk"></b></div>
<div class="card"><small>Lots rejected (QA)</small><b id="k_rej"></b></div><div class="card"><small>Picks where FEFO differs from FIFO</small><b id="k_fefo"></b></div>
<div class="card"><small>Blocked resource-hours (finite buffers)</small><b id="k_blk"></b></div><div class="card"><small>Clock</small><b id="clock"></b></div><div class="card"><small>Lots/batches finished</small><b id="fin"></b></div><div class="card"><small>In the plant now</small><b id="wip"></b></div></div>
<div class="bar"><button id="pp">Pause</button><label>Speed <select id="sp"><option value="0.5">0.5 h/s (watch trips)</option><option value="2">2 h/s</option><option value="6">6 h/s</option><option value="12" selected>12 h/s</option><option value="24">1 day/s</option><option value="72">3 days/s</option></select></label>
<input id="sl" type="range" min="0" max="100" step="1" value="0"></div>
<div class="grid"><div><svg id="v" viewBox="0 0 1060 __SH__" width="100%"></svg>
<div class="lg">Product:__LEG__ <span style="background:#c98a00"></span>waiting <span style="background:#00857c"></span>working or moving &nbsp; <b>&#9632;</b> forklift carrying a lot</div></div>
<div class="panel" id="panel"><h3>Parameters (re-run live)</h3></div></div>
<h2>Signals and transactions (simulated)</h2>
<div class="bar" id="evbar"></div>
<table id="log"><thead><tr><th>Time</th><th>Kind</th><th>Source</th><th>Lot</th><th>Event</th></tr></thead><tbody></tbody></table>
<svg id="ec" viewBox="0 0 1060 150" width="100%"></svg>
<h2>Plant over time</h2><svg id="c" viewBox="0 0 1060 210" width="100%"></svg>
<h2>Utilisation per stage (steady state)</h2><svg id="u" viewBox="0 0 1060 __UH__" width="100%"></svg>
<div class="foot"><b>About the signal layer.</b> PLC and sensor events (door sensors, scans, scales, conveyors, palletizer, labelling, serialization) and WMS, ERP and QA events are generated from the simulated material flow, with invented values. The "SAP-style" events are <b>simulated, not a real SAP integration</b>. They only use generic concepts and the movement types 101 (goods receipt for purchase or production order), 261 (goods issue to production order) and 321 (transfer posting from quality inspection to unrestricted-use stock), as named on the public SAP Learning pages:
<span class="u">learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/posting-a-goods-receipt-with-reference</span>,
<span class="u">learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-manufacturing/executing-production-orders_eebd35c8-b7ed-4f36-bd4a-fb527dfa1322</span>,
<span class="u">learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/performing-transfer-postings</span> (checked 1 Oct 2026). Document numbers are simulated sequence numbers. No SAP field names or transaction codes are used. Serial shipping container code is a GS1 concept.</div></main><script>
__ENGINE__
const BASE=__CONFIG__;
const NS="http://www.w3.org/2000/svg",COL={A:"#005b96",B:"#7a3fb0",C:"#d1495b"};
function el(p,n,a,t){const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);if(t)e.textContent=t;p.appendChild(e);return e}
const v=document.getElementById("v"),L=BASE.layout,li={};L.forEach((l,i)=>li[l.id]=i);
let P,R,dots=[],T=0,play=true,t0=0,tmax=1,stLoc,mvFrom,mvTo;
const ctr=l=>({x:l.x+l.w/2,y:l.y+l.h/2});
// static map
const seen={};BASE.stages.forEach((s,k)=>{if(s.kind==="move"){const a=li[BASE.stages[k-1].loc],b=li[BASE.stages[k+1].loc],key=a+"-"+b;if(!seen[key]&&a!==b){seen[key]=1;const p=ctr(L[a]),q=ctr(L[b]);el(v,"line",{x1:p.x,y1:p.y,x2:q.x,y2:q.y,stroke:"#b8c2cf","stroke-width":4,"stroke-dasharray":"7 6"})}}});
const boxes=L.map(l=>{const r=el(v,"rect",{x:l.x,y:l.y,width:l.w,height:l.h,rx:8,fill:"#f7f9fb",stroke:"#8a94a6","stroke-width":2});
 el(v,"text",{x:l.x+8,y:l.y+16,"font-size":11,"font-weight":600},l.name);const q=el(v,"text",{x:l.x+8,y:l.y+l.h-7,"font-size":10.5,fill:"#4a5668"},"");return{r,q}});
const layer=el(v,"g",{});const fkLayer=el(v,"g",{});
// parameters
const H=Object.fromEntries(location.hash.slice(1).split("&").filter(Boolean).map(x=>x.split("=")));
const G={release_every:BASE.release_every,seed:BASE.seed,speed:+H.sp||BASE.speed_kmh||6,handling:H.h!=null?+H.h:(BASE.handling_min==null?6:BASE.handling_min),rule:H.rule==='FIFO'?'FIFO':'FEFO',brk_mult:1,changeover_mult:1,retest_p:null,labs247:false,buf:H.buf!=="0",bufadd:+H.ba||0};
const panel=document.getElementById("panel");
function num(label,get,set,step,min,max){const lb=document.createElement("label");lb.textContent=label;const i=document.createElement("input");i.type="number";i.value=get();i.step=step;i.min=min;i.max=max;i.oninput=()=>{const x=parseFloat(i.value);if(!isNaN(x)){set(x);schedule()}};lb.appendChild(i);panel.appendChild(lb)}
function h3(t){const h=document.createElement("h3");h.textContent=t;panel.appendChild(h)}
h3("Demand");num("Release a lot every (h)",()=>G.release_every,x=>G.release_every=Math.max(1,x),1,1,200);num("Random seed",()=>G.seed,x=>G.seed=x,1,1,9999);
h3("Resources (servers)");const SV={};BASE.stages.forEach(s=>{if(s.kind==="process"||(s.pool&&!SV[s.pool])){const key=s.pool||s.name;SV[key]=(s.pool&&+H.fk)||s.servers||1;num(s.pool?s.pool+" (forklifts)":s.name,()=>SV[key],x=>SV[key]=Math.max(1,Math.round(x)),1,1,12)}});
h3("Multipliers");num("Forklift speed (km/h)",()=>G.speed,x=>G.speed=Math.max(0.2,x),1,0.2,25);num("Handling per leg (min)",()=>G.handling,x=>G.handling=Math.max(0,x),1,0,120);num("Breakdown chance x",()=>G.brk_mult,x=>G.brk_mult=Math.max(0,x),0.5,0,10);num("Changeover time x",()=>G.changeover_mult,x=>G.changeover_mult=Math.max(0,x),0.5,0,5);
const rl=document.createElement("label");rl.textContent="Raw-material pick rule";const rsel=document.createElement("select");["FEFO","FIFO"].forEach(x=>{const o=document.createElement("option");o.textContent=x;rsel.appendChild(o)});rsel.value=G.rule;rsel.onchange=()=>{G.rule=rsel.value;schedule()};rl.appendChild(rsel);panel.appendChild(rl);
const lb=document.createElement("label");lb.textContent="QC/QA open 24/7";const cb=document.createElement("input");cb.type="checkbox";cb.onchange=()=>{G.labs247=cb.checked;schedule()};lb.appendChild(cb);panel.appendChild(lb);
{const l2=document.createElement("label");l2.textContent="Finite buffers (blocking)";const c2=document.createElement("input");c2.type="checkbox";c2.checked=G.buf;c2.onchange=()=>{G.buf=c2.checked;schedule()};l2.appendChild(c2);panel.appendChild(l2)}
num("Buffer size change (lots, + or -)",()=>G.bufadd,x=>G.bufadd=Math.round(x),1,-5,20);
const rs=document.createElement("button");rs.className="sec";rs.textContent="Reset";rs.onclick=()=>location.reload();panel.appendChild(rs);
function params(){const q=JSON.parse(JSON.stringify(BASE));q.release_every=G.release_every;q.seed=G.seed;
 q.speed_kmh=G.speed;q.handling_min=G.handling;
 q.stages.forEach(s=>{if(s.kind==="move"){s.servers=SV[s.pool]}else if(s.kind==="process")s.servers=SV[s.name];
  if(s.pool)s.servers=SV[s.pool];if(s.breakdown_p)s.breakdown_p=Math.min(1,s.breakdown_p*G.brk_mult);if(s.changeover)s.changeover*=G.changeover_mult;
  if(!G.buf)delete s.buffer;else if(s.buffer!=null)s.buffer=Math.max(1,s.buffer+G.bufadd);
  if(G.labs247&&s.window&&/QC|QA/.test(s.name)){delete s.window;s.workdays=7}});return q}
let tm=0;function schedule(){clearTimeout(tm);tm=setTimeout(run,150)}
function run(){P=params();R=simulate(P);t0=P.warmup;tmax=P.horizon-t0;
 stLoc=P.stages.map(s=>s.kind==="move"?null:li[s.loc]);mvFrom=P.stages.map((s,k)=>s.kind==="move"?stLoc[k-1]:null);mvTo=P.stages.map((s,k)=>s.kind==="move"?stLoc[k+1]:null);
 layer.textContent="";fkLayer.textContent="";dots=[];R.vis=R.batches.filter(b=>b.r>=t0&&b.d!=null&&b.r<P.horizon);
 R.vis.forEach(b=>dots.push(el(layer,"circle",{r:6,fill:COL[b.p]||"#555",stroke:"#fff","stroke-width":1.5,visibility:"hidden"})));
 R.fk=[];for(const name in R.pools){const n=SV[name];R.fk.push({name,els:[...Array(n)].map(()=>el(fkLayer,"rect",{width:14,height:9,rx:2,fill:"#070f26",visibility:"hidden"}))})}
 const sl=document.getElementById("sl");sl.max=Math.round(tmax);if(T>tmax)T=0;
 document.getElementById("k_tp").textContent=R.throughput.toFixed(1)+" batches/week";document.getElementById("k_lt").textContent=R.leadDays.toFixed(1)+" days";
 document.getElementById("k_bn").textContent=R.bottleneck;document.getElementById("k_rej").textContent=R.rejected;document.getElementById("k_blk").textContent=(function(){let a=0,m=0;R.stats.forEach((x,k)=>{a+=x.blocked||0;if(P.stages[k].kind==="move")m+=x.blocked||0});return a.toFixed(0)+" h ("+m.toFixed(0)+" h forklifts)"})();document.getElementById("k_fk").textContent=Object.values(R.pools).map(x=>(100*x).toFixed(0)+"%").join(", ")||"-";
 drawUtil();drawChart();buildLog();draw()}
function state(b,T){const t=T+t0;if(t<b.r)return null;for(const[k,a,s,e,lv]of b.t){if(t<a)return null;if(t<s)return[k,"wait"];if(t<e)return[k,"proc",(t-s)/Math.max(e-s,1e-9)];if(lv!=null&&t<lv)return[k,"block"]}return null}
function draw(){const cnt=L.map(_=>({w:0,p:0,mv:0,b:0})),lim=L.map(_=>null);P.stages.forEach((s,k)=>{if(s.buffer!=null&&s.kind==="process")lim[stLoc[k]]=s.buffer});let fin=0,wip=0;const fu={};for(const n in R.pools)fu[n]=0;
 R.vis.forEach((b,i)=>{const d=dots[i];const lastE=b.t[b.t.length-1][3];if(T+t0>=lastE){d.setAttribute("visibility","hidden");fin++;return}
  const st=state(b,T);if(!st){d.setAttribute("visibility","hidden");return}wip++;const[k,ph,f]=st,s=P.stages[k];let x,y;
  if(s.kind==="move"&&ph==="proc"){const p=ctr(L[mvFrom[k]]),q=ctr(L[mvTo[k]]);x=p.x+(q.x-p.x)*f;y=p.y+(q.y-p.y)*f;const e=R.fk.find(z=>z.name===s.pool).els[fu[s.pool]++];if(e){e.setAttribute("x",x-7);e.setAttribute("y",y+7);e.setAttribute("visibility","visible")}cnt[mvFrom[k]].mv++}
  else if(s.kind==="move"&&ph==="block"){const l=L[mvTo[k]],c=cnt[mvTo[k]],slot=c.b++,cols=Math.max(1,Math.floor((l.w-16)/17));x=l.x+14+(slot%cols)*17;y=l.y+l.h-24-Math.floor(slot/cols)*15;const e=R.fk.find(z=>z.name===s.pool).els[fu[s.pool]++];if(e){e.setAttribute("x",x-7);e.setAttribute("y",y+7);e.setAttribute("visibility","visible")}}
  else{const i2=s.kind==="move"?mvFrom[k]:stLoc[k],l=L[i2],c=cnt[i2],slot=ph==="wait"||ph==="block"?(ph==="wait"?c.w++:c.w+c.b++):c.p++,cols=Math.max(1,Math.floor((l.w-16)/17)),col=slot%cols,row=Math.floor(slot/cols);x=l.x+14+col*17;y=ph==="proc"?l.y+34+row*15:l.y+l.h-24-row*15}
  d.setAttribute("cx",x);d.setAttribute("cy",y);d.setAttribute("visibility","visible");d.setAttribute("stroke",b.rej&&s.kind==="hold"?"#b3261e":ph==="block"?"#b3261e":ph==="wait"?"#c98a00":"#00857c");d.setAttribute("stroke-width",3)});
 R.fk.forEach(p=>p.els.forEach((e,j)=>{if(j>=fu[p.name])e.setAttribute("visibility","hidden")}));
 L.forEach((l,i)=>{boxes[i].q.textContent="waiting "+cnt[i].w+(lim[i]!=null?"/"+lim[i]:"")+" | working "+cnt[i].p+(cnt[i].b?" | blocked "+cnt[i].b:"")+(cnt[i].mv?" | leaving "+cnt[i].mv:"");boxes[i].r.setAttribute("fill",cnt[i].b?"#fbe0dd":cnt[i].w>=3?"#fff0cf":"#f7f9fb")});
 const t=T+t0,day=Math.floor(t/24),h=Math.floor(t%24);document.getElementById("clock").textContent=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][day%7]+" "+String(h).padStart(2,"0")+":00 (day "+(day+1)+")";
 document.getElementById("fin").textContent=fin;document.getElementById("wip").textContent=wip;document.getElementById("sl").value=T;
 if(cur)cur.setAttribute("x1",cx(T)),cur.setAttribute("x2",cx(T));if(ecCur){ecCur.setAttribute("x1",cx(T));ecCur.setAttribute("x2",cx(T))}if(typeof logDraw==="function")logDraw()}
// live chart: batches in plant + cumulative finished
let cur=null;const CW=1060,CL=50,CR=20,CT=14,CB=34,CH=210;const cx=T=>CL+(CW-CL-CR)*Math.min(T/tmax,1);
function drawChart(){const c=document.getElementById("c");c.textContent="";const N=Math.ceil(tmax/6),wip=[],cum=[];
 for(let i=0;i<=N;i++){const t=t0+i*6;let w=0,f=0;R.vis.forEach(b=>{if(b.r<=t&&t<b.d)w++;if(b.d<=t)f++});wip.push(w);cum.push(f)}
 const mw=Math.max(5,...wip)*1.1,mc=Math.max(5,...cum)*1.05,X=i=>CL+(CW-CL-CR)*i/N,Yw=y=>CT+(CH-CT-CB)*(1-y/mw),Yc=y=>CT+(CH-CT-CB)*(1-y/mc);
 for(let g=0;g<=4;g++){const y=CT+(CH-CT-CB)*g/4;el(c,"line",{x1:CL,x2:CW-CR,y1:y,y2:y,stroke:"#e3e8ee"});el(c,"text",{x:CL-6,y:y+4,"font-size":10,"text-anchor":"end",fill:"#c98a00"},(mw*(1-g/4)).toFixed(0));el(c,"text",{x:CW-CR+4,y:y+4,"font-size":10,fill:"#00857c"},(mc*(1-g/4)).toFixed(0))}
 el(c,"polyline",{fill:"none",stroke:"#c98a00","stroke-width":2.2,points:wip.map((y,i)=>X(i)+","+Yw(y)).join(" ")});
 el(c,"polyline",{fill:"none",stroke:"#00857c","stroke-width":2.2,points:cum.map((y,i)=>X(i)+","+Yc(y)).join(" ")});
 for(let d=0;d*24<=tmax;d+=Math.ceil(tmax/24/8))el(c,"text",{x:cx(d*24),y:CH-18,"font-size":10,"text-anchor":"middle"},"day "+(Math.floor(t0/24)+d+1));
 el(c,"text",{x:CL,y:CH-4,"font-size":10.5,fill:"#c98a00"},"Lots in the plant (left axis)");el(c,"text",{x:CL+220,y:CH-4,"font-size":10.5,fill:"#00857c"},"Cumulative finished (right axis)");
 cur=el(c,"line",{x1:0,x2:0,y1:CT,y2:CH-CB,stroke:"#070f26","stroke-width":1.5})}
function drawUtil(){const u=document.getElementById("u");u.textContent="";const rows=[],done={};
 P.stages.forEach((s,k)=>{if(s.pool){if(!done[s.pool]){done[s.pool]=1;rows.push({n:s.pool+" (pool of "+s.servers+")",process:R.pools[s.pool],setup:0,repair:0})}}else if(s.kind==="process")rows.push({n:s.name,...R.util[k]})});
 rows.forEach((x,i)=>{const y=8+i*28;el(u,"text",{x:230,y:y+15,"font-size":12,"text-anchor":"end"},x.n);let c=240;
  [["process","#00857c"],["setup","#c98a00"],["repair","#b3261e"]].forEach(([k,col])=>{const w=780*Math.min(x[k],1);if(w>0){const r=el(u,"rect",{x:c,y:y,width:w,height:20,fill:col});el(r,"title",{},x.n+" "+k+": "+(100*x[k]).toFixed(1)+"%");c+=w}});
  el(u,"text",{x:c+6,y:y+15,"font-size":11},(100*(x.process+x.setup+x.repair)).toFixed(0)+"%")});
 el(u,"text",{x:240,y:8+rows.length*28+14,"font-size":11,fill:"#4a5668"},"green = processing/moving, amber = changeover/cleaning, red = repair. Over 100% means the stage cannot keep up.")}

// ---- event log, filters, export
const KC={PLC:"#00857c",WMS:"#005b96",ERP:"#7a3fb0",QA:"#c98a00"};let EV=[],FEV=[],lotSel="",kinds={PLC:true,WMS:true,ERP:true,QA:true};
const bar=document.getElementById("evbar");
Object.keys(KC).forEach(k=>{const l=document.createElement("label");l.innerHTML='<span class="chip" style="background:'+KC[k]+'">'+k+'</span> ';const c=document.createElement("input");c.type="checkbox";c.checked=true;c.onchange=()=>{kinds[k]=c.checked;refilter()};l.appendChild(c);bar.appendChild(l)});
const lsel=document.createElement("select");lsel.onchange=()=>{lotSel=lsel.value;refilter()};bar.appendChild(lsel);
function dl(name,mime,text){const a=document.createElement("a");a.href="data:"+mime+";charset=utf-8,"+encodeURIComponent(text);a.download=name;document.body.appendChild(a);a.click();a.remove()}
[["Export CSV",()=>dl("plant_events.csv","text/csv",eventsCsv(EV,t0))],["Export JSON",()=>dl("plant_events.json","application/json",JSON.stringify(EV.map(e=>({...e,clock:clockLabel(e.t+t0)})),null,1))]].forEach(([n,f])=>{const b=document.createElement("button");b.className="sec";b.textContent=n;b.onclick=f;bar.appendChild(b)});
const vsel=document.createElement("select");["Table view","MQTT-style messages"].forEach(x=>{const o=document.createElement("option");o.textContent=x;vsel.appendChild(o)});vsel.onchange=()=>{mq=vsel.selectedIndex===1;logDraw()};bar.insertBefore(vsel,bar.children[5]);let mq=false;if(H.v==="mqtt"){vsel.selectedIndex=1;mq=true}
{const b=document.createElement("button");b.className="sec";b.textContent="Export MQTT lines";b.onclick=()=>dl("plant_messages.jsonl","application/x-ndjson",mqttLines(EV,t0));bar.appendChild(b)}
const cntEl=document.createElement("span");bar.appendChild(cntEl);
function buildLog(){EV=buildEvents(P,R,t0,P.horizon,G.rule);const pk=EV.pick;document.getElementById("k_fefo").textContent=pk?pk.diff+" of "+pk.picks:"-";const lots=[...new Set(EV.map(e=>e.lot))];lsel.textContent="";const o0=document.createElement("option");o0.value="";o0.textContent="All lots";lsel.appendChild(o0);lots.forEach(l=>{const o=document.createElement("option");o.value=l;o.textContent=l;lsel.appendChild(o)});lsel.value=lots.includes(lotSel)?lotSel:"";lotSel=lsel.value;refilter();drawEC()}
function refilter(){FEV=EV.filter(e=>kinds[e.kind]&&(!lotSel||e.lot===lotSel));logDraw()}
function logDraw(){let lo=0,hi=FEV.length;while(lo<hi){const m=(lo+hi)>>1;if(FEV[m].t<=T)lo=m+1;else hi=m}
 const tb=document.querySelector("#log tbody");tb.textContent="";document.querySelector("#log thead tr").innerHTML=mq?"<th>Time</th><th>Kind</th><th>Topic</th><th>Payload (JSON)</th>":"<th>Time</th><th>Kind</th><th>Source</th><th>Lot</th><th>Event</th>";cntEl.textContent=" "+lo+" of "+FEV.length+" events so far";
 for(let i=lo-1;i>=Math.max(0,lo-14);i--){const e=FEV[i],tr=document.createElement("tr");
  (mq?(m=>[clockLabel(e.t+t0).replace(/ \(day.*/,""),null,m.topic,JSON.stringify(m.payload)])(mqtt(e,t0)):[clockLabel(e.t+t0).replace(/ \(day.*/,""),null,e.src,e.lot,e.detail]).forEach((x,j)=>{const td=document.createElement("td");if(j===1){const c=document.createElement("span");c.className="chip";c.style.background=KC[e.kind];c.textContent=e.kind;td.appendChild(c)}else td.textContent=x;tr.appendChild(td)});tb.appendChild(tr)}}
let ecCur=null;function drawEC(){const c=document.getElementById("ec");c.textContent="";const N=Math.ceil(tmax/6),bins=Object.keys(KC).map(_=>Array(N+1).fill(0)),ks=Object.keys(KC);
 EV.forEach(e=>{const i=Math.floor(e.t/6);if(i>=0&&i<=N)bins[ks.indexOf(e.kind)][i]++});
 const tot=bins[0].map((_,i)=>bins.reduce((a,b)=>a+b[i],0)),mx=Math.max(5,...tot)*1.1,bw=(CW-CL-CR)/(N+1);
 for(let i=0;i<=N;i++){let y=CH2-20;ks.forEach((k,j)=>{const h=(CH2-34)*bins[j][i]/mx;if(h>0){el(c,"rect",{x:CL+i*bw,y:y-h,width:Math.max(bw-0.5,0.5),height:h,fill:KC[k]});y-=h}})}
 el(c,"text",{x:CL,y:12,"font-size":10.5,fill:"#4a5668"},"Events per 6 h (max "+Math.round(mx/1.1)+"), stacked by kind");
 for(let d=0;d*24<=tmax;d+=Math.ceil(tmax/24/8))el(c,"text",{x:cx(d*24),y:CH2-6,"font-size":10,"text-anchor":"middle"},"day "+(Math.floor(t0/24)+d+1));
 ecCur=el(c,"line",{x1:0,x2:0,y1:18,y2:CH2-20,stroke:"#070f26","stroke-width":1.5})}
const CH2=150;
const m=location.hash.match(/t=(\d+)/);if(m){T=+m[1];play=false;document.getElementById("pp").textContent="Play"}
const sp=document.getElementById("sp");const ms=location.hash.match(/s=([\d.]+)/);if(ms)sp.value=ms[1];
let last=performance.now();function loop(now){const dt=Math.min((now-last)/1000,0.2);last=now;if(play){T+=dt*+sp.value;if(T>tmax)T=0}draw();requestAnimationFrame(loop)}
document.getElementById("pp").onclick=function(){play=!play;this.textContent=play?"Pause":"Play"};
document.getElementById("sl").oninput=function(){T=+this.value;draw()};
run();requestAnimationFrame(loop);
</script></body></html>"""


def to_config(plant: Plant) -> dict:
    d = {"products": plant.products, "release_every": plant.release_every, "horizon": plant.horizon,
         "warmup": plant.warmup, "seed": plant.seed, "m_per_px": plant.m_per_px, "speed_kmh": plant.speed_kmh, "handling_min": plant.handling_min, "layout": plant.layout or _auto_layout(plant), "stages": []}
    for s in plant.stages:
        x = {k: v for k, v in dataclasses.asdict(s).items() if v is not None}
        if not plant.layout and s.kind != "move":
            x["loc"] = s.name
        d["stages"].append(x)
    return d


def _auto_layout(plant: Plant):
    locs, seen = [], set()
    for s in plant.stages:
        if s.kind == "move" or s.name in seen:
            continue
        seen.add(s.name)
        r, c = divmod(len(locs), 5)
        locs.append({"id": s.name, "name": s.name, "x": 20 + (4 - c if r % 2 else c) * 192, "y": 20 + r * 160, "w": 172, "h": 92})
    return locs


def render(plant: Plant, res=None, title: str = "Pharma plant simulation (fictitious)") -> str:
    cfg = to_config(plant)
    engine = open(os.path.join(HERE, "engine.js"), encoding="utf-8").read()
    import re
    engine = re.sub(r'^if\(typeof module.*$', '', engine, flags=re.M)
    height = max(l["y"] + l["h"] for l in cfg["layout"]) + 20
    nrows = len({(s.pool or s.name) for s in plant.stages if s.kind == "process"} | {s.pool for s in plant.stages if s.pool})
    leg = "".join(f'<span style="background:{c}"></span>{p}' for p, c in zip(plant.products, ["#005b96", "#7a3fb0", "#d1495b"]))
    return (PAGE.replace("__TITLE__", html.escape(title)).replace("__ENGINE__", engine)
            .replace("__CONFIG__", json.dumps(cfg).replace("</", "<\\/")).replace("__LEG__", leg)
            .replace("__SH__", str(height)).replace("__UH__", str(nrows * 28 + 30)))
