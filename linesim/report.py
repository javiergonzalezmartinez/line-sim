"""Single-file HTML report (own SVG, no external resources)."""
from __future__ import annotations

import html
from typing import List

from .sim import Config, Result

COLORS = {"busy": "#00857c", "down": "#b3261e", "blocked": "#c98a00", "starved": "#8a94a6"}
LABELS = {"busy": "Working", "down": "Down (repair)", "blocked": "Blocked", "starved": "Starved"}


def _stack_chart(res: Result) -> str:
    w, rowh, left = 640, 34, 120
    h = 40 + rowh * len(res.stations)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Time shares per station">']
    for k, key in enumerate(COLORS):
        out.append(f'<rect x="{left + k * 120}" y="6" width="10" height="10" fill="{COLORS[key]}"/>'
                   f'<text x="{left + k * 120 + 14}" y="15" font-size="11">{LABELS[key]}</text>')
    for r, s in enumerate(res.stations):
        y = 30 + r * rowh
        out.append(f'<text x="{left - 8}" y="{y + 16}" font-size="12" text-anchor="end">{html.escape(s.name)}</text>')
        x = left
        for key, share in s.shares(res.window).items():
            wd = (w - left - 10) * max(share, 0)
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{wd:.1f}" height="22" fill="{COLORS[key]}">'
                       f'<title>{html.escape(s.name)} - {LABELS[key]}: {share:.1%}</title></rect>')
            if share > 0.08:
                out.append(f'<text x="{x + wd / 2:.1f}" y="{y + 15}" font-size="11" fill="#fff" text-anchor="middle">{share:.0%}</text>')
            x += wd
    out.append("</svg>")
    return "".join(out)


def _sweep_chart(rows: List[dict]) -> str:
    w, h, l, b, t = 640, 260, 60, 40, 16
    hi = max(r["max"] for r in rows) * 1.08 or 1
    lo = 0.0
    px = lambda i: l + (w - l - 20) * (i / max(len(rows) - 1, 1))
    py = lambda v: t + (h - t - b) * (1 - (v - lo) / (hi - lo))
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Throughput versus buffer size">']
    for g in range(5):
        v = lo + (hi - lo) * g / 4
        out.append(f'<line x1="{l}" x2="{w - 20}" y1="{py(v):.1f}" y2="{py(v):.1f}" stroke="#e3e8ee"/>'
                   f'<text x="{l - 6}" y="{py(v) + 4:.1f}" font-size="11" text-anchor="end">{v:.0f}</text>')
    band = " ".join(f"{px(i):.1f},{py(r['max']):.1f}" for i, r in enumerate(rows)) + " " + \
        " ".join(f"{px(i):.1f},{py(r['min']):.1f}" for i, r in reversed(list(enumerate(rows))))
    out.append(f'<polygon points="{band}" fill="#00857c" opacity="0.15"/>')
    out.append('<polyline fill="none" stroke="#00857c" stroke-width="2.5" points="' +
               " ".join(f"{px(i):.1f},{py(r['throughput']):.1f}" for i, r in enumerate(rows)) + '"/>')
    for i, r in enumerate(rows):
        out.append(f'<circle cx="{px(i):.1f}" cy="{py(r["throughput"]):.1f}" r="3.5" fill="#00857c"><title>buffer {r["buffer"]}: {r["throughput"]:.1f} parts/h</title></circle>'
                   f'<text x="{px(i):.1f}" y="{h - b + 16}" font-size="11" text-anchor="middle">{r["buffer"]}</text>')
    out.append(f'<text x="{(l + w) / 2}" y="{h - 6}" font-size="11" text-anchor="middle">Buffer capacity between stations (parts)</text></svg>')
    return "".join(out)


def render(cfg: Config, res: Result, sweep: List[dict], title: str = "Line simulation") -> str:
    rows = "".join(
        f"<tr><td>{html.escape(s.name)}</td><td>{cfg.stations[i].cycle_time:g}</td><td>{s.shares(res.window)['busy']:.1%}</td>"
        f"<td>{s.shares(res.window)['down']:.1%}</td><td>{s.shares(res.window)['blocked']:.1%}</td><td>{s.shares(res.window)['starved']:.1%}</td><td>{s.parts}</td></tr>"
        for i, s in enumerate(res.stations))
    ideal = 3600.0 / max(s.cycle_time for s in cfg.stations)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:">
<title>{html.escape(title)}</title><style>
body{{font:14px/1.45 system-ui,sans-serif;margin:0;color:#070f26}}header{{background:#070f26;color:#fff;padding:14px 20px}}h1{{margin:0;font-size:20px}}
main{{padding:0 20px 24px;max-width:960px}}h2{{color:#005b96;font-size:16px;margin:22px 0 8px}}.cards{{display:flex;gap:10px;flex-wrap:wrap}}
.card{{background:#f7f9fb;border:1px solid #d5dce4;border-radius:6px;padding:8px 12px;min-width:150px}}.card small{{display:block;color:#4a5668}}.card b{{font-size:20px}}
table{{border-collapse:collapse;width:100%}}th{{background:#070f26;color:#fff;text-align:left;padding:6px 8px;font-size:12px}}td{{padding:5px 8px;border-top:1px solid #d5dce4}}
.note{{margin:12px 0;padding:8px 12px;border-left:4px solid #c98a00;background:#fff6d6}}</style></head><body>
<header><h1>{html.escape(title)}</h1></header><main>
<div class="note"><b>Fictitious example line.</b> The numbers describe an invented line, not any real plant.</div>
<h2>Result</h2><div class="cards">
<div class="card"><small>Throughput (after warm-up)</small><b>{res.throughput:.1f} parts/h</b></div>
<div class="card"><small>Slowest station alone would give</small><b>{ideal:.1f} parts/h</b></div>
<div class="card"><small>Loss vs that ideal</small><b>{(1 - res.throughput / ideal):.1%}</b></div>
<div class="card"><small>Busiest station</small><b>{html.escape(res.bottleneck)}</b></div></div>
<h2>Where each station spends its time</h2>{_stack_chart(res)}
<table><tr><th>Station</th><th>Cycle (s)</th><th>Working</th><th>Down</th><th>Blocked</th><th>Starved</th><th>Parts</th></tr>{rows}</table>
<h2>What do bigger buffers buy?</h2>{_sweep_chart(sweep)}
<p>Line: mean over seeds; shaded band: min to max. Run: {cfg.duration / 3600:g} h simulated, {cfg.warmup / 3600:g} h warm-up discarded.</p>
</main></body></html>"""
