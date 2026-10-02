"""FME-022 "yield below threshold": threshold sweep (synthetic, illustrative).

Failure mode from the twin spec (spec/failures.json, provided by Javi, synthetic): FME-022, domain Process, "Yield below threshold", simulation injection "yield random tail".
Modelled here as: each run of a stage with `yield_mean` draws a yield from a Beta distribution with that mean and coefficient of variation `yield_cv`
(Beta chosen by this code because a yield lives in 0..1; no source for it is claimed); if the yield is below `yield_min` the run is repeated
(rework: a fresh process time and a fresh yield draw), and counted in `low_yield`. The sweep varies `yield_min` for ONE stage, same seeds in every row.
Shown: low-yield runs in the window, repeat hours, throughput and lead time with 95% CI (t, as in whatif.py).
The yield itself does not change the amount produced (a lot is a lot): only the repeat costs time. Not modelled: scrap of the low-yield material, a hold or
deviation record downstream, a yield that depends on the machine state or on the product, the cost. Mean, cv and thresholds are placeholders.
"""
from __future__ import annotations

import dataclasses
import html as H
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, stage: str, mean: float, cv: float, thresholds: List[float], n: int = 8) -> List[dict]:
    names = [s.name for s in plant.stages]
    if stage not in names:
        raise ValueError("unknown stage " + stage)
    k = names.index(stage)
    out = []
    for th in thresholds:
        st = [dataclasses.replace(s, yield_mean=mean, yield_cv=cv, yield_min=th) if s.name == stage else s for s in plant.stages]
        rs = [simulate(dataclasses.replace(plant, stages=st, seed=plant.seed + i)) for i in range(n)]
        row = {"th": th}
        row["low"] = mean_ci([float(r.stats[k].low_yield) for r in rs])[:3]
        row["hours"] = mean_ci([r.stats[k].rerun_hours for r in rs])[:3]
        row["thr"] = mean_ci([r.throughput_per_week for r in rs])[:3]
        row["lt"] = mean_ci([r.mean_lead_time_days for r in rs])[:3]
        out.append(row)
    return out


def render_html(rows: List[dict], stage: str, mean: float, cv: float) -> str:
    W, Hh, L = 700, 230, 50
    X = lambda i: L + (W - L - 30) * i / max(len(rows) - 1, 1)
    lmax = max(r["lt"][2] for r in rows) * 1.05; lmin = min(r["lt"][1] for r in rows) * 0.95
    Y = lambda v: 16 + (Hh - 60) * (1 - (v - lmin) / ((lmax - lmin) or 1))
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">', '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["lt"][0])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["th"] * 100:g}%</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r["lt"][1]):.1f}" y2="{Y(r["lt"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">mean lead time, days {lmin:.1f}..{lmax:.1f} (whiskers 95% CI)</text><text x="{L}" y="{Hh - 8}" fill="#5c6b80">yield threshold of {H.escape(stage)}: runs below it are repeated</text></svg>')
    f = lambda t, d=2: f"{t[0]:.{d}f} [{t[1]:.{d}f}, {t[2]:.{d}f}]"
    body = "".join(f"<tr><td>{r['th'] * 100:g}%</td><td>{f(r['low'], 1)}</td><td>{f(r['hours'], 0)}</td><td>{f(r['thr'])}</td><td>{f(r['lt'], 1)}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-022 yield threshold sweep (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-022 yield below threshold: {H.escape(stage)} (synthetic)</h2><div class=n>Synthetic and illustrative. Failure mode FME-022 "Yield below threshold" (twin spec provided by Javi, synthetic). Each run draws a yield from a Beta distribution (mean {mean * 100:g}%, cv {cv * 100:g}%; the Beta is a choice of this code, no source claimed); a run below the threshold is repeated with a fresh time and a fresh draw. Same seeds in every row, 95% CI. The yield does not change the quantity produced; only the repeats cost time. No scrap, hold or cost is modelled.</div>{''.join(s)}
<table><tr><th>Yield threshold</th><th>Low-yield runs in window [CI]</th><th>Repeat hours (all repeats of the stage) [CI]</th><th>Throughput /week [CI]</th><th>Lead time, days [CI]</th></tr>{body}</table></body></html>"""
