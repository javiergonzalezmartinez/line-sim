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
KEYS = ("idle", "run", "tau_h", "noise_sd", "sample_s", "deadband", "limits", "faults")
FAULTS = {"drift": ("start_h", "rate_per_h"), "step": ("start_h", "dur_h", "delta"), "stochastic_excursion": ("rate_per_100h", "dur_h", "delta"),
          "calibration_overdue": ("valid_until_h",)}
FAULT_ID = {"drift": "FME-017", "step": "FME-020", "stochastic_excursion": "FME-028", "calibration_overdue": "FME-019"}
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


def apply_faults(samples, p, seed_key, horizon):
    """Return (faulted samples, calibration_valid_until or None, injections[(type, start, end)]). Ground truth is not changed, only what the sensor reports."""
    out = list(samples)
    cal, inj = None, []
    rng = random.Random(seed_key)
    for f in p.get("faults", []):
        ty = f["type"]
        if ty == "drift":
            a, b = f["start_h"], f.get("end_h", horizon)
            out = [(t, v + f["rate_per_h"] * (min(t, b) - a) if t >= a else v) for t, v in out]
            inj.append((ty, a, b))
        elif ty == "step":
            a, b = f["start_h"], f["start_h"] + f["dur_h"]
            out = [(t, v + f["delta"] if a <= t < b else v) for t, v in out]
            inj.append((ty, a, b))
        elif ty == "stochastic_excursion":
            t, wins = 0.0, []
            while f["rate_per_100h"] > 0:
                t += rng.expovariate(f["rate_per_100h"] / 100.0)
                if t >= horizon:
                    break
                wins.append((t, t + f["dur_h"]))
                t += f["dur_h"]
            for a, b in wins:
                inj.append((ty, a, b))
            out = [(t, v + f["delta"] if any(a <= t < b for a, b in wins) else v) for t, v in out]
        else:
            cal = f["valid_until_h"]
            inj.append((ty, cal, horizon))
    return out, cal, inj


def excursions(samples, limits):
    """Limit evaluator: [(open_t, close_t or None)] where the value is outside [low, high]."""
    lim = limits or {}
    lo, hi, hy = lim.get("low"), lim.get("high"), lim.get("hysteresis", 0.0)
    res, cur = [], None
    for t, v in samples:
        if cur is None:
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                cur = t
        elif not ((lo is not None and v < lo + hy) or (hi is not None and v > hi - hy)):
            res.append((cur, t))
            cur = None
    if cur is not None:
        res.append((cur, None))
    return res


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
            for f in p.get("faults", []):
                if f.get("type") not in FAULTS or set(FAULTS[f["type"]]) - set(f) or set(f) - set(FAULTS[f["type"]]) - {"type", "end_h"}:
                    raise ValueError(f"process_values {stage}/{sn}: fault needs type in {sorted(FAULTS)} and its parameters {FAULTS.get(f.get('type'))}")
                if f["type"] == "stochastic_excursion" and (f["rate_per_100h"] < 0 or f["dur_h"] <= 0):
                    raise ValueError(f"process_values {stage}/{sn}: rate_per_100h >= 0 and dur_h > 0")
            lim = p.get("limits")
            if lim is not None and (set(lim) - {"low", "high", "hysteresis"} or not (set(lim) & {"low", "high"}) or lim.get("hysteresis", 0) < 0 or (("low" in lim and "high" in lim) and lim["low"] >= lim["high"])):
                raise ValueError(f"process_values {stage}/{sn}: limits needs low and/or high, low < high")
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
            samples, cal, _inj = apply_faults(samples, p, f"{plant.seed}/{eq}/{sn}/faults", plant.horizon)
            for xa, xb in excursions(samples, p.get("limits")):
                for tt2, ev2 in ((xa, "excursion.opened"), (xb, "excursion.closed")):
                    if tt2 is None:
                        continue
                    seq += 1
                    xo = f"EXC-{eq}-{sn}-{int(xa * 1000):07d}"
                    ee = {"event_id": str(uuid.uuid5(NS, f"{plant.seed}/pvx/{seq}")), "event_class": "CONTROL", "event_type": ev2, "action": "OBSERVE", "event_time": _iso(tt2), "record_time": _iso(tt2), "event_time_zone_offset": "+00:00", "correlation_id": f"CORR-{eq}", "causation_id": None, "sequence_no": None, "object_ids": [xo], "equipment_id": eq, "business_step": stage, "result": "OK" if ev2 == "excursion.closed" else "ERROR", "reason_code": f"limit evaluator on {sn}: {p['limits']} (FME-020/FME-028)", "schema_version": schema_version}
                    ee["payload_hash"] = _hash(ee)
                    out.append(ee)
            for tt, v in deadband_filter(samples, p.get("deadband", 0.0)):
                seq += 1
                el = {"measurement_type": sn, "signal_id": sid, "signal_quality": "UNCERTAIN" if cal is not None and tt >= cal else "GOOD", "device_id": eq, "value": round(v, 4), "uom": uom,
                      "source_timestamp": _iso(tt), "server_timestamp": _iso(tt), "time": _iso(tt)}
                e = {"event_id": str(uuid.uuid5(NS, f"{plant.seed}/pv/{seq}")), "event_class": "SENSOR", "event_type": "signal.changed", "action": "OBSERVE",
                     "event_time": _iso(tt), "record_time": _iso(tt), "event_time_zone_offset": "+00:00", "correlation_id": f"CORR-{eq}",
                     "causation_id": None, "sequence_no": None, "object_ids": [eq], "equipment_id": eq, "business_step": stage, "result": "OK",
                     "sensor_elements": [el], "schema_version": schema_version}
                e["payload_hash"] = _hash(e)
                out.append(e)
    out.sort(key=lambda e: (e["event_time"], e["equipment_id"], e["event_type"]))
    return out


def excursion_kpis(evs):
    """KPI-024 ExcursionDuration (h): close - open per excursion; open ones are counted separately."""
    from .kpis import hours
    op, durs = {}, []
    for e in evs:
        if e["event_type"] == "excursion.opened":
            op[e["object_ids"][0]] = hours(e["event_time"])
        elif e["event_type"] == "excursion.closed":
            durs.append(hours(e["event_time"]) - op.pop(e["object_ids"][0]))
    return {"excursions_closed": len(durs), "excursions_open_at_end": len(op), "KPI-024 ExcursionDuration mean (h)": round(sum(durs) / len(durs), 4) if durs else None,
            "KPI-024 ExcursionDuration total (h)": round(sum(durs), 4)}


def reduction(plant, evs: List[dict], cfg: Dict) -> Dict[str, dict]:
    """Per equipment/signal: reported points, samples taken, share kept by the deadband."""
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    names = {st.name: k for k, st in enumerate(plant.stages)}
    out: Dict[str, dict] = {}
    for stage, sigs in cfg.items():
        for sn, p in sigs.items():
            key = f"EQ-STAGE-{names[stage] + 1:02d}/{sn}"
            n = int(plant.horizon / (p.get("sample_s", 60) / 3600.0)) + 1
            rep = sum(1 for e in evs if e["event_class"] == "SENSOR" and f"{e['equipment_id']}/{e['sensor_elements'][0]['measurement_type']}" == key)
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
    smp, cal, inj = apply_faults(smp, p, f"{plant.seed}/{eq}/{sn}/faults", plant.horizon)
    rep = deadband_filter(smp, p.get("deadband", 0.0))
    exc = excursions(smp, p.get("limits"))
    first = next((a for a, _ in busy), 0.0)
    t0 = max(0.0, first - 6)
    if p.get("faults"):
        t0, hours_ = plant.warmup, plant.horizon - plant.warmup
    t1 = t0 + hours_
    W, Hh, L, B = 1000, 300, 50, 30
    vals = [v for t, v in smp if t0 <= t <= t1] or [0, 1]
    lo, hi = min(vals), max(vals)
    X = lambda t: L + (W - L - 10) * (t - t0) / (t1 - t0)
    Y = lambda v: Hh - B - (Hh - B - 12) * (v - lo) / ((hi - lo) or 1)
    bands = "".join(f'<rect x="{X(max(a, t0)):.1f}" y="12" width="{max(1, X(min(b, t1)) - X(max(a, t0))):.1f}" height="{Hh - B - 12}" fill="#fff0cf"/>' for a, b in busy if b > t0 and a < t1)
    step = max(1, int(sum(1 for t, _ in smp if t0 <= t <= t1) / 1500))
    raw = " ".join(f"{X(t):.1f},{Y(v):.1f}" for i, (t, v) in enumerate(smp) if t0 <= t <= t1 and i % step == 0)
    lim = p.get("limits") or {}
    limline = "".join(f'<line x1={L} x2={W - 10} y1={Y(lim[k]):.1f} y2={Y(lim[k]):.1f} stroke="#c92a2a" stroke-dasharray="5 4"/><text x={W - 120} y={Y(lim[k]) - 3:.1f} font-size=11 fill="#c92a2a">{k} limit {lim[k]}</text>' for k in ("low", "high") if k in lim)
    xbands = "".join(f'<rect x="{X(max(a, t0)):.1f}" y="12" width="{max(1.5, X(min(b if b is not None else t1, t1)) - X(max(a, t0))):.1f}" height="{Hh - B - 12}" fill="#f8d7da" opacity="0.8"/>' for a, b in exc if (b is None or b > t0) and a < t1)
    cband = f'<rect x="{X(max(cal, t0)):.1f}" y="{Hh - B + 2}" width="{max(1, X(t1) - X(max(cal, t0))):.1f}" height="6" fill="#c98a00"/>' if cal is not None and cal < t1 else ""
    injtxt = "".join(f'<text x="{X(max(a, t0)):.1f}" y="{26 + 12 * i}" font-size=10 fill="#7a3fb0">{FAULT_ID[ty]} {ty}</text><line x1="{X(max(a, t0)):.1f}" x2="{X(max(a, t0)):.1f}" y1=12 y2={Hh - B} stroke="#7a3fb0" stroke-dasharray="2 3"/>' for i, (ty, a, b) in enumerate(i2 for i2 in inj if i2[0] != "stochastic_excursion") if t0 <= a <= t1)
    pts = [(t, v) for t, v in rep if t0 <= t <= t1]
    if hours_ > 200:
        dots = '<polyline points="' + " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in pts) + '" fill="none" stroke="#00857c" stroke-width="1"/>'
    else:
        dots = "".join(f'<circle cx="{X(t):.1f}" cy="{Y(v):.1f}" r="2.2" fill="#00857c"/>' for t, v in pts)
    nraw = sum(1 for t, _ in smp if t0 <= t <= t1)
    uom = _analog_signals()[sn][1]
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{H.escape(title)}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>{H.escape(title)}</h2><div class=n>Synthetic and ILLUSTRATIVE: first-order response (tau {p['tau_h']} h) between {p['idle']} and {p['run']} {H.escape(uom)}, noise sd {p.get('noise_sd', 0)}, sample every {p.get('sample_s', 60)} s, absolute deadband {p.get('deadband', 0)} {H.escape(uom)} (OPC UA DataChangeFilter semantics). The spec has no values.</div>
<div>{H.escape(stage)} / {H.escape(sn)} ({H.escape(uom)}), hours {t0:.0f} to {t1:.0f}: <b>{nraw}</b> samples, <b>{len(pts)}</b> reported ({len(pts) / max(nraw, 1):.1%}). Amber = equipment executing{", red = excursion open (limit evaluator)" if exc else ""}{", amber strip under the axis = calibration overdue, quality UNCERTAIN" if cal is not None else ""}. {len(exc)} excursions.</div>
<svg width={W} height={Hh} style="background:#fafbfc;border:1px solid #dde3ea">{bands}{xbands}{limline}{injtxt}{cband}<polyline points="{raw}" fill="none" stroke="#b0b8c4" stroke-width="1"/>{dots}<line x1={L} y1={Hh - B} x2={W - 10} y2={Hh - B} stroke="#889"/><text x=4 y=20 font-size=11>{hi:.1f}</text><text x=4 y={Hh - B} font-size=11>{lo:.1f}</text><text x={L} y={Hh - 8} font-size=11>{t0:.0f} h</text><text x={W - 60} y={Hh - 8} font-size=11>{t1:.0f} h</text></svg>
<div><span style="color:#b0b8c4">&#9632;</span> every sample (thinned) &nbsp; <span style="color:#00857c">&#9679;</span> reported points (joined by a line on long windows)</div></body></html>"""
