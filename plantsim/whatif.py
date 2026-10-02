"""What-if comparator: scenario A vs scenario B over N replications (seeds), with 95% confidence intervals.

Each scenario is simulated with seeds seed, seed+1, ... seed+N-1 (independent replications). For every metric:
  * mean and 95% confidence interval of each scenario: mean +/- t(0.975, N-1) * s / sqrt(N)
    (NIST/SEMATECH e-Handbook of Statistical Methods, 7.2.2.1 confidence interval approach,
     https://itl.nist.gov/div898/handbook/prc/section2/prc221.htm, read 2 Oct 2026);
  * the paired difference B - A per seed, its mean and 95% confidence interval (same handbook, 7.3.1.1 analysis of paired
    observations, https://www.itl.nist.gov/div898/handbook/prc/section3/prc311.htm, read 2 Oct 2026). The difference is
    called "clear" when that interval does not contain 0.
Caveat: the two scenarios use the same seed numbers but different structures, so their random streams are not synchronised;
pairing by seed is a valid way to form differences but does not guarantee a variance reduction.
The Student t quantile is computed here (regularised incomplete beta, bisection), standard library only.
Metrics come from the plant model (throughput after warm-up, lead time, rejected lots, busiest-stage utilisation, blocked hours).
Not modelled: common random numbers across structures, multiple-comparison correction, sequential stopping.
"""
from __future__ import annotations

import dataclasses
import json
import math
from typing import Dict, List

from .model import simulate


def _betacf(a, b, x):
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        dl = d * c
        h *= dl
        if abs(dl - 1.0) < 1e-14:
            break
    return h


def _ibeta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    p = 0.5 * _ibeta(df / 2.0, 0.5, x)
    return 1.0 - p if t > 0 else p


def t_quantile(p: float, df: int) -> float:
    """Student t quantile by bisection on the CDF (p in (0.5, 1))."""
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def mean_ci(xs: List[float], conf: float = 0.95):
    n = len(xs)
    m = sum(xs) / n
    if n < 2:
        return m, float("nan"), float("nan"), float("nan")
    s = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    h = t_quantile(0.5 + conf / 2, n - 1) * s / math.sqrt(n)
    return m, m - h, m + h, s


def metrics(plant, res) -> Dict[str, float]:
    util = max(sum(res.utilisation(st).values()) for st in res.stats)
    m = {"Throughput (batches/week)": res.throughput_per_week, "Mean lead time (days)": res.mean_lead_time_days,
            "Rejected lots (window)": float(res.rejected), "Busiest stage utilisation": util,
            "Blocked resource-hours": sum(st.blocked for st in res.stats),
            "Setup hours (all stages)": sum(st.setup for st in res.stats), "Repair hours (all stages)": sum(st.repair for st in res.stats), "Preventive maintenance hours": sum(st.pm for st in res.stats), "Longest queue wait (h)": max(st.max_queue_wait for st in res.stats)}
    return _with_due(plant, res, m)


def _with_due(plant, res, m):
    if plant.due_h is not None:
        late = [b.done - plant.due_date(b) for b in res.finished if res.horizon - res.window <= b.done <= res.horizon]
        if late:
            m["Tardy lots (share)"] = sum(1 for x in late if x > 0) / len(late)
            m["Mean tardiness (h)"] = sum(max(x, 0.0) for x in late) / len(late)
            m["Maximum lateness (h)"] = max(late)
    return m


def replicate(plant, n: int) -> List[Dict[str, float]]:
    out = []
    for i in range(n):
        out.append(metrics(plant, simulate(dataclasses.replace(plant, seed=plant.seed + i))))
    return out


def _need_n(n, md, hd):
    """Rough planning figure: the CI half-width shrinks like 1/sqrt(n) (NIST e-Handbook 7.2.2.1: half-width = t*s/sqrt(n)), so if the observed
    mean difference were the true one, about n*(half-width/|mean diff|)^2 seeds would make the interval just exclude 0 (t quantile change ignored).
    Returns None when the difference is about 0 (nothing to plan for) or the interval already excludes 0."""
    h = hd - md
    if abs(md) < 1e-12 or h <= 0 or abs(md) > h:
        return None
    return int(math.ceil(n * (h / abs(md)) ** 2))


def compare(plant_a, plant_b, n: int = 20) -> Dict:
    if n < 2:
        raise ValueError("need at least 2 replications")
    ra, rb = replicate(plant_a, n), replicate(plant_b, n)
    rows = {}
    for k in ra[0]:
        xa, xb = [r[k] for r in ra], [r[k] for r in rb]
        d = [b - a for a, b in zip(xa, xb)]
        ma, la, ha, _ = mean_ci(xa)
        mb, lb, hb, _ = mean_ci(xb)
        md, ld, hd, _ = mean_ci(d)
        rows[k] = {"A": (ma, la, ha), "B": (mb, lb, hb), "diff": (md, ld, hd), "clear": abs(md) > 1e-12 and not (ld <= 0 <= hd), "need_n": _need_n(n, md, hd)}
    return {"n": n, "metrics": rows}


def render_html(cmp: Dict, name_a: str = "A", name_b: str = "B", note_a: str = "", note_b: str = "", title: str = "What-if: scenario A vs B (synthetic)") -> str:
    import html as H
    rows = ""
    for k, v in cmp["metrics"].items():
        (ma, la, ha), (mb, lb, hb), (md, ld, hd) = v["A"], v["B"], v["diff"]
        lo = min(la, lb, 0.0 if min(la, lb) > 0 else min(la, lb))
        hi = max(ha, hb) * 1.05 or 1.0
        X = lambda x: 20 + 380 * (x - lo) / ((hi - lo) or 1)
        bar = lambda m, l, h, y, c: f'<rect x="20" y="{y}" width="{max(1, X(m) - 20):.1f}" height="12" fill="{c}"/><line x1="{X(l):.1f}" x2="{X(h):.1f}" y1="{y + 6}" y2="{y + 6}" stroke="#222" stroke-width="2"/><line x1="{X(l):.1f}" x2="{X(l):.1f}" y1="{y + 1}" y2="{y + 11}" stroke="#222"/><line x1="{X(h):.1f}" x2="{X(h):.1f}" y1="{y + 1}" y2="{y + 11}" stroke="#222"/>'
        svg = f'<svg width=420 height=44>{bar(ma, la, ha, 4, "#868e96")}{bar(mb, lb, hb, 24, "#00857c")}</svg>'
        nn = v.get("need_n")
        verdict = '<b style="color:#00857c">clear</b>' if v["clear"] else '<span style="color:#868e96">not clear (CI includes 0)</span>' + (f'<br><small>if this difference were real, about {nn} seeds would show it (rough planning figure, not evidence)</small>' if nn else '')
        rows += f"<tr><td>{H.escape(k)}</td><td>{svg}</td><td>{ma:.3f} [{la:.3f}, {ha:.3f}]</td><td>{mb:.3f} [{lb:.3f}, {hb:.3f}]</td><td><b>{md:+.3f}</b> [{ld:+.3f}, {hd:+.3f}]</td><td>{verdict}</td></tr>"
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{H.escape(title)}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1180px}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea;vertical-align:middle}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>{H.escape(title)}</h2><div class=n>Synthetic and illustrative. {cmp['n']} replications per scenario (seeds consecutive), 95% confidence intervals from the t distribution (NIST/SEMATECH e-Handbook 7.2.2.1 and 7.3.1.1). Grey bar = A ({H.escape(name_a)}) {H.escape(note_a)}; green bar = B ({H.escape(name_b)}) {H.escape(note_b)}. Whiskers = 95% CI of the mean. "Clear" means the paired difference B-A has a 95% CI that does not contain 0.</div>
<table><tr><th>Metric</th><th>A (grey) and B (green)</th><th>A mean [95% CI]</th><th>B mean [95% CI]</th><th>B - A (paired) [95% CI]</th><th>Verdict</th></tr>{rows}</table></body></html>"""
