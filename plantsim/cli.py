from __future__ import annotations
import argparse, json, sys
from .model import Plant, Stage, simulate

def load(path):
    d = json.load(open(path, encoding="utf-8"))
    st = []
    for s in d["stages"]:
        s = dict(s)
        if "window" in s:
            s["window"] = tuple(s["window"])
        st.append(Stage(**s))
    return Plant(st, d["products"], d["release_every"], d.get("horizon", 2016), d.get("warmup", 336), d.get("seed", 1), d.get("layout"), d.get("m_per_px", 0.0), d.get("speed_kmh", 6.0), d.get("handling_min", 6.0))

def main(argv=None):
    ap = argparse.ArgumentParser(prog="plantsim"); ap.add_argument("config"); ap.add_argument("--view", help="write animated HTML view")
    a = ap.parse_args(argv)
    p = load(a.config); r = simulate(p)
    print(f"throughput {r.throughput_per_week:.2f} batches/week, mean lead time {r.mean_lead_time_days:.1f} days, busiest: {r.bottleneck}, rejected lots in window: {r.rejected}")
    for st, sg in zip(r.stats, p.stages):
        if sg.kind == 'hold':
            continue
        u = r.utilisation(st); n = max(st.batches, 1)
        print(f"  {st.name:<28} proc {u['process']:5.0%} setup {u['setup']:5.0%} repair {u['repair']:5.0%}  mean wait {st.wait/n:6.1f} h")
    for n, u in r.pool_utilisation(p).items():
        print(f"  pool {n}: busy {u:.0%}")
    if a.view:
        from .view import render
        open(a.view, 'w', encoding='utf-8').write(render(p, r))
        print('view written to', a.view)
    return 0
if __name__ == "__main__":
    sys.exit(main())
