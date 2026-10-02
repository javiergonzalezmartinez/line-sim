"""FME-023 "Unauthorized operation": what does the authority check stop, and what does the alert queue cost? (synthetic, illustrative)

Spec record FME-023 (spec/failures.json): domain Human, detection "authority check", immediate effect "action denied", downstream "none if control works", safe response "audit + alert",
simulation injection "role mismatch", GxP CRITICAL. The spec gives no mismatch rate, coverage or review time (TBD); none is claimed.
Model (this code's choice, not from a source): each finished lot of the plant simulation has `ops` operations; every operation is attempted with the wrong role with probability q
(role mismatch). The authority check guards a share `cover` of the operations. A guarded mismatch is denied, audited and raises an alert; an unguarded mismatch is executed (unauthorized
operation done). Alerts wait in one FIFO review queue with one reviewer who is always available and needs `s` minutes per alert, starting at the lot completion time.
Per row (q): unauthorized operations executed per 1000 lots, alerts per day, mean wait in the review queue and share of alerts that wait at all; closed forms: N q (1-cover) per 1000 lots,
alerts per day = lots per day x ops x q x cover, and for the wait the M/D/1 formula Wq = rho s / (2 (1 - rho)) (Poisson arrivals, fixed review time; source: standard queueing result).
Lots are bursty and several finish at the same instant, so the simulated wait is expected to exceed the M/D/1 value.
Not modelled: several reviewers, shifts, alert fatigue (reviewers that skip), a mismatch that is a real emergency, the cost of an unauthorized operation, money.
"""
from __future__ import annotations

import dataclasses
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, qs: List[float], cover: float, ops: int, s_min: float, n: int = 8) -> List[dict]:
    if not 0 <= cover <= 1 or ops < 1 or s_min <= 0 or not qs or any(not 0 <= q <= 1 for q in qs):
        raise ValueError("need 0<=q<=1, 0<=cover<=1, ops>=1, s>0")
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = r.horizon - r.window
        runs.append((r.window, sorted(b.done for b in r.finished if t0 <= b.done <= r.horizon)))
    lots_day = sum(len(x[1]) / (x[0] / 24.0) for x in runs) / len(runs)
    s_h = s_min / 60.0
    out = []
    for q in qs:
        unauth, alerts, waits, waited = [], [], [], []
        for i, (win, dones) in enumerate(runs):
            rg = random.Random(plant.seed * 15485863 + i)
            ua, al = 0, []
            for t in dones:
                for _ in range(ops):
                    if rg.random() < q:
                        if rg.random() < cover:
                            al.append(t)
                        else:
                            ua += 1
            free = 0.0
            w = []
            for t in al:
                start = max(t, free)
                w.append((start - t) * 60.0)
                free = start + s_h
            nl = len(dones)
            unauth.append(ua * 1000.0 / nl if nl else 0.0)
            alerts.append(len(al) / (win / 24.0))
            if w:
                waits.append(sum(w) / len(w)); waited.append(sum(1 for x in w if x > 1e-9) / len(w))
        rate_h = lots_day * ops * q * cover / 24.0
        rho = rate_h * s_h
        wq = (rho * s_min / (2 * (1 - rho))) if rho < 1 else float("inf")
        out.append({"q": q, "unauth": mean_ci(unauth)[:3], "alerts": mean_ci(alerts)[:3], "wait": mean_ci(waits)[:3] if waits else (0.0, 0.0, 0.0),
                    "waited": mean_ci(waited)[:3] if waited else (0.0, 0.0, 0.0),
                    "unauth_th": 1000.0 * ops * q * (1 - cover), "alerts_th": lots_day * ops * q * cover, "wait_th": wq, "rho": rho})
    return out


def render_html(rows: List[dict], cover: float, ops: int, s_min: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["unauth"][2], r["unauth_th"]) for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["unauth"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["unauth_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["q"] * 100:g}%</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["unauth"][1], 0)):.1f}" y2="{Y(r["unauth"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">unauthorized operations executed per 1000 lots, 0..{ymax:.0f} (dashed: N q (1-cover))</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">share of operations attempted with the wrong role (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['q'] * 100:g}%</td><td>{f(r['unauth'])}</td><td>{r['unauth_th']:.1f}</td><td>{f(r['alerts'], 2)}</td><td>{r['alerts_th']:.2f}</td><td>{f(r['wait'], 1)}</td><td>{r['wait_th']:.1f}</td><td>{r['waited'][0] * 100:.0f}%</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-023 unauthorized operation (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-023 unauthorized operation: what the authority check stops (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-023 "Unauthorized operation" (spec provided by Javi, synthetic): authority check, action denied, audit and alert. {ops} operations per lot, the authority check guards {cover * 100:g}% of them, one reviewer needs {s_min:g} min per alert (all placeholders, TBD in the spec). Lots come from the plant simulation ({n} seeds). A guarded role mismatch is denied and alerted; an unguarded one is executed. Closed forms: N q (1-cover) per 1000 lots, alerts per day = lots per day x ops x q x cover, and the M/D/1 wait Wq = rho s / (2(1-rho)). Lots are bursty and some finish at the same instant, so the simulated wait is expected to exceed M/D/1. No several reviewers, no shifts, no alert fatigue, no cost of an unauthorized operation, no money.</div>{''.join(s)}
<table><tr><th>Wrong-role share</th><th>Executed per 1000 lots [CI]</th><th>formula</th><th>Alerts per day [CI]</th><th>formula</th><th>Mean review wait, min [CI]</th><th>M/D/1</th><th>Alerts that wait</th></tr>{body}</table></body></html>"""
