"""Trade-off of the same_product_first rule against its starvation guard (synthetic, illustrative).

The guard `dispatch_max_wait_h` (config key) makes a lot that has waited longer than that go first, even if a changeover is needed.
Aging as a way to avoid starvation is described at https://en.wikipedia.org/wiki/Aging_(scheduling) (read 2 Oct 2026, general
operating-systems description; this is an analogy for lots in a queue, not an implementation of any published factory rule).
For each guard value (and for plain FIFO) the plant is simulated over `n` seeds; the page shows setup hours and the longest queue wait
with 95% confidence intervals (t distribution, as in whatif.py) and throughput.
Not modelled: due dates, per-product priorities, a smooth ageing score (this is a hard threshold), guard values per stage.
"""
from __future__ import annotations

import dataclasses
from typing import List, Optional

from .whatif import mean_ci, replicate


def sweep(plant, guards: List[Optional[float]], n: int = 10) -> List[dict]:
    out = []
    fifo = dataclasses.replace(plant, dispatch="fifo", dispatch_max_wait_h=None)
    cases = [("FIFO", fifo)] + [("no guard" if g is None else f"guard {g:g} h", dataclasses.replace(plant, dispatch="same_product_first", dispatch_max_wait_h=g)) for g in guards]
    for name, p in cases:
        rs = replicate(p, n)
        row = {"name": name}
        for key, short in (("Setup hours (all stages)", "setup"), ("Longest queue wait (h)", "wait"), ("Throughput (batches/week)", "thr")):
            row[short] = mean_ci([r[key] for r in rs])[:3]
        out.append(row)
    return out


def render_html(rows: List[dict]) -> str:
    import html as H
    W, Hh, L, B = 760, 340, 70, 44
    xs = [r["wait"][0] for r in rows]; ys = [r["setup"][0] for r in rows]
    x0, x1 = 0, max(r["wait"][2] for r in rows) * 1.08
    y0, y1 = min(r["setup"][1] for r in rows) * 0.95, max(r["setup"][2] for r in rows) * 1.03
    X = lambda v: L + (W - L - 20) * (v - x0) / ((x1 - x0) or 1)
    Y = lambda v: 16 + (Hh - B - 16) * (1 - (v - y0) / ((y1 - y0) or 1))
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">']
    for i, r in enumerate(rows):
        c = "#868e96" if r["name"] == "FIFO" else "#00857c"
        (mx, lx, hx), (my, ly, hy) = r["wait"], r["setup"]
        s.append(f'<line x1="{X(lx):.1f}" x2="{X(hx):.1f}" y1="{Y(my):.1f}" y2="{Y(my):.1f}" stroke="{c}"/><line x1="{X(mx):.1f}" x2="{X(mx):.1f}" y1="{Y(ly):.1f}" y2="{Y(hy):.1f}" stroke="{c}"/><circle cx="{X(mx):.1f}" cy="{Y(my):.1f}" r="5" fill="{c}"/><text x="{X(mx) + 8:.1f}" y="{Y(my) - 6:.1f}" fill="{c}">{H.escape(r["name"])}</text>')
    s.append(f'<text x="{L}" y="{Hh - 8}" fill="#5c6b80">longest queue wait (h), mean and 95% CI</text><text x="4" y="12" fill="#5c6b80">setup hours (all stages)</text></svg>')
    body = "".join(f"<tr><td>{H.escape(r['name'])}</td><td>{r['setup'][0]:,.0f} [{r['setup'][1]:,.0f}, {r['setup'][2]:,.0f}]</td><td>{r['wait'][0]:,.0f} [{r['wait'][1]:,.0f}, {r['wait'][2]:,.0f}]</td><td>{r['thr'][0]:.2f} [{r['thr'][1]:.2f}, {r['thr'][2]:.2f}]</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Dispatch guard trade-off (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:900px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>Same product first: starvation guard trade-off (synthetic)</h2><div class=n>Synthetic and illustrative. Each row is the mean over the same seeds with a 95% confidence interval. The guard is a hard waiting-time threshold, inspired by the aging idea (Wikipedia, "Aging (scheduling)", read 2 Oct 2026). Example changeover times are placeholders, so the size of the effects means nothing for a real line.</div>{''.join(s)}
<table><tr><th>Rule</th><th>Setup hours [95% CI]</th><th>Longest queue wait h [95% CI]</th><th>Throughput /week [95% CI]</th></tr>{body}</table></body></html>"""
