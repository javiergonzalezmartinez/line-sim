"""Twin calibration against a SYNTHETIC reference run (synthetic, illustrative).

Idea (operational validity): compare the model's output with the behaviour of the real system and adjust until they agree. See
Sargent, "Verification and Validation of Simulation Models", Winter Simulation Conference 2011 (https://www.informs-sim.org/wsc11papers/016.pdf,
read 2 Oct 2026), which describes comparing model and system behaviour as the operational validity step inside an iterative modelling process.
This module does NOT use real data. A hidden "truth" (a different mean process time of one stage) generates a reference
summary (mean throughput and mean lead time over several seeds). The model is then calibrated by changing that one parameter:
a coarse grid, then a finer grid around the best value, each point averaged over `seeds` replications with seeds different from the reference's.
Loss = squared relative error of throughput + squared relative error of mean lead time.
What this shows: that the fitting procedure can recover a known value in a controlled case. What it does not show: that the model
is valid for any real plant, that several parameters are identifiable at once, or what happens with a wrong model structure.
With few seeds the fit has a noise floor; the report gives the error of the fitted value next to the true one.
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List


def _with_hours(plant, stage: str, hours: float, seed_offset: int = 0):
    st = [dataclasses.replace(s, hours=hours) if s.name == stage else s for s in plant.stages]
    return dataclasses.replace(plant, stages=st, seed=plant.seed + seed_offset)


def summary(plant, n: int, seed0: int):
    from .model import simulate
    rs = [simulate(dataclasses.replace(plant, seed=plant.seed + seed0 + i)) for i in range(n)]
    return sum(r.throughput_per_week for r in rs) / n, sum(r.mean_lead_time_days for r in rs) / n


def loss(thr, lt, ref):
    return ((thr - ref[0]) / ref[0]) ** 2 + ((lt - ref[1]) / ref[1]) ** 2


def calibrate(plant, stage: str, truth: float, lo: float, hi: float, coarse: float = 0.5, fine: float = 0.1, seeds: int = 8, ref_seeds: int = 12) -> Dict:
    if stage not in [s.name for s in plant.stages]:
        raise ValueError("unknown stage " + stage)
    start = next(s.hours for s in plant.stages if s.name == stage)
    ref = summary(_with_hours(plant, stage, truth), ref_seeds, 1000)
    pts: List[Dict] = []

    def ev(h):
        thr, lt = summary(_with_hours(plant, stage, h), seeds, 0)
        pts.append({"hours": round(h, 6), "thr": thr, "lt": lt, "loss": loss(thr, lt, ref)})

    h = lo
    while h <= hi + 1e-9:
        ev(h); h += coarse
    best = min(pts, key=lambda p: p["loss"])["hours"]
    h = max(lo, best - coarse)
    while h <= min(hi, best + coarse) + 1e-9:
        if not any(abs(p["hours"] - h) < 1e-9 for p in pts):
            ev(h)
        h += fine
    pts.sort(key=lambda p: p["hours"])
    b = min(pts, key=lambda p: p["loss"])
    return {"stage": stage, "start": start, "truth": truth, "fitted": b["hours"], "error": b["hours"] - truth, "ref": ref,
            "fit_thr": b["thr"], "fit_lt": b["lt"], "points": pts, "seeds": seeds, "ref_seeds": ref_seeds}


def render_html(r: Dict) -> str:
    import html as H
    pts = r["points"]
    W, Hh, L, B = 760, 300, 60, 40
    xs = [p["hours"] for p in pts]
    mx = max(p["loss"] for p in pts)
    X = lambda v: L + (W - L - 20) * (v - min(xs)) / ((max(xs) - min(xs)) or 1)
    Y = lambda v: 20 + (Hh - B - 20) * (1 - v / (mx or 1))
    path = " ".join(f"{X(p['hours']):.1f},{Y(p['loss']):.1f}" for p in pts)
    dots = "".join(f'<circle cx="{X(p["hours"]):.1f}" cy="{Y(p["loss"]):.1f}" r="3" fill="#00857c"><title>{p["hours"]:.2f} h: loss {p["loss"]:.5f}</title></circle>' for p in pts)
    vl = lambda v, c, t, dy: f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="20" y2="{Hh - B}" stroke="{c}" stroke-dasharray="4 3"/><text x="{X(v) + 4:.1f}" y="{30 + dy}" fill="{c}" font-size="11">{t} {v:.2f}</text>'
    ticks = "".join(f'<text x="{X(v):.1f}" y="{Hh - B + 16}" font-size="10" text-anchor="middle" fill="#5c6b80">{v:g}</text>' for v in sorted({round(x) for x in xs}))
    svg = f'<svg width="{W}" height="{Hh}"><polyline points="{path}" fill="none" stroke="#00857c" stroke-width="2"/>{dots}{vl(r["truth"], "#c0392b", "hidden truth", 0)}{vl(r["fitted"], "#2b8a3e", "fitted", 14)}{vl(r["start"], "#868e96", "model start", 28)}{ticks}<text x="{L}" y="{Hh - 6}" font-size="11" fill="#5c6b80">mean process time of {H.escape(r["stage"])} (h)</text><text x="4" y="14" font-size="11" fill="#5c6b80">loss</text></svg>'
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Calibration against a synthetic reference</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:900px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}td,th{{padding:4px 10px;border-bottom:1px solid #dde3ea;text-align:left}}th{{background:#0b1226;color:#fff}}</style></head><body><h2>Calibration against a synthetic reference run</h2><div class=n>Synthetic and illustrative. The "truth" is a value I chose to generate a reference; no real data is used. This shows that the search can recover a known value, not that the model is valid for any real plant. Idea from Sargent (WSC 2011, read 2 Oct 2026): compare model and system behaviour, adjust, repeat. Reference = {r['ref_seeds']} seeds, each candidate = {r['seeds']} other seeds.</div>
<table><tr><th>Stage</th><th>Model start</th><th>Hidden truth</th><th>Fitted</th><th>Error (fitted - truth)</th></tr><tr><td>{H.escape(r['stage'])}</td><td>{r['start']:.2f} h</td><td>{r['truth']:.2f} h</td><td><b>{r['fitted']:.2f} h</b></td><td>{r['error']:+.2f} h</td></tr></table>
<p>Reference: {r['ref'][0]:.2f} batches/week, {r['ref'][1]:.2f} days lead time. Fitted model: {r['fit_thr']:.2f} batches/week, {r['fit_lt']:.2f} days.</p>{svg}</body></html>"""
