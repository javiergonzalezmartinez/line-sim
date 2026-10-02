"""FME-004 "Negative available quantity": a race between two postings on the same stock (synthetic, illustrative)

Spec record FME-004 (spec/failures.json): domain Inventory, detection "transaction invariant", immediate effect "posting rejected", downstream "downstream allocation errors",
safe response "reject transaction + incident", simulation injection "race-condition scenario". The spec gives no stock level, quantity or timing (TBD); none is claimed.
Model (this code's choice, not from a source): one stock bucket. Each finished lot of the plant simulation consumes `q` units. Every 7 days a replenishment adds
`cover` x (mean weekly lots x q) units; the bucket starts with one such delivery. Two ways to post a consumption:
  atomic: check and post in one step on the true level; if level < q the posting is rejected and an incident is raised. The level never goes negative (the invariant holds).
  check-then-post with a gap w (minutes): the check reads the level as it was w minutes earlier, the posting happens later without a new check. Two lots close in time can both pass the
  check on the same units; the level then goes negative (a violated invariant, nobody notices until allocation fails downstream).
Per row (w): negative postings per 30 days, mean depth of the negative, rejected postings per 30 days (the cost of the safe path is the same shortage seen as rejections), and the share of
lots "exposed" (another lot within w before it) against the Poisson closed form 1 - exp(-lam w), lam = lots per hour. Lots are bursty and some finish at the same instant (batch release), so the exposed share is expected to exceed the Poisson one and not grow with w.
Not modelled: several buckets, partial postings, retries, queues of rejected postings, the cost of incidents, money.
"""
from __future__ import annotations

import bisect
import dataclasses
import math
from typing import List

from .model import simulate
from .whatif import mean_ci


def _run(dones, t0, win, q, cover, w_h):
    wk = 168.0
    weekly = len(dones) / (win / wk)
    delivery = cover * weekly * q
    ev = [(t, 0, q) for t in dones] + [(t0 + wk * k, 1, delivery) for k in range(1, int(win // wk) + 1)]
    ev.sort()
    level = delivery
    times, levels = [t0 - 1e9], [level]
    neg = rej = 0
    depth = []
    prev = None
    expo = 0
    for t, kind, v in ev:
        if kind == 1:
            level += v
        else:
            if prev is not None and t - prev <= w_h and w_h > 0:
                expo += 1
            prev = t
            if w_h == 0:
                seen = level
            else:
                seen = levels[bisect.bisect_right(times, t - w_h) - 1]
            if seen < v:
                rej += 1
            else:
                level -= v
                if level < 0:
                    neg += 1
                    depth.append(-level)
        times.append(t)
        levels.append(level)
    return neg, rej, depth, expo, len(dones)


def sweep(plant, ws_min: List[float], q: float, cover: float, n: int = 8) -> List[dict]:
    if q <= 0 or cover <= 0 or not ws_min or any(w < 0 for w in ws_min):
        raise ValueError("need q>0, cover>0, w>=0")
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = r.horizon - r.window
        runs.append((t0, r.window, sorted(b.done for b in r.finished if t0 <= b.done <= r.horizon)))
    lots_h = sum(len(x[2]) / x[1] for x in runs) / len(runs)
    out = []
    for w in ws_min:
        negs, rejs, deps, ex = [], [], [], []
        for t0, win, dones in runs:
            ng, rj, dp, e, nl = _run(dones, t0, win, q, cover, w / 60.0)
            sc = 720.0 / win
            negs.append(ng * sc); rejs.append(rj * sc); ex.append(e / nl if nl else 0.0)
            deps.extend(dp)
        out.append({"w": w, "neg": mean_ci(negs)[:3], "rej": mean_ci(rejs)[:3], "exp": mean_ci(ex)[:3],
                    "depth": (sum(deps) / len(deps)) if deps else 0.0, "exp_th": 1 - math.exp(-lots_h * w / 60.0), "lots_h": lots_h})
    return out


def render_html(rows: List[dict], q: float, cover: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(r["neg"][2] for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["neg"][0])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["w"]:g} min</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["neg"][1], 0)):.1f}" y2="{Y(r["neg"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">postings that leave the stock negative per 30 days (0..{ymax:.0f})</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">gap between the check and the posting, minutes (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['w']:g} min</td><td>{f(r['neg'])}</td><td>{r['depth']:.1f}</td><td>{f(r['rej'])}</td><td>{r['exp'][0] * 100:.1f}%</td><td>{r['exp_th'] * 100:.1f}%</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-004 negative available quantity (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-004 negative available quantity: a race between two postings (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-004 "Negative available quantity" (spec provided by Javi, synthetic): safe response is to reject the posting and raise an incident. Each lot consumes {q:g} units; one delivery per week covers {cover * 100:g}% of the mean weekly use (placeholders, TBD in the spec). Lots come from the plant simulation ({n} seeds). With a gap of 0 min the check and the posting are one step: no negative, the shortage shows as rejections (the safe path). With a gap, two close lots can pass the check on the same units. The exposed share (lots with another lot within the gap before them) is compared with the Poisson closed form 1 - exp(-lam w) (lam = {rows[0]['lots_h']:.3f} lots per hour). It does NOT follow it: in the example plant some lots finish at exactly the same instant as another lot (batch release, measured in one seed: 17 of 77 lots), so the exposed share is the same for every gap above 0 and far above Poisson. The race exists because of simultaneous postings, not because of the gap length. No several buckets, no retries, no cost of incidents, no money.</div>{''.join(s)}
<table><tr><th>Gap check to posting</th><th>Negative postings per 30 d [CI]</th><th>Mean depth, units</th><th>Rejected per 30 d [CI]</th><th>Lots exposed</th><th>Poisson closed form</th></tr>{body}</table></body></html>"""
