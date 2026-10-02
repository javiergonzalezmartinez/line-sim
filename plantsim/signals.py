"""Machine telemetry from the simulation, as sensor events (state-change sampling).

Per equipment (a process or move stage) the sim drives the MACHINERY_ITEM_STATE and
MACHINERY_OPERATION_MODE machines from fsm.py. A stage with several servers is one equipment here: it is
EXECUTING while at least one server works. Signals produced (ids from spec/signals.json): SIG-0001 item_state,
SIG-0002 operation_mode, SIG-0003 cycle_counter, SIG-0004 operating_time (s), SIG-0010 job_id (single-server
stages only). Signals the sim has no basis for (power, safety, fault, alarm, speed, process values) are NOT
produced. Signal quality is GOOD for every simulated value. Synthetic data, not a real historian or OPC UA.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import List

from .events import NS, _hash, _iso
from .fsm import Machine, state_hash

SIGNALS = {"item_state": "SIG-0001", "operation_mode": "SIG-0002", "cycle_counter": "SIG-0003", "operating_time": "SIG-0004", "job_id": "SIG-0010"}


def _merge(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1] + 1e-12:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def telemetry(plant, result, schema_version: str = "2.0") -> List[dict]:
    out: List[dict] = []
    for k, s in enumerate(plant.stages):
        if s.kind not in ("process", "move"):
            continue
        eq = f"EQ-STAGE-{k + 1:02d}"
        raw = []          # (start, end, lot)
        for b in result.batches:
            for rec in b.trace:
                if rec[0] == k and rec[3] > rec[2]:
                    raw.append((rec[2], rec[3], f"LOT-{b.id + 1:06d}"))
        busy = _merge([(a, b) for a, b, _ in raw])
        item = Machine("MACHINERY_ITEM_STATE", "NOT_AVAILABLE", eq)
        mode = Machine("MACHINERY_OPERATION_MODE", "NONE", eq)
        seq = [0]
        last = [None]

        def emit(t, sig, value, mach=None, tr=None):
            seq[0] += 1
            el = {"measurement_type": sig, "signal_id": SIGNALS[sig], "signal_quality": "GOOD", "device_id": eq,
                  "source_timestamp": _iso(t), "server_timestamp": _iso(t), "time": _iso(t)}
            if isinstance(value, str):
                el["string_value"] = value
            else:
                el["value"] = value
                el["uom"] = "s" if sig == "operating_time" else "count"
            e = {"event_id": str(uuid.uuid5(NS, f"{plant.seed}/tele/{k}/{seq[0]}")), "event_class": "SENSOR", "event_type": "signal.changed",
                 "action": "OBSERVE", "event_time": _iso(t), "record_time": _iso(t), "event_time_zone_offset": "+00:00",
                 "correlation_id": f"CORR-{eq}", "causation_id": last[0], "sequence_no": seq[0] - 1, "object_ids": [eq], "equipment_id": eq,
                 "business_step": s.name, "business_location": s.loc, "result": "OK", "sensor_elements": [el], "schema_version": schema_version}
            if tr:
                e["state_before_hash"], e["state_after_hash"] = state_hash(tr[0], tr[1]), state_hash(tr[0], tr[2])
                e["reason_code"] = f"{tr[0]}:{tr[1]}>{tr[2]}"
            e["payload_hash"] = _hash(e)
            last[0] = e["event_id"]
            out.append(e)

        b0, a0 = item.fire("Commission")
        emit(0.0, "item_state", a0, tr=("MACHINERY_ITEM_STATE", b0, a0))
        emit(0.0, "operation_mode", "NONE")
        emit(0.0, "cycle_counter", 0)
        emit(0.0, "operating_time", 0)
        cycles, opt, ends = 0, 0.0, sorted(raw, key=lambda x: x[1])
        pts = []
        for a, b in busy:
            pts.append((a, "start"))
            pts.append((b, "stop"))
        # completed cycles are counted at each lot end; state changes at merged-interval edges
        marks = sorted([(a, 0, "start", None) for a, b in busy] + [(b, 2, "stop", None) for a, b in busy] + [(e, 1, "cycle", lot) for _, e, lot in ends])
        run_start = None
        for t, _, kind, lot in marks:
            if kind == "start":
                b_, a_ = item.fire("StartExecution")
                emit(t, "item_state", a_, tr=("MACHINERY_ITEM_STATE", b_, a_))
                b_, a_ = mode.fire("EnterProcessing")
                emit(t, "operation_mode", a_, tr=("MACHINERY_OPERATION_MODE", b_, a_))
                run_start = t
                if s.servers == 1:
                    emit(t, "job_id", next(l for st, en, l in raw if abs(st - t) < 1e-9))
            elif kind == "cycle":
                cycles += 1
                emit(t, "cycle_counter", cycles)
            else:
                b_, a_ = item.fire("StopExecution")
                emit(t, "item_state", a_, tr=("MACHINERY_ITEM_STATE", b_, a_))
                b_, a_ = mode.fire("ProcessComplete")
                emit(t, "operation_mode", a_, tr=("MACHINERY_OPERATION_MODE", b_, a_))
                opt += t - run_start
                emit(t, "operating_time", round(opt * 3600.0, 3))
    out.sort(key=lambda e: (e["event_time"], e["equipment_id"], e["sequence_no"]))
    return out


def render_timeline(tele: List[dict], days: float = 5.0, title: str = "Equipment state over time (synthetic)") -> str:
    """SVG timeline: one row per equipment, bars where item_state is EXECUTING, from the first `days` days."""
    from html import escape
    from datetime import datetime
    t0 = datetime.fromisoformat(_iso(0.0).replace("Z", "+00:00"))
    rows = {}
    for e in tele:
        el = e["sensor_elements"][0]
        if el["measurement_type"] != "item_state":
            continue
        h = (datetime.fromisoformat(el["time"].replace("Z", "+00:00")) - t0).total_seconds() / 3600.0
        rows.setdefault((e["equipment_id"], e["business_step"]), []).append((h, el["string_value"]))
    W, L, rh, T = 1100, 330, 22, 40
    H = T + rh * len(rows) + 60
    sx = (W - L - 20) / (days * 24.0)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" font-family="system-ui,sans-serif" font-size="11">']
    for d in range(int(days) + 1):
        x = L + d * 24 * sx
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{T - 6}" y2="{H - 30}" stroke="#dde3ea"/><text x="{x:.1f}" y="{T - 12}" text-anchor="middle" fill="#556">day {d}</text>')
    for i, ((eq, step), ev) in enumerate(sorted(rows.items())):
        y = T + i * rh
        out.append(f'<text x="{L - 8}" y="{y + 14}" text-anchor="end" fill="#223">{escape(eq)} {escape((step or "")[:34])}</text>')
        run = None
        for h, st in ev:
            if st == "EXECUTING":
                run = h
            elif run is not None and st != "EXECUTING":
                a, b = max(run, 0) * sx, min(h, days * 24) * sx
                if run < days * 24 and b > a:
                    out.append(f'<rect x="{L + a:.1f}" y="{y + 3}" width="{max(b - a, 0.8):.1f}" height="{rh - 7}" fill="#00857c"/>')
                run = None
    out.append(f'<text x="{L}" y="{H - 14}" fill="#556">Green = EXECUTING (item_state from the simulation). Illustrative, synthetic.</text></svg>')
    return f'<!doctype html><html><head><meta charset="utf-8"><title>{escape(title)}</title></head><body style="margin:16px;font-family:system-ui"><h2>{escape(title)}</h2>{"".join(out)}</body></html>'
