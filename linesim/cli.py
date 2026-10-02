"""Command line: python -m linesim config.json [--out report.html]"""
from __future__ import annotations

import argparse
import json
import sys

from .report import render
from .sim import Config, Station, simulate, sweep_buffer


def load(path: str) -> Config:
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    st = [Station(s["name"], s["cycle_time"], s.get("cv", 0.0), s.get("mtbf"), s.get("mttr", 0.0)) for s in d["stations"]]
    return Config(st, d["buffers"], d.get("duration", 8 * 3600.0), d.get("warmup", 3600.0), d.get("seed", 1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="linesim", description="Serial production line simulator")
    ap.add_argument("config")
    ap.add_argument("--out", default="report.html")
    ap.add_argument("--sizes", default="0,1,2,4,8,16,32", help="buffer sizes for the sweep")
    a = ap.parse_args(argv)
    cfg = load(a.config)
    res = simulate(cfg)
    sweep = sweep_buffer(cfg, [int(x) for x in a.sizes.split(",")])
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(render(cfg, res, sweep))
    print(f"throughput {res.throughput:.1f} parts/h, busiest station: {res.bottleneck}")
    for s in res.stations:
        sh = s.shares(res.window)
        print(f"  {s.name:<14} working {sh['busy']:6.1%}  down {sh['down']:6.1%}  blocked {sh['blocked']:6.1%}  starved {sh['starved']:6.1%}")
    print("buffer sweep (parts/h): " + ", ".join(f"{r['buffer']}: {r['throughput']:.1f}" for r in sweep))
    print(f"report written to {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
