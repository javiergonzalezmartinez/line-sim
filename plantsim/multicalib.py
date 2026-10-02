"""Calibrating TWO parameters at once against a SYNTHETIC reference: is each one identifiable? (synthetic, illustrative)

Follow-up of calibrate.py, whose note says it does not show that several parameters are identifiable together. Operational-validity idea as in
Sargent, WSC 2011 (https://www.informs-sim.org/wsc11papers/016.pdf, read 2 Oct 2026): compare model output with the system's behaviour. No real data here.
A hidden truth (mean process hours of two stages A and B) generates reference summaries (mean over `ref_seeds` seeds). The loss is then evaluated on a
grid of (A, B) values, each cell averaged over `seeds` other seeds, for two sets of observables:
  set 1: throughput and mean lead time (what calibrate.py uses)
  set 2: set 1 plus the mean queue wait per lot at stage A and at stage B
Loss = sum of squared relative errors of the observables. A valley (many cells with a loss near the minimum) means the data cannot tell the two
values apart; a round basin means they can. "Near" is: loss <= minimum + 2 x the loss of the TRUTH cell (the centre of the grid), which is pure noise
because that cell has the true values; it is a rule of this code, not a statistical test. With few seeds the minimum may not sit on the truth.
What this does not show: other parameter pairs, a wrong model structure, or real data.
"""
from __future__ import annotations

import dataclasses
import html as H
from typing import Dict, List

from .model import simulate


def _plant(plant, a, b, ha, hb, off):
    st = [dataclasses.replace(s, hours=ha) if s.name == a else (dataclasses.replace(s, hours=hb) if s.name == b else s) for s in plant.stages]
    return dataclasses.replace(plant, stages=st, seed=plant.seed + off)


def _obs(plant, a, b, n, seed0):
    ia = [s.name for s in plant.stages].index(a); ib = [s.name for s in plant.stages].index(b)
    tot = [0.0, 0.0, 0.0, 0.0]
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + seed0 + i))
        tot[0] += r.throughput_per_week; tot[1] += r.mean_lead_time_days
        tot[2] += r.stats[ia].wait / max(r.stats[ia].batches, 1); tot[3] += r.stats[ib].wait / max(r.stats[ib].batches, 1)
    return [x / n for x in tot]


def _loss(o, ref, k):
    return sum(((o[j] - ref[j]) / ref[j]) ** 2 for j in range(k) if abs(ref[j]) > 1e-9)


def run(plant, a: str, b: str, truth, span: float = 0.4, steps: int = 7, seeds: int = 4, ref_seeds: int = 10) -> Dict:
    names = [s.name for s in plant.stages]
    if a not in names or b not in names or a == b:
        raise ValueError("need two different existing stages")
    if steps % 2 == 0:
        raise ValueError("steps must be odd so that the centre cell is the truth")
    ta, tb = truth
    ref = _obs(_plant(plant, a, b, ta, tb, 0), a, b, ref_seeds, 1000)
    va = [ta * (1 - span + 2 * span * i / (steps - 1)) for i in range(steps)]
    vb = [tb * (1 - span + 2 * span * i / (steps - 1)) for i in range(steps)]
    cells = []
    for x in va:
        row = []
        for y in vb:
            o = _obs(_plant(plant, a, b, x, y, 0), a, b, seeds, 0)
            row.append({"obs": o, "l1": _loss(o, ref, 2), "l2": _loss(o, ref, 4)})
        cells.append(row)
    out = {"a": a, "b": b, "truth": truth, "va": va, "vb": vb, "ref": ref, "cells": cells, "seeds": seeds, "ref_seeds": ref_seeds}
    for key in ("l1", "l2"):
        flat = [(c[key], i, j) for i, r in enumerate(cells) for j, c in enumerate(r)]
        mn = min(flat)
        mid = cells[steps // 2][steps // 2][key]
        near = sum(1 for v, _, _ in flat if v <= mn[0] + 2 * mid + 1e-12)
        out[key + "_best"] = (va[mn[1]], vb[mn[2]], mn[0]); out[key + "_near"] = near
    out["cells_total"] = steps * steps
    return out


def _heat(res, key, title):
    n = len(res["va"]); cs = 44; L = 70; T = 26
    vals = [c[key] for r in res["cells"] for c in r]; mx = max(vals) or 1.0
    best = res[key + "_best"]
    s = [f'<svg width="{L + n * cs + 10}" height="{T + n * cs + 40}" font-size="10"><text x="{L}" y="14" font-weight="bold">{H.escape(title)}</text>']
    for i, r in enumerate(res["cells"]):
        for j, c in enumerate(r):
            t = min(c[key] / mx, 1.0) ** 0.5
            col = f"rgb({int(255 - 200 * (1 - t))},{int(140 + 100 * t)},{int(130 + 100 * t)})" if False else f"rgb({int(0 + 255 * t)},{int(133 + 90 * t)},{int(124 + 110 * t)})"
            ring = ' stroke="#000" stroke-width="2"' if (res["va"][i], res["vb"][j]) == best[:2] else ' stroke="#fff"'
            s.append(f'<rect x="{L + j * cs}" y="{T + i * cs}" width="{cs - 1}" height="{cs - 1}" fill="{col}"{ring}/><text x="{L + j * cs + cs / 2}" y="{T + i * cs + cs / 2 + 3}" text-anchor="middle" fill="#000">{c[key]:.3f}</text>')
    for i, v in enumerate(res["va"]):
        s.append(f'<text x="{L - 4}" y="{T + i * cs + cs / 2 + 3}" text-anchor="end">{v:.1f}</text>')
    for j, v in enumerate(res["vb"]):
        s.append(f'<text x="{L + j * cs + cs / 2}" y="{T + n * cs + 12}" text-anchor="middle">{v:.1f}</text>')
    s.append(f'<text x="{L}" y="{T + n * cs + 28}" fill="#5c6b80">columns: {H.escape(res["b"])} hours; rows: {H.escape(res["a"])} hours</text></svg>')
    return "".join(s)


def render_html(res: Dict) -> str:
    ta, tb = res["truth"]
    def line(k, lab):
        b = res[k + "_best"]
        return f"<li>{lab}: lowest loss {b[2]:.4f} at {H.escape(res['a'])} = {b[0]:.1f} h, {H.escape(res['b'])} = {b[1]:.1f} h (truth {ta:.1f} / {tb:.1f}); cells near the minimum (minimum + 2 x the truth-cell loss): <b>{res[k + '_near']} of {res['cells_total']}</b></li>"
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Two-parameter calibration (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1000px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}.g{{display:flex;gap:24px;flex-wrap:wrap}}</style></head><body><h2>Two parameters at once: can the data tell them apart? (synthetic)</h2><div class=n>Synthetic and illustrative. Hidden truth: mean process hours of two stages. The reference summary comes from {res['ref_seeds']} seeds at the truth; each grid cell is {res['seeds']} other seeds. Loss = sum of squared relative errors of the observables. Set 1: throughput and lead time. Set 2: set 1 plus mean queue wait per lot at each of the two stages. Teal = low loss, bright = high; black frame = lowest cell. A broad low area (many cells near the minimum: within the minimum plus twice the loss of the truth cell, a rule of this code) means the observables cannot separate the two values. Operational-validity idea as in Sargent, WSC 2011 (read 2 Oct 2026). No real data, one stage pair only, few seeds.</div>
<ul>{line('l1', 'Set 1')}{line('l2', 'Set 2')}</ul><div class=g>{_heat(res, 'l1', 'Loss, set 1: throughput + lead time')}{_heat(res, 'l2', 'Loss, set 2: + queue wait at both stages')}</div></body></html>"""
