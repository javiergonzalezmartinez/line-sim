import unittest
from plantsim.clockskew import sweep, render_html, closed_forms, K
from plantsim.cli import load

class T(unittest.TestCase):
    def test_closed(self):
        m, f, w = closed_forms(50, 24, 1.0, 1.0)
        self.assertAlmostEqual(m, 25 * 12 * K)
        self.assertGreater(f, 0); self.assertLess(w, f)
        m2, f2, w2 = closed_forms(50, 1, 1.0, 1.0)
        self.assertEqual((f2, w2), (0.0, 0.0))
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [1, 24, 168], 50, 1.0, 1.0, 3, 40)
        self.assertLessEqual(r[0]["wrong"][0], r[1]["wrong"][0]); self.assertLessEqual(r[1]["wrong"][0], r[2]["wrong"][0])
        for x in r: self.assertAlmostEqual(x["mean"][0], x["mean_th"], delta=0.25 * x["mean_th"] + 1e-3)
        self.assertIn("ppm", render_html(r, 50, 1.0, 1.0, 3))
    def test_bad(self):
        with self.assertRaises(ValueError): sweep(load("examples/pharma_flow.json"), [], 50, 1, 1)
if __name__ == "__main__": unittest.main()
