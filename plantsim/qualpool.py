"""FME-025 "Task executed by unqualified person": how many qualified people keep the denied tasks short? (synthetic, illustrative)

Spec record FME-025 (spec/failures.json): domain Human, detection "qualification guard", immediate effect "task denied", downstream "capacity impact",
safe response "reassign qualified resource", simulation injection "qualification unavailable", GxP CRITICAL. The spec gives no task length or pool size (TBD); none is claimed.
Model (this code's choice, not from a source): every finished lot of the plant simulation creates one task of `s` hours that only a qualified person may do. The pool has c qualified
people. The guard denies any other person; if all qualified people are busy the task is denied for now and reassigned to the first qualified person who becomes free (FIFO).
Per row (c): share of tasks that find no qualified person free (denied first), mean wait before a qualified person starts, and utilisation of the pool, against the Erlang C formulas
for an M/M/c queue (Poisson arrivals, exponential task length; see Wikipedia "M/M/c queue"): P(wait) = C(c, A), Wq = C(c, A) / (c mu - lambda), A = lambda s.
With a FIXED task length the M/D/c wait is about half of the M/M/c one, so both the full Erlang C value and its half are shown. Lots leave a pipeline with regular spacing (less variable than Poisson) but some finish at the same instant, so the two effects pull in opposite directions; the simulated wait is compared, not assumed.
Not modelled: shifts and absences (the injection "qualification unavailable" is the pool size c itself), qualification per task type, training time, overtime, money.
"""
from __future__ import annotations

import dataclasses
import heapq
import math
from typing import List

from .model import simulate
from .whatif import mean_ci


def erlang_c(c: int, A: float) -> float:
    if A >= c:
        return 1.0
    top = (A ** c / math.factorial(c)) * (c / (c - A))
    return top / (sum(A ** k / math.factorial(k) for k in range(c)) + top)


def sweep(plant, cs: List[int], s_h: float, n: int = 8) -> List[dict]:
    if s_h <= 0 or not cs or any(c < 1 for c in cs):
        raise ValueError("need s>0, c>=1")
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = r.horizon - r.window
        runs.append((r.window, sorted(b.done for b in r.finished if t0 <= b.done <= r.horizon)))
    lam = sum(len(x[1]) / x[0] for x in runs) / len(runs)
    A = lam * s_h
    out = []
    for c in cs:
        denied, wait, util = [], [], []
        for win, dones in runs:
            free = [0.0] * c
            heapq.heapify(free)
            w, d, busy = [], 0, 0.0
            for t in dones:
                f = heapq.heappop(free)
                st = max(t, f)
                if st > t + 1e-9:
                    d += 1
                w.append((st - t))
                heapq.heappush(free, st + s_h)
                busy += s_h
            nl = len(dones)
            if nl:
                denied.append(d / nl); wait.append(sum(w) / nl)
            util.append(busy / (c * win))
        rho = A / c
        pc = erlang_c(c, A)
        wq = pc / (c / s_h - lam) if A < c else float("inf")
        out.append({"c": c, "denied": mean_ci(denied)[:3], "wait": mean_ci(wait)[:3], "util": mean_ci(util)[:3],
                    "pw_th": pc, "wq_th": wq, "wqd_th": wq / 2.0, "rho": rho, "A": A})
    return out


def render_html(rows: List[dict], s_h: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["wait"][2], r["wq_th"]) for r in rows if r["wq_th"] != float("inf")) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - min(v, ymax) / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["wait"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["wq_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["c"]} qualified</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["wait"][1], 0)):.1f}" y2="{Y(r["wait"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">mean wait for a qualified person, hours, 0..{ymax:.1f} (dashed: Erlang C, M/M/c)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">size of the qualified pool (placeholder)</text></svg>')
    f = lambda t, k=2: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['c']}</td><td>{r['rho'] * 100:.0f}%</td><td>{r['denied'][0] * 100:.0f}%</td><td>{r['pw_th'] * 100:.0f}%</td><td>{f(r['wait'])}</td><td>{r['wq_th']:.2f}</td><td>{r['wqd_th']:.2f}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-025 task by unqualified person (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-025 task by an unqualified person: how many qualified people (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-025 "Task executed by unqualified person" (spec provided by Javi, synthetic): qualification guard, task denied, reassign a qualified resource. Each finished lot ({n} seeds of the plant simulation) creates one task of {s_h:g} h (placeholder, TBD in the spec) that only a qualified person may do; if all qualified people are busy the task is denied for now and goes to the first one that is free. Closed forms: Erlang C for M/M/c (Poisson arrivals, exponential tasks; source Wikipedia "M/M/c queue"); with a fixed task length the wait is about half of it. Lots leave a pipeline with regular spacing (less variable than Poisson) but some finish at the same instant, so the two effects pull in opposite directions; the simulated wait is compared, not assumed. No shifts or absences (the injection is the pool size), no task types, no training, no money.</div>{''.join(s)}
<table><tr><th>Qualified people</th><th>Load per person</th><th>Denied first [sim]</th><th>Erlang C P(wait)</th><th>Mean wait, h [CI]</th><th>Erlang C Wq, h</th><th>about half (fixed length)</th></tr>{body}</table></body></html>"""
