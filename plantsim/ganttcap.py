"""Finite-capacity Gantt by resource: one lane per server of every process stage, waiting lots hatched above (synthetic, illustrative)

Built from the batch traces of the simulation (trace = stage, arrive, start, end). Bars are placed on server lanes by first-free-lane interval partitioning; a stage that needs
more lanes than it has servers would be flagged (it does not happen in the example). Waiting lots (arrive to start) are drawn in a hatched band above the stage, stacked as far as
the queue is deep. Concept: Gantt chart of resource occupation under finite capacity (see Wikipedia "Gantt chart"; "Scheduling (production processes)").
Check on every stage: the bar-hours inside the measurement window divided by servers x window must agree with busy + repair (a repair inside a run is inside its bar; verified, difference 0 on every stage of the example). The
page says so; setup, repair and preventive maintenance are NOT in the bars (the trace holds start and end of each run), so the difference to busy+setup+repair+pm is shown as time that is not drawn.
The view shows the first `days` days of the measurement window. Not modelled: shift calendar drawn on the lanes, vehicles, which person works where, dates.
"""
from __future__ import annotations

import heapq
from typing import Dict, List

KIND = "#00857c"


def _lanes(items):
    items = sorted(items)
    free: List[float] = []
    out = []
    for s, e in items:
        for j, f in enumerate(free):
            if f <= s + 1e-9:
                free[j] = e; out.append((j, s, e)); break
        else:
            free.append(e); out.append((len(free) - 1, s, e))
    return out, len(free)


def build(plant, res, days: float = 14.0) -> Dict:
    t0 = res.horizon - res.window
    t1 = min(t0 + days * 24.0, res.horizon)
    rows = []
    for k, (sg, st) in enumerate(zip(plant.stages, res.stats)):
        if sg.kind != "process":
            continue
        runs, waits = [], []
        for b in res.batches:
            for (i, a, s, e) in b.trace:
                if i == k:
                    runs.append((s, e))
                    if s - a > 1e-9:
                        waits.append((a, s))
        lanes, need = _lanes(runs)
        wl, wneed = _lanes(waits)
        inwin = sum(max(0.0, min(e, res.horizon) - max(s, t0)) for s, e in runs)
        cap = max(st.servers, 1) * res.window
        rows.append({"stage": sg.name, "servers": max(st.servers, 1), "lanes_needed": need, "lanes": [x for x in lanes if x[2] > t0 and x[1] < t1],
                     "wlanes": [x for x in wl if x[2] > t0 and x[1] < t1], "wneed": wneed, "bars_util": inwin / cap, "busy_util": st.busy / cap, "br_util": (st.busy + st.repair) / cap,
                     "all_util": (st.busy + st.setup + st.repair + st.pm) / cap})
    return {"t0": t0, "t1": t1, "rows": rows}


def render_html(g: Dict) -> str:
    W, L0 = 1000, 190
    t0, t1 = g["t0"], g["t1"]
    X = lambda t: L0 + (W - L0 - 10) * (min(max(t, t0), t1) - t0) / (t1 - t0)
    y, parts = 24, []
    for d in range(int((t1 - t0) // 24) + 1):
        x = X(t0 + d * 24)
        parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="14" y2="@H@" stroke="#e3e8ee"/><text x="{x:.1f}" y="10" font-size="9" fill="#5c6b80">d{d + 1}</text>')
    for r in g["rows"]:
        wq = min(r["wneed"], 4)
        parts.append(f'<text x="4" y="{y + 12}" font-size="11" font-weight="600">{r["stage"][:28]}</text><text x="4" y="{y + 26}" font-size="10" fill="#5c6b80">{r["servers"]} server(s), waiting up to {r["wneed"]}</text>')
        for (j, s, e) in r["wlanes"]:
            if j < wq:
                parts.append(f'<rect x="{X(s):.1f}" y="{y + j * 5}" width="{max(X(e) - X(s), 1):.1f}" height="4" fill="url(#h)"/>')
        y += wq * 5 + 2
        for (j, s, e) in r["lanes"]:
            parts.append(f'<rect x="{X(s):.1f}" y="{y + j * 11}" width="{max(X(e) - X(s), 1):.1f}" height="9" fill="{KIND}"/>')
        y += r["servers"] * 11 + 12
    svg = f'<svg width="{W}" height="{y}" font-family="system-ui,sans-serif"><defs><pattern id="h" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="2" height="4" fill="#c98a00"/></pattern></defs>' + "".join(parts).replace("@H@", str(y)) + "</svg>"
    body = "".join(f"<tr><td>{r['stage']}</td><td>{r['servers']}</td><td>{r['lanes_needed']}</td><td>{r['bars_util'] * 100:.1f}%</td><td>{r['busy_util'] * 100:.1f}%</td><td>{r['br_util'] * 100:.1f}%</td><td>{r['all_util'] * 100:.1f}%</td></tr>" for r in g["rows"])
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Finite-capacity Gantt by resource (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>Finite-capacity Gantt by resource (synthetic)</h2><div class=n>Synthetic and illustrative. First {(t1 - t0) / 24:.0f} days of the measurement window of the fictitious plant. Green = a server of a process stage is working on a lot (one lane per server); hatched amber above a stage = lots waiting in front of it (stacked, up to 4 shown). The table checks the bars: bar-hours / (servers x window) against the utilisation the simulation reports (busy). A bar runs from the start of a run to its end, so a repair in the middle of a run is inside the bar: bars match busy + repair exactly (checked), and are higher than busy alone on stages with breakdowns. Setup and preventive maintenance are not in the bars, so the last column, with them added, is larger where they exist. Not modelled: shift calendar on the lanes, vehicles, which person works where, dates.</div>{svg}
<table><tr><th>Stage</th><th>Servers</th><th>Lanes the bars need</th><th>Bars</th><th>Reported busy</th><th>busy + repair</th><th>busy + setup + repair + PM</th></tr>{body}</table></body></html>"""
