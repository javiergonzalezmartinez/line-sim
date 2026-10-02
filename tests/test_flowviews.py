import os, tempfile, unittest
from plantsim.cli import load, main
from plantsim.model import simulate
from plantsim.flowviews import heatmap, flow, gantt

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "pharma_flow.json")
P = load(EX); R = simulate(P)


class F(unittest.TestCase):
    def test_heatmap_bounds_and_total(self):
        h = heatmap(P, R, 12)
        self.assertEqual(len(h["rows"]), sum(1 for s in P.stages if s.kind == "process"))
        for row in h["rows"]:
            self.assertEqual(len(row["util"]), 12)
            for u in row["util"]:
                self.assertGreaterEqual(u, 0.0); self.assertLessEqual(u, 1.0 + 1e-9)

    def test_heatmap_hours_match_traces(self):
        h = heatmap(P, R, 12)
        k = [i for i, s in enumerate(P.stages) if s.kind == "process"][0]
        row = h["rows"][0]
        occ = sum(row["util"]) * row["servers"] * h["bucket_h"]
        want = sum(e - s for b in R.batches for (i, a, s, e) in b.trace if i == k and s >= 0 and e <= R.horizon)
        self.assertAlmostEqual(occ, want, 4)

    def test_flow_conservation(self):
        f = flow(P, R)
        self.assertEqual(f["stages"][0][1], f["total"])
        reached = [x[1] for x in f["stages"]]
        self.assertEqual(reached, sorted(reached, reverse=True))
        lost = sum(x[2] + x[3] for x in f["stages"])
        self.assertEqual(f["finished"] + lost, f["total"])

    def test_gantt_lot_is_sequential(self):
        for lot in gantt(P, R, 6)["lots"]:
            prev_end = None
            for b in lot["bars"]:
                self.assertLessEqual(b["arrive"], b["start"] + 1e-9); self.assertLessEqual(b["start"], b["end"] + 1e-9)
                if prev_end is not None:
                    self.assertGreaterEqual(b["arrive"], prev_end - 1e-6)
                prev_end = b["end"]

    def test_cli_page(self):
        out = os.path.join(tempfile.mkdtemp(), "f.html")
        main([EX, "--flow-view", out])
        t = open(out, encoding="utf-8").read()
        self.assertIn("Synthetic and illustrative", t); self.assertEqual(t.count("<svg"), 3)
