"""Warm-up check with Welch's moving average (synthetic, illustrative).

Procedure as read (2 Oct 2026) at https://hsma-tools.github.io/vidigi/reference/analysis.welch_moving_average.html (documentation of a
Python function that cites Law, "Simulation Modeling and Analysis"): run several replications, average the same time series across
replications, smooth the ensemble average with a symmetric moving average of full width 2w+1 (near the start the window shrinks to a
narrower symmetric one), and read off by eye where the curve stops drifting. The DES guide at
https://pythonhealthdatascience.github.io/des_rap_book/pages/guide/output_analysis/length_warmup.html (read the same day) asks for at least five replications.
Here: each replication is simulated with warm-up 0 and the plant's own horizon; the series are work in progress (lots released and not yet
finished, sampled every 24 h) and lots finished per day (trailing 7-day mean, to remove the weekly working-calendar cycle). The vertical line is the warm-up set in the config.
The "settles" marker is a rule of this code, not from the sources: the first day from which the smoothed curve stays within 5% of the mean of
its last quarter. It is a reading aid, the judgement stays with the person looking at the curve.
Not modelled: per-product series, a statistical test for the end of the transient, long runs to see slow drifts.
"""
from __future__ import annotations

import dataclasses
import html as H
from typing import Dict, List

from .model import simulate


def wip_series(res, day: float = 24.0) -> List[float]:
    n = int(res.horizon // day)
    return [float(sum(1 for b in res.batches if b.released <= (i + 1) * day and (b.done is None or b.done > (i + 1) * day))) for i in range(n)]


def done_series(res, day: float = 24.0) -> List[float]:
    n = int(res.horizon // day)
    c = [0.0] * n
    for b in res.batches:
        if b.done is not None and not b.rejected:
            k = int(b.done // day)
            if 0 <= k < n:
                c[k] += 1
    return [sum(c[max(0, i - 6):i + 1]) / min(i + 1, 7) for i in range(n)]    # trailing 7-day mean: removes the weekly working-calendar cycle


def welch(avg: List[float], w: int) -> List[float]:
    n = len(avg)
    if not (0 < w < n):
        raise ValueError("window half-width must be between 1 and the series length")
    out = []
    for i in range(n - w):
        h = min(w, i)
        seg = avg[i - h:i + h + 1]
        out.append(sum(seg) / len(seg))
    return out


def settles(sm: List[float], tol: float = 0.05) -> int:
    q = sm[-max(len(sm) // 4, 1):]
    ref = sum(q) / len(q)
    last_bad = -1
    for i, v in enumerate(sm):
        if abs(v - ref) > tol * max(abs(ref), 1e-9):
            last_bad = i
    return last_bad + 1


def analyse(plant, n: int = 10, w: int = 7) -> Dict:
    if n < 5:
        raise ValueError("use at least 5 replications")
    runs = [simulate(dataclasses.replace(plant, warmup=0.0, seed=plant.seed + i)) for i in range(n)]
    out = {"n": n, "w": w, "warmup_day": plant.warmup / 24.0}
    for key, fn in (("wip", wip_series), ("done", done_series)):
        ser = [fn(r) for r in runs]
        m = min(len(s) for s in ser)
        avg = [sum(s[i] for s in ser) / n for i in range(m)]
        sm = welch(avg, w)
        out[key] = {"avg": avg, "smooth": sm, "settles": settles(sm)}
    return out


def render_html(a: Dict) -> str:
    W, Hh, L, B = 780, 250, 50, 28
    def chart(key, title):
        d = a[key]; avg, sm = d["avg"], d["smooth"]
        top = max(avg) * 1.08 or 1
        X = lambda i: L + (W - L - 15) * i / max(len(avg) - 1, 1)
        Y = lambda v: 14 + (Hh - B - 14) * (1 - v / top)
        pa = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(avg)); ps = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(sm))
        return (f'<h3>{title}</h3><svg width="{W}" height="{Hh}" font-size="11"><polyline points="{pa}" fill="none" stroke="#adb5bd"/><polyline points="{ps}" fill="none" stroke="#1971c2" stroke-width="2.5"/>'
                f'<line x1="{X(a["warmup_day"]):.1f}" x2="{X(a["warmup_day"]):.1f}" y1="14" y2="{Hh - B}" stroke="#c0392b" stroke-dasharray="5 3"/><text x="{X(a["warmup_day"]) + 4:.1f}" y="26" fill="#c0392b">configured warm-up: day {a["warmup_day"]:.0f}</text>'
                f'<line x1="{X(d["settles"]):.1f}" x2="{X(d["settles"]):.1f}" y1="14" y2="{Hh - B}" stroke="#2b8a3e" stroke-dasharray="2 3"/><text x="{X(d["settles"]) + (-4 if d["settles"] > len(avg) * 0.6 else 4):.1f}" y="44" text-anchor="{"end" if d["settles"] > len(avg) * 0.6 else "start"}" fill="#2b8a3e">settles (rule of this code): day {d["settles"]}</text>'
                f'<text x="{L}" y="{Hh - 8}" fill="#5c6b80">day of the simulation</text><text x="4" y="12" fill="#5c6b80">0 .. {top:.1f}</text></svg>')
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Warm-up check, Welch (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:900px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>Warm-up check with Welch's moving average (synthetic)</h2><div class=n>Synthetic and illustrative. Procedure as described in the vidigi documentation (hsma-tools.github.io/vidigi, welch_moving_average, which cites Law) and the DES RAP book (pythonhealthdatascience.github.io), both read 2 Oct 2026. {a['n']} replications with warm-up 0, same series averaged, grey = ensemble average, blue = Welch moving average (w = {a['w']} days). The "settles" marker (smoothed curve within 5% of the mean of its last quarter from then on) is a rule of this code, not from the sources. Judge the curve yourself.</div>{chart('wip', 'Work in progress (lots in the plant, daily)')}{chart('done', 'Lots finished per day (trailing 7-day mean)')}<p>If the blue curve is still drifting after the red line, the configured warm-up is too short for that measure. Not modelled: per-product series, a statistical end-of-transient test, longer runs for slow drifts.</p></body></html>"""
