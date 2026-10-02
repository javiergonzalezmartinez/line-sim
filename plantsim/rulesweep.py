"""Queue-rule comparison with due dates: FIFO, EDD, SPT and critical ratio (synthetic, illustrative).

Rule definitions as read (2 Oct 2026) at https://www.uky.edu/~dsianita/300/schedule.html and
https://metricgate.com/docs/critical-ratio-dispatch-rule/ :
  FIFO  first come, first served at each stage queue.
  EDD   earliest due date first.
  SPT   shortest processing time first (here: the nominal process time of the lot at that stage).
  CR    critical ratio = time remaining before the due date / remaining processing time; the smallest goes first (CR < 1: behind).
How they are applied here (choices of this code): remaining processing time = nominal process hours of the stages still ahead
(process stages only: queues, changeovers, moves and waits are not counted), times the product factor. Every rule is applied at each
process/move stage queue separately. `hours_factor` and `due_h` in the example are placeholders; with equal factors for all products
SPT and CR reduce to FIFO and EDD (that is why the example config sets different factors).
Each rule is simulated over the same seeds; the page shows means with 95% confidence intervals (t distribution, as in whatif.py).
Not modelled: setup-aware variants, dynamic due-date setting, release control, rule choice per stage.
"""
from __future__ import annotations

import dataclasses
import html as H
from typing import List

from .whatif import mean_ci, replicate

RULES = [("FIFO", "fifo"), ("EDD", "edd"), ("SPT", "spt"), ("CR", "cr")]
KEYS = [("Tardy lots (share)", "tardy", "{:.1%}"), ("Mean tardiness (h)", "mt", "{:,.0f}"), ("Maximum lateness (h)", "ml", "{:,.0f}"),
        ("Mean lead time (days)", "lt", "{:.1f}"), ("Throughput (batches/week)", "thr", "{:.2f}")]


def sweep(plant, n: int = 10) -> List[dict]:
    if plant.due_h is None:
        raise ValueError("the rules sweep needs due_h in the config")
    out = []
    for name, rule in RULES:
        rs = replicate(dataclasses.replace(plant, dispatch=rule, dispatch_max_wait_h=None), n)
        row = {"name": name}
        for key, short, _ in KEYS:
            row[short] = mean_ci([r[key] for r in rs])[:3]
        out.append(row)
    return out


def _bars(rows, short, title, fmt, color):
    W, bh, lw = 520, 22, 60
    hi = max(r[short][2] for r in rows) * 1.08 or 1
    sx = lambda v: lw + (W - lw - 70) * v / hi
    s = [f'<svg width="{W}" height="{len(rows) * bh + 26}" font-size="11"><text x="0" y="12" font-weight="bold">{title}</text>']
    for i, r in enumerate(rows):
        m, lo, up = r[short]; y = 22 + i * bh
        s.append(f'<text x="{lw - 6}" y="{y + 13}" text-anchor="end">{r["name"]}</text><rect x="{lw}" y="{y}" width="{sx(m) - lw:.1f}" height="{bh - 6}" fill="{color}"/>'
                 f'<line x1="{sx(lo):.1f}" x2="{sx(up):.1f}" y1="{y + 8}" y2="{y + 8}" stroke="#000"/><text x="{sx(up) + 5:.1f}" y="{y + 13}" fill="#5c6b80">{fmt.format(m)}</text>')
    s.append("</svg>")
    return "".join(s)


def render_html(rows: List[dict]) -> str:
    body = "".join("<tr><td><b>%s</b></td>%s</tr>" % (r["name"], "".join("<td>%s [%s, %s]</td>" % (f.format(r[sh][0]), f.format(r[sh][1]), f.format(r[sh][2])) for _, sh, f in KEYS)) for r in rows)
    head = "".join(f"<th>{k} [95% CI]</th>" for k, _, _ in KEYS)
    charts = '<div style="display:flex;flex-wrap:wrap;gap:20px">' + _bars(rows, "mt", "Mean tardiness (h)", "{:,.0f}", "#c98a00") + _bars(rows, "ml", "Maximum lateness (h)", "{:,.0f}", "#c0392b") + _bars(rows, "tardy", "Tardy lots (share)", "{:.0%}", "#845ef7") + _bars(rows, "thr", "Throughput (batches/week)", "{:.2f}", "#00857c") + "</div>"
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Queue rules with due dates (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1100px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FIFO, EDD, SPT and critical ratio with due dates (synthetic)</h2><div class=n>Synthetic and illustrative. Rule definitions as read at uky.edu/~dsianita/300/schedule.html and metricgate.com/docs/critical-ratio-dispatch-rule (2 Oct 2026). Due dates and the per-product process-time factors are placeholders, and they overload this plant, so only the ranking of rules under this model means anything, not the numbers. Remaining work counts nominal process hours only. Same seeds for every rule; bars are means, whiskers 95% CI.</div>{charts}
<table><tr><th>Rule</th>{head}</tr>{body}</table></body></html>"""
