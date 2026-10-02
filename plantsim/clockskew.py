"""FME-015 "Clock skew": how often must clocks be synchronised? (synthetic, illustrative)

Spec record FME-015 (spec/failures.json): domain Interface, detection "timestamp monitor", safe response "flag quality + sync correction", simulation injection "clock drift".
The spec gives no drift rate, sync interval or threshold (TBD); none is claimed.
Model (this code's choice, not from a source): each device clock runs at a constant rate error r (parts per million, see Wikipedia "Parts-per_notation"), drawn uniformly from
[-R, R] per device; a sync service resets the offset to zero every S hours (random phase per device pair), so the offset at time t is r x (hours since the last sync) x 3600 x 1e-6 seconds per hour per ppm.
Events are the finished lots of the plant simulation: at each lot completion, device A stamps the end of a step and device B stamps the start of the next one `g` seconds later (true gap).
The timestamp monitor flags a stamp whose offset exceeds `theta` seconds (quality flag). The order of A and B is wrong when A's offset minus B's offset is larger than g.
Per row (S): mean absolute offset of A's stamps, share of stamps flagged, share of event pairs stamped in the wrong order, each against a closed form: with |r| uniform on [0, R] and the time since
the last sync uniform on [0, S], mean |offset| = (R/2)(S/2) k with k = 3600e-6 s per h per ppm; flagged share = E[max(0, 1 - theta/(|r| k S))]; wrong order = (1/2) E[max(0, 1 - g/(|d| k S))] with d = r_A - r_B (triangular on [-2R, 2R]).
Lots complete at irregular times, so the time since sync is only approximately uniform; the sample uses the lot times of the simulation.
Not modelled: drift that changes with temperature, step corrections that jump the clock, network delay in the sync (it is assumed perfect), several time sources, money.
"""
from __future__ import annotations

import dataclasses
import random
from typing import List

from .model import simulate
from .whatif import mean_ci

K = 3600e-6  # seconds of offset per hour per ppm


def _integrate(f, a, b, n=2000):
    h = (b - a) / n
    return sum(f(a + (i + 0.5) * h) for i in range(n)) * h


def closed_forms(R: float, S: float, theta: float, g: float):
    mean_abs = (R / 2.0) * (S / 2.0) * K
    flag = _integrate(lambda x: max(0.0, 1 - theta / (x * K * S)) if x > 0 else 0.0, 0.0, R) / R
    wrong = 0.5 * _integrate(lambda x: ((2 * R - x) / (2 * R ** 2)) * (max(0.0, 1 - g / (x * K * S)) if x > 0 else 0.0), 0.0, 2 * R)
    return mean_abs, flag, wrong


def sweep(plant, ss_h: List[float], R: float, theta: float, g: float, n: int = 8, pairs: int = 60) -> List[dict]:
    if R <= 0 or theta <= 0 or g <= 0 or not ss_h or any(s <= 0 for s in ss_h) or pairs < 1:
        raise ValueError("need R,theta,g,S>0")
    runs = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        t0 = r.horizon - r.window
        runs.append([b.done for b in r.finished if t0 <= b.done <= r.horizon])
    out = []
    for S in ss_h:
        ma, fl, wr = [], [], []
        for i, dones in enumerate(runs):
            rg = random.Random(plant.seed * 7368787 + i + int(S))
            a_off, flagged, wrong, tot = 0.0, 0, 0, 0
            for _ in range(pairs):
                ra, rb = rg.uniform(-R, R), rg.uniform(-R, R)
                ph = rg.uniform(0, S)
                for t in dones:
                    u = (t - ph) % S
                    oa, ob = ra * K * u, rb * K * u
                    a_off += abs(oa); flagged += abs(oa) > theta; wrong += (oa - ob) > g; tot += 1
            if tot:
                ma.append(a_off / tot); fl.append(flagged / tot); wr.append(wrong / tot)
        m_th, f_th, w_th = closed_forms(R, S, theta, g)
        out.append({"S": S, "mean": mean_ci(ma)[:3], "flag": mean_ci(fl)[:3], "wrong": mean_ci(wr)[:3], "mean_th": m_th, "flag_th": f_th, "wrong_th": w_th,
                    "max_th": R * K * S})
    return out


def render_html(rows: List[dict], R: float, theta: float, g: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(max(r["wrong"][2], r["wrong_th"]) for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["wrong"][0])) for i, r in enumerate(rows)),
         '<polyline points="%s" fill="none" stroke="#5c6b80" stroke-width="1.5" stroke-dasharray="5 4"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["wrong_th"])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">sync {r["S"]:g} h</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["wrong"][1], 0)):.1f}" y2="{Y(r["wrong"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">event pairs stamped in the wrong order, 0..{ymax * 100:.0f}% (dashed: closed form)</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">hours between clock syncs (placeholder)</text></svg>')
    f = lambda t, k=2: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['S']:g} h</td><td>{f(r['mean'])}</td><td>{r['mean_th']:.2f}</td><td>{r['max_th']:.1f}</td><td>{r['flag'][0] * 100:.1f}%</td><td>{r['flag_th'] * 100:.1f}%</td><td>{r['wrong'][0] * 100:.1f}% [{max(r['wrong'][1], 0) * 100:.1f}, {r['wrong'][2] * 100:.1f}]</td><td>{r['wrong_th'] * 100:.1f}%</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-015 clock skew (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-015 clock skew: how often to synchronise (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-015 "Clock skew" (spec provided by Javi, synthetic): timestamp monitor, flag quality, sync correction. Each device clock drifts at a constant rate drawn from +/-{R:g} ppm (a placeholder; ppm = parts per million, Wikipedia "Parts-per_notation"), a sync resets the offset every S hours. Events are the lot completions of the plant simulation ({n} seeds): device A stamps the end of a step, device B the start of the next one {g:g} s later. A stamp is flagged when its offset exceeds {theta:g} s; the order is wrong when A's offset minus B's is larger than {g:g} s. The closed forms assume the time since the last sync is uniform; lot completions are irregular, so a gap is possible. Not modelled: temperature-dependent drift, step corrections, network delay in the sync, several time sources, money.</div>{''.join(s)}
<table><tr><th>Sync every</th><th>Mean abs offset of A, s [CI]</th><th>closed form</th><th>worst case R k S, s</th><th>Stamps flagged</th><th>closed form</th><th>Pairs in wrong order [CI]</th><th>closed form</th></tr>{body}</table></body></html>"""
