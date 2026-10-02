"""FME-030 "Backup/restore failure": how often must a restore be tested? (synthetic, illustrative, generic)

Spec record FME-030 (spec/failures.json): domain Data, detection "periodic test", safe response "incident + remediation", simulation injection "scenario only". The spec gives no backup interval,
fault rate or remediation time (TBD); none is claimed. This page is generic: it names no real backup product or system.
Model (this code's choice, not from a source): a backup is taken every B hours. A fault that makes every following backup unusable starts as a Poisson process with rate mu per day (it is not seen by the
backup job itself). A restore test every Tt days finds a standing fault at the next test; remediation then takes `rem` hours, during which backups are still unusable, and the system is healthy again.
A disaster at a random moment is repaired from the latest usable backup; the data-loss window is the time between that backup and the disaster, expressed also as plant lots per day x hours.
Closed forms (renewal argument): fault duration D = U + rem with U uniform on [0, Tt] (the onset falls at a random phase of the test period). E[D] = Tt/2 + rem, E[D^2] = Tt^2/3 + Tt rem + rem^2.
Share of time in a fault P = mu E[D] / (1 + mu E[D]) (mu per hour). Mean loss = B/2 + P E[D^2] / (2 E[D]): without a fault the window is the time since the last backup (mean B/2); in a fault it is B/2 before
the onset plus the age of the fault (length-biased).
The uniform-phase assumption holds when a test period is short against the time between faults (mu Tt much below 1); when a fault is cleared at a test + rem, the next onset comes just after a test and has to wait almost a whole period, so for mu Tt around 1 or more the simulation (which keeps the real clock of the tests) is above the formula. The page shows the gap and does not hide it.
Per row (Tt): P(fault), mean loss window (hours and lots), 95th percentile of the loss window (simulated only), each against the closed form where it exists.
Not modelled: partial faults, backups that fail one at a time (each independent bad backup only adds B x f/(1-f) to the mean), restore time itself (RTO), a person finding the fault by other means, money.
"""
from __future__ import annotations

import dataclasses
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def closed(B: float, mu_h: float, Tt_h: float, rem: float):
    ED = Tt_h / 2 + rem
    ED2 = Tt_h ** 2 / 3 + Tt_h * rem + rem ** 2
    P = mu_h * ED / (1 + mu_h * ED)
    return P, B / 2 + P * ED2 / (2 * ED)


def closed_exact(B: float, mu_h: float, Tt_h: float, rem: float, n: int = 4000):
    """Phase-corrected closed form (M75 follow-up). After a fault is cleared at a test + rem, the next healthy time H is exponential, so the onset phase in the
    test period is (rem + H) mod Tt, not uniform; the fault then lasts D = (Tt - phase) + rem. Same renewal argument as `closed`, with E[D], E[D^2] taken over that
    wrapped exponential (midpoint integration, n cells). Equals `closed` when mu Tt is small."""
    import math
    w = Tt_h / n
    dens, tot = [], 0.0
    for i in range(n):
        ph = (i + 0.5) * w
        k0 = max(0, math.ceil((rem - ph) / Tt_h))          # first test period in which the onset can fall at this phase
        f = mu_h * math.exp(-mu_h * (ph + k0 * Tt_h - rem)) / (1.0 - math.exp(-mu_h * Tt_h))   # geometric sum over later periods
        dens.append(f); tot += f
    ED = ED2 = 0.0
    for i, f in enumerate(dens):
        D = Tt_h - (i + 0.5) * w + rem
        ED += f / tot * D; ED2 += f / tot * D * D
    P = ED / (1.0 / mu_h + ED)
    return P, B / 2 + P * ED2 / (2 * ED)


def _one(rg, B, mu_h, Tt_h, rem, horizon, draws):
    # fault intervals [onset, end)
    faults, t = [], 0.0
    while True:
        t += rg.expovariate(mu_h)
        if t >= horizon:
            break
        det = (int(t // Tt_h) + 1) * Tt_h
        end = det + rem
        faults.append((t, end))
        t = end
    losses, infault = [], 0
    import bisect
    starts = [f[0] for f in faults]
    for _ in range(draws):
        x = rg.uniform(0, horizon)
        j = bisect.bisect_right(starts, x) - 1
        if j >= 0 and x < faults[j][1]:
            infault += 1
            last_good = faults[j][0] - (faults[j][0] % B)
            losses.append(x - last_good)
        else:
            losses.append(x % B)
    return infault / draws, losses


def sweep(plant, tts_d: List[float], B_h: float, mu_day: float, rem_h: float, n: int = 8, draws: int = 4000) -> List[dict]:
    if B_h <= 0 or mu_day <= 0 or rem_h < 0 or not tts_d or any(t <= 0 for t in tts_d):
        raise ValueError("need B>0, mu>0, rem>=0, Tt>0")
    lots = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        lots.append(sum(1 for b in r.finished if r.horizon - r.window <= b.done <= r.horizon) / (r.window / 24.0))
    per_day = sum(lots) / len(lots)
    mu_h = mu_day / 24.0
    out = []
    for Td in tts_d:
        Tt = Td * 24.0
        horizon = max(Tt * 40, 24.0 * 365 * 30)
        ps, ms, p95 = [], [], []
        for i in range(n):
            rg = random.Random(plant.seed * 5003 + i + int(Td * 10))
            p, ls = _one(rg, B_h, mu_h, Tt, rem_h, horizon, draws)
            ls.sort()
            ps.append(p); ms.append(sum(ls) / len(ls)); p95.append(ls[int(0.95 * len(ls))])
        P, M = closed(B_h, mu_h, Tt, rem_h)
        out.append({"Tt": Td, "p": mean_ci(ps)[:3], "mean": mean_ci(ms)[:3], "p95": mean_ci(p95)[:3], "p_th": P, "mean_th": M, "lots": mean_ci(ms)[0] / 24.0 * per_day, "per_day": per_day})
    return out


def render_html(rows: List[dict], B_h: float, mu_day: float, rem_h: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["mean"][2], r["mean_th"]) for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["mean"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["mean_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["Tt"]:g} d</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["mean"][1], 0)):.1f}" y2="{Y(r["mean"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">mean data-loss window at a disaster, hours, 0..{ymax:.0f} (dashed: closed form)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">days between restore tests (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['Tt']:g} d</td><td>{r['p'][0] * 100:.2f}% / {r['p_th'] * 100:.2f}%</td><td>{f(r['mean'])}</td><td>{r['mean_th']:.1f}</td><td>{r['lots']:.1f}</td><td>{f(r['p95'], 0)}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-030 backup and restore test (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-030 backup and restore failure: how often to test a restore (synthetic)</h2><div class=n>Synthetic, illustrative and generic (no real backup system is named). Spec record FME-030 "Backup/restore failure" (spec provided by Javi, synthetic): periodic test, incident and remediation, scenario only. A backup every {B_h:g} h; a fault that makes every following backup unusable starts at {mu_day:.4g} per day (a placeholder, TBD in the spec); a restore test every Tt days finds it at the next test and remediation takes {rem_h:g} h. A disaster at a random moment loses the time since the latest usable backup ({rows[0]['per_day']:.2f} lots per day from the plant simulation, {n} seeds, convert it to lots). Closed form from a renewal argument: fault length D = U + rem, U uniform on [0, Tt]; share of time in a fault P = mu E[D]/(1 + mu E[D]); mean loss = B/2 + P E[D^2]/(2 E[D]). The formula assumes mu Tt is small: for 90 and 180 days between tests (mu Tt about 1 and 2 here) the simulation is higher because the onset phase is not uniform. Not modelled: partial faults, independent bad backups (they add B f/(1-f)), the restore time itself, finding the fault by other means, money.</div>{''.join(s)}
<table><tr><th>Restore test every</th><th>Time in a fault, sim / formula</th><th>Mean loss window, h [CI]</th><th>formula, h</th><th>Mean loss in lots</th><th>95th percentile, h [CI]</th></tr>{body}</table></body></html>"""
