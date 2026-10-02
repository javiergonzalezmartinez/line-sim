"""How many replications are enough? Confidence interval method (synthetic, illustrative).

Method as read (2 Oct 2026) at https://pythonhealthdatascience.github.io/des_rap_book/pages/guide/output_analysis/n_reps.html :
run replications one after another, after each one compute the confidence interval of the mean, and look at its half-width relative
to the mean; the smallest number of replications (above a minimum) where that relative half-width falls below the desired precision
(that page uses 0.1 = 10%) is the answer for that performance measure. The page cites the automated procedure of Hoad, Robinson and
Davies (Automated selection of the number of replications for a discrete-event simulation, J. Operational Research Society, 2010;
only the abstract page was seen, not its full text, so this code does not implement their look-ahead rule).
Here: 95% interval with the t distribution (as in whatif.py), minimum 5 replications, default precision 5%, up to `max_n` replications
with consecutive seeds. Two numbers per measure: "first n" (first time under the target) and "stable from n" (under the target for every
n from there to max_n; the second one is an addition of this code to avoid stopping at a lucky early dip).
A measure whose mean is close to 0 has a huge relative half-width; it is flagged instead of forced.
Not modelled: sequential stopping inside a running experiment, correlated replications, common random numbers between scenarios.
"""
from __future__ import annotations

import dataclasses
import math
from typing import Dict, List, Optional

from .whatif import mean_ci, metrics
from .model import simulate


def run(plant, max_n: int = 40, precision: float = 0.05, min_n: int = 5) -> Dict:
    if max_n < min_n or min_n < 3:
        raise ValueError("need 3 <= min_n <= max_n")
    series: Dict[str, List[float]] = {}
    for i in range(max_n):
        m = metrics(plant, simulate(dataclasses.replace(plant, seed=plant.seed + i)))
        for k, v in m.items():
            series.setdefault(k, []).append(v)
    out = {"precision": precision, "min_n": min_n, "max_n": max_n, "measures": []}
    for k, xs in series.items():
        rel: List[Optional[float]] = []
        for n in range(1, max_n + 1):
            if n < min_n:
                rel.append(None); continue
            m, lo, hi, _ = mean_ci(xs[:n])
            rel.append(((hi - lo) / 2) / abs(m) if abs(m) > 1e-9 else None)
        ok = [(r is not None and r <= precision) for r in rel]
        first = next((i + 1 for i, o in enumerate(ok) if o), None)
        stable = None
        for i in range(max_n - 1, min_n - 2, -1):
            if ok[i]:
                stable = i + 1
            else:
                break
        out["measures"].append({"name": k, "mean": sum(xs) / len(xs), "rel": rel, "first": first, "stable": stable if first else None, "near_zero": abs(sum(xs) / len(xs)) <= 1e-9})
    return out


def render_html(a: Dict) -> str:
    import html as H
    W, Hh, L, B = 760, 300, 55, 28
    ms = [m for m in a["measures"] if not m["near_zero"]]
    top = min(max((r for m in ms for r in m["rel"] if r is not None), default=0.1), 0.3)
    X = lambda n: L + (W - L - 20) * (n - 1) / max(a["max_n"] - 1, 1)
    Y = lambda v: 14 + (Hh - B - 14) * (1 - min(v, top) / top)
    pal = ["#1971c2", "#c0392b", "#2b8a3e", "#c98a00", "#845ef7", "#0b7285", "#868e96", "#e8590c", "#5f3dc4", "#364fc7", "#a61e4d"]
    s = [f'<svg width="{W}" height="{Hh}" font-size="11"><line x1="{L}" x2="{W - 20}" y1="{Y(a["precision"]):.1f}" y2="{Y(a["precision"]):.1f}" stroke="#e03131" stroke-dasharray="5 3"/><text x="{W - 150}" y="{Y(a["precision"]) - 4:.1f}" fill="#e03131">target {a["precision"]:.0%}</text>']
    for j, m in enumerate(ms):
        pts = " ".join(f"{X(n + 1):.1f},{Y(r):.1f}" for n, r in enumerate(m["rel"]) if r is not None)
        if pts:
            s.append(f'<polyline points="{pts}" fill="none" stroke="{pal[j % len(pal)]}" stroke-width="1.8"><title>{H.escape(m["name"])}</title></polyline>')
    s.append(f'<text x="{L}" y="{Hh - 8}" fill="#5c6b80">number of replications (up to {a["max_n"]})</text><text x="4" y="12" fill="#5c6b80">CI half-width / mean (capped at {top:.0%})</text></svg>')
    leg = "".join(f'<span style="color:{pal[j % len(pal)]};margin-right:12px">&#9632; {H.escape(m["name"])}</span>' for j, m in enumerate(ms))
    rows = "".join(f"<tr><td>{H.escape(m['name'])}</td><td>{m['mean']:,.3f}</td><td>{m['first'] if m['first'] else 'not reached'}</td><td>{m['stable'] if m['stable'] else ('not reached' if not m['first'] else 'dips under, does not stay')}</td><td>{'mean is about 0: relative width meaningless' if m['near_zero'] else ''}</td></tr>" for m in a["measures"])
    worst = max((m["stable"] or a["max_n"] + 1) for m in a["measures"] if not m["near_zero"])
    return f"""<!doctype html><html><head><meta charset=utf-8><title>How many replications (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:920px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>How many replications are enough? (synthetic)</h2><div class=n>Synthetic and illustrative. Confidence interval method as described in the DES RAP book (pythonhealthdatascience.github.io, n_reps page, read 2 Oct 2026): the first number of replications where the 95% interval half-width is within {a['precision']:.0%} of the mean. "Stable from" is an addition of this code (stays under the target up to {a['max_n']} replications). The Hoad, Robinson and Davies paper is cited there; only its abstract page was seen, its look-ahead rule is not implemented.</div><p>{'All measures reach the target by <b>%d</b> replications.' % worst if worst <= a['max_n'] else 'Some measures do <b>not</b> reach the target within %d replications.' % a['max_n']}</p>{''.join(s)}<p>{leg}</p>
<table><tr><th>Measure</th><th>Mean</th><th>First n under target</th><th>Stable from n</th><th>Note</th></tr>{rows}</table></body></html>"""
