"""Transport tasks (forklift / AGV) as TRANSPORT_TASK state-machine events, plus fleet KPIs.

One task per move stage of every lot. The task is requested when the plant model starts the move (any wait before that is already in the plant model) and a vehicle
of the fleet takes it when one is free (FIFO). The vehicle carries the load for exactly the modelled move time
(start..end of that stage), so no travel time is invented. This is an OVERLAY: it measures what the given fleet
would do with the moves the plant model already simulated; a late vehicle does NOT delay the plant model.
Parameters (cfg key `transport`, all optional, none has a spec value, so defaults invent nothing):
  fleet_size     number of vehicles; None = unlimited (no queueing, utilisation not computed)
  accept_h       time from assignment to accept (default 0)
  route_block_p, route_block_h   probability a trip hits a blocked route, and how long it lasts (default 0)
  due_h          task due this long after the request; enables KPI-014 TaskOnTime (default None = not computed)
Not modelled: move.timeout / retry (ERROR state), cancelled tasks, vehicle travel to the pick-up point, charging, routes.
"""
from __future__ import annotations

import random
import uuid
from typing import Dict, List, Optional

from .events import NS, _hash, _iso
from .fsm import Machine, state_hash

KEYS = ("fleet_size", "accept_h", "route_block_p", "route_block_h", "due_h")


def transport(plant, result, cfg: Optional[Dict] = None, schema_version: str = "2.0") -> List[dict]:
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    unknown = set(cfg) - set(KEYS)
    if unknown:
        raise ValueError(f"unknown transport parameters: {sorted(unknown)}")
    fleet, acc = cfg.get("fleet_size"), cfg.get("accept_h", 0.0)
    bp, bh = cfg.get("route_block_p", 0.0), cfg.get("route_block_h", 0.0)
    if fleet is not None and not (isinstance(fleet, int) and fleet >= 1):
        raise ValueError("fleet_size must be an integer >= 1 or null")
    if acc < 0 or bh < 0 or not 0 <= bp <= 1:
        raise ValueError("accept_h, route_block_h >= 0 and route_block_p in [0,1]")
    rng = random.Random(plant.seed + 2)
    free = [0.0] * (fleet or 0)
    tasks = []
    for b in result.batches:
        for rec in b.trace:
            if plant.stages[rec[0]].kind == "move":
                tasks.append((rec[2], b, rec))
    tasks.sort(key=lambda x: (x[0], x[1].id))
    out: List[dict] = []
    seq = [0]
    for req, b, rec in tasks:
        k = rec[0]
        lot = f"LOT-{b.id + 1:06d}"
        tid = f"TT-{b.id + 1:06d}-{k + 1:02d}"
        if fleet:
            v = min(range(fleet), key=lambda i: (free[i], i))
            assign = max(req, free[v])
            veh = f"VEH-{v + 1:02d}"
        else:
            assign, veh = req, "VEH-UNLIM"
        pick = max(rec[2], assign + acc)
        blocked = bp and rng.random() < bp
        drop = pick + (rec[3] - rec[2]) + (bh if blocked else 0.0)
        if fleet:
            free[v] = drop
        m = Machine("TRANSPORT_TASK", "CREATED", tid)
        last = [None]

        def emit(t, ev, extra=None):
            bf, af = m.fire(ev)
            seq[0] += 1
            e = {"event_id": str(uuid.uuid5(NS, f"{plant.seed}/tt/{seq[0]}")), "event_class": "OBJECT", "event_type": ev, "action": "OBSERVE",
                 "event_time": _iso(t), "record_time": _iso(t), "event_time_zone_offset": "+00:00", "correlation_id": f"CORR-{b.id + 1:06d}",
                 "causation_id": last[0], "sequence_no": None, "object_ids": [tid], "lot_id": lot, "business_step": plant.stages[k].name,
                 "equipment_id": veh, "result": "OK", "reason_code": f"TRANSPORT_TASK:{bf}>{af}", "schema_version": schema_version,
                 "state_before_hash": state_hash("TRANSPORT_TASK", bf), "state_after_hash": state_hash("TRANSPORT_TASK", af), "_o": seq[0]}
            if extra:
                e.update(extra)
            e["payload_hash"] = _hash(e)
            last[0] = e["event_id"]
            out.append(e)

        if assign > req + 1e-9:
            emit(req, "move.queued")
        emit(assign, "move.assigned")
        emit(assign + acc, "move.accepted")
        emit(pick, "move.picked")
        emit(pick, "move.departed")
        if blocked:
            emit(pick + (rec[3] - rec[2]) / 2, "move.route_blocked")
            emit(pick + (rec[3] - rec[2]) / 2 + bh, "route.cleared")
        emit(drop, "move.dropped")
        emit(drop, "move.completed", {"payload": {"requested_at": _iso(req), "due_h": cfg.get("due_h")}})
    out.sort(key=lambda e: (e["event_time"], e["object_ids"][0], e["_o"]))
    for e in out:
        del e["_o"]
    return out


def transport_kpis(evs: List[dict], cfg: Optional[Dict] = None, horizon_h: Optional[float] = None) -> dict:
    """KPI-004 queue wait (request to assignment), KPI-006 fleet utilisation (carrying time / (fleet x horizon), only with a fleet),
    KPI-014 TaskOnTime (only with due_h). Everything else is reported as None = not computed."""
    from .kpis import hours
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    req, asg, pick, drop = {}, {}, {}, {}
    for e in evs:
        o, t = e["object_ids"][0], hours(e["event_time"])
        ty = e["event_type"]
        if ty == "move.completed":
            req[o] = hours(e["payload"]["requested_at"])
        elif ty == "move.assigned":
            asg[o] = t
        elif ty == "move.picked":
            pick[o] = t
        elif ty == "move.dropped":
            drop[o] = t
    waits = sorted(asg[o] - req[o] for o in req if o in asg)
    n = len(req)
    fleet, due = cfg.get("fleet_size"), cfg.get("due_h")
    hz = horizon_h or (max(drop.values()) if drop else 0)
    carry = sum(min(drop[o], hz) - min(pick[o], hz) for o in drop if o in pick)
    return {"tasks": n, "KPI-004 QueueWait mean (h)": round(sum(waits) / n, 4) if n else 0.0,
            "KPI-004 QueueWait p95 (h)": round(waits[int(0.95 * (n - 1))], 4) if n else 0.0,
            "KPI-006 FleetUtilization": round(carry / (fleet * hz), 4) if fleet and hz else None,
            "KPI-014 TaskOnTime": round(sum(1 for o in req if o in drop and drop[o] <= req[o] + due + 1e-9) / n, 4) if due is not None and n else None}


def render_html(plant, result, cfg: Optional[Dict] = None, title: str = "Forklift / AGV fleet (synthetic)") -> str:
    import html
    from .kpis import hours
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    fs = cfg.get("fleet_size") or 1
    rows = ""
    for f in sorted({1, 2, 3, 4, fs}):
        c = dict(cfg, fleet_size=f)
        k = transport_kpis(transport(plant, result, c), c, plant.horizon)
        sel = ' style="background:#e6f4f2"' if f == fs else ""
        rows += (f"<tr{sel}><td>{f}</td><td>{k['KPI-004 QueueWait mean (h)']:.3f}</td><td>{k['KPI-004 QueueWait p95 (h)']:.3f}</td>"
                 f"<td>{k['KPI-006 FleetUtilization']:.1%}</td><td>{'' if k['KPI-014 TaskOnTime'] is None else format(k['KPI-014 TaskOnTime'], '.1%')}</td></tr>")
    ev = transport(plant, result, dict(cfg, fleet_size=fs))
    pk = {e["object_ids"][0]: hours(e["event_time"]) for e in ev if e["event_type"] == "move.picked"}
    dr = {e["object_ids"][0]: (hours(e["event_time"]), e["equipment_id"]) for e in ev if e["event_type"] == "move.dropped"}
    t1 = min(72.0, max(t for t, _ in dr.values())) if dr else 72.0
    W, L, RH = 1000, 60, 26
    X = lambda t: L + (W - L - 10) * t / t1
    bars = ""
    for o, (d, v) in dr.items():
        if o in pk and pk[o] < t1:
            i = int(v.split("-")[1]) - 1
            bars += f'<rect x="{X(pk[o]):.1f}" y="{12 + i * RH}" width="{max(1.5, X(min(d, t1)) - X(pk[o])):.1f}" height="{RH - 8}" fill="#00857c"/>'
    H = 20 + fs * RH + 22
    lab = "".join(f'<text x=4 y={12 + i * RH + 12} font-size=11>VEH-{i + 1:02d}</text>' for i in range(fs))
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{title}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>{title}</h2><div class=n>Synthetic. Fleet size, accept time and due time are illustrative placeholders (no spec values). Vehicles carry the load for the modelled move time; no travel time is invented. Overlay: a late vehicle does not delay the plant model.</div>
<h3>Fleet size sweep (selected: {fs})</h3><table><tr><th>Vehicles</th><th>Queue wait mean (h)</th><th>Queue wait p95 (h)</th><th>Utilisation (KPI-006)</th><th>On time (KPI-014)</th></tr>{rows}</table>
<h3>Vehicle occupation, first {t1:.0f} h (fleet {fs})</h3><svg width={W} height={H} style="background:#fafbfc;border:1px solid #dde3ea">{lab}{bars}<line x1={L} y1={H - 18} x2={W - 10} y2={H - 18} stroke="#889"/><text x={L} y={H - 4} font-size=11>0 h</text><text x={W - 50} y={H - 4} font-size=11>{t1:.0f} h</text></svg></body></html>"""
