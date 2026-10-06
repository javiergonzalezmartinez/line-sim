import random, unittest
from plantsim.backuptest import sweep, render_html, closed, closed_exact, _one
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
    def test_phase_corrected_form(self):
        mu, Tt = 0.0111 / 24, 90 * 24.0
        rg = random.Random(11)
        p, ls = _one(rg, 24, mu, Tt, 12, 24 * 365 * 150, 40000)
        m = sum(ls) / len(ls)
        P1, M1 = closed(24, mu, Tt, 12); P2, M2 = closed_exact(24, mu, Tt, 12)
        self.assertLess(abs(M2 - m) / m, 0.08); self.assertAlmostEqual(P2, p, delta=0.02)
        self.assertGreater(abs(M1 - m) / m, 0.10)          # the uniform-phase form is clearly off here
        a, b = closed(24, 1e-6, 24.0, 12), closed_exact(24, 1e-6, 24.0, 12)
        self.assertAlmostEqual(a[1], b[1], delta=0.01 * a[1])   # equal when mu Tt is small
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [1, 30, 180], 24, 1 / 90.0, 12, 3, 1500)
        self.assertLess(r[0]["mean"][0], r[2]["mean"][0])
        self.assertIn("renewal", render_html(r, 24, 1 / 90.0, 12, 3))
        # the table's formula is the phase-corrected one; the first form is kept only as a comparison column
        for row in r:
            P, M = closed_exact(24, 1 / 90.0 / 24, row["Tt"] * 24.0, 12); P0, M0 = closed(24, 1 / 90.0 / 24, row["Tt"] * 24.0, 12)
            self.assertAlmostEqual(row["mean_th"], M, places=9); self.assertAlmostEqual(row["mean_old"], M0, places=9)
        self.assertGreater(r[2]["mean_th"], r[2]["mean_old"] * 1.15)    # at 180 d the corrected form is well above the uniform-phase one
        self.assertIn("phase-corrected", render_html(r, 24, 1 / 90.0, 12, 3))
    def test_bad(self):
        with self.assertRaises(ValueError): sweep(load("examples/pharma_flow.json"), [], 24, 0.1, 1)
if __name__ == "__main__": unittest.main()
