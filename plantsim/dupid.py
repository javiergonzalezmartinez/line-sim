"""FME-002 "Duplicate HU identifier": how long must an identifier be if it is drawn at random? (synthetic, illustrative)

Spec record FME-002 (spec/failures.json): domain Identity, detection "uniqueness constraint", immediate effect "create rejected", downstream "traceability compromise if undetected",
safe response "hard reject + incident", simulation injection "scenario fault", GxP CRITICAL. The spec gives no identifier format or length (TBD); none is claimed.
Model (this code's choice, not from a source): each finished lot of the plant simulation creates `hu_per_lot` handling units; the lots per day are measured from the simulation and
scaled to one year of production. Every HU gets an identifier drawn uniformly at random from N = 10^d values (d digits, a stand-in for an offline or manually allocated range).
Without a uniqueness constraint a repeat is an undetected duplicate (traceability compromised). With the constraint the create is rejected, an incident is raised and a new id is drawn.
Per row (d): probability of at least one duplicate in a year, duplicates per year (= rejected creates with the constraint), against the birthday-problem closed forms
1 - exp(-n(n-1)/(2N)) and n(n-1)/(2N), n = HUs per year. The id draws are a separate simulated layer (the plant simulation only sets n).
The duplicate-count formula n(n-1)/(2N) is a first-order approximation: it overcounts when the range is nearly full (4 digits), the simulation counts exact repeats.
Not modelled: sequential or check-digit identifiers (they cannot repeat by design), several sites, the cost of an incident, money.
"""
from __future__ import annotations

import dataclasses
import math
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, digits: List[int], hu_per_lot: int, n: int = 8, reps: int = 40) -> List[dict]:
    if hu_per_lot < 1 or not digits or any(d < 1 or d > 9 for d in digits) or reps < 1:
        raise ValueError("need hu_per_lot>=1, 1<=digits<=9, reps>=1")
    lots = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = r.horizon - r.window
        lots.append(sum(1 for b in r.finished if t0 <= b.done <= r.horizon) / (r.window / 24.0))
    per_day = sum(lots) / len(lots)
    hus = int(round(per_day * 365 * hu_per_lot))
    out = []
    for d in digits:
        N = 10 ** d
        rg = random.Random(plant.seed * 7919 + d)
        anyd, dup = [], []
        for _ in range(reps * n):
            seen, c = set(), 0
            for _ in range(hus):
                v = rg.randrange(N)
                if v in seen:
                    c += 1
                else:
                    seen.add(v)
            anyd.append(1.0 if c else 0.0); dup.append(float(c))
        pairs = hus * (hus - 1) / (2.0 * N)
        out.append({"d": d, "N": N, "any": mean_ci(anyd)[:3], "dup": mean_ci(dup)[:3], "any_th": 1 - math.exp(-pairs), "dup_th": pairs, "hus": hus, "per_day": per_day})
    return out


def render_html(rows: List[dict], hu_per_lot: int, n: int, reps: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    Y = lambda v: 16 + (Hh - 60) * (1 - v)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["any"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["any_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["d"]} digits</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["any"][1], 0)):.1f}" y2="{Y(min(r["any"][2], 1)):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">probability of at least one duplicate in a year, 0..100% (dashed: birthday formula)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">random identifier length in digits (placeholder)</text></svg>')
    f = lambda t, k=2: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['d']} (N = {r['N']:,})</td><td>{r['any'][0] * 100:.1f}% [{max(r['any'][1], 0) * 100:.1f}, {min(r['any'][2], 1) * 100:.1f}]</td><td>{r['any_th'] * 100:.1f}%</td><td>{f(r['dup'])}</td><td>{r['dup_th']:.2f}</td></tr>" for r in rows)
    r0 = rows[0]
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-002 duplicate HU identifier (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-002 duplicate HU identifier: how long must a random id be (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-002 "Duplicate HU identifier" (spec provided by Javi, synthetic): uniqueness constraint, hard reject plus incident. The plant simulation ({n} seeds) gives {r0['per_day']:.2f} lots per day, so {hu_per_lot} HUs per lot make {r0['hus']} HUs in a year; each gets a random id of d digits (a stand-in for an offline range; the spec sets no format, TBD). Without the constraint a repeat is an undetected duplicate; with it the create is rejected (rejected = duplicates per year). {reps * n} simulated years per row against the birthday formulas. The duplicates-per-year formula n(n-1)/(2N) is first order and overshoots when the range is nearly used up (it gives 140 against a simulated 132 at 4 digits). Sequential or check-digit ids cannot repeat by design and are not modelled; no incident cost, no money.</div>{''.join(s)}
<table><tr><th>Id length</th><th>P(at least one duplicate in a year) [CI]</th><th>formula</th><th>Duplicates (= rejected creates) per year [CI]</th><th>formula</th></tr>{body}</table></body></html>"""
