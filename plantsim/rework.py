"""Rework (repeat) sweep: what does a repeat probability cost? (synthetic, illustrative)

A step with `retest_p` is repeated with that probability (the step is run again, as for an out-of-specification investigation); a repeat can repeat again.
Sweep: set `retest_p` of ONE stage to several values, same seeds in every row, and show repeats started in the window, the resource-hours they used,
that share of the stage's busy hours, plus throughput and mean lead time with 95% CI (t, as in whatif.py).
Framing: repeated work as hidden capacity loss ("hidden factory"). That term and its figures were NOT read from a source in this project, so no external claim is made:
the page only reports what this simulation does. The repeat takes a fresh draw of the same process time and a lot can repeat several times
(geometric number of repeats, mean p/(1-p) per lot).
Not modelled: that a repeat changes the product quality or the downstream hold, repeat cost in money, a different (shorter) repeat time, a limit on repeats.
All numbers come from placeholders in the config.
"""
from __future__ import annotations

import dataclasses
import html as H
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, stage: str, probs: List[float], n: int = 8) -> List[dict]:
    names = [s.name for s in plant.stages]
    if stage not in names:
        raise ValueError("unknown stage " + stage)
    k = names.index(stage)
    out = []
    for p in probs:
        if not 0 <= p < 1:
            raise ValueError("probability must be in [0, 1)")
        st = [dataclasses.replace(s, retest_p=p) if s.name == stage else s for s in plant.stages]
        rs = [simulate(dataclasses.replace(plant, stages=st, seed=plant.seed + i)) for i in range(n)]
        row = {"p": p}
        row["thr"] = mean_ci([r.throughput_per_week for r in rs])[:3]
        row["lt"] = mean_ci([r.mean_lead_time_days for r in rs])[:3]
        row["reruns"] = mean_ci([float(r.stats[k].reruns) for r in rs])[:3]
        row["hours"] = mean_ci([r.stats[k].rerun_hours for r in rs])[:3]
        row["share"] = mean_ci([r.stats[k].rerun_hours / r.stats[k].busy if r.stats[k].busy else 0.0 for r in rs])[:3]
        out.append(row)
    return out


def render_html(rows: List[dict], stage: str) -> str:
    W, Hh, L = 700, 240, 50
    X = lambda i: L + (W - L - 30) * i / max(len(rows) - 1, 1)
    tmax = max(r["thr"][2] for r in rows) * 1.05; tmin = min(r["thr"][1] for r in rows) * 0.95
    Y = lambda v: 16 + (Hh - 60) * (1 - (v - tmin) / ((tmax - tmin) or 1))
    smax = max(r["share"][2] for r in rows) * 1.1 or 1.0
    Y2 = lambda v: 16 + (Hh - 60) * (1 - v / smax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#00857c" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["thr"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y2(r["share"][0])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["p"] * 100:g}%</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r["thr"][1]):.1f}" y2="{Y(r["thr"][2]):.1f}" stroke="#00857c"/><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y2(r["share"][1]):.1f}" y2="{Y2(r["share"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#00857c">throughput /week {tmin:.1f}..{tmax:.1f}</text><text x="{W - 330}" y="12" fill="#c0392b">repeat share of stage busy hours 0..{smax * 100:.0f}%</text><text x="{L}" y="{Hh - 8}" fill="#5c6b80">repeat probability of {H.escape(stage)} (retest_p)</text></svg>')
    f = lambda t, d=2: f"{t[0]:.{d}f} [{t[1]:.{d}f}, {t[2]:.{d}f}]"
    body = "".join(f"<tr><td>{r['p'] * 100:g}%</td><td>{f(r['reruns'], 1)}</td><td>{f(r['hours'], 0)}</td><td>{r['share'][0] * 100:.1f}% [{r['share'][1] * 100:.1f}, {r['share'][2] * 100:.1f}]</td><td>{f(r['thr'])}</td><td>{f(r['lt'], 1)}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Rework sweep (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>What a repeat probability costs: {H.escape(stage)} (synthetic)</h2><div class=n>Synthetic and illustrative: placeholder parameters. A repeated step runs again with a fresh draw of its process time, and can repeat again (mean p/(1-p) repeats per lot). Same seeds in every row, 95% CI. No external source is used for the "hidden capacity" framing; the page reports only what this simulation does. Hours only, no cost; a repeat does not change quality or holds downstream.</div>{''.join(s)}
<table><tr><th>Repeat probability</th><th>Repeats in window [CI]</th><th>Repeat hours [CI]</th><th>Share of stage busy hours [CI]</th><th>Throughput /week [CI]</th><th>Lead time, days [CI]</th></tr>{body}</table></body></html>"""
