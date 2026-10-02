"""FME-029 "Audit record write failure": a storage outage, fail closed against fail open (synthetic, illustrative)

Spec record FME-029 (spec/failures.json): domain Data, detection "transactional persistence", immediate effect "business mutation must not commit", downstream "data integrity risk",
safe response "fail closed", simulation injection "storage fault", GxP CRITICAL. The spec gives no outage frequency or length (TBD); none is claimed.
Model (this code's choice, not from a source): every finished lot of the plant simulation makes `m` business mutations and each needs an audit record written in the same transaction.
One storage outage of D minutes starts at a uniformly random moment of the measurement window (many random starts per seed).
  fail closed (the spec's response): mutations during the outage do not commit; they wait until the audit store is back. Cost: blocked mutations and their wait. Integrity gap: zero by construction.
  fail open (the unsafe alternative, shown for contrast): mutations commit during the outage without an audit record. Cost: none visible; integrity gap = the same count of unaudited mutations.
Per row (D): blocked (= unaudited if fail open) mutations per outage, mean wait of a blocked mutation, and the share of lots that finish inside the outage, against closed forms for a Poisson stream:
blocked = m x lots per hour x D/60, mean wait = D/2. With a uniformly random start the MEAN count equals the Poisson value whatever the burstiness (only the spread differs), so a match is expected, not a surprise; the mean wait D/2 holds only if arrivals are spread evenly inside the outage and is checked.
Not modelled: several stores, a queue that holds work until recovery with a limit, partial writes, independent single write failures, the cost of an outage, money.
"""
from __future__ import annotations

import bisect
import dataclasses
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, ds_min: List[float], m: int, n: int = 8, starts: int = 200) -> List[dict]:
    if m < 1 or not ds_min or any(d <= 0 for d in ds_min) or starts < 1:
        raise ValueError("need m>=1, D>0, starts>=1")
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = r.horizon - r.window
        runs.append((t0, r.window, sorted(b.done for b in r.finished if t0 <= b.done <= r.horizon)))
    lots_h = sum(len(x[2]) / x[1] for x in runs) / len(runs)
    out = []
    for D in ds_min:
        Dh = D / 60.0
        blk, wait, share = [], [], []
        for i, (t0, win, dones) in enumerate(runs):
            if win <= Dh:
                continue
            rg = random.Random(plant.seed * 104729 + i + int(D))
            for _ in range(starts):
                s = t0 + rg.random() * (win - Dh)
                a, b = bisect.bisect_left(dones, s), bisect.bisect_right(dones, s + Dh)
                k = b - a
                blk.append(k * m)
                share.append(k / len(dones) if dones else 0.0)
                if k:
                    wait.append(sum(s + Dh - t for t in dones[a:b]) / k * 60.0)
        out.append({"D": D, "blk": mean_ci(blk)[:3], "wait": mean_ci(wait)[:3] if wait else (0.0, 0.0, 0.0), "share": mean_ci(share)[:3],
                    "blk_th": m * lots_h * Dh, "wait_th": D / 2.0, "lots_h": lots_h})
    return out


def render_html(rows: List[dict], m: int, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["blk"][2], r["blk_th"]) for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["blk"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["blk_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["D"]:g} min</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["blk"][1], 0)):.1f}" y2="{Y(r["blk"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">mutations blocked per outage (= unaudited if fail open), 0..{ymax:.0f} (dashed: Poisson)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">outage length, minutes (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['D']:g} min</td><td>{f(r['blk'])}</td><td>{r['blk_th']:.1f}</td><td>{f(r['wait'], 0)}</td><td>{r['wait_th']:.0f}</td><td>{r['share'][0] * 100:.1f}%</td><td>0 (fail closed) / same as blocked (fail open)</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-029 audit write failure (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-029 audit record write failure: fail closed against fail open (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-029 "Audit record write failure" (spec provided by Javi, synthetic): the business mutation must not commit, fail closed. One storage outage of D minutes at a random moment of the window; each finished lot makes {m} mutations ({n} seeds of the plant simulation; outage length and {m} are placeholders, TBD in the spec). Fail closed: blocked mutations wait for recovery and the integrity gap is zero. Fail open (unsafe, shown for contrast): the same mutations commit without an audit record. Closed forms use the mean rate of {rows[0]['lots_h']:.3f} lots per hour; with a uniformly random start the mean blocked count matches it whatever the burstiness (expected, not a finding), and the check that adds information is the mean wait against D/2. No several stores, no limited queue, no single write failures, no cost of an outage, no money.</div>{''.join(s)}
<table><tr><th>Outage</th><th>Blocked mutations [CI]</th><th>Poisson</th><th>Mean wait of a blocked one, min [CI]</th><th>D/2</th><th>Lots inside the outage</th><th>Unaudited mutations</th></tr>{body}</table></body></html>"""
