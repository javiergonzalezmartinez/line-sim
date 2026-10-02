"""Little's law check of the simulator (synthetic): average lots in the plant L against arrival rate x time in the plant (lambda x W).

Law as read (2 Oct 2026) at https://en.wikipedia.org/wiki/Little%27s_law : the long-term average number of customers L in a stationary system
equals the long-term average effective arrival rate lambda times the average time W a customer spends in the system. The same page says an
unstable system (arrivals above exits) has a count that grows, and that effective arrivals (those that enter) are what counts.
What is computed here, from the lots of one run, over the measurement window [horizon - window, horizon]:
  L      = time-average number of lots in the plant (from entry to done, rejected lots count until they leave; area / window length)
  lambda = lots that entered the plant in the window / window length ("entry" = release, or the entry time when `conwip` holds orders outside)
  W      = mean (done - entry) of the lots that entered in the window
  gap    = (lambda W - L) / L
With a finite window the identity is only approximate (lots straddle both ends of the window), so a small gap is expected and a large
one is a warning that the plant is not in steady state (growing queue) or that there is a bug. Several seeds, mean and range are shown.
Not checked: sub-systems (a single stage), non-stationary phases, lots released after the horizon (the run continues until they finish).
"""
from __future__ import annotations

import dataclasses
import html as H
from typing import Dict, List

from .model import simulate


def one(plant) -> Dict[str, float]:
    res = simulate(plant)
    a, z = res.horizon - res.window, res.horizon
    area, arr, wsum = 0.0, 0, 0.0
    for b in res.batches:
        t0 = b.entered if b.entered is not None else b.released
        t1 = b.done if b.done is not None else z
        area += max(0.0, min(t1, z) - max(t0, a))
        if a <= t0 <= z:
            arr += 1
            wsum += t1 - t0
    T = z - a
    L, lam = area / T, arr / T
    W = wsum / arr if arr else 0.0
    return {"L": L, "lam": lam, "W": W, "lamW": lam * W, "gap": ((lam * W - L) / L) if L else 0.0}


def check(plant, n: int = 8) -> List[Dict[str, float]]:
    return [one(dataclasses.replace(plant, seed=plant.seed + i)) for i in range(n)]


def render_html(rows: List[Dict[str, float]], name: str = "") -> str:
    body = "".join(f"<tr><td>{i + 1}</td><td>{r['L']:.2f}</td><td>{r['lam'] * 24:.2f}</td><td>{r['W'] / 24:.2f}</td><td>{r['lamW']:.2f}</td><td style='color:{'#c0392b' if abs(r['gap']) > 0.1 else '#00857c'}'><b>{r['gap'] * 100:+.1f}%</b></td></tr>" for i, r in enumerate(rows))
    g = [r["gap"] for r in rows]
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Little's law check (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:900px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>Little's law check {H.escape(name)} (synthetic)</h2><div class=n>Synthetic and illustrative. Law as described at en.wikipedia.org/wiki/Little%27s_law (read 2 Oct 2026): average lots in the system L = arrival rate x average time in the system. Here L is the time average of lots in the plant over the measurement window; lambda and W come from the lots that entered in that window. With a finite window the match is approximate; red = gap above 10% (a rule of this code, not of the law), which would point to a growing queue or a bug. Lots per day and days in the table. Sub-systems and non-stationary phases are not checked.</div>
<p>Seeds: {len(rows)}. Gap range {min(g) * 100:+.1f}% to {max(g) * 100:+.1f}%, mean {sum(g) / len(g) * 100:+.1f}%.</p>
<table><tr><th>Seed</th><th>L: lots in plant (avg)</th><th>lambda: entries /day</th><th>W: days in plant</th><th>lambda x W</th><th>Gap (lambda W - L) / L</th></tr>{body}</table></body></html>"""
