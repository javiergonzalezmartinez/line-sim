"""Shifting bottleneck detector: active period method applied to the simulated batch traces (synthetic).

Method: Roser, Nakano, Tanaka, "Shifting Bottleneck Detection" (Winter Simulation Conference 2002, preprint read 2 Oct 2026:
https://www.allaboutlean.com/wp-content/uploads/2015/02/2002_WSC-Shifting-Bottleneck-Detection-Preprint.pdf).
As read there: a machine is active while working or in repair, inactive while waiting; the active periods without interruption
are compared, and the machine with the longest active period at a given moment is the momentary bottleneck. With historical or
simulation data the full duration of every active period is known.
How it is applied here (choices of this code):
  * a "machine" is a process stage; its active periods are the merged busy intervals [start, end] of all lots in that stage
    (union over the stage's servers, so a multi-server stage counts as active while any server works). The union lengthens
    periods of multi-server stages compared with a single machine.
  * setup/changeover time is not in the traces, so it is neither active nor inactive here; it appears as a gap between periods.
  * the momentary bottleneck is sampled every `step_h` hours (default 1 h) inside the window after warm-up. If the longest and
    second-longest active periods differ by less than `margin` (relative, default 5%), the moment is labelled "unclear".
  * a shift is a change of the momentary bottleneck between two consecutive clear moments; "unclear" moments do not count as a shift.
Not modelled: transport and wait stages as machines, tool changes, a real-time (forward-looking) variant, a statistical test.
"""
from __future__ import annotations

import html as H
from typing import Dict, List, Tuple


def active_periods(plant, res) -> Dict[str, List[Tuple[float, float]]]:
    out = {}
    for k, sg in enumerate(plant.stages):
        if sg.kind != "process":
            continue
        iv = sorted((s, e) for b in res.batches for (i, a, s, e) in b.trace if i == k and e > s)
        merged: List[List[float]] = []
        for s, e in iv:
            if merged and s <= merged[-1][1] + 1e-9:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        out[sg.name] = [(s, e) for s, e in merged]
    return out


def detect(plant, res, step_h: float = 1.0, margin: float = 0.05) -> Dict:
    ap = active_periods(plant, res)
    t0 = res.horizon - res.window
    n = int(res.window / step_h)
    ptr = {k: 0 for k in ap}
    seq: List[str] = []
    for j in range(n):
        t = t0 + (j + 0.5) * step_h
        best = []
        for name, per in ap.items():
            i = ptr[name]
            while i < len(per) and per[i][1] < t:
                i += 1
            ptr[name] = i
            if i < len(per) and per[i][0] <= t < per[i][1]:
                best.append((per[i][1] - per[i][0], name))
        best.sort(reverse=True)
        if not best:
            seq.append("none")
        elif len(best) > 1 and (best[0][0] - best[1][0]) < margin * best[0][0]:
            seq.append("unclear")
        else:
            seq.append(best[0][1])
    share: Dict[str, float] = {}
    for s in seq:
        share[s] = share.get(s, 0) + 1
    share = {k: v / n for k, v in share.items()}
    shifts, last = 0, None
    for s in seq:
        if s in ("unclear", "none"):
            continue
        if last is not None and s != last:
            shifts += 1
        last = s
    return {"seq": seq, "share": share, "shifts": shifts, "step_h": step_h, "margin": margin, "t0": t0, "periods": {k: len(v) for k, v in ap.items()}}


_PAL = ["#00857c", "#4c6ef5", "#c98a00", "#c0392b", "#845ef7", "#2b8a3e", "#e8590c", "#1098ad", "#d6336c"]


def render_html(d: Dict, title: str = "Shifting bottleneck (synthetic)") -> str:
    names = sorted(k for k in d["share"] if k not in ("unclear", "none"))
    col = {n: _PAL[i % len(_PAL)] for i, n in enumerate(names)}
    col["unclear"], col["none"] = "#ced4da", "#f1f3f5"
    seq, W = d["seq"], 1100
    rects, i = [], 0
    while i < len(seq):
        j = i
        while j < len(seq) and seq[j] == seq[i]:
            j += 1
        rects.append(f'<rect x="{W * i / len(seq):.1f}" y="0" width="{max(W * (j - i) / len(seq), 0.6):.1f}" height="34" fill="{col[seq[i]]}"><title>{H.escape(seq[i])}: {(j - i) * d["step_h"]:.0f} h</title></rect>')
        i = j
    days = len(seq) * d["step_h"] / 24
    ticks = "".join(f'<text x="{W * x / days:.0f}" y="50" font-size="10" fill="#5c6b80">{x:.0f} d</text>' for x in range(0, int(days) + 1, 14))
    rows = "".join(f'<tr><td><i style="background:{col[k]}"></i>{H.escape(k)}</td><td>{v:.1%}</td><td>{d["periods"].get(k, "-")}</td></tr>' for k, v in sorted(d["share"].items(), key=lambda x: -x[1]))
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{title}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1160px}}table{{border-collapse:collapse;width:520px}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}td i{{display:inline-block;width:10px;height:10px;margin-right:6px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>{title}</h2><div class=n>Synthetic and illustrative. Active period method of Roser, Nakano and Tanaka (WSC 2002, preprint read 2 Oct 2026) applied to simulated busy intervals, sampled every {d['step_h']:g} h; moments where the two longest active periods differ by less than {d['margin']:.0%} are "unclear". Setup time is not in the traces. Multi-server stages are treated as active while any server works.</div>
<p><b>{d['shifts']}</b> shifts of the momentary bottleneck between clear moments.</p><svg width="{W}" height="60">{''.join(rects)}{ticks}</svg>
<h3>Share of time as momentary bottleneck</h3><table><tr><th>Stage</th><th>Share of time</th><th>Active periods</th></tr>{rows}</table></body></html>"""
