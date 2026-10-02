"""Pareto of lost resource-hours by cause and stage (synthetic, illustrative).

Concept as read (2 Oct 2026, https://pmc.ncbi.nlm.nih.gov/articles/PMC10228985/): a Pareto chart is a bar graph with the contributing
factors in descending order and a line of the cumulative percentage; where the line reaches 80% the factors to its left account for
that share of the total.
Here the factors are loss causes per stage, in resource-hours inside the measurement window, taken from the simulation statistics:
  repair (breakdowns), setup / changeover, preventive maintenance "PM" (only if configured), blocked (finished lot held because the next
  buffer was full), waiting for material (only if configured).
Choices of this code: queue waiting of lots is NOT a loss of the resource and is excluded; idle time without a lot is not a cause
and is excluded. Hours are resource-hours, so a 2-server stage can add up to twice the window. The 80% marker is a reading aid.
Not modelled: minor stops, operator absence, reason codes entered by people, cost weighting (hours only, not money).
"""
from __future__ import annotations

import html as H
from typing import Dict, List

CAUSES = [("repair", "Repair"), ("setup", "Setup"), ("pm", "PM"), ("blocked", "Blocked"), ("short_hours", "Material wait")]


def losses(plant, res) -> List[Dict]:
    out = []
    for k, sg in enumerate(plant.stages):
        st = res.stats[k]
        for attr, label in CAUSES:
            v = getattr(st, attr, 0.0)
            if v > 1e-9:
                out.append({"stage": sg.name, "cause": label, "hours": v})
    out.sort(key=lambda r: -r["hours"])
    tot = sum(r["hours"] for r in out)
    cum = 0.0
    for r in out:
        cum += r["hours"]
        r["share"] = r["hours"] / tot if tot else 0.0
        r["cum"] = cum / tot if tot else 0.0
    return out


def render_html(rows: List[Dict]) -> str:
    W, Hh, ml, mb, mt = 860, 400, 60, 180, 24
    n = max(len(rows), 1)
    top = max([r["hours"] for r in rows] or [1.0])
    bw = (W - ml - 50) / n
    y = lambda v: mt + (Hh - mt - mb) * (1 - v / top)
    yc = lambda c: mt + (Hh - mt - mb) * (1 - c)
    colors = {"Repair": "#c0392b", "Setup": "#c98a00", "PM": "#2b8a3e", "Blocked": "#845ef7", "Material wait": "#1971c2"}
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">']
    for r_, v in enumerate((0.0, 0.5, 0.8, 1.0)):
        s.append(f'<line x1="{ml}" x2="{W - 50}" y1="{yc(v):.1f}" y2="{yc(v):.1f}" stroke="{"#e03131" if v == 0.8 else "#e3e8ee"}" stroke-dasharray="{"4 3" if v == 0.8 else "0"}"/><text x="{W - 46}" y="{yc(v) + 4:.1f}" fill="#5c6b80">{int(v * 100)}%</text>')
    pts = []
    for i, r in enumerate(rows):
        x = ml + i * bw
        s.append(f'<rect x="{x + 3:.1f}" y="{y(r["hours"]):.1f}" width="{bw - 6:.1f}" height="{y(0) - y(r["hours"]):.1f}" fill="{colors.get(r["cause"], "#888")}"><title>{H.escape(r["stage"])} - {r["cause"]}: {r["hours"]:.0f} h ({r["share"]:.1%})</title></rect>')
        s.append(f'<text transform="translate({x + bw / 2:.1f},{Hh - mb + 8}) rotate(60)" fill="#26324a">{H.escape(r["stage"])} - {r["cause"]}</text>')
        pts.append(f"{x + bw / 2:.1f},{yc(r['cum']):.1f}")
    if pts:
        s.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#14213d" stroke-width="2"/>' + "".join(f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="3" fill="#14213d"/>' for p in pts))
    s.append(f'<text x="4" y="12" fill="#5c6b80">hours</text><text x="4" y="{y(0):.1f}" fill="#5c6b80">0</text><text x="4" y="{y(top) + 12:.1f}" fill="#5c6b80">{top:.0f}</text></svg>')
    tot = sum(r["hours"] for r in rows)
    k80 = next((i + 1 for i, r in enumerate(rows) if r["cum"] >= 0.8), len(rows))
    tr = "".join(f"<tr><td>{H.escape(r['stage'])}</td><td>{r['cause']}</td><td>{r['hours']:,.0f}</td><td>{r['share']:.1%}</td><td>{r['cum']:.1%}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Pareto of lost hours (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1000px}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>Pareto of lost resource-hours by cause and stage (synthetic)</h2><div class=n>Synthetic and illustrative: fictitious plant, placeholder parameters. Pareto concept as described at pmc.ncbi.nlm.nih.gov/articles/PMC10228985 (read 2 Oct 2026). Hours only, not money. Queue waiting and idle time are not counted as losses. Not modelled: minor stops, operator absence, reason codes entered by people.</div>
<p>Total lost: <b>{tot:,.0f} resource-hours</b> in the window. The first <b>{k80}</b> of {len(rows)} causes reach 80% of it (the red dashed line).</p>{''.join(s)}
<table><tr><th>Stage</th><th>Cause</th><th>Hours</th><th>Share</th><th>Cumulative</th></tr>{tr}</table></body></html>"""
