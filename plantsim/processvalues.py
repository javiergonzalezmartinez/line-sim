"""Analog process values (temperature, pressure, rpm, mass, ...) for the equipment, with report-by-exception sampling.

Spec signals SIG-0013..SIG-0026 are continuous values sampled between 100 ms and 60 s with a configurable deadband. The
simulation has no physics, so these values exist ONLY if the config gives them, per stage and signal (key `process_values`):

  {"<stage name>": {"<signal>": {"idle": 22.0, "run": 60.0, "tau_h": 0.25, "noise_sd": 0.4, "sample_s": 60, "deadband": 1.0}}}

Model (public, textbook): the value follows a first-order response, dx/dt = (setpoint - x) / tau, with setpoint = `run` while
the equipment is EXECUTING (merged busy intervals of the stage) and `idle` otherwise; the exact solution
x(t) = sp + (x0 - sp) exp(-dt/tau) is used between samples. A seeded Gaussian measurement noise (`noise_sd`) is added.
Sampling every `sample_s` seconds; a sample is reported only if |value - last reported value| > deadband (absolute deadband
of the OPC UA DataChangeFilter, OPC 10000-4 section 7.22.2: "Generate a Notification if absolute value of (last cached
value - current value) > AbsoluteDeadband"); the first sample is always reported. deadband 0 reports every sample.
All numbers come from the config and are ILLUSTRATIVE; the spec has none. Signals not named in the config are NOT produced.
Not modelled: sensor drift, calibration, bad/stale quality (quality is GOOD), physical coupling between signals.
"""
from __future__ import annotations

import json
import math
import os
import random
import uuid
from typing import Dict, List, Tuple

from .events import NS, _hash, _iso
from .signals import _merge

SPEC = os.path.join(os.path.dirname(__file__), "..", "spec", "signals.json")
KEYS = ("idle", "run", "tau_h", "noise_sd", "sample_s", "deadband")
ANALOG = range(13, 27)


def _analog_signals():
    recs = json.load(open(SPEC, encoding="utf-8"))["records"]
    return {r["Señal"]: (r["ID"], r["Unidad"]) for r in recs if int(r["ID"][4:]) in ANALOG}


def first_order(x0: float, sp: float, dt: float, tau: float) -> float:
    """Exact first-order step response over dt hours (tau > 0)."""
    return sp + (x0 - sp) * math.exp(-dt / tau)


def deadband_filter(samples: List[Tuple[float, float]], deadband: float) -> List[Tuple[float, float]]:
    out: List[Tuple[float, float]] = []
    for t, v in samples:
        if not out or abs(v - out[-1][1]) > deadband:
            out.append((t, v))
    return out


def _samples(plant, eq, sn, p, busy):
    edges = sorted({0.0} | {x for a, b in busy for x in (a, b)})
    sp_at = lambda t: p["run"] if any(a <= t < b for a, b in busy) else p["idle"]
    dt_h = p.get("sample_s", 60) / 3600.0
    rng = random.Random(f"{plant.seed}/{eq}/{sn}")
    n = int(plant.horizon / dt_h)
    x, samples, t, ei = p["idle"], [], 0.0, 1
    for i in range(n + 1):
        tt = i * dt_h
        # integrate through setpoint switches between the previous sample and this one
        while t < tt - 1e-12:
            nxt = tt
            while ei < len(edges) and edges[ei] <= t + 1e-12:
                ei += 1
            if ei < len(edges) and edges[ei] < tt:
                nxt = edges[ei]
            x = first_order(x, sp_at(t + 1e-9), nxt - t, p["tau_h"])
            t = nxt
        samples.append((tt, x + (rng.gauss(0, p["noise_sd"]) if p.get("noise_sd") else 0.0)))
    return samples


def process_values(plant, result, cfg: Dict = None, schema_version: str = "2.0") -> List[dict]:
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    sig = _analog_signals()
    names = {s.name: k for k, s in enumerate(plant.stages)}
    for stage, sigs in cfg.items():
        if stage not in names:
            raise ValueError(f"process_values: unknown stage {stage!r}")
        if plant.stages[names[stage]].kind not in ("process", "move"):
            raise ValueError(f"process_values: {stage!r} is not a process or move stage")
        for sn, p in sigs.items():
            if sn not in sig:
                raise ValueError(f"process_values: {sn!r} is not an analog signal of the spec")
            bad = set(p) - set(KEYS)
            if bad or "idle" not in p or "run" not in p or "tau_h" not in p:
                raise ValueError(f"process_values {stage}/{sn}: needs idle, run, tau_h; unknown {sorted(bad)}")
            if p["tau_h"] <= 0 or p.get("noise_sd", 0) < 0 or p.get("sample_s", 60) <= 0 or p.get("deadband", 0) < 0:
                raise ValueError(f"process_values {stage}/{sn}: tau_h and sample_s > 0, noise_sd and deadband >= 0")
    out: List[dict] = []
    seq = 0
    for stage, sigs in cfg.items():
        k = names[stage]
        eq = f"EQ-STAGE-{k + 1:02d}"
        busy = _merge([(r[2], r[3]) for b in result.batches for r in b.trace if r[0] == k and r[3] > r[2]])
        for sn, p in sigs.items():
            sid, uom = sig[sn]
            samples = _samples(plant, eq, sn, p, busy)
            for tt, v in deadband_filter(samples, p.get("deadband", 0.0)):
                seq += 1
                el = {"measurement_type": sn, "signal_id": sid, "signal_quality": "GOOD", "device_id": eq, "value": round(v, 4), "uom": uom,
                      "source_timestamp": _iso(tt), "server_timestamp": _iso(tt), "time": _iso(tt)}
                e = {"event_id": str(uuid.uuid5(NS, f"{plant.seed}/pv/{seq}")), "event_class": "SENSOR", "event_type": "signal.changed", "action": "OBSERVE",
                     "event_time": _iso(tt), "record_time": _iso(tt), "event_time_zone_offset": "+00:00", "correlation_id": f"CORR-{eq}",
                     "causation_id": None, "sequence_no": None, "object_ids": [eq], "equipment_id": eq, "business_step": stage, "result": "OK",
                     "sensor_elements": [el], "schema_version": schema_version}
                e["payload_hash"] = _hash(e)
                out.append(e)
    out.sort(key=lambda e: (e["event_time"], e["equipment_id"]))
    return out


def reduction(plant, evs: List[dict], cfg: Dict) -> Dict[str, dict]:
    """Per equipment/signal: reported points, samples taken, share kept by the deadband."""
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    names = {st.name: k for k, st in enumerate(plant.stages)}
    out: Dict[str, dict] = {}
    for stage, sigs in cfg.items():
        for sn, p in sigs.items():
            key = f"EQ-STAGE-{names[stage] + 1:02d}/{sn}"
            n = int(plant.horizon / (p.get("sample_s", 60) / 3600.0)) + 1
            rep = sum(1 for e in evs if f"{e['equipment_id']}/{e['sensor_elements'][0]['measurement_type']}" == key)
            out[key] = {"reported": rep, "samples": n, "kept": round(rep / n, 4)}
    return out


def render_html(plant, result, cfg: Dict, stage: str, sn: str, hours_: float = 60.0, title: str = "Process value with deadband (synthetic)") -> str:
    """Chart of one signal: every sample (grey), reported points (teal, report by exception), busy bands (amber), first hours_ hours."""
    import html as H
    cfg = {k: v for k, v in cfg.items() if not k.startswith("_")}
    p = cfg[stage][sn]
    k = [s.name for s in plant.stages].index(stage)
    eq = f"EQ-STAGE-{k + 1:02d}"
    busy = _merge([(r[2], r[3]) for b in result.batches for r in b.trace if r[0] == k and r[3] > r[2]])
    smp = _samples(plant, eq, sn, p, busy)
    rep = deadband_filter(smp, p.get("deadband", 0.0))
    first = next((a for a, _ in busy), 0.0)
    t0 = max(0.0, first - 6)
    t1 = t0 + hours_
    W, Hh, L, B = 1000, 300, 50, 30
    vals = [v for t, v in smp if t0 <= t <= t1] or [0, 1]
    lo, hi = min(vals), max(vals)
    X = lambda t: L + (W - L - 10) * (t - t0) / (t1 - t0)
    Y = lambda v: Hh - B - (Hh - B - 12) * (v - lo) / ((hi - lo) or 1)
    bands = "".join(f'<rect x="{X(max(a, t0)):.1f}" y="12" width="{max(1, X(min(b, t1)) - X(max(a, t0))):.1f}" height="{Hh - B - 12}" fill="#fff0cf"/>' for a, b in busy if b > t0 and a < t1)
    raw = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in smp if t0 <= t <= t1)
    pts = [(t, v) for t, v in rep if t0 <= t <= t1]
    dots = "".join(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="2.2" fill="#00857c"/>' for t, v in pts)
    nraw = sum(1 for t, _ in smp if t0 <= t <= t1)
    uom = _analog_signals()[sn][1]
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{H.escape(title)}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>{H.escape(title)}</h2><div class=n>Synthetic and ILLUSTRATIVE: first-order response (tau {p['tau_h']} h) between {p['idle']} and {p['run']} {H.escape(uom)}, noise sd {p.get('noise_sd', 0)}, sample every {p.get('sample_s', 60)} s, absolute deadband {p.get('deadband', 0)} {H.escape(uom)} (OPC UA DataChangeFilter semantics). The spec has no values.</div>
<div>{H.escape(stage)} / {H.escape(sn)} ({H.escape(uom)}), hours {t0:.0f} to {t1:.0f}: <b>{nraw}</b> samples, <b>{len(pts)}</b> reported ({len(pts) / max(nraw, 1):.1%}). Amber = equipment executing.</div>
<svg width={W} height={Hh} style="background:#fafbfc;border:1px solid #dde3ea">{bands}<polyline points="{raw}" fill="none" stroke="#b0b8c4" stroke-width="1"/>{dots}<line x1={L} y1={Hh - B} x2={W - 10} y2={Hh - B} stroke="#889"/><text x=4 y=20 font-size=11>{hi:.1f}</text><text x=4 y={Hh - B} font-size=11>{lo:.1f}</text><text x={L} y={Hh - 8} font-size=11>{t0:.0f} h</text><text x={W - 60} y={Hh - 8} font-size=11>{t1:.0f} h</text></svg>
<div><span style="color:#b0b8c4">&#9632;</span> every sample &nbsp; <span style="color:#00857c">&#9679;</span> reported point</div></body></html>"""
