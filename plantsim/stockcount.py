"""FME-003 "Logical stock != physical": how often must you count to keep the book near the physical stock? (synthetic, illustrative)

Spec record FME-003 (spec/failures.json): domain Inventory, detection "count/zero pass/exception", effect "task or consumption mismatch", downstream
"reservation/production disruption", safe response "hold + count + reconciliation", simulation injection "inject delta". The spec gives no error rate or delta (TBD) and none is claimed.
Model (this code's choice, not from a source): each finished lot in the measurement window makes `postings` stock postings; every posting is wrong with probability e
and then moves the book away from the physical stock by +delta or -delta units (equal chance). A cycle count every `T` days finds the whole accumulated difference,
holds, counts and reconciles (book := physical). The book is assumed right at the start of the window, so only full count intervals inside the window are used.
Per row (T): share of time with at least one undetected posting error, root-mean-square book-vs-physical difference found at a count, and mean age of an error when it is found,
simulated with the same lots and seeds and compared with the closed forms: with lam_lot = lots per day x (1-(1-e)^postings) (the postings of one lot happen at the same moment) the time share is 1 - (1 - exp(-lam_lot T))/(lam_lot T); with lam = postings x e x lots per day the RMS difference is delta x sqrt(lam T) and the mean age T/2.
Lots come from the plant simulation (synthetic); the error draws are a separate simulated layer. Lots do not finish as a Poisson process (measured in 10 seeds of the example: completions fall only on the first six days of each week, few on the sixth, and only between hours 6 and 18 of the day), so a gap to the formula is expected, mostly in the mean age.
Not modelled: errors that are not independent, errors correlated with the lot size, a mismatch that stops production before the count (the disruption itself), the cost of counting, money.
"""
from __future__ import annotations

import dataclasses
import math
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, ts: List[float], e: float, postings: int, delta: float, n: int = 8) -> List[dict]:
    if not 0 <= e <= 1 or postings < 1 or delta < 0 or not ts or any(t <= 0 for t in ts):
        raise ValueError("need 0<=e<=1, postings>=1, delta>=0, T>0")
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = r.horizon - r.window
        runs.append((t0, r.window, [b.done for b in r.finished if t0 <= b.done <= r.horizon]))
    days = runs[0][1] / 24.0
    lots_day = sum(len(x[2]) for x in runs) / len(runs) / days
    lam = postings * e * lots_day
    lam_lot = lots_day * (1 - (1 - e) ** postings)  # distinct moments with at least one error (all postings of a lot happen at the same time)
    out = []
    for T in ts:
        Th = T * 24.0
        share, rms, age = [], [], []
        for i, (t0, win, dones) in enumerate(runs):
            rg = random.Random(plant.seed * 1481 + i)
            ev = []
            for t in dones:
                for _ in range(postings):
                    if rg.random() < e:
                        ev.append((t, delta if rg.random() < 0.5 else -delta))
            k = int(win // Th)
            if k < 1:
                continue
            tot_exp, sq, ages, n_ev = 0.0, [], [], 0
            for j in range(k):
                a, b = t0 + j * Th, t0 + (j + 1) * Th
                inside = [(t, d) for t, d in ev if a <= t < b]
                if inside:
                    tot_exp += b - min(t for t, _ in inside)
                sq.append(sum(d for _, d in inside) ** 2)
                ages.extend(b - t for t, _ in inside)
            share.append(tot_exp / (k * Th))
            rms.append(math.sqrt(sum(sq) / len(sq)))
            if ages:
                age.append(sum(ages) / len(ages) / 24.0)
        x = lam * T
        xl = lam_lot * T
        out.append({"T": T, "share": mean_ci(share)[:3] if share else (0.0, 0.0, 0.0), "rms": mean_ci(rms)[:3] if rms else (0.0, 0.0, 0.0),
                    "age": mean_ci(age)[:3] if age else (0.0, 0.0, 0.0),
                    "share_th": (1 - (1 - math.exp(-xl)) / xl) if xl > 0 else 0.0, "rms_th": delta * math.sqrt(x), "age_th": T / 2.0, "lam": lam})
    return out


def render_html(rows: List[dict], e: float, postings: int, delta: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = min(1.0, max(max(r["share"][2], r["share_th"]) for r in rows) * 1.1) or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["share"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["share_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["T"]:g} d</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r["share"][1]):.1f}" y2="{Y(r["share"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">share of time with an undetected posting error, 0..{ymax * 100:.0f}% (dashed: closed form)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">days between cycle counts (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['T']:g} d</td><td>{r['share'][0] * 100:.1f}% [{max(r['share'][1], 0) * 100:.1f}, {r['share'][2] * 100:.1f}]</td><td>{r['share_th'] * 100:.1f}%</td><td>{f(r['rms'], 2)}</td><td>{r['rms_th']:.2f}</td><td>{f(r['age'], 1)}</td><td>{r['age_th']:.1f}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-003 stock mismatch (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-003 logical stock differs from physical: how often to count (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-003 "Logical stock != physical" (spec provided by Javi, synthetic): count, hold, reconcile. Posting error probability {e * 100:g}%, {postings} postings per lot and an error size of +/-{delta:g} units are placeholders (TBD in the spec, no real rate claimed). Lots come from the plant simulation ({n} seeds); the error draws are a separate simulated layer compared with closed forms based on a Poisson rate of {rows[0]['lam']:.2f} posting errors per day. Lots do not finish as a Poisson process (completions fall on weekdays and in the day shift), so a gap is expected, mostly in the mean age. The book is right at the start of the window; no cost of counting, no money.</div>{''.join(s)}
<table><tr><th>Count every</th><th>Time with an undetected error [CI]</th><th>closed form</th><th>RMS difference found, units [CI]</th><th>closed form</th><th>Mean age of an error when found, d [CI]</th><th>closed form</th></tr>{body}</table></body></html>"""
