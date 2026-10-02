"""Does using the same seeds for scenario A and B help? (common random numbers check, synthetic)

Idea as read (2 Oct 2026) at https://en.wikipedia.org/wiki/Variance_reduction (section "Common Random Numbers"): when comparing configurations,
use the same random numbers in both; the variance of the difference is Var(X1)+Var(X2)-2Cov(X1,X2), so a positive correlation
between A and B shrinks it, and a negative one makes it worse. The page also says the streams need to be SYNCHRONISED (the same draw used
for the same purpose in every configuration).
This simulator uses ONE random stream per run (a Python random.Random(seed)), so the draws stay aligned only until the two scenarios take
different paths; after that the same seed does not mean the same event. So the benefit is not guaranteed and is measured here:
for each metric, A and B are run with the same seeds (what `--whatif` does) and, as a reference, B is run with other seeds (independent).
Shown: the correlation between A and B over the seeds, and the half-width of the 95% CI of B-A in both ways (same seeds: paired t interval;
other seeds: Welch interval, degrees of freedom by Welch-Satterthwaite, rounded). Fewer is better; ratio < 1 means the same seeds helped.
With n seeds both half-widths are themselves noisy; they are an estimate for this config pair only.
Not done: synchronised streams per purpose (would need one stream per stage and event type).
"""
from __future__ import annotations

import dataclasses
import html as H
import math
from typing import Dict, List

from .whatif import metrics, t_quantile
from .model import simulate


def _run(plant, seeds):
    return [metrics(plant, simulate(dataclasses.replace(plant, seed=s))) for s in seeds]


def _mv(x):
    n = len(x); m = sum(x) / n
    return m, (sum((v - m) ** 2 for v in x) / (n - 1))


def check(a, b, n: int = 10) -> Dict:
    if n < 3:
        raise ValueError("need at least 3 seeds")
    sa = [a.seed + i for i in range(n)]
    ra = _run(a, sa)
    rb_same = _run(b, sa)
    rb_ind = _run(b, [b.seed + 1000 + i for i in range(n)])
    rows = {}
    for k in ra[0]:
        xa, xs, xi = [r[k] for r in ra], [r[k] for r in rb_same], [r[k] for r in rb_ind]
        ma, va = _mv(xa); ms, vs = _mv(xs); mi, vi = _mv(xi)
        d = [y - x for x, y in zip(xa, xs)]
        _, vd = _mv(d)
        hp = t_quantile(0.975, n - 1) * math.sqrt(vd / n)
        se2 = va / n + vi / n
        if se2 > 0:
            df = max(2, round(se2 ** 2 / ((va / n) ** 2 / (n - 1) + (vi / n) ** 2 / (n - 1))))
            hw = t_quantile(0.975, df) * math.sqrt(se2)
        else:
            hw = 0.0
        rho = None
        if va > 0 and vs > 0:
            rho = sum((x - ma) * (y - ms) for x, y in zip(xa, xs)) / ((n - 1) * math.sqrt(va * vs))
        rows[k] = {"rho": rho, "paired": hp, "indep": hw, "ratio": (hp / hw) if hw > 0 else None, "diff": ms - ma}
    return {"n": n, "metrics": rows}


def render_html(c: Dict, title: str = "Same seeds or not? (synthetic)") -> str:
    body = ""
    for k, v in c["metrics"].items():
        rho = "-" if v["rho"] is None else f"{v['rho']:+.2f}"
        ratio = "-" if v["ratio"] is None else f"{v['ratio']:.2f}"
        col = "#868e96" if v["ratio"] is None else ("#00857c" if v["ratio"] < 0.9 else ("#c0392b" if v["ratio"] > 1.1 else "#868e96"))
        w = 0 if v["ratio"] is None else min(v["ratio"], 2.0) * 100
        bar = f'<svg width=220 height=14><rect width=200 height=14 fill="#eef1f5"/><rect width="{w:.0f}" height=14 fill="{col}" opacity=.85/><line x1=100 x2=100 y1=0 y2=14 stroke="#222"/></svg>'
        body += f"<tr><td>{H.escape(k)}</td><td>{rho}</td><td>{v['paired']:.3f}</td><td>{v['indep']:.3f}</td><td>{bar} <b>{ratio}</b></td></tr>"
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{H.escape(title)}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1000px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>{H.escape(title)}</h2><div class=n>Synthetic and illustrative. Common random numbers idea as read at en.wikipedia.org/wiki/Variance_reduction (2 Oct 2026): the same random numbers in both scenarios make the difference less noisy if A and B are positively correlated, and can make it worse if negatively. This simulator has ONE stream per run, so the draws only stay aligned until the scenarios diverge; the benefit is measured here, not assumed. {c['n']} seeds. Column "same seeds" = half-width of the 95% CI of B-A with the same seeds (paired); "other seeds" = same with B on independent seeds (Welch). Ratio below 1 (green) = same seeds helped; the black line marks 1. Half-widths come from few runs and are noisy. Synchronised streams per stage and event type are not implemented.</div>
<table><tr><th>Metric</th><th>Correlation A-B</th><th>CI half-width, same seeds</th><th>CI half-width, other seeds</th><th>Ratio same/other</th></tr>{body}</table></body></html>"""
