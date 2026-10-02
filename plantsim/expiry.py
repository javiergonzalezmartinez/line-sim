"""FME-006 "Expired lot selected": how many lots would a hold-time / expiry guard reject? (synthetic, illustrative)

Spec record FME-006 (spec/failures.json): detection "FEFO/expiry guard", immediate effect "candidate rejected", safe response "hard guard".
Here a lot "expires" when it waits in front of a stage longer than a limit (a hold-time limit). The limit values are placeholders: no real
hold time or shelf life is claimed, and the spec gives none (TBD).
Method: the plant runs unchanged (same seeds in every row); per lot the longest queue wait over its stages is read from the lot's `waits`.
A guard with limit L would have rejected the lots whose wait exceeded L at the stage where it did, so the page counts, for the lots that
finished in the measurement window, the share with a wait above L, and which stage causes most of them.
The CI is a t interval over seeds, clamped to 0..100% because a share cannot leave that range.
Not modelled: the rejection does not feed back (the rejected lot stays in the flow, so later waits are not relieved and its lost value is not
counted), no FEFO ordering, no per-material shelf life, no re-test or extension of a limit, no money.
"""
from __future__ import annotations

import dataclasses
import html as H
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, limits: List[float], n: int = 8) -> List[dict]:
    if not limits or any(x <= 0 for x in limits):
        raise ValueError("limits must be > 0 hours")
    runs = [simulate(dataclasses.replace(plant, seed=plant.seed + i)) for i in range(n)]
    names = [s.name for s in plant.stages]
    out = []
    for L in limits:
        shares, top = [], {k: 0 for k in names}
        for r in runs:
            fin = [b for b in r.finished if r.horizon - r.window <= b.done <= r.horizon]
            bad = 0
            for b in fin:
                w = {k: v for k, v in b.waits.items() if v > L}
                if w:
                    bad += 1
                    top[max(w, key=w.get)] += 1
            shares.append(bad / len(fin) if fin else 0.0)
        out.append({"limit": L, "share": tuple(min(1.0, max(0.0, x)) for x in mean_ci(shares)[:3]), "top": top})
    return out


def render_html(rows: List[dict], n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(r["share"][2] for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11"><polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["share"][0])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["limit"]:g} h</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r["share"][1]):.1f}" y2="{Y(r["share"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">share of lots a guard would reject, 0..{ymax * 100:.0f}%</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">queue-wait (hold-time) limit, hours</text></svg>')
    body = ""
    for r in rows:
        tp = sorted(r["top"].items(), key=lambda kv: -kv[1])[:2]
        tot = sum(r["top"].values())
        cause = ", ".join(f"{k} ({v / tot * 100:.0f}%)" for k, v in tp if v) if tot else "none"
        body += f"<tr><td>{r['limit']:g} h</td><td>{r['share'][0] * 100:.1f}% [{r['share'][1] * 100:.1f}, {r['share'][2] * 100:.1f}]</td><td>{H.escape(cause)}</td></tr>"
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-006 expiry guard (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:980px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-006 expired lot: what a hold-time guard would reject (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-006 "Expired lot selected" (spec provided by Javi, synthetic): detection by an expiry guard, the candidate is rejected. Limits are placeholders (no real hold time or shelf life, TBD in the spec). The plant runs unchanged, {n} seeds, 95% CI over seeds; a lot counts when it waited longer than the limit at any stage. The rejection does not feed back into the flow, no FEFO ordering, no money.</div>{''.join(s)}
<table><tr><th>Limit</th><th>Lots over the limit [CI]</th><th>Where it happens (largest share of causes)</th></tr>{body}</table></body></html>"""
