"""Flow views from the batch traces of the simulation: utilisation heat map, Sankey-style material flow, Gantt of lots.

Source data: each batch has a trace of (stage index, arrive, start, end) in simulated hours. Everything is synthetic.
Heat map: occupied share of each process stage per time bucket = sum of overlap of [start, end] with the bucket, divided by
servers x bucket length. The [start, end] interval can include repair or setup time inside the stage, so this is "occupied",
not "value-adding". Stages with unlimited servers are shown against the configured server count of the stage.
Material flow: widths are lot counts, drawn between the process stages only (transport and wait stages are skipped so the
diagram stays readable); a lot is counted at a stage if its trace reaches that stage. Lots that stop before the end are
either rejected (at the last stage they reached) or still in progress at the end of the run.
Gantt: first N finished lots; grey = waiting in front of a stage (arrive to start), colour = in the stage, by stage kind.
Not modelled in these views: shift calendars on the axis, calendar dates, setup/repair split inside a bar, transport vehicles.
"""
from __future__ import annotations

import html as H
from typing import Dict, List

KIND_COL = {"process": "#00857c", "move": "#4c6ef5", "wait": "#c98a00", "hold": "#c0392b", "wave": "#845ef7"}


def heatmap(plant, res, buckets: int = 12) -> Dict:
    T = res.horizon
    w = T / buckets
    rows = []
    for k, (sg, st) in enumerate(zip(plant.stages, res.stats)):
        if sg.kind != "process":
            continue
        occ = [0.0] * buckets
        for b in res.batches:
            for (i, arr, s, e) in b.trace:
                if i != k:
                    continue
                for j in range(buckets):
                    lo, hi = j * w, (j + 1) * w
                    ov = min(e, hi) - max(s, lo)
                    if ov > 0:
                        occ[j] += ov
        cap = max(st.servers, 1) * w
        rows.append({"stage": sg.name, "servers": max(st.servers, 1), "util": [o / cap for o in occ]})
    return {"bucket_h": w, "rows": rows}


def flow(plant, res) -> Dict:
    idx = [k for k, s in enumerate(plant.stages) if s.kind == "process"]
    reached = {k: 0 for k in idx}
    for b in res.batches:
        seen = {i for (i, *_r) in b.trace}
        for k in idx:
            if k in seen:
                reached[k] += 1
    total = len(res.batches)
    rejected_at, unfinished_at = {k: 0 for k in idx}, {k: 0 for k in idx}
    finished = 0
    last_k = idx[-1]
    for b in res.batches:
        if b.done is not None and not b.rejected:
            finished += 1
            continue
        pk = [k for k in idx if k in {i for (i, *_r) in b.trace}]
        if not pk:
            continue
        (rejected_at if b.rejected else unfinished_at)[pk[-1]] += 1
    return {"total": total, "stages": [(plant.stages[k].name, reached[k], rejected_at[k], unfinished_at[k]) for k in idx], "finished": finished}


def gantt(plant, res, n: int = 8) -> Dict:
    lots = [b for b in res.batches if b.done is not None and not b.rejected][:n]
    return {"lots": [{"id": b.id, "product": b.product, "bars": [{"stage": plant.stages[i].name, "kind": plant.stages[i].kind, "arrive": a, "start": s, "end": e} for (i, a, s, e) in b.trace]} for b in lots]}


def _heat_col(u):
    u = max(0.0, min(1.0, u))
    r, g, b = int(240 - 240 * u), int(244 - 159 * u), int(248 - 124 * u)
    return f"rgb({r},{g},{b})"


def render_html(plant, res, buckets: int = 12, n_lots: int = 8) -> str:
    h = heatmap(plant, res, buckets)
    f = flow(plant, res)
    g = gantt(plant, res, n_lots)
    # heat map
    cw, rh, lw = 54, 22, 190
    hs = [f'<svg width="{lw + cw * buckets + 10}" height="{rh * len(h["rows"]) + 40}" font-size="11">']
    for j in range(buckets):
        hs.append(f'<text x="{lw + j * cw + cw / 2}" y="14" text-anchor="middle" fill="#5c6b80">{j * h["bucket_h"] / 24:.0f}-{(j + 1) * h["bucket_h"] / 24:.0f} d</text>')
    for r, row in enumerate(h["rows"]):
        y = 24 + r * rh
        hs.append(f'<text x="{lw - 6}" y="{y + 15}" text-anchor="end">{H.escape(row["stage"])}</text>')
        for j, u in enumerate(row["util"]):
            hs.append(f'<rect x="{lw + j * cw}" y="{y}" width="{cw - 2}" height="{rh - 2}" fill="{_heat_col(u)}"><title>{row["stage"]}: {u:.0%}</title></rect><text x="{lw + j * cw + cw / 2 - 1}" y="{y + 14}" text-anchor="middle" fill="{"#fff" if u > 0.55 else "#14213d"}">{u:.0%}</text>')
    hs.append("</svg>")
    # sankey-style flow
    st = f["stages"]
    sw, gap, hh, top = 64, 60, 190, 30
    W = 20 + len(st) * (sw + gap)
    sc = (hh - 10) / max(f["total"], 1)
    ss = [f'<svg width="{W}" height="{hh + top + 70}" font-size="11">']
    prev = None
    for i, (name, n, rej, unf) in enumerate(st):
        x = 10 + i * (sw + gap)
        ss.append(f'<rect x="{x}" y="{top}" width="14" height="{n * sc:.1f}" fill="#00857c"/><text x="{x}" y="{top - 14}" font-size="10">{H.escape(name[:22])}</text><text x="{x}" y="{top - 3}" fill="#5c6b80">{n} lots</text>')
        if prev is not None:
            px, pn = prev
            ss.append(f'<path d="M{px + 14},{top} C{px + 14 + gap / 2 + sw / 2},{top} {x - gap / 2 - sw / 2},{top} {x},{top} L{x},{top + n * sc:.1f} C{x - gap / 2 - sw / 2},{top + n * sc:.1f} {px + 14 + gap / 2 + sw / 2},{top + pn * sc:.1f} {px + 14},{top + pn * sc:.1f} Z" fill="#00857c" opacity=".22"/>')
        if rej or unf:
            yy = top + n * sc + 8
            ss.append(f'<rect x="{x}" y="{yy:.1f}" width="14" height="{max((rej + unf) * sc, 2):.1f}" fill="#c0392b"/><text x="{x + 20}" y="{yy + 10:.1f}" fill="#c0392b">{rej} rejected, {unf} in progress</text>')
        prev = (x, n)
    ss.append("</svg>")
    # gantt
    tmax = max((b["end"] for l in g["lots"] for b in l["bars"]), default=1.0)
    gw, gl, gr = 900, 70, 20
    sx = lambda t: gl + (gw - gl - gr) * t / tmax
    gs = [f'<svg width="{gw}" height="{len(g["lots"]) * 26 + 50}" font-size="11">']
    for l, lot in enumerate(g["lots"]):
        y = 14 + l * 26
        gs.append(f'<text x="{gl - 8}" y="{y + 12}" text-anchor="end">LOT {lot["id"]}</text>')
        for b in lot["bars"]:
            if b["start"] > b["arrive"] + 1e-9:
                gs.append(f'<rect x="{sx(b["arrive"]):.1f}" y="{y + 6}" width="{max(sx(b["start"]) - sx(b["arrive"]), 0.5):.1f}" height="4" fill="#ced4da"><title>waiting before {H.escape(b["stage"])}: {b["start"] - b["arrive"]:.1f} h</title></rect>')
            gs.append(f'<rect x="{sx(b["start"]):.1f}" y="{y}" width="{max(sx(b["end"]) - sx(b["start"]), 0.8):.1f}" height="16" fill="{KIND_COL.get(b["kind"], "#868e96")}"><title>{H.escape(b["stage"])} ({b["kind"]}): {b["end"] - b["start"]:.1f} h</title></rect>')
    for t in range(0, int(tmax) + 1, 24 * 14):
        gs.append(f'<line x1="{sx(t):.1f}" x2="{sx(t):.1f}" y1="8" y2="{len(g["lots"]) * 26 + 12}" stroke="#e6ebf1"/><text x="{sx(t):.1f}" y="{len(g["lots"]) * 26 + 28}" text-anchor="middle" fill="#5c6b80">{t / 24:.0f} d</text>')
    gs.append("</svg>")
    leg = "".join(f'<span><i style="background:{c}"></i>{k}</span>' for k, c in KIND_COL.items()) + '<span><i style="background:#ced4da"></i>waiting</span>'
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Flow views (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1240px}}h3{{margin:18px 0 4px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}.l span{{margin-right:12px}}.l i{{display:inline-block;width:10px;height:10px;margin-right:4px}}.sc{{overflow-x:auto}}</style></head><body><h2>Flow views of the fictitious plant (synthetic)</h2><div class=n>Synthetic and illustrative. Built from the simulated batch traces. Heat map = occupied share of each process stage per time bucket (may include repair or setup inside the stage). Material flow = lot counts between process stages only. Gantt = first {len(g['lots'])} finished lots. Not modelled in the views: shift calendar, dates, setup/repair split, vehicles.</div>
<h3>Utilisation heat map (occupied share, {h['bucket_h'] / 24:.1f}-day buckets)</h3><div class=sc>{''.join(hs)}</div>
<h3>Material flow between process stages ({f['total']} lots released, {f['finished']} finished)</h3><div class=sc>{''.join(ss)}</div>
<h3>Gantt of the first finished lots</h3><div class=l>{leg}</div><div class=sc>{''.join(gs)}</div></body></html>"""
