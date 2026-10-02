import os, tempfile, unittest, dataclasses
from plantsim.cli import load, main
from plantsim.model import simulate
from plantsim.oee import oee

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "pharma_flow.json")
P = load(EX); R = simulate(P); ROWS = oee(P, R)


class O(unittest.TestCase):
    def test_product_of_factors(self):
        for r in ROWS:
            self.assertAlmostEqual(r["OEE"], r["A"] * r["P"] * r["Q"], 12)
            self.assertAlmostEqual(r["OEE_planned"], r["OEE"] * r["loading"], 12)

    def test_bounds(self):
        for r in ROWS:
            for k in ("A", "Q", "loading"):
                self.assertGreaterEqual(r[k], 0.0); self.assertLessEqual(r[k], 1.0 + 1e-9)
            self.assertGreater(r["P"], 0.5); self.assertLess(r["P"], 1.5)

    def test_time_accounting(self):
        for r in ROWS:
            self.assertAlmostEqual(r["idle_h"] + r["busy_h"] + r["setup_h"] + r["repair_h"], r["planned_h"], 6)

    def test_no_losses_gives_unity(self):
        stages = [dataclasses.replace(s, cv=0.0, breakdown_p=0.0, changeover=0.0, retest_p=0.0) if s.kind == "process" else s for s in P.stages]
        q = dataclasses.replace(P, stages=stages)
        for r in oee(q, simulate(q)):
            if r["lots"]:
                self.assertAlmostEqual(r["A"], 1.0, 6); self.assertAlmostEqual(r["P"], 1.0, 1)

    def test_rejections_hit_quality(self):
        self.assertTrue(any(r["Q"] < 1.0 for r in ROWS))
        self.assertEqual(sum(r["rejected"] for r in ROWS), R.rejected)

    def test_cli_page(self):
        out = os.path.join(tempfile.mkdtemp(), "o.html")
        main([EX, "--oee-view", out])
        self.assertIn("Synthetic and illustrative", open(out, encoding="utf-8").read())
