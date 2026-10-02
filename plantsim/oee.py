"""OEE decomposition per process stage from the simulation (synthetic, illustrative).

Definitions follow the three-factor structure published at https://www.oee.com/oee-factors/ (read 2 Oct 2026): availability is
run time over planned production time, performance and quality are the other two factors, and OEE is their product.
How the factors are computed here (choices made in this code, not taken from the page):
  planned time   = servers x window (the plant is treated as scheduled for the whole window; shift closures and idle
                   time without a lot are NOT removed, so "loading" below shows how much of it had work).
  loaded time    = busy + setup + repair (time the stage had a lot to work on).
  availability A = busy / loaded time          (setup/changeover and repair are the availability losses).
  performance  P = ideal / busy                ideal = nominal mean process time of the stage (the config `hours`) x lots finished
                   at the stage in the window. Because the simulation draws process times around that mean (cv) and may
                   repeat a step (retest_p), P measures that variability and repetition only. It can exceed 1 by chance; it is not clamped.
  quality      Q = 1 - rejected at the stage / lots finished at the stage in the window (a lot is attributed to the last
                   process stage it reached before rejection).
  OEE = A x P x Q (relative to loaded time); OEE on planned time = OEE x loading, loading = loaded / planned.
Not modelled: speed loss from running slower than nominal by choice, minor stops, start-up rejects, rework as a separate loss,
a planned-production-time calendar, per-product ideal cycle times.
"""
from __future__ import annotations

import html as H
from typing import Dict, List


def oee(plant, res) -> List[Dict]:
    lo = res.horizon - res.window
    idx = {k: s for k, s in enumerate(plant.stages) if s.kind == "process"}
    n = {k: 0 for k in idx}
    rej = {k: 0 for k in idx}
    for b in res.batches:
        ks = [i for (i, a, s, e) in b.trace if i in idx]
        for (i, a, s, e) in b.trace:
            if i in idx and lo <= e <= res.horizon:
                n[i] += 1
        if b.rejected and ks and b.done is not None and lo <= b.done <= res.horizon:
            rej[ks[-1]] += 1
    out = []
    for k, sg in idx.items():
        st = res.stats[k]
        planned = max(st.servers, 1) * res.window
        loaded = st.busy + st.setup + st.repair
        A = st.busy / loaded if loaded else 0.0
        ideal = sg.hours * n[k]
        P = ideal / st.busy if st.busy else 0.0
        Q = 1.0 - rej[k] / n[k] if n[k] else 0.0
        out.append({"stage": sg.name, "planned_h": planned, "idle_h": max(planned - loaded, 0.0), "setup_h": st.setup, "repair_h": st.repair,
                    "busy_h": st.busy, "ideal_h": ideal, "lots": n[k], "rejected": rej[k], "loading": loaded / planned if planned else 0.0,
                    "A": A, "P": P, "Q": Q, "OEE": A * P * Q, "OEE_planned": A * P * Q * (loaded / planned if planned else 0.0)})
    return out


def render_html(rows: List[Dict], focus: str = "") -> str:
    f = max(rows, key=lambda r: r["loading"]) if not focus else next(r for r in rows if r["stage"] == focus)
    steps = [("Planned time", f["planned_h"], "#14213d"), ("No lot waiting", -f["idle_h"], "#adb5bd"), ("Setup / changeover", -f["setup_h"], "#c98a00"),
             ("Repair", -f["repair_h"], "#c0392b"), ("Run time (busy)", None, "#00857c"), ("Speed loss (busy - ideal; up = faster)", -(f["busy_h"] - f["ideal_h"]), "#845ef7"),
             ("Rejected lots", -f["ideal_h"] * (f["rejected"] / f["lots"] if f["lots"] else 0), "#e03131"), ("Fully productive", None, "#2b8a3e")]
    W, bh, lw = 760, 24, 250
    tot = f["planned_h"]
    sx = lambda v: lw + (W - lw - 90) * v / tot
    svg = [f'<svg width="{W}" height="{bh * len(steps) + 20}" font-size="11">']
    level = tot
    for i, (name, d, c) in enumerate(steps):
        y = 10 + i * bh
        if name == "Planned time":
            a, b = 0, tot
        elif name == "Run time (busy)":
            a, b = 0, f["busy_h"]; level = f["busy_h"]
        elif name == "Fully productive":
            a, b = 0, level
        else:
            a, b = level + d, level
            level += d
        if b < a:
            a, b = b, a
        svg.append(f'<text x="{lw - 6}" y="{y + 15}" text-anchor="end">{name}</text><rect x="{sx(a):.1f}" y="{y}" width="{max(sx(b) - sx(a), 1):.1f}" height="{bh - 5}" fill="{c}"><title>{name}</title></rect><text x="{sx(b) + 4:.1f}" y="{y + 15}" fill="#5c6b80">{abs(b - a):,.0f} h</text>')
    svg.append("</svg>")
    body = "".join(f"<tr><td>{H.escape(r['stage'])}</td><td>{r['loading']:.0%}</td><td>{r['A']:.1%}</td><td>{r['P']:.1%}</td><td>{r['Q']:.1%}</td><td><b>{r['OEE']:.1%}</b></td><td>{r['OEE_planned']:.1%}</td><td>{r['lots']}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>OEE decomposition (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1000px}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>OEE decomposition per process stage (synthetic)</h2><div class=n>Synthetic and illustrative. Three-factor structure as on oee.com/oee-factors (read 2 Oct 2026); the exact formulas are this code's choices, see the README. Performance compares the simulation's busy time with the configured nominal process time, so it only shows the variability and repeats of the simulation, and can exceed 100%. Not modelled: minor stops, shift calendar, rework, per-product ideal times.</div>
<h3>Loss waterfall of the most loaded stage: {H.escape(f['stage'])} (hours in the window)</h3>{''.join(svg)}
<h3>All process stages</h3><table><tr><th>Stage</th><th>Loading (loaded/planned)</th><th>Availability</th><th>Performance</th><th>Quality</th><th>OEE (loaded time)</th><th>OEE x loading</th><th>Lots</th></tr>{body}</table></body></html>"""
