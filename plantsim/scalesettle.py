"""FME-018 "Scale unstable": when is a weighing stable enough to capture? (synthetic, illustrative)

Spec record FME-018 (spec/failures.json): domain Equipment, detection "stability criterion", safe response "do not capture until stable", simulation injection "noise model".
The spec gives no noise level, settling time or tolerance (TBD); none is claimed.
Model (this code's choice, not from a source): after a load is placed the scale shows  reading(t) = A exp(-t/tau) + noise  with noise N(0, sigma) per reading, one reading every
dt seconds (A = initial offset, tau = settling time). Stability criterion: capture the second of two consecutive readings as soon as they differ by no more than tol. Before that nothing is captured.
Per row (tol): mean time to capture, mean absolute error of the captured value (true value is 0), share of captures with an error above 2 sigma, and the seconds added per day
for the weighings of the plant (the plant simulation gives lots per day; `w` weighings per lot).
Closed form checked: with pure noise (A = 0) a FRESH pair of readings is accepted with probability p = 2 Phi(tol / (sigma sqrt 2)) - 1 (difference of two normals, standard result);
the simulated acceptance over fresh pairs must agree. The capture rule uses overlapping pairs, so the mean capture time is compared with the simple estimate dt (1/p + 1), which is only an approximation (overlapping pairs are not independent).
Without noise the rule stops as soon as the step between readings A exp(-t/tau)(1 - exp(-dt/tau)) is at most tol, so the leftover error is at most tol/(1 - exp(-dt/tau)): a tolerance on two readings bounds the STEP, not the distance to the final value (the table shows this bound; noise can make it fail, see below). With noise the simulated error is LARGER than that bound (6.2 g against 2.1 g at tol 0.25 in the default run), because noise can make two readings agree by chance while the scale is still falling. That is a finding about the rule, not about the scale.
Not modelled: drift over the day, vibration bursts, calibration error (that is FME-019), operator pressing capture early, money.
"""
from __future__ import annotations

import dataclasses
import math
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def _phi(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def capture(rg, tol, A, tau, sigma, dt, tmax=120.0):
    t, prev = 0.0, None
    while t <= tmax:
        x = A * math.exp(-t / tau) + rg.gauss(0, sigma)
        if prev is not None and abs(x - prev) <= tol:
            return t, x
        prev = x
        t += dt
    return None, None


def sweep(plant, tols: List[float], A: float, tau: float, sigma: float, dt: float, w: int, n: int = 8, reps: int = 400) -> List[dict]:
    if sigma <= 0 or tau <= 0 or dt <= 0 or w < 1 or A < 0 or not tols or any(t <= 0 for t in tols):
        raise ValueError("need sigma,tau,dt,tol>0, A>=0, w>=1")
    lots = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        lots.append(sum(1 for b in r.finished if r.horizon - r.window <= b.done <= r.horizon) / (r.window / 24.0))
    per_day = sum(lots) / len(lots)
    out = []
    for tol in tols:
        tm, er, bad, cnt = [], [], [], 0
        for i in range(n):
            rg = random.Random(plant.seed * 31337 + i + int(tol * 1000))
            t_l, e_l, b_l = [], [], 0
            for _ in range(reps):
                t, x = capture(rg, tol, A, tau, sigma, dt)
                if t is None:
                    continue
                t_l.append(t); e_l.append(abs(x)); b_l += abs(x) > 2 * sigma
            if t_l:
                tm.append(sum(t_l) / len(t_l)); er.append(sum(e_l) / len(e_l)); bad.append(b_l / len(t_l))
        # fresh pairs, pure noise
        rg = random.Random(plant.seed + 99)
        acc = sum(1 for _ in range(20000) if abs(rg.gauss(0, sigma) - rg.gauss(0, sigma)) <= tol) / 20000.0
        p = 2 * _phi(tol / (sigma * math.sqrt(2))) - 1
        out.append({"tol": tol, "time": mean_ci(tm)[:3], "err": mean_ci(er)[:3], "bad": mean_ci(bad)[:3], "acc": acc, "acc_th": p,
                    "time_th": dt * (1 / p + 1) if p > 0 else float("inf"), "bound": tol / (1 - math.exp(-dt / tau)), "day_s": per_day * w * mean_ci(tm)[0], "per_day": per_day})
    return out


def render_html(rows: List[dict], A: float, tau: float, sigma: float, dt: float, w: int, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(r["err"][2] for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["err"][0])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">tol {r["tol"]:g}</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["err"][1], 0)):.1f}" y2="{Y(r["err"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">mean absolute error of the captured value, 0..{ymax:.2f} g (true value 0)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">stability tolerance between two readings, g (placeholder)</text></svg>')
    f = lambda t, k=2: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['tol']:g} g</td><td>{f(r['time'], 1)}</td><td>{r['time_th']:.1f}</td><td>{f(r['err'])}</td><td>{r['bad'][0] * 100:.1f}%</td><td>{r['bound']:.1f}</td><td>{r['acc'] * 100:.1f}%</td><td>{r['acc_th'] * 100:.1f}%</td><td>{r['day_s'] / 60:.1f}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-018 scale unstable (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-018 scale unstable: when to capture the weight (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-018 "Scale unstable" (spec provided by Javi, synthetic): stability criterion, do not capture until stable. Model: reading = {A:g} g x exp(-t/{tau:g} s) + noise (sigma {sigma:g} g), one reading every {dt:g} s; capture when two consecutive readings differ by at most the tolerance (all numbers placeholders, TBD in the spec). {w} weighings per lot, {rows[0]['per_day']:.2f} lots per day from the plant simulation ({n} seeds). Closed form checked: a fresh pair of pure-noise readings is accepted with p = 2 Phi(tol/(sigma sqrt 2)) - 1. The capture time is compared with dt (1/p + 1), which only describes pure noise (A = 0) and is far too short while the scale is still settling; the table shows both. The no-noise bound on the leftover error is also shown; with noise the simulated error is larger than it (a lucky pair can agree while the scale is still falling). Not modelled: drift, vibration bursts, calibration error, an operator capturing early, money.</div>{''.join(s)}
<table><tr><th>Tolerance</th><th>Time to capture, s [CI]</th><th>dt(1/p+1)</th><th>Mean abs error, g [CI]</th><th>Error above 2 sigma</th><th>No-noise bound tol/(1-exp(-dt/tau)), g</th><th>Fresh pairs accepted</th><th>formula p</th><th>Added minutes per day</th></tr>{body}</table></body></html>"""
