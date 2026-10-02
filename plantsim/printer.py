"""FME-026 "Printer unavailable": what does label-printer downtime cost the lots? (synthetic, illustrative)

Spec record FME-026 (spec/failures.json): domain Printing, injection "downtime". The spec gives no MTBF or MTTR (TBD) and none is claimed.
Model (this code's choice): one label printer alternates up and down with exponential up times (mean `mtbf_h`) and exponential repairs (mean `mttr_h`).
Each lot finished in the measurement window needs a label at the moment it is done; if the printer is down then, the label waits until the repair ends.
Per row (MTTR): share of lots whose label is delayed, mean and 95th percentile of the delay among all lots, and the closed form from the model:
P(down) = MTTR/(MTBF+MTTR) and, by the memoryless repair time, mean delay given down = MTTR. Simulation and formula are shown side by side.
Lots come from the plant simulation (same seeds); the printer is a separate simulated layer.
Not modelled: the label delay does not hold the lot back in the plant (no feedback), a second printer or manual fallback, print queues with several jobs, wrong-label
association (FME-027), money.
"""
from __future__ import annotations

import dataclasses
import html as H
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def _down_intervals(rg, mtbf, mttr, horizon):
    t, out = 0.0, []
    while t < horizon:
        t += rg.expovariate(1 / mtbf)
        d = rg.expovariate(1 / mttr) if mttr > 0 else 0.0
        out.append((t, t + d)); t += d
    return out


def sweep(plant, mttrs: List[float], mtbf: float, n: int = 8) -> List[dict]:
    if mtbf <= 0 or not mttrs or any(x < 0 for x in mttrs):
        raise ValueError("need mtbf > 0 and mttr >= 0")
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        runs.append((r.horizon, [b.done for b in r.finished if r.horizon - r.window <= b.done <= r.horizon]))
    out = []
    for m in mttrs:
        sh, mean_d, p95 = [], [], []
        for i, (hz, dones) in enumerate(runs):
            rg = random.Random(plant.seed * 7919 + i)
            dn = _down_intervals(rg, mtbf, m, hz * 1.5)
            delays = []
            for t in dones:
                w = 0.0
                for a, b in dn:
                    if a <= t < b:
                        w = b - t; break
                    if a > t:
                        break
                delays.append(w)
            k = len(delays)
            sh.append(sum(1 for x in delays if x > 0) / k if k else 0.0)
            mean_d.append(sum(delays) / k if k else 0.0)
            p95.append(sorted(delays)[int(0.95 * (k - 1))] if k else 0.0)
        c = lambda v: tuple(max(0.0, x) for x in mean_ci(v)[:3])
        out.append({"mttr": m, "share": c(sh), "mean": c(mean_d), "p95": c(p95), "p_down": m / (mtbf + m), "mean_th": m * m / (mtbf + m)})
    return out


def render_html(rows: List[dict], mtbf: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(r["share"][2] for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11"><polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/><polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % (
        " ".join("%.1f,%.1f" % (X(i), Y(r["share"][0])) for i, r in enumerate(rows)), " ".join("%.1f,%.1f" % (X(i), Y(r["p_down"])) for i, r in enumerate(rows)))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["mttr"]:g} h</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r["share"][1]):.1f}" y2="{Y(r["share"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">share of lots with a delayed label, 0..{ymax * 100:.0f}% (dashed: closed form)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">mean repair time of the printer (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{t[1]:.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['mttr']:g} h</td><td>{r['share'][0] * 100:.1f}% [{r['share'][1] * 100:.1f}, {r['share'][2] * 100:.1f}]</td><td>{r['p_down'] * 100:.1f}%</td><td>{f(r['mean'], 2)}</td><td>{r['mean_th']:.2f}</td><td>{f(r['p95'], 1)}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-026 printer unavailable (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-026 printer unavailable: label delay (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-026 "Printer unavailable" (injection: downtime; spec provided by Javi, synthetic). MTBF {mtbf:g} h and the repair times are placeholders (TBD in the spec, no real printer data). One printer, exponential up and repair times; lots come from the plant simulation ({n} seeds) and need a label when they are done. The delay does not hold the lot in the plant (no feedback), no spare printer, no money.</div>{''.join(s)}
<table><tr><th>Mean repair</th><th>Lots delayed [CI]</th><th>closed form P(down)</th><th>Mean delay, h [CI]</th><th>closed form</th><th>95th percentile delay, h [CI]</th></tr>{body}</table></body></html>"""
