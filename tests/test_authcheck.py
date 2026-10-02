import unittest
from plantsim.authcheck import sweep, render_html
from plantsim.cli import load

class T(unittest.TestCase):
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [0.0, 0.05, 0.2], 0.9, 6, 30, 4)
        self.assertEqual(r[0]["unauth"][0], 0.0); self.assertEqual(r[0]["alerts"][0], 0.0)
        self.assertLess(r[1]["alerts"][0], r[2]["alerts"][0])
        self.assertAlmostEqual(r[2]["unauth"][0], r[2]["unauth_th"], delta=0.25 * r[2]["unauth_th"])
        full = sweep(p, [0.2], 1.0, 6, 30, 3)
        self.assertEqual(full[0]["unauth"][0], 0.0)
        self.assertIn("M/D/1", render_html(r, 0.9, 6, 30, 4))
    def test_bad(self):
        p = load("examples/pharma_flow.json")
        with self.assertRaises(ValueError): sweep(p, [0.1], 1.5, 6, 30)
        with self.assertRaises(ValueError): sweep(p, [0.1], 0.9, 6, 0)
if __name__ == "__main__": unittest.main()
