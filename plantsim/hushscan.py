"""FME-001 "Wrong HU scanned": what do rejected scans cost, and what slips through? (synthetic, illustrative)

Spec record FME-001 (spec/failures.json): domain Identity, detection "scan mismatch", effect "reject action", downstream "prevents wrong move/consume",
safe response "block + rescan + audit", simulation injection "Bernoulli on scan". The spec gives no wrong-scan rate (TBD) and none is claimed.
Model (this code's choice, not from a source): each finished lot in the measurement window needs `moves` scans (one per move or consume step).
Every scan attempt picks the wrong handling unit with probability s (Bernoulli). The system detects the mismatch with probability d (spec: it rejects the action,
so d = 1 by default); a detected one is blocked, audited and rescanned after `rescan_min` minutes; an undetected wrong scan lets the wrong move through (an escape).
The attempts repeat until one is accepted. Per attempt the chance to stop is 1 - s d, so per move the closed forms are: rejects s d / (1 - s d),
escapes s (1-d) / (1 - s d), extra operator time rejects x rescan_min.
Per row (s): rejects (= audit entries) and escapes per 1000 lots and the extra operator hours in the window, simulated with the same lots and seeds and compared with the closed forms.
Lots come from the plant simulation (synthetic); the scan draws are a separate simulated layer.
Not modelled: a repeated mistake by the same operator (not independent), scanner faults, the rescan delay holding the lot in the plant (no feedback), the cost of an escape, money.
"""
from __future__ import annotations

import dataclasses
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, ss: List[float], d: float, moves: int, rescan_min: float, n: int = 8) -> List[dict]:
    if not 0 <= d <= 1 or moves < 1 or rescan_min < 0 or not ss or any(not 0 <= s < 1 for s in ss) or any(s * d >= 1 for s in ss):
        raise ValueError("need 0<=s<1, 0<=d<=1, moves>=1, rescan_min>=0")
    lots = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        lots.append(sum(1 for b in r.finished if r.horizon - r.window <= b.done <= r.horizon))
    out = []
    for s in ss:
        rej, esc, hrs = [], [], []
        for i, nl in enumerate(lots):
            rg = random.Random(plant.seed * 1237 + i)
            rj = ec = 0
            for _ in range(nl * moves):
                while True:
                    if rg.random() < s:
                        if rg.random() < d:
                            rj += 1; continue
                        ec += 1
                    break
            per = 1000.0 / nl if nl else 0.0
            rej.append(rj * per); esc.append(ec * per); hrs.append(rj * rescan_min / 60.0)
        q = s * d
        out.append({"s": s, "rej": mean_ci(rej)[:3], "esc": mean_ci(esc)[:3], "hours": mean_ci(hrs)[:3],
                    "rej_th": 1000.0 * moves * q / (1 - q), "esc_th": 1000.0 * moves * s * (1 - d) / (1 - q)})
    return out


def render_html(rows: List[dict], d: float, moves: int, rescan_min: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(r["rej"][2] for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#00857c" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["rej"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["rej_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["s"] * 100:g}%</text>')
    s.append(f'<text x="4" y="12" fill="#00857c">rejected scans (audit entries) per 1000 lots, 0..{ymax:.0f} (dashed: closed form)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">probability that a scan picks the wrong HU (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['s'] * 100:g}%</td><td>{f(r['rej'])}</td><td>{r['rej_th']:.1f}</td><td>{f(r['esc'])}</td><td>{r['esc_th']:.2f}</td><td>{f(r['hours'], 1)}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-001 wrong HU scanned (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-001 wrong HU scanned: rejects, rescans, escapes (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-001 "Wrong HU scanned" (spec provided by Javi, synthetic): scan mismatch, reject the action, block, rescan and audit. Wrong-scan probability, mismatch detection d={d * 100:g}%, {moves} scans per lot and {rescan_min:g} min per rescan are placeholders (TBD in the spec, no real rate claimed). Lots come from the plant simulation ({n} seeds); the scan draws are a separate simulated layer compared with the closed forms rejects = moves s d/(1-s d) and escapes = moves s (1-d)/(1-s d) per lot. Independent scans (no repeated operator mistake), no feedback on the plant, no money.</div>{''.join(s)}
<table><tr><th>Wrong-scan probability</th><th>Rejects (audit entries) /1000 lots [CI]</th><th>closed form</th><th>Escapes /1000 lots [CI]</th><th>closed form</th><th>Extra operator hours in window [CI]</th></tr>{body}</table></body></html>"""
