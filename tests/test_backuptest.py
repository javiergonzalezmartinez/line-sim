import random, unittest
from plantsim.backuptest import sweep, render_html, closed, _one
from plantsim.cli import load

class T(unittest.TestCase):
    def test_closed(self):
        P, M = closed(24, 1 / 2160.0, 7 * 24.0, 12)
        self.assertGreater(P, 0); self.assertGreater(M, 12)
        P0, M0 = closed(24, 1e-12, 24.0, 12)
        self.assertAlmostEqual(M0, 12.0, places=3)
    def test_sim_matches(self):
        rg = random.Random(3)
        p, ls = _one(rg, 24, 1 / 500.0, 168.0, 12, 24 * 365 * 40, 20000)
        P, M = closed(24, 1 / 500.0, 168.0, 12)
        self.assertAlmostEqual(p, P, delta=0.02)
        self.assertAlmostEqual(sum(ls) / len(ls), M, delta=0.12 * M)
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [1, 30, 180], 24, 1 / 90.0, 12, 3, 1500)
        self.assertLess(r[0]["mean"][0], r[2]["mean"][0])
        self.assertIn("renewal", render_html(r, 24, 1 / 90.0, 12, 3))
    def test_bad(self):
        with self.assertRaises(ValueError): sweep(load("examples/pharma_flow.json"), [], 24, 0.1, 1)
if __name__ == "__main__": unittest.main()
