"""One-at-a-time sensitivity (tornado) of a result to the placeholder parameters (synthetic, illustrative).

Method as read (2 Oct 2026) at https://docs.analytica.com/index.php/Tornado_charts and
https://help.goldsim.com/Content/GS/sensitivityanalysistornadochart.htm : vary one input at a time to a low and a high value while all
others stay at their nominal values; show the result range per input as a bar, with the inputs sorted by the size of that range
(the largest on top, hence the "tornado"). Analytica lists "all inputs varied by the same relative amount" (e.g. 90% / 110%) as one
way to choose the low/high values; this code uses that option, default plus and minus 20%.
Inputs varied (only those that are non-zero in the config): per process stage the mean process time, changeover, breakdown probability and
repair time; the release interval of the plant. Each setting is simulated over the same seeds (consecutive, as in whatif.py) and the
mean over seeds is plotted. A bar shorter than twice the 95% half-width of the nominal mean is marked "within noise" (a rule of
this code; the paired seeds make it conservative). Interactions between inputs are not seen by this method.
Not modelled: varying several inputs together, parameter ranges from real data, categorical inputs (dispatch rule, layout).
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List

from .model import Stage
from .whatif import mean_ci, metrics, replicate

KEYS = [("Throughput (batches/week)", "thr", "{:.2f}"), ("Mean lead time (days)", "lt", "{:.2f}")]
STAGE_PARAMS = ("hours", "changeover", "breakdown_p", "repair")


def _with(plant, si, attr, factor):
    if si is None:
        return dataclasses.replace(plant, release_every=plant.release_every * factor)
    st = list(plant.stages)
    st[si] = dataclasses.replace(st[si], **{attr: getattr(st[si], attr) * factor})
    return dataclasses.replace(plant, stages=st)


def run(plant, pct: float = 0.2, n: int = 10) -> Dict:
    if not 0 < pct < 1:
        raise ValueError("pct must be between 0 and 1")
    nom = replicate(plant, n)
    base = {}
    for k, short, _ in KEYS:
        m, lo, hi, _ = mean_ci([r[k] for r in nom])
        base[short] = {"mean": m, "half": (hi - lo) / 2}
    rows = []
    items = [(None, "release_every", "Plant: release interval")]
    for i, s in enumerate(plant.stages):
        if s.kind != "process":
            continue
        for a in STAGE_PARAMS:
            if getattr(s, a) > 0:
                items.append((i, a, f"{s.name}: {a}"))
    for si, attr, label in items:
        row = {"label": label}
        for k, short, _ in KEYS:
            vals = []
            for f in (1 - pct, 1 + pct):
                rs = replicate(_with(plant, si, attr, f), n)
                vals.append(sum(r[k] for r in rs) / n)
            row[short] = {"low": vals[0], "high": vals[1], "range": abs(vals[1] - vals[0]), "noise": abs(vals[1] - vals[0]) < 2 * base[short]["half"]}
        rows.append(row)
    return {"pct": pct, "n": n, "base": base, "rows": rows}


def render_html(a: Dict) -> str:
    import html as H
    def chart(short, title, fmt):
        rows = sorted(a["rows"], key=lambda r: -r[short]["range"])[:14]
        W, bh, lw = 640, 20, 220
        b = a["base"][short]["mean"]
        span = max(max(abs(r[short]["low"] - b), abs(r[short]["high"] - b)) for r in rows) * 1.1 or 1
        X = lambda v: lw + (W - lw - 20) * ((v - b) / span + 1) / 2
        s = [f'<h3>{title} (nominal {fmt.format(b)})</h3><svg width="{W}" height="{len(rows) * bh + 24}" font-size="11"><line x1="{X(b):.1f}" x2="{X(b):.1f}" y1="4" y2="{len(rows) * bh + 6}" stroke="#222"/>']
        for i, r in enumerate(rows):
            d = r[short]; y = 8 + i * bh
            for v, c in ((d["low"], "#74c0fc"), (d["high"], "#1864ab")):
                x0, x1 = sorted((X(b), X(v)))
                s.append(f'<rect x="{x0:.1f}" y="{y}" width="{max(x1 - x0, 1):.1f}" height="{bh - 6}" fill="{c}" opacity="{0.45 if d["noise"] else 0.95}"><title>{H.escape(r["label"])}: {fmt.format(v)}</title></rect>')
            s.append(f'<text x="{lw - 6}" y="{y + 12}" text-anchor="end" fill="{"#868e96" if d["noise"] else "#000"}">{H.escape(r["label"])}</text>')
        s.append("</svg>")
        return "".join(s)
    pc = int(round(a["pct"] * 100))
    srt = sorted(a["rows"], key=lambda r: -r["thr"]["range"])
    dom = (f"<p><b>Reading:</b> {H.escape(srt[0]['label'])} moves throughput {srt[0]['thr']['range'] / max(srt[1]['thr']['range'], 1e-9):.0f} times more than the next input. When the release interval dominates, the plant is limited by how much work is released, not by its machines (in this model, with these placeholders).</p>"
           if len(srt) > 1 and srt[0]["thr"]["range"] > 3 * srt[1]["thr"]["range"] else "")
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Sensitivity (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:900px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>One-at-a-time sensitivity: tornado (synthetic)</h2><div class=n>Synthetic and illustrative: every parameter is a placeholder, so this shows which placeholders the result is most sensitive to, not what a real plant would do. Method as described at docs.analytica.com (Tornado charts) and help.goldsim.com (tornado chart), read 2 Oct 2026: one input at a time to -{pc}% (light blue) and +{pc}% (dark blue) of nominal, the rest nominal, sorted by range. Mean over the same {a['n']} seeds. Grey faded names/bars: range smaller than twice the 95% half-width of the nominal mean ("within noise", a rule of this code). Interactions are not seen. This is where real data would matter most: measure the top bars first.</div>{dom}{chart('thr', 'Throughput (batches/week)', '{:.2f}')}{chart('lt', 'Mean lead time (days)', '{:.2f}')}</body></html>"""
