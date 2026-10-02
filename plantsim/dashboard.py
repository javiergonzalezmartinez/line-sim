"""Live dashboard: the animated plant view (view.py) plus a digital-twin panel synchronised to the animation clock.

The panel shows, for the clock time of the animation, the cumulative counts and the latest events of the canonical event
log, the quality status events, the transport tasks, the interface messages and the pallets, all computed in Python from the
same config (same seed, same plant model) and embedded in the page. Config keys `handshake`, `handling`, `transport` and
`quality` hold the (illustrative) parameters. If the user changes the parameter panel of the animation, the animation re-runs
but this panel does not: the page says so. Own code, no network. Synthetic."""
from __future__ import annotations

import json
from bisect import bisect_right

from .events import events
from .handling import handling
from .handshakes import messages
from .kpis import hours
from .model import simulate
from .quality import quality
from .transport import transport
from .view import render as render_view

CATS = [("PLANT", "#005b96"), ("QUALITY", "#c98a00"), ("TRANSPORT", "#00857c"), ("MESSAGE", "#7a3fb0"), ("PALLET", "#3b5bdb")]

PANEL = r"""<h2>Digital twin layer (synchronised with the clock above)</h2>
<div class="note" id="tw_note"><b>Precomputed in Python for the loaded config</b> (same seed and plant model). Events, parameters for failures, vehicles, pallets and quality are <b>illustrative placeholders</b>; the spec leaves them TBD. Synthetic. Counts run from hour 0 and include the warm-up, so they differ from the steady-state cards above.</div>
<div class="cards" id="tw_cards"></div>
<table id="tw_log"><thead><tr><th>Hour</th><th>Stream</th><th>Object</th><th>Event</th><th>State change / reason</th></tr></thead><tbody></tbody></table>
<style>#tw_log{border-collapse:collapse;width:100%;font:12px ui-monospace,monospace;background:#fff}#tw_log th{background:#070f26;color:#fff;text-align:left;padding:4px 6px}#tw_log td{padding:3px 6px;border-top:1px solid #e3e8ee}</style>
"""

SCRIPT = r"""
const TW=__TW__;
function TWSTALE(){const n=document.getElementById("tw_note");if(n&&!n.dataset.s){n.dataset.s=1;n.style.borderColor="#b3261e";n.insertAdjacentHTML("afterbegin","<b style='color:#b3261e'>Parameters changed: the animation re-ran, this panel still shows the loaded config. Reload to reset.</b> ")}}
function twCount(a,t){let lo=0,hi=a.length;while(lo<hi){const m=(lo+hi)>>1;if(a[m]<=t)lo=m+1;else hi=m}return lo}
function twDraw(){const t=T+t0,S=TW.series,c=k=>twCount(S[k],t);
 const hold=c("hold_on")-c("hold_off"),pq=c("pal_built")-c("pal_rel"),
 cards=[["Canonical events so far",twCount(TW.all,t)],["Lots dispatched",c("disp")],["Lots rejected",c("rej")],["Quality holds active",hold],["Transport tasks done",c("tt")],["Messages reconciled",c("msg_ok")],["Message retries",c("msg_retry")],["Pallets in quarantine",pq],["Pallets shipped",c("pal_ship")]];
 document.getElementById("tw_cards").innerHTML=cards.map(x=>'<div class="card"><small>'+x[0]+'</small><b>'+x[1]+'</b></div>').join("");
 let lo=twCount(TW.st,t);const tb=document.querySelector("#tw_log tbody");let h="";
 for(let i=lo-1;i>=Math.max(0,lo-12);i--){const e=TW.s[i],cat=TW.cats[e[1]];h+='<tr><td>'+e[0].toFixed(2)+'</td><td><span class="chip" style="background:'+cat[1]+'">'+cat[0]+'</span></td><td>'+e[2]+'</td><td>'+e[3]+'</td><td>'+e[4]+'</td></tr>'}
 tb.innerHTML=h}
"""


def build(plant, cfg: dict, title: str = "Digital twin dashboard (fictitious pharma plant)") -> str:
    r = simulate(plant)
    cj = lambda k: cfg.get(k)
    plant_ev = events(plant, r)
    q_ev = quality(plant, r, cj("quality"))
    t_ev = transport(plant, r, cj("transport"))
    m_ev = messages(plant, r, cj("handshake"))
    h_ev = [e for e in handling(plant, r, cj("handling")) if e["object_ids"][0].startswith("PAL-")]
    stream = []

    def add(cat, evs, keep=lambda e: True):
        for e in evs:
            if keep(e):
                rc = e.get("reason_code") or ""
                stream.append([round(hours(e["event_time"]), 3), cat, e["object_ids"][0], e["event_type"], rc.split(" ")[-1] if cat != 0 else rc.split(":", 1)[-1] if rc else ""])
    add(0, plant_ev, lambda e: e["event_type"] in ("lot.released", "lot.dispatched", "lot.rejected", "phase.completed"))
    add(1, q_ev)
    add(2, t_ev, lambda e: e["event_type"] in ("move.assigned", "move.picked", "move.route_blocked", "move.completed"))
    add(3, m_ev, lambda e: e["event_type"] != "message.sent")
    add(4, h_ev)
    stream.sort(key=lambda e: e[0])
    ts = lambda evs, ty: sorted(hours(e["event_time"]) for e in evs if e["event_type"] in ty)
    series = {"disp": ts(plant_ev, ("lot.dispatched",)), "rej": ts(plant_ev, ("lot.rejected",)) + ts(q_ev, ("sample.status_rejected",)),
              "hold_on": ts(q_ev, ("quality.hold_applied",)), "hold_off": ts(q_ev, ("quality.hold_released",)),
              "tt": ts(t_ev, ("move.completed",)), "msg_ok": ts(m_ev, ("message.reconciled",)), "msg_retry": ts(m_ev, ("message.retry",)),
              "pal_built": ts(h_ev, ("pallet.built",)), "pal_rel": ts(h_ev, ("quality.status_changed:RELEASED",)), "pal_ship": ts(h_ev, ("shipment.dispatched",))}
    series["rej"].sort()
    tw = {"all": sorted(hours(e["event_time"]) for e in plant_ev), "series": series, "s": stream, "st": [e[0] for e in stream], "cats": CATS}
    page = render_view(plant, r, title)
    js = SCRIPT.replace("__TW__", json.dumps(tw, separators=(",", ":")))
    page = page.replace('<h2>Signals and transactions (simulated)</h2>', PANEL + '<h2>Signals and transactions (simulated)</h2>', 1)
    page = page.replace("run();requestAnimationFrame(loop)", js + "run();requestAnimationFrame(loop)", 1)
    page = page.replace("draw();requestAnimationFrame(loop)", "draw();twDraw();requestAnimationFrame(loop)", 1)
    page = page.replace("function schedule(){", "function schedule(){TWSTALE();", 1)
    return page
