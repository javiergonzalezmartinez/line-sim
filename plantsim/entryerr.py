"""FME-024 "Critical manual entry error": what does an independent second check buy? (synthetic, illustrative)

Spec record FME-024 (spec/failures.json): detection "second check/electronic validation", effect "entry rejected/corrected", downstream "wrong data risk",
safe response "independent check", simulation injection "input error model". The spec gives no error rate (TBD) and none is claimed.
Model (this code's choice, not from a source): each finished lot in the measurement window has `entries` critical manual entries; every entry is wrong with
probability p; an independent second check catches a wrong entry with probability d (independent of the first, no common cause); a caught entry is corrected
and costs `fix_min` minutes of operator time; an uncaught one is a residual wrong-data entry.
Per row (p): residual wrong entries per 1000 lots without a check (N p) and with it (N p (1-d)), both simulated with the same lots and seeds and compared
with the closed form; the plain-language check: the two must agree within the Monte Carlo interval. Lots come from the plant simulation (synthetic).
Not modelled: common-cause errors (the same mistake twice), a checker who learns or tires, errors that change the process, the cost of a wrong entry, money.
"""
from __future__ import annotations

import dataclasses
import html as H
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, ps: List[float], d: float, entries: int, fix_min: float, n: int = 8) -> List[dict]:
    if not 0 <= d <= 1 or entries < 1 or fix_min < 0 or not ps or any(not 0 <= p <= 1 for p in ps):
        raise ValueError("need 0<=p<=1, 0<=d<=1, entries>=1, fix_min>=0")
    lots = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        lots.append(sum(1 for b in r.finished if r.horizon - r.window <= b.done <= r.horizon))
    out = []
    for p in ps:
        res0, res1, fix = [], [], []
        for i, nl in enumerate(lots):
            rg = random.Random(plant.seed * 1000 + i)
            wrong = sum(1 for _ in range(nl * entries) if rg.random() < p)
            caught = sum(1 for _ in range(wrong) if rg.random() < d)
            per = 1000.0 / nl if nl else 0.0
            res0.append(wrong * per); res1.append((wrong - caught) * per); fix.append(caught * fix_min / 60.0)
        out.append({"p": p, "no": mean_ci(res0)[:3], "chk": mean_ci(res1)[:3], "fix_h": mean_ci(fix)[:3],
                    "no_th": 1000.0 * entries * p, "chk_th": 1000.0 * entries * p * (1 - d)})
    return out


def render_html(rows: List[dict], d: float, entries: int, fix_min: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(r["no"][2] for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["no"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#00857c" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["chk"][0])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["p"] * 100:g}%</text>')
    s.append(f'<text x="4" y="12" fill="#c0392b">no check: wrong entries per 1000 lots, 0..{ymax:.0f}</text><text x="{W - 300}" y="12" fill="#00857c">with second check (d={d * 100:g}%)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">error probability per entry (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['p'] * 100:g}%</td><td>{f(r['no'])}</td><td>{r['no_th']:.1f}</td><td>{f(r['chk'])}</td><td>{r['chk_th']:.1f}</td><td>{f(r['fix_h'], 1)}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-024 manual entry error (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-024 manual entry error: what a second check buys (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-024 "Critical manual entry error" (spec provided by Javi, synthetic): independent second check, entry corrected. Error probability, check detection d={d * 100:g}%, {entries} critical entries per lot and {fix_min:g} min per correction are placeholders (TBD in the spec, no real rate claimed). Lots come from the plant simulation ({n} seeds); the error draws are a separate simulated layer and are compared with the closed form N p (1-d). Assumes the two checks are independent (no common-cause error), no money.</div>{''.join(s)}
<table><tr><th>p per entry</th><th>No check: wrong /1000 lots [CI]</th><th>closed form</th><th>With check [CI]</th><th>closed form</th><th>Correction hours in window [CI]</th></tr>{body}</table></body></html>"""
