"""FME-027 "Wrong label association": what does the verification scan buy? (synthetic, illustrative)

Spec record FME-027 (spec/failures.json): domain Printing, detection "verification scan", effect "verification fails", downstream "traceability risk",
safe response "block HU + destroy/reissue label", simulation injection "mismatch event". The spec gives no mismatch rate (TBD) and none is claimed.
Model (this code's choice, not from a source): every lot finished in the measurement window gets one label; with probability p it is associated with the wrong
handling unit; each verification scan catches a wrong association with probability d (independent scans, `scans` of them); a caught one blocks the HU, the label is
destroyed and reissued and the HU waits `reissue_h` hours; an uncaught one is an escaped wrong label (a traceability risk).
Per row (d): escaped wrong labels per 1000 lots and blocked HUs per 1000 lots, simulated with the same lots and seeds and compared with the closed forms
1000 p (1-d)^scans and 1000 p (1-(1-d)^scans); hold hours in the window.
Lots come from the plant simulation (synthetic); the mismatch draws are a separate simulated layer.
Not modelled: common-cause errors (a scan that always misses the same defect), a mismatch that is not independent of the printer state (FME-026), the hold delaying the plant (no feedback), the cost of an escaped label, money.
"""
from __future__ import annotations

import dataclasses
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, ds: List[float], p: float, scans: int, reissue_h: float, n: int = 8) -> List[dict]:
    if not 0 <= p <= 1 or scans < 0 or reissue_h < 0 or not ds or any(not 0 <= d <= 1 for d in ds):
        raise ValueError("need 0<=p<=1, 0<=d<=1, scans>=0, reissue_h>=0")
    lots = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        lots.append(sum(1 for b in r.finished if r.horizon - r.window <= b.done <= r.horizon))
    out = []
    for d in ds:
        esc, blk, hold = [], [], []
        for i, nl in enumerate(lots):
            rg = random.Random(plant.seed * 1013 + i)
            e = b = 0
            for _ in range(nl):
                if rg.random() < p:
                    if any(rg.random() < d for _ in range(scans)):
                        b += 1
                    else:
                        e += 1
            per = 1000.0 / nl if nl else 0.0
            esc.append(e * per); blk.append(b * per); hold.append(b * reissue_h)
        miss = (1 - d) ** scans
        out.append({"d": d, "esc": mean_ci(esc)[:3], "blk": mean_ci(blk)[:3], "hold_h": mean_ci(hold)[:3],
                    "esc_th": 1000.0 * p * miss, "blk_th": 1000.0 * p * (1 - miss)})
    return out


def render_html(rows: List[dict], p: float, scans: int, reissue_h: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["esc"][2], r["blk"][2]) for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["esc"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#00857c" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["blk"][0])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["d"] * 100:g}%</text>')
    s.append(f'<text x="4" y="12" fill="#c0392b">escaped wrong labels per 1000 lots, 0..{ymax:.0f}</text><text x="{W - 250}" y="12" fill="#00857c">blocked HUs per 1000 lots</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">detection probability of one verification scan (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['d'] * 100:g}%</td><td>{f(r['esc'])}</td><td>{r['esc_th']:.2f}</td><td>{f(r['blk'])}</td><td>{r['blk_th']:.2f}</td><td>{f(r['hold_h'], 1)}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-027 wrong label association (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-027 wrong label association: what the verification scan buys (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-027 "Wrong label association" (spec provided by Javi, synthetic): verification scan, block the HU, destroy and reissue the label. Mismatch probability {p * 100:g}%, {scans} independent verification scan(s) and {reissue_h:g} h per reissue are placeholders (TBD in the spec, no real rate claimed). Lots come from the plant simulation ({n} seeds); the mismatch draws are a separate simulated layer compared with the closed forms 1000 p (1-d)^scans. No common-cause misses, no feedback on the plant, no money.</div>{''.join(s)}
<table><tr><th>Detection d per scan</th><th>Escaped /1000 lots [CI]</th><th>closed form</th><th>Blocked HUs /1000 lots [CI]</th><th>closed form</th><th>Hold hours in window [CI]</th></tr>{body}</table></body></html>"""
