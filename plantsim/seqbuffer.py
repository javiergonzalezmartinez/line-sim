"""FME-012 "Out-of-order messages": what does a sequence buffer with a timeout cost? (synthetic, illustrative)

Spec record FME-012 (spec/failures.json): domain Interface, detection "sequence gap", safe response "sequence buffer + timeout", simulation injection "reorder stream". The spec gives no
message rate, delay or timeout (TBD); none is claimed.
Model (this code's choice, not from a source): each finished lot of the plant simulation sends a stream of `m` numbered messages `g` seconds apart; every message gets an independent network delay,
exponential with mean `d` seconds, so later messages can overtake earlier ones. The receiver keeps a sequence buffer: it delivers message n only after n-1 was delivered or skipped; when a later
message arrives while n is missing, it waits at most T seconds (counted from the arrival that opened the gap) and then skips n (a sequence gap is flagged) and delivers what it holds. A skipped message that arrives afterwards is discarded as late.
Per row (T): share of messages skipped (late beyond T), mean added latency of the delivered messages (delivery time minus arrival time), and the number of messages per day affected (lots per day from the plant simulation x m).
Estimate of the skipped share: a message is skipped when it is later than its next neighbour by more than g + T, probability 1/2 exp(-(g+T)/d) (ignores the other successors, so it is an approximation).
Closed form checked: with exponential delays and spacing g, a message is overtaken by its successor with probability 1/2 exp(-g/d) (the pair arrives swapped); the simulated raw swap share must agree.
Not modelled: loss of messages (that is FME-009/013), duplicates (FME-011), several senders, retransmission requests, clock skew (FME-015), money.
"""
from __future__ import annotations

import dataclasses
import math
import random
from typing import List

from .model import simulate
from .whatif import mean_ci


def run_stream(rg, m: int, g: float, d: float, T: float):
    """One lot: returns (swapped_pairs, skipped, latencies)."""
    arr = sorted((i * g + rg.expovariate(1.0 / d), i) for i in range(m))
    at = {s: t for t, s in arr}
    swapped = sum(1 for i in range(m - 1) if at[i] > at[i + 1])
    st = {"exp": 0, "skip": 0, "dl": None}
    held, lat = {}, []

    def flush(now):
        while st["exp"] in held:
            lat.append(now - held.pop(st["exp"])); st["exp"] += 1

    def fire_until(t):
        while st["dl"] is not None and st["dl"] <= t and held:
            nxt = min(held)
            st["skip"] += nxt - st["exp"]; st["exp"] = nxt
            fired = st["dl"]
            flush(fired)
            st["dl"] = fired + T if held else None
        if not held:
            st["dl"] = None

    for t, sq in arr:
        fire_until(t)
        if sq < st["exp"]:
            continue  # arrived after it was skipped: discarded as late
        held[sq] = t
        before = st["exp"]
        flush(t)
        if st["exp"] != before or not held:
            st["dl"] = None
        if held and st["dl"] is None:
            st["dl"] = t + T
    fire_until(float("inf"))
    return swapped, st["skip"], lat


def sweep(plant, ts: List[float], m: int, g: float, d: float, n: int = 8, reps: int = 300) -> List[dict]:
    if m < 2 or g <= 0 or d <= 0 or not ts or any(t < 0 for t in ts):
        raise ValueError("need m>=2, g>0, d>0, T>=0")
    lots = []
    for i in range(n):
        r = simulate(dataclasses.replace(plant, seed=plant.seed + i))
        lots.append(sum(1 for b in r.finished if r.horizon - r.window <= b.done <= r.horizon) / (r.window / 24.0))
    per_day = sum(lots) / len(lots)
    out = []
    for T in ts:
        sw, sk, la = [], [], []
        for i in range(n):
            rg = random.Random(plant.seed * 2750159 + i + int(T * 100))
            s_, k_, l_ = 0, 0, []
            for _ in range(reps):
                a, b, c = run_stream(rg, m, g, d, T)
                s_ += a; k_ += b; l_.extend(c)
            sw.append(s_ / (reps * (m - 1))); sk.append(k_ / (reps * m))
            la.append(sum(l_) / len(l_) if l_ else 0.0)
        out.append({"T": T, "swap": mean_ci(sw)[:3], "skip": mean_ci(sk)[:3], "lat": mean_ci(la)[:3], "swap_th": 0.5 * math.exp(-g / d), "skip_th": 0.5 * math.exp(-(g + T) / d),
                    "day_skip": per_day * m * mean_ci(sk)[0], "per_day": per_day})
    return out


def render_html(rows: List[dict], m: int, g: float, d: float, n: int) -> str:
    W, Hh, L0 = 700, 230, 50
    X = lambda i: L0 + (W - L0 - 30) * i / max(len(rows) - 1, 1)
    ymax = max(r["skip"][2] for r in rows) * 1.1 or 1.0
    Y = lambda v: 16 + (Hh - 60) * (1 - v / ymax)
    s = [f'<svg width="{W}" height="{Hh}" font-size="11">',
         '<polyline points="%s" fill="none" stroke="#c0392b" stroke-width="2.5"/>' % " ".join("%.1f,%.1f" % (X(i), Y(r["skip"][0])) for i, r in enumerate(rows))]
    for i, r in enumerate(rows):
        s.append(f'<text x="{X(i):.1f}" y="{Hh - 26}" text-anchor="middle">T {r["T"]:g} s</text><line x1="{X(i):.1f}" x2="{X(i):.1f}" y1="{Y(max(r["skip"][1], 0)):.1f}" y2="{Y(r["skip"][2]):.1f}" stroke="#c0392b"/>')
    s.append(f'<text x="4" y="12" fill="#c0392b">share of messages skipped (late beyond the timeout), 0..{ymax * 100:.1f}%</text><text x="{L0}" y="{Hh - 8}" fill="#5c6b80">timeout of the sequence buffer, seconds (placeholder)</text></svg>')
    f = lambda t, k=2: f"{t[0]:.{k}f} [{max(t[1], 0):.{k}f}, {t[2]:.{k}f}]"
    body = "".join(f"<tr><td>{r['T']:g} s</td><td>{r['skip'][0] * 100:.2f}% [{max(r['skip'][1], 0) * 100:.2f}, {r['skip'][2] * 100:.2f}]</td><td>{r['skip_th'] * 100:.2f}%</td><td>{f(r['lat'])}</td><td>{r['day_skip']:.2f}</td></tr>" for r in rows)
    return f"""<!doctype html><html><head><meta charset=utf-8><title>FME-012 out-of-order messages (synthetic)</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}</style></head><body><h2>FME-012 out-of-order messages: sequence buffer and timeout (synthetic)</h2><div class=n>Synthetic and illustrative. Spec record FME-012 "Out-of-order messages" (spec provided by Javi, synthetic): sequence gap, sequence buffer plus timeout. Each lot ({rows[0]['per_day']:.2f} per day, {n} seeds of the plant simulation) sends {m} numbered messages {g:g} s apart; each has an independent exponential delay with mean {d:g} s (all placeholders, TBD in the spec). Closed form checked on the raw stream: a pair arrives swapped with probability 1/2 exp(-g/d) = {rows[0]['swap_th'] * 100:.1f}%; simulated {rows[0]['swap'][0] * 100:.1f}% [{max(rows[0]['swap'][1], 0) * 100:.1f}, {rows[0]['swap'][2] * 100:.1f}]. The buffer delivers in order and skips a missing message after T seconds; a skipped message that arrives later is discarded. Not modelled: lost messages (FME-009/013), duplicates (FME-011), several senders, retransmission requests, clock skew, money.</div>{''.join(s)}
<table><tr><th>Timeout T</th><th>Messages skipped [CI]</th><th>Estimate 1/2 exp(-(g+T)/d)</th><th>Mean added latency, s [CI]</th><th>Skipped messages per day</th></tr>{body}</table></body></html>"""
