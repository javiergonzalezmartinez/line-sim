"""CONWIP card sweep: throughput and time inside the plant against the number of cards (synthetic, illustrative).

CONWIP as read (2 Oct 2026) at https://en.wikipedia.org/wiki/CONWIP : a pull-oriented control that limits the work in process of a whole
line with cards; a new job is let in only when a card is free (when a job leaves), so the WIP is capped while it is not
tuned station by station as in kanban. The original paper is Spearman, Woodruff and Hopp (1990); only its listing pages were seen.
How it is applied here (choices of this code): `conwip` = maximum number of lots inside the plant (all lots share the cards); orders that
find no free card wait outside, in order of arrival (first in, first out), and keep their original release time as the order date, so
"lead time" includes that wait while "time inside the plant" starts when the lot enters. Rejected lots return their card when they leave.
The simulation keeps running after the horizon until every released order is done, so the window throughput is what is compared. Each card count is simulated over the same seeds; means with 95% CI (t distribution, as in whatif.py).
Not modelled: card counts per product, different cards per product family, order priorities, a card delay after the lot finishes.
"""
from __future__ import annotations

import dataclasses
from typing import List, Optional

from .whatif import mean_ci, replicate


def sweep(plant, cards: List[Optional[int]], n: int = 8) -> List[dict]:
    out = []
    for c in cards:
        rs = replicate(dataclasses.replace(plant, conwip=c), n)
        row = {"cards": c}
        for key, short in (("Throughput (batches/week)", "thr"), ("Mean time inside the plant (days)", "ins"), ("Mean lead time (days)", "lt"), ("Mean wait for a card (days)", "wait")):
            xs = [r.get(key, float("nan")) for r in rs]
            row[short] = mean_ci(xs)[:3] if all(x == x for x in xs) else None
        if c is None:                      # no cards: nothing waits outside, inside time = lead time
            row["ins"], row["wait"] = row["lt"], (0.0, 0.0, 0.0)
        out.append(row)
    return out


def render_html(rows: List[dict]) -> str:
    W, Hh, L, B = 700, 260, 60, 34
    num = [r for r in rows if r["cards"] is not None]
    thr_max = max(r["thr"][2] for r in rows) * 1.08
    X = lambda i: L + (W - L - 60) * i / max(len(rows) - 1, 1)
    Y = lambda v: 14 + (Hh - B - 14) * (1 - v / thr_max)
    ins_max = max((r["ins"][2] for r in rows if r["ins"]), default=1.0) * 1.08
    Y2 = lambda v: 14 + (Hh - B - 14) * (1 - v / ins_max)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">']
    pt = " ".join(f"{X(i):.1f},{Y(r['thr'][0]):.1f}" for i, r in enumerate(rows))
    s.append(f'<polyline points="{pt}" fill="none" stroke="#00857c" stroke-width="2.5"/>')
    ins_pts = [(i, r) for i, r in enumerate(rows) if r["ins"]]
    p2 = " ".join("%.1f,%.1f" % (X(i), Y2(r["ins"][0])) for i, r in ins_pts)
    s.append(f'<polyline points="{p2}" fill="none" stroke="#c0392b" stroke-width="2.5"/>')
    for i, r in enumerate(rows):
        lab = "no limit" if r["cards"] is None else str(r["cards"])
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 14}" text-anchor="middle">{lab}</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(r["thr"][1]):.1f}" y2="{Y(r["thr"][2]):.1f}" stroke="#00857c"/>')
    s.append(f'<text x="{L}" y="{Hh - 2}" fill="#5c6b80">number of cards (lots allowed inside the plant)</text><text x="4" y="12" fill="#00857c">throughput /week (green) 0..{thr_max:.1f}</text><text x="{W - 250}" y="12" fill="#c0392b">time inside the plant, days (red) 0..{ins_max:.0f}</text></svg>')
    f = lambda t, d=2: "-" if t is None else f"{t[0]:.{d}f} [{t[1]:.{d}f}, {t[2]:.{d}f}]"
    body = "".join(f"<tr><td>{'no limit' if r['cards'] is None else r['cards']}</td><td>{f(r['thr'])}</td><td>{f(r['ins'], 1)}</td><td>{f(r['lt'], 1)}</td><td>{f(r['wait'], 1)}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>CONWIP card sweep (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:900px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>CONWIP: cards against throughput and time inside the plant (synthetic)</h2><div class=n>Synthetic and illustrative: placeholder parameters, fast order release so that the cards bind. CONWIP idea as described at en.wikipedia.org/wiki/CONWIP (read 2 Oct 2026): a cap on the lots inside the whole line, a new lot enters when one leaves. Orders without a free card wait outside in arrival order and count in the lead time, not in the time inside the plant. Same seeds for every row, 95% CI.</div>{''.join(s)}
<table><tr><th>Cards</th><th>Throughput /week [CI]</th><th>Time inside plant, days [CI]</th><th>Lead time incl. waiting for a card, days [CI]</th><th>Mean wait for a card, days [CI]</th></tr>{body}</table></body></html>"""
