// Browser/Node port of plantsim/model.py. Same semantics; own seeded RNG (results match Python exactly only when cv=0, no breakdowns, no retests).
function makeRng(seed){let a=(seed>>>0)||1;const u=()=>{a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296};
  const norm=()=>{let x=0,y=0;while(x===0)x=u();y=u();return Math.sqrt(-2*Math.log(x))*Math.cos(2*Math.PI*y)};
  const gam=k=>{if(k<1){return gam(k+1)*Math.pow(u()||1e-12,1/k)}const d=k-1/3,c=1/Math.sqrt(9*d);for(;;){let x,v;do{x=norm();v=1+c*x}while(v<=0);v=v*v*v;const r=u();if(r<1-0.0331*x*x*x*x||Math.log(r)<0.5*x*x+d*(1-v+Math.log(v)))return d*v}};
  return{u,gamma:(mean,cv)=>{if(mean<=0)return 0;if(cv<=0)return mean;const k=1/(cv*cv);return gam(k)*mean/k}}}
function nextOpen(t,s){if(!s.window&&(s.workdays==null||s.workdays>=7))return t;const o=s.window?s.window[0]:0,c=s.window?s.window[1]:24,wd=s.workdays==null?7:s.workdays;
  for(let i=0;i<14;i++){const day=Math.floor(t/24),h=t-day*24;if(day%7<wd){if(h<o)return day*24+o;if(h<c)return t}t=(day+1)*24}return t}
function nextWave(t,w){const day=Math.floor(t/24),ws=[...w].sort((a,b)=>a-b);for(let d=day;d<day+8;d++)for(const x of ws)if(d*24+x>=t)return d*24+x;return t}
function simulate(P){
  const rng=makeRng(P.seed||1),S=P.stages,n=S.length,keys=S.map((s,k)=>s.pool||String(k));
  const free={},last={};keys.forEach((key,k)=>{if(!free[key]){free[key]=Array(S[k].servers||1).fill(0);last[key]=Array(S[k].servers||1).fill(null)}});
  const st=S.map(s=>({busy:0,setup:0,repair:0,wait:0,n:0}));const w0=P.warmup,w1=P.horizon;
  const batches=[];const heap=[];
  const less=(a,b)=>a[0]<b[0]||(a[0]===b[0]&&(a[1]<b[1]||(a[1]===b[1]&&a[2]<b[2])));
  const push=x=>{heap.push(x);let i=heap.length-1;while(i>0){const p=(i-1)>>1;if(less(heap[i],heap[p])){[heap[i],heap[p]]=[heap[p],heap[i]];i=p}else break}};
  const pop=()=>{const top=heap[0],l=heap.pop();if(heap.length){heap[0]=l;let i=0;for(;;){let a=2*i+1,b=a+1,m=i;if(a<heap.length&&less(heap[a],heap[m]))m=a;if(b<heap.length&&less(heap[b],heap[m]))m=b;if(m===i)break;[heap[i],heap[m]]=[heap[m],heap[i]];i=m}}return top};
  let t=0,id=0;while(t<P.horizon){batches.push({id,p:P.products[id%P.products.length],r:t,d:null,t:[]});push([t,id,0]);id++;t+=P.release_every}
  const credit=(kind,k,a,b)=>{a=Math.max(a,w0);b=Math.min(b,w1);if(b>a)st[k][kind]+=b-a};
  while(heap.length){const[at,i,k]=pop();const b=batches[i],s=S[k];let end,wait,ps;
    if(s.kind==="wave"){end=nextWave(at,s.waves);wait=end-at;ps=at}
    else if(s.kind==="wait"){end=at+rng.gamma(s.hours,s.cv==null?0.1:s.cv);wait=0;ps=at}
    else{const key=keys[k],f=free[key];let j=0;for(let x=1;x<f.length;x++)if(f[x]<f[j])j=x;
      const start=nextOpen(Math.max(at,f[j]),s);wait=start-at;let cur=start;
      if(last[key][j]!==null&&last[key][j]!==b.p&&(s.changeover||0)>0){credit("setup",k,cur,cur+s.changeover);cur+=s.changeover}
      last[key][j]=b.p;ps=cur;const cv=s.cv==null?0.1:s.cv;let dur=rng.gamma(s.hours,cv);
      for(;;){credit("busy",k,cur,cur+dur);cur+=dur;
        if(s.breakdown_p&&rng.u()<s.breakdown_p){const r=rng.gamma(s.repair,0.5);credit("repair",k,cur,cur+r);cur+=r}
        if(s.retest_p&&rng.u()<s.retest_p){dur=rng.gamma(s.hours,cv);continue}break}
      end=cur;f[j]=end}
    b.t.push([k,at,ps,end]);if(at>=w0&&at<w1){st[k].wait+=wait;st[k].n++}
    if(k+1<n)push([end,i,k+1]);else b.d=end}
  const win=w1-w0,done=batches.filter(b=>b.d!==null&&b.d>=w0&&b.d<=w1);
  const util=S.map((s,k)=>{const cap=(s.servers||1)*win;return{process:st[k].busy/cap,setup:st[k].setup/cap,repair:st[k].repair/cap}});
  const pools={};S.forEach((s,k)=>{if(s.pool){pools[s.pool]=pools[s.pool]||{n:s.servers,busy:0};pools[s.pool].busy+=st[k].busy+st[k].repair}});
  for(const p in pools)pools[p]=pools[p].busy/(pools[p].n*win);
  let bn=-1,bname="";S.forEach((s,k)=>{if(s.kind==="move")return;const u=util[k],tot=u.process+u.setup+u.repair;if(tot>bn){bn=tot;bname=s.name}});
  return{batches,stats:st,util,pools,throughput:done.length/(win/168),leadDays:done.length?done.reduce((a,b)=>a+b.d-b.r,0)/done.length/24:0,bottleneck:bname,window:win}}
if(typeof module!=="undefined")module.exports={simulate,makeRng,nextOpen,nextWave};

// ---- signal / transaction layer: derives PLC, WMS, ERP and QA events from the simulated trace -------------
// Texts come from the stage "events" in the config. "SAP-style" events use only generic, publicly documented concepts
// (see README sources); document numbers are simulated sequence numbers, not real SAP documents.
function lotLabel(id){return "LOT-"+String(id+1).padStart(4,"0")}
function lotWeight(id){let x=(id+1)*2654435761>>>0;x^=x>>>13;x=Math.imul(x,1274126177)>>>0;return 900+(x%2000)/10}   // 900.0 to 1099.9 kg, simulated
function buildEvents(P,R,t0,tEnd){
  const ev=[];
  for(const b of R.batches){if(b.r<t0||b.d==null||b.r>=tEnd)continue;
    for(const[k,a,s,e]of b.t){const st=P.stages[k];for(const x of(st.events||[])){
      let t=x.at==="arrive"?a:x.at==="start"?s:x.at==="end"?e:s+(e-s)*x.at;
      ev.push({t:t-t0,seq:ev.length,lot:lotLabel(b.id),p:b.p,kind:x.kind,src:x.src,stage:st.name,text:x.text,w:lotWeight(b.id)})}}}
  ev.sort((u,v)=>u.t-v.t||u.seq-v.seq);let doc=4900000000;
  ev.forEach(e=>{if(e.text.includes("{doc}"))e.doc=String(++doc);
    e.detail=e.text.replace("{lot}",e.lot).replace("{p}","product "+e.p).replace("{w}",e.w.toFixed(1)).replace("{doc}",e.doc||"");delete e.text;delete e.seq});
  return ev}
function eventsCsv(ev,t0){const q=s=>'"'+String(s).replace(/"/g,'""')+'"';
  return["hour_from_start,clock,lot,product,kind,source,stage,detail,doc_simulated"].concat(ev.map(e=>[e.t.toFixed(3),q(clockLabel(e.t+t0)),e.lot,e.p,e.kind,q(e.src),q(e.stage),q(e.detail),e.doc||""].join(","))).join("\n")}
function clockLabel(t){const d=Math.floor(t/24),h=t-d*24,hh=Math.floor(h),mm=Math.floor((h-hh)*60);return["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d%7]+" "+String(hh).padStart(2,"0")+":"+String(mm).padStart(2,"0")+" (day "+(d+1)+")"}
if(typeof module!=="undefined")Object.assign(module.exports,{buildEvents,eventsCsv,lotLabel,clockLabel});
