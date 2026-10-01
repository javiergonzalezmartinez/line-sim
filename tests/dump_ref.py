"""Writes Python reference results for the JS engine cross-check (used by tests/engine.test.js)."""
import json, sys
from plantsim.cli import load
from plantsim.model import simulate
def ref(path, zero=False, seeds=(1,)):
    out = []
    for sd in seeds:
        p = load(path); p.seed = sd
        if zero:
            for s in p.stages: s.cv = 0; s.breakdown_p = 0; s.retest_p = 0
        r = simulate(p)
        out.append({"seed": sd, "tp": r.throughput_per_week, "lt": r.mean_lead_time_days, "done": [b.done for b in r.batches][:30]})
    return out
if __name__ == "__main__":
    json.dump({"zero": ref("examples/pharma_flow.json", True), "stat": ref("examples/pharma_flow.json", False, tuple(range(1, 21)))}, open(sys.argv[1], "w"))
