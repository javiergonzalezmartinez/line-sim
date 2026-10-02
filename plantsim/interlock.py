"""FME-021 "Phase interlock trip": safe hold against abort and rerun (synthetic, illustrative)

Spec record FME-021 (spec/failures.json): domain Process, detection "control system", safe response "safe hold/abort rules", simulation injection "interlock event". The spec gives no trip rate,
hold time or rule choice (TBD); none is claimed.
Model (this code's choice, not from a source): during every run of a process stage of the plant simulation (runs inside the measurement window, their real lengths h) an interlock trips as a Poisson
process with `lam` trips per run-hour (the clock stops during a hold, so the exposure of one attempt is its own running time).
  safe hold: the run stops, a person clears the cause in `r` hours, the run resumes where it stopped. Extra time per run = (number of trips) x r.
  abort and rerun: the run is aborted at the trip and started again from the beginning; this repeats until an attempt finishes. Extra time per run = time of the aborted attempts.
Closed forms for one run of length h: share of runs with at least one trip = 1 - exp(-lam h); hold: extra = lam h r hours on average; abort and rerun: expected total running time = (exp(lam h) - 1) / lam
(a standard result for restarting a task of length h under Poisson interruptions), so extra = (exp(lam h) - 1) / lam - h. The simulated numbers use the same run lengths.
Per row (lam): trips per 30 days, runs affected, extra resource hours per 30 days for hold and for abort, and the break-even hold time r* = ((exp(lam h) - 1)/lam - h) / (lam h) averaged over runs, above which abort is cheaper.
Not modelled: scrapped batches (a share of aborts that cannot be rerun), yield loss, the cause of the trip, trips that depend on the product, queueing caused by the extra time, money.
"""
from __future__ import annotations

import dataclasses
import math
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, lams: List[float], r_h: float, n: int = 8) -> List[dict]:
    if r_h < 0 or not lams or any(l <= 0 for l in lams):
        raise ValueError("need lam>0, r>=0")
    pk = [k for k, s in enumerate(plant.stages) if s.kind == "process"]
    runs = []
    for i in range(n):
        res = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = res.horizon - res.window
        hs = [e - s for b in res.batches for (k, a, s, e) in b.trace if k in pk and t0 <= s <= res.horizon and e > s]
        runs.append((hs, res.window / 24.0))
    out = []
    for lam in lams:
        trips, aff, hold, abort = [], [], [], []
        for i, (hs, days) in enumerate(runs):
            rg = random.Random(plant.seed * 6700417 + i + int(lam * 1e5))
            t_n = a_n = 0
            h_x = ab_x = 0.0
            for h in hs:
                # one run, safe hold: count trips over h
                k, t = 0, rg.expovariate(lam)
                while t < h:
                    k += 1; t += rg.expovariate(lam)
                t_n += k; a_n += 1 if k else 0; h_x += k * r_h
                # one run, abort and rerun
                while True:
                    t = rg.expovariate(lam)
                    if t >= h:
                        break
                    ab_x += t
            sc = 30.0 / days
            trips.append(t_n * sc); aff.append(a_n / len(hs) if hs else 0.0); hold.append(h_x * sc); abort.append(ab_x * sc)
        allh = [h for hs, _d in runs for h in hs]
        per30 = sum(len(hs) / d for hs, d in runs) / len(runs) * 30.0
        mh = len(allh) and sum(allh) / len(allh)
        th_trips = per30 * sum(lam * h for h in allh) / len(allh)
        th_aff = sum(1 - math.exp(-lam * h) for h in allh) / len(allh)
        th_hold = th_trips * r_h
        th_abort = per30 * sum((math.exp(lam * h) - 1) / lam - h for h in allh) / len(allh)
        rstar = sum(((math.exp(lam * h) - 1) / lam - h) / (lam * h) for h in allh) / len(allh)
        out.append({"lam": lam, "trips": mean_ci(trips)[:3], "aff": mean_ci(aff)[:3], "hold": mean_ci(hold)[:3], "abort": mean_ci(abort)[:3],
                    "trips_th": th_trips, "aff_th": th_aff, "hold_th": th_hold, "abort_th": th_abort, "rstar": rstar, "runs": per30, "mean_h": mh})
    return out


def render_html(rows: List[dict], r_h: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["abort"][2], r["abort_th"], r["hold"][2]) for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["abort"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#00857c" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["hold"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["abort_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">{r["lam"]:g} /h</text>')
    s.append(f'<text x="4" y="12" fill="#c0392b">extra resource hours per 30 days: red abort and rerun (dashed: closed form), green safe hold of {r_h:g} h; 0..{ymax:.0f}</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">interlock trips per run-hour (placeholder)</text></svg>')
    f = lambda t, k=1: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['lam']:g}</td><td>{f(r['trips'])}</td><td>{r['trips_th']:.1f}</td><td>{r['aff'][0] * 100:.1f}% / {r['aff_th'] * 100:.1f}%</td><td>{f(r['hold'])}</td><td>{r['hold_th']:.1f}</td><td>{f(r['abort'])}</td><td>{r['abort_th']:.1f}</td><td>{r['rstar']:.1f}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-021 phase interlock trip (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-021 phase interlock trip: safe hold or abort and rerun (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-021 "Phase interlock trip" (spec provided by Javi, synthetic): safe hold / abort rules. Runs of process stages come from the plant simulation ({n} seeds, {rows[0]['runs']:.0f} runs per 30 days, mean {rows[0]['mean_h']:.1f} h). An interlock trips as a Poisson process with lam trips per run-hour (a placeholder, TBD in the spec). Safe hold: a person clears it in {r_h:g} h and the run resumes. Abort and rerun: the run starts again from the beginning until an attempt finishes. Closed forms: affected share 1 - exp(-lam h); hold extra lam h r; abort extra (exp(lam h) - 1)/lam - h per run (restart under Poisson interruptions). The last column is the hold time above which abort is cheaper. Not modelled: scrapped batches, yield loss, the cause of the trip, product-dependent trips, queueing from the extra time, money.</div>{''.join(s)}
<table><tr><th>lam /run-h</th><th>Trips per 30 d [CI]</th><th>closed form</th><th>Runs affected sim / formula</th><th>Hold: extra h per 30 d [CI]</th><th>formula</th><th>Abort: extra h per 30 d [CI]</th><th>formula</th><th>Break-even hold time, h</th></tr>{body}</table></body></html>"""
