"""Preventive-maintenance interval sweep (synthetic, illustrative).

Question: how often should a machine get preventive maintenance (PM) when breakdown probability rises with run-hours since the last one?
Frame as read (2 Oct 2026) at https://en.wikipedia.org/wiki/Preventive_maintenance : parts with scheduled maintenance at fixed intervals are
time-change interval items, usually because of wear-out. That page gives no rule for choosing the interval, so none is claimed here;
this page only shows what the simulation does for several intervals.
Applied to every process stage that has `wear_per_100h > 0` in the config; each gets `pm_every_h` = the interval and keeps its own `pm_hours`
(a stage with pm_hours = 0 stays at 0, so give it one in the config). "never" = no PM. Same seeds for every row, mean and 95% CI (t).
The wear law, repair times and PM durations are placeholders from the config; the optimum is a property of those placeholders, not of a real machine.
Not modelled: PM that restores only partly, condition-based triggers, spare parts, PM cost (hours only, no money).
"""
from __future__ import annotations

import dataclasses
import html as H
from typing import List, Optional

from .whatif import mean_ci, replicate

HL = ' style="background:#e6f4f2"'
KEYS = (("Throughput (batches/week)", "thr"), ("Mean lead time (days)", "lt"), ("Repair hours (all stages)", "rep"), ("Preventive maintenance hours", "pm"))


def sweep(plant, intervals: List[Optional[float]], n: int = 8) -> List[dict]:
    out = []
    for iv in intervals:
        st = [dataclasses.replace(s, pm_every_h=iv) if s.wear_per_100h > 0 else s for s in plant.stages]
        rs = replicate(dataclasses.replace(plant, stages=st), n)
        row = {"iv": iv}
        for k, short in KEYS:
            row[short] = mean_ci([r[k] for r in rs])[:3]
        row["down"] = (row["rep"][0] + row["pm"][0], row["rep"][1] + row["pm"][1], row["rep"][2] + row["pm"][2])
        out.append(row)
    return out


def render_html(rows: List[dict]) -> str:
    W, Hh, L = 720, 250, 50
    X = lambda i: L + (W - L - 30) * i / max(len(rows) - 1, 1)
    tmax = max(r["thr"][2] for r in rows) * 1.08
    tmin = min(r["thr"][1] for r in rows) * 0.9
    Y = lambda v: 16 + (Hh - 50) * (1 - (v - tmin) / (tmax - tmin or 1))
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">']
    s.append('<polyline points="%s" fill="none" stroke="#00857c" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["thr"][0])) for i, r in enumerate(rows)))
    for i, r in enumerate(rows):
        lab = "never" if r["iv"] is None else f"{r['iv']:g} h"
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 22}" text-anchor="middle">{lab}</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r["thr"][1]):.1f}" y2="{Y(r["thr"][2]):.1f}" stroke="#00857c" stroke-width="2"/><circle cx="{X(i):.1f}" cy="{Y(r["thr"][0]):.1f}" r="3.5" fill="#00857c"/>')
    s.append(f'<text x="4" y="12" fill="#00857c">throughput /week, {tmin:.1f}..{tmax:.1f} (whiskers 95% CI)</text><text x="{L}" y="{Hh - 6}" fill="#5c6b80">PM interval (run-hours between preventive maintenances)</text></svg>')
    f = lambda t, d=2: f"{t[0]:.{d}f} [{t[1]:.{d}f}, {t[2]:.{d}f}]"
    best = max(range(len(rows)), key=lambda i: rows[i]["thr"][0])
    body = "".join(f"<tr{HL if i == best else ''}><td>{'never' if r['iv'] is None else str(r['iv']) + ' h'}</td><td>{f(r['thr'])}</td><td>{f(r['lt'], 1)}</td><td>{f(r['rep'], 0)}</td><td>{f(r['pm'], 0)}</td><td>{f(r['down'], 0)}</td></tr>" for i, r in enumerate(rows))
    return f"""<!doctype html><html><head><meta charset=utf-8><title>PM interval sweep (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>Preventive maintenance interval sweep (synthetic)</h2><div class=n>Synthetic and illustrative: wear law, repair and PM durations are placeholders. Fixed-interval maintenance as in en.wikipedia.org/wiki/Preventive_maintenance (read 2 Oct 2026), which gives no rule for the interval, so none is claimed. Same seeds in every row; highlighted row = highest mean throughput (differences between neighbouring rows can be inside the CI: look at the whiskers). Hours only, no cost.</div>{''.join(s)}
<table><tr><th>PM interval</th><th>Throughput /week [CI]</th><th>Lead time, days [CI]</th><th>Repair hours, all stages [CI]</th><th>PM hours, all stages [CI]</th><th>Repair + PM hours [CI]</th></tr>{body}</table></body></html>"""
