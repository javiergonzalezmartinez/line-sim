"""Single-file animated 2D plant view (own SVG + JS, no network)."""
from __future__ import annotations
import html, json
from .model import Plant, Result

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:">
<title>__TITLE__</title><style>
body{font:14px/1.4 system-ui,sans-serif;margin:0;color:#070f26;background:#f4f6f9}
header{background:#070f26;color:#fff;padding:12px 20px}h1{margin:0;font-size:19px}
main{padding:10px 20px 24px;max-width:1100px}
.note{margin:10px 0;padding:8px 12px;border-left:4px solid #c98a00;background:#fff6d6}
.bar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}
button{background:#005b96;color:#fff;border:0;border-radius:4px;padding:6px 14px;font-size:14px;cursor:pointer}
input[type=range]{flex:1;min-width:200px}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0}.card{background:#fff;border:1px solid #d5dce4;border-radius:6px;padding:6px 12px}
.card small{display:block;color:#4a5668}.card b{font-size:18px}
svg{background:#fff;border:1px solid #d5dce4;border-radius:6px}
.lg span{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px 0 12px}
</style></head><body><header><h1>__TITLE__</h1></header><main>
<div class="note"><b>Fictitious plant, illustrative numbers.</b> Generic oral-solid-dose process. Not any real site. Simulated, not measured.</div>
<div class="cards"><div class="card"><small>Throughput (steady state)</small><b>__TP__ batches/week</b></div>
<div class="card"><small>Mean lead time</small><b>__LT__ days</b></div><div class="card"><small>Busiest stage</small><b>__BN__</b></div>
<div class="card"><small>Clock</small><b id="clock"></b></div><div class="card"><small>Batches finished</small><b id="fin"></b></div></div>
<div class="bar"><button id="pp">Pause</button><label>Speed <select id="sp"><option value="6">6 h/s</option><option value="12" selected>12 h/s</option><option value="24">1 day/s</option><option value="72">3 days/s</option></select></label>
<input id="sl" type="range" min="0" max="__H__" step="1" value="0"></div>
<svg id="v" viewBox="0 0 1060 __SH__" width="100%"></svg>
<div class="lg">Batch product:__LEG__ <span style="background:#c98a00"></span>waiting <span style="background:#00857c"></span>in process</div>
<h2 style="color:#005b96;font-size:16px">Utilisation per stage (steady state)</h2><svg id="u" viewBox="0 0 1060 __UH__" width="100%"></svg>
</main><script>
const D=__DATA__;
const NS="http://www.w3.org/2000/svg";const v=document.getElementById("v");
const COL={A:"#005b96",B:"#7a3fb0",C:"#d1495b"};
function el(p,n,a,t){const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);if(t)e.textContent=t;p.appendChild(e);return e}
const n=D.stages.length,cols=5,bw=170,bh=92,gx=22,gy=70,x0=20,y0=30;
const pos=D.stages.map((s,i)=>{const r=Math.floor(i/cols),c=i%cols;return{x:x0+(r%2?cols-1-c:c)*(bw+gx),y:y0+r*(bh+gy)}});
const boxes=[];
D.stages.forEach((s,i)=>{const p=pos[i];
 if(i<n-1){const q=pos[i+1];el(v,"line",{x1:p.x+bw/2,y1:p.y+bh/2,x2:q.x+bw/2,y2:q.y+bh/2,stroke:"#b8c2cf","stroke-width":3,"stroke-dasharray":"6 5"})}});
D.stages.forEach((s,i)=>{const p=pos[i];
 const r=el(v,"rect",{x:p.x,y:p.y,width:bw,height:bh,rx:8,fill:"#f7f9fb",stroke:"#8a94a6","stroke-width":2});
 el(v,"text",{x:p.x+8,y:p.y+16,"font-size":11,"font-weight":600},s.name);
 const q=el(v,"text",{x:p.x+8,y:p.y+bh-8,"font-size":11,fill:"#4a5668"},"");boxes.push({r,q})});
const dots=D.batches.map(b=>el(v,"circle",{r:6,fill:COL[b.p]||"#555",stroke:"#fff","stroke-width":1.5,visibility:"hidden"}));
function state(b,t){ // returns [stage,phase,slot]
 const tr=b.t; if(t<b.r)return null;
 for(let j=0;j<tr.length;j++){const[k,a,s,e]=tr[j];
  if(t<a)return[k>0?k-1:0,"gap"]; // between stages (instant)
  if(t<s)return[k,"wait"]; if(t<e)return[k,"proc"];}
 return null}
let T=0,play=true;const m=location.hash.match(/t=(\d+)/);if(m){T=+m[1];play=false}
function draw(){const cnt=D.stages.map(_=>({w:0,p:0}));let fin=0;
 D.batches.forEach((b,i)=>{const d=dots[i];const last=b.t[b.t.length-1];
  if(T>=last[3]){d.setAttribute("visibility","hidden");if(T>=b.d)fin++;return}
  const st=state(b,T);if(!st){d.setAttribute("visibility","hidden");return}
  const[k,ph]=st;const c=cnt[k];const slot=(ph==="wait"?c.w++:c.p++);
  const p=pos[k];const col=slot%8,row=Math.floor(slot/8);
  const x=p.x+14+col*18+(ph==="proc"?0:0),y=ph==="proc"?p.y+34+row*14:p.y+60+row*14;
  d.setAttribute("cx",x);d.setAttribute("cy",Math.min(y,p.y+bh+30));d.setAttribute("visibility","visible");
  d.setAttribute("stroke",ph==="wait"?"#c98a00":"#00857c");d.setAttribute("stroke-width",ph==="wait"?3:3)});
 D.stages.forEach((s,i)=>{boxes[i].q.textContent=s.kind==="wait"?"in transit/quarantine: "+(cnt[i].w+cnt[i].p):"waiting "+cnt[i].w+" | in process "+cnt[i].p+" / "+s.servers;
  boxes[i].r.setAttribute("fill",cnt[i].w>=3?"#fff0cf":"#f7f9fb")});
 const day=Math.floor(T/24),h=Math.floor(T%24);document.getElementById("clock").textContent=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][day%7]+" "+String(h).padStart(2,"0")+":00 (day "+(day+1)+")";
 document.getElementById("fin").textContent=fin;document.getElementById("sl").value=T}
let last=performance.now();
function loop(now){const dt=(now-last)/1000;last=now;if(play){T+=dt*+document.getElementById("sp").value;if(T>D.h){T=0}}draw();requestAnimationFrame(loop)}
if(!play)document.getElementById("pp").textContent="Play";document.getElementById("pp").onclick=function(){play=!play;this.textContent=play?"Pause":"Play"};
document.getElementById("sl").oninput=function(){T=+this.value;draw()};
const u=document.getElementById("u");D.util.forEach((x,i)=>{const y=8+i*28;
 el(u,"text",{x:230,y:y+15,"font-size":12,"text-anchor":"end"},x.n);let cx=240;
 [["process","#00857c"],["setup","#c98a00"],["repair","#b3261e"]].forEach(([k,c])=>{const w=780*x[k];if(w>0){el(u,"rect",{x:cx,y:y,width:w,height:20,fill:c}).appendChild(document.createElementNS(NS,"title")).textContent=x.n+" "+k+": "+(100*x[k]).toFixed(1)+"%";cx+=w}});
 el(u,"text",{x:cx+6,y:y+15,"font-size":11},(100*(x.process+x.setup+x.repair)).toFixed(0)+"%")});
el(u,"text",{x:240,y:8+D.util.length*28+14,"font-size":11,fill:"#4a5668"},"green = processing, amber = changeover/cleaning, red = repair");
requestAnimationFrame(loop);
</script></body></html>"""


def render(plant: Plant, res: Result, title: str = "Pharma plant simulation (fictitious)", max_batches: int = 70) -> str:
    stages = [{"name": s.name, "kind": s.kind, "servers": s.servers} for s in plant.stages]
    fin = [b for b in res.batches if b.done is not None and b.released >= 0]
    start_t = plant.warmup
    bs = [b for b in fin if b.released >= start_t][:max_batches]
    t0 = bs[0].released if bs else 0
    batches = [{"p": b.product, "r": round(b.released - t0, 2), "d": round(b.done - t0, 2),
                "t": [[k, round(a - t0, 2), round(s - t0, 2), round(e - t0, 2)] for k, a, s, e in b.trace]} for b in bs]
    h = int(max(b["d"] for b in batches)) + 1
    util = []
    for st in res.stats:
        u = res.utilisation(st)
        util.append({"n": st.name, **{k: round(v, 4) for k, v in u.items()}})
    nrows = (len(stages) + 4) // 5
    leg = "".join(f'<span style="background:{c}"></span>{p}' for p, c in zip(plant.products, ["#005b96", "#7a3fb0", "#d1495b"]))
    data = json.dumps({"stages": stages, "batches": batches, "h": h, "util": util})
    return (PAGE.replace("__TITLE__", html.escape(title)).replace("__DATA__", data).replace("__H__", str(h))
            .replace("__TP__", f"{res.throughput_per_week:.1f}").replace("__LT__", f"{res.mean_lead_time_days:.1f}")
            .replace("__BN__", html.escape(res.bottleneck)).replace("__LEG__", leg)
            .replace("__SH__", str(30 + nrows * 162)).replace("__UH__", str(len(util) * 28 + 30)))
