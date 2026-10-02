"""KPIs computed from the event log (not from the simulator's own counters), ids and names from spec/kpis.json.

Computed: KPI-001 Throughput, KPI-002 LeadTime, KPI-003 CycleTime, KPI-004 QueueWait, KPI-005 WIP,
KPI-006 ResourceUtilization (time executing, from phase events), KPI-018 SensorGoodQuality (always 100%
here by construction), KPI-026 ScrapRate (rejected lots / closed lots, lot basis).
Not computed, because the event log has no basis: BlockingTime, StarvationTime, SetupFraction (changeover is
before the traced start), DowntimeFraction, FirstPassYield, rework, inventory, messages and the GxP ones.
Window = plant.warmup .. plant.horizon (hours), like the simulator.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from .events import START, _iso

_T0 = datetime.fromisoformat(_iso(0.0).replace("Z", "+00:00"))


def hours(iso: str) -> float:
    return (datetime.fromisoformat(iso.replace("Z", "+00:00")) - _T0).total_seconds() / 3600.0


def kpis(plant, evs: List[dict], tele: List[dict] = ()) -> dict:
    w0, w1 = plant.warmup, plant.horizon
    win = w1 - w0
    rel, close, steps = {}, {}, defaultdict(dict)       # lot -> time ; (lot, stage) -> times
    for e in evs:
        lot, t, ty = e["lot_id"], hours(e["event_time"]), e["event_type"]
        if ty == "lot.released":
            rel[lot] = t
        elif ty in ("lot.dispatched", "lot.rejected"):
            close[lot] = (t, ty)
        else:
            k = plant.stages.index(next(s for s in plant.stages if s.name == e["business_step"]))
            st = steps[(lot, k)]
            st[{"queue.entered": "arrive", "phase.started": "start", "phase.completed": "end", "phase.aborted": "end"}.get(ty, ty)] = t
    done = {l: v for l, v in close.items() if w0 <= v[0] <= w1}
    good = [l for l, v in done.items() if v[1] == "lot.dispatched"]
    out: dict = {"window_h": win}
    out["KPI-001 Throughput (lots/week)"] = len(good) / (win / 168.0)
    lts = [done[l][0] - rel[l] for l in good]
    out["KPI-002 LeadTime (days, mean)"] = sum(lts) / len(lts) / 24.0 if lts else 0.0
    out["KPI-026 ScrapRate (lot basis)"] = (len(done) - len(good)) / len(done) if done else 0.0
    # per stage
    per = []
    for k, s in enumerate(plant.stages):
        rows = [v for (l, kk), v in steps.items() if kk == k and "end" in v]
        inwin = [v for v in rows if w0 <= v["arrive"] < w1]
        qw = [v["start"] - v["arrive"] for v in inwin]
        ct = [v["end"] - v["start"] for v in inwin]
        exe = sum(max(0.0, min(v["end"], w1) - max(v["start"], w0)) for v in rows) if s.kind in ("process", "move") else None
        per.append({"stage": s.name, "kind": s.kind, "servers": s.servers, "lots": len(inwin),
                    "queue_wait_h": sum(qw) / len(qw) if qw else 0.0, "cycle_time_h": sum(ct) / len(ct) if ct else 0.0,
                    "utilisation": exe / (s.servers * win) if exe is not None else None})
    out["stages"] = per
    # WIP: lots released and not yet closed, time average over the window
    pts = [(t, 1) for t in rel.values()] + [(v[0], -1) for v in close.values()]
    pts.sort()
    area, wip, prev = 0.0, 0, w0
    for t, d in pts:
        a, b = max(prev, w0), min(t, w1)
        if b > a:
            area += wip * (b - a)
        wip += d
        prev = max(prev, t)
    if prev < w1:
        area += wip * (w1 - max(prev, w0))
    out["KPI-005 WIP (lots, time average)"] = area / win
    q = [e["sensor_elements"][0]["signal_quality"] for e in tele]
    out["KPI-018 SensorGoodQuality"] = (sum(1 for x in q if x == "GOOD") / len(q)) if q else None
    return out


def render_html(k: dict, title: str = "KPIs from the event log (synthetic)") -> str:
    from html import escape
    rows = "".join(f"<tr><td>{escape(s['stage'])}</td><td>{s['lots']}</td><td>{s['queue_wait_h']:.1f}</td><td>{s['cycle_time_h']:.1f}</td>"
                   f"<td>{'' if s['utilisation'] is None else format(s['utilisation'], '.0%')}</td></tr>" for s in k["stages"] if s["kind"] != "move")
    head = "".join(f"<div class=c><small>{escape(n)}</small><b>{v:.2f}</b></div>" for n, v in k.items() if n.startswith("KPI") and v is not None and "Scrap" not in n and "Sensor" not in n)
    head += f"<div class=c><small>KPI-026 ScrapRate (lot basis)</small><b>{k['KPI-026 ScrapRate (lot basis)']:.1%}</b></div>"
    return ('<!doctype html><html><head><meta charset="utf-8"><title>KPIs</title><style>body{font:13px system-ui,sans-serif;margin:16px;color:#111}.g{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}'
            '.c{border:1px solid #dde3ea;border-top:3px solid #00857c;border-radius:8px;padding:8px 10px}.c small{display:block;color:#556}.c b{font-size:20px}table{border-collapse:collapse;width:100%;margin-top:14px}'
            'th{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}td{padding:4px 8px;border-bottom:1px solid #dde3ea}.n{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}</style></head><body>'
            f'<h2>{escape(title)}</h2><div class="n">Illustrative. Computed from events only; blocking, starvation, setup, yield are not derivable from this log. Synthetic data.</div><div class="g">{head}</div>'
            f'<table><tr><th>Stage</th><th>Lots in window</th><th>Queue wait (h)</th><th>Cycle time (h)</th><th>Utilisation (executing)</th></tr>{rows}</table></body></html>')
