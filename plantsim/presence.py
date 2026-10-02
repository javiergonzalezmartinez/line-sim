"""FME-007 "Source presence missing": blind retry against stop and reconcile (synthetic, illustrative)

Spec record FME-007 (spec/failures.json): domain Movement, detection "sensor/scan timeout", safe response "no blind retry; reconcile physical/logical", simulation injection "presence=false".
The spec gives no miss rate, retry count or reconcile time (TBD); none is claimed.
Model (this code's choice, not from a source): every move task of the plant simulation (all lots, all stages of kind "move") finds the source empty with probability q. A share `absent` of those cases
is a real absence (the unit is not there although the system says it is); the rest is a transient sensor miss (the unit is there; each new attempt misses again with probability q).
  blind retry (the unsafe policy, shown for contrast): the vehicle goes again up to n times. Against a real absence every retry fails (n wasted trips and still unresolved); against a transient miss
  retry k fails with probability q^k. A trip costs `trip` minutes of vehicle time.
  stop and reconcile (the spec): no retry; a person reconciles the physical and the logical stock in `rec` minutes and the case is resolved (found, or booked as missing).
Per row (q): events per day, wasted trips per day and wasted vehicle minutes per day with blind retry, share of events still unresolved after the retries, and the reconcile minutes per day of the safe policy;
closed forms: events = moves per day x q; wasted trips per event = absent x n + (1 - absent) x (q + q^2 + ... + q^n); unresolved = absent.
Not modelled: several vehicles queueing behind a blocked trip, the cost of a lot waiting, a reconcile that takes longer at night, money.
"""
from __future__ import annotations

import dataclasses
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def sweep(plant, qs: List[float], absent: float, n_retry: int, trip: float, rec: float, n: int = 8) -> List[dict]:
    if not 0 <= absent <= 1 or n_retry < 1 or trip <= 0 or rec < 0 or not qs or any(not 0 < q < 1 for q in qs):
        raise ValueError("need 0<q<1, 0<=absent<=1, retries>=1, trip>0, rec>=0")
    moves = []
    mk = [k for k, s in enumerate(plant.stages) if s.kind == "move"]
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = r.horizon - r.window
        cnt = sum(1 for b in r.batches for (k, a, s, e) in b.trace if k in mk and t0 <= s <= r.horizon)
        runs.append((cnt, r.window / 24.0))
    per_day = sum(c / d for c, d in runs) / len(runs)
    out = []
    for q in qs:
        ev, wt, un = [], [], []
        for i, (cnt, days) in enumerate(runs):
            rg = random.Random(plant.seed * 982451 + i + int(q * 1e4))
            e = w = u = 0
            for _ in range(cnt):
                if rg.random() < q:
                    e += 1
                    if rg.random() < absent:
                        w += n_retry; u += 1
                    else:
                        for _k in range(n_retry):
                            if rg.random() < q:
                                w += 1
                            else:
                                break
                        else:
                            u += 1
            ev.append(e / days); wt.append(w / days); un.append(u / e if e else 0.0)
        geo = sum(q ** k for k in range(1, n_retry + 1))
        tr_th = absent * n_retry + (1 - absent) * geo
        un_th = absent + (1 - absent) * q ** n_retry
        out.append({"q": q, "ev": mean_ci(ev)[:3], "wt": mean_ci(wt)[:3], "un": mean_ci(un)[:3],
                    "ev_th": per_day * q, "wt_th": per_day * q * tr_th, "un_th": un_th, "min": mean_ci(wt)[0] * trip, "rec_min": mean_ci(ev)[0] * rec, "moves": per_day})
    return out


def render_html(rows: List[dict], absent: float, n_retry: int, trip: float, rec: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["min"], r["rec_min"]) for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["min"])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#00857c" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["rec_min"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">q {r["q"] * 100:g}%</text>')
    s.append(f'<text x="4" y="12" fill="#c0392b">red: vehicle minutes wasted per day by blind retry; green: reconcile minutes per day (stop and reconcile); 0..{ymax:.0f}</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">share of move tasks that find the source empty (placeholder)</text></svg>')
    f = lambda t, k=2: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['q'] * 100:g}%</td><td>{r['ev'][0]:.2f}</td><td>{f(r['wt'])}</td><td>{r['wt_th']:.2f}</td><td>{r['min']:.1f}</td><td>{r['un'][0] * 100:.0f}%</td><td>{r['un_th'] * 100:.0f}%</td><td>{r['rec_min']:.1f}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-007 source presence missing (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-007 source presence missing: blind retry against reconcile (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-007 "Source presence missing" (spec provided by Javi, synthetic): no blind retry, reconcile physical and logical. The plant simulation ({n} seeds) has {rows[0]['moves']:.1f} move tasks per day. A share q of them finds the source empty; {absent * 100:g}% of those cases are a real absence, the rest a transient sensor miss. Blind retry (unsafe, for contrast): up to {n_retry} more trips of {trip:g} min; against a real absence every retry fails. Stop and reconcile (the spec): {rec:g} min of a person, no retry, every case resolved. All numbers are placeholders, TBD in the spec. Closed forms: wasted trips per event = absent x n + (1 - absent)(q + ... + q^n). Not modelled: vehicles queueing behind a blocked trip, the cost of a lot waiting, money.</div>{''.join(s)}
<table><tr><th>q</th><th>Events per day</th><th>Wasted trips per day, blind retry [CI]</th><th>closed form</th><th>Wasted vehicle min per day</th><th>Unresolved after retries</th><th>closed form</th><th>Reconcile min per day (spec)</th></tr>{body}</table></body></html>"""
