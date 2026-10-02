"""FME-019 "Calibration overdue": how many lots finish while an instrument is overdue? (synthetic, illustrative)

Spec record FME-019 (spec/failures.json): domain Equipment, injection "calendar event". The spec gives no calibration interval or lateness (TBD) and none is claimed.
Model (this code's choice): one instrument is due for calibration every `interval_d` days counted from the previous actual calibration; the actual calibration
happens late by an exponential time with mean `late_d` days (0 = always on time). While overdue the instrument is "overdue".
Each lot finished in the measurement window is "at risk" if the instrument is overdue at that moment (its results would need review). Per row (mean lateness):
share of lots at risk, simulated and by the renewal-reward closed form m/(I+m) (overdue time per cycle = mean lateness, cycle length = I + lateness).
The calendar starts 20 cycles before time 0 with a random phase, so it is in steady state when the window starts. Lots come from the plant simulation (same seeds); the calibration calendar is a separate simulated layer.
Not modelled: that the lot is actually wrong or held (at risk only), a grace period, several instruments, risk-based intervals, money.
"""
from __future__ import annotations

import dataclasses
import html as H
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


CAL = 25


def _overdue(rg, interval, late, horizon):
    t, out = -20.0 * (interval + late) - rg.random() * (interval + late), []   # start long before time 0 with a random phase, so the calendar is in steady state at the window
    while t < horizon:
        due = t + interval
        d = rg.expovariate(1 / late) if late > 0 else 0.0
        out.append((due, due + d)); t = due + d
    return out


def sweep(plant, lates: List[float], interval_d: float, n: int = 8) -> List[dict]:
    if interval_d <= 0 or not lates or any(x < 0 for x in lates):
        raise ValueError("need interval_d > 0 and lateness >= 0")
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        runs.append((r.horizon, [b.done for b in r.finished if r.horizon - r.window <= b.done <= r.horizon]))
    out = []
    for m in lates:
        sh = []
        for i, (hz, dones) in enumerate(runs):
            for j in range(CAL):   # many calendars per plant run: one overdue spell covers many lots, so the share is very noisy otherwise
                rg = random.Random(plant.seed * 104729 + i * 1000 + j)
                ov = _overdue(rg, interval_d * 24.0, m * 24.0, hz * 1.5)
                bad = sum(1 for t in dones if any(a <= t < b for a, b in ov))
                sh.append(bad / len(dones) if dones else 0.0)
        ci = mean_ci(sh)[:3]
        out.append({"late": m, "share": tuple(min(1.0, max(0.0, x)) for x in ci), "th": m / (interval_d + m)})
    return out


def render_html(rows: List[dict], interval_d: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["share"][2], r["th"]) for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11"><polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/><polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % (
        " ".join("%.1f,%.1f" % (X(i), Y(r["share"][0])) for i, r in enumerate(rows)), " ".join("%.1f,%.1f" % (X(i), Y(r["th"])) for i, r in enumerate(rows)))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["late"]:g} d</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r["share"][1]):.1f}" y2="{Y(r["share"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">share of lots finished while the instrument is overdue, 0..{ymax * 100:.0f}% (dashed: closed form)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">mean lateness of the calibration, days (placeholder)</text></svg>')
    body = "".join(f"<tr><td>{r['late']:g} d</td><td>{r['share'][0] * 100:.1f}% [{r['share'][1] * 100:.1f}, {r['share'][2] * 100:.1f}]</td><td>{r['th'] * 100:.1f}%</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-019 calibration overdue (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-019 calibration overdue: lots at risk (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-019 "Calibration overdue" (injection: calendar event; spec provided by Javi, synthetic). Interval {interval_d:g} days (counted from the previous actual calibration) and the lateness are placeholders (TBD in the spec). Lots come from the plant simulation ({n} seeds x 25 calendars); "at risk" means the instrument was overdue when the lot finished, not that the result is wrong. Closed form: lateness/(interval+lateness). No grace period, one instrument, no money.</div>{''.join(s)}
<table><tr><th>Mean lateness</th><th>Lots at risk [CI]</th><th>closed form</th></tr>{body}</table></body></html>"""
