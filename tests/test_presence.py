import unittest
from plantsim.presence import sweep, render_html
from plantsim.cli import load

class T(unittest.TestCase):
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [0.01, 0.05, 0.2], 0.3, 3, 6, 15, 4)
        self.assertLess(r[0]["wt"][0], r[2]["wt"][0])
        for x in r:
            self.assertAlmostEqual(x["wt"][0], x["wt_th"], delta=0.3 * x["wt_th"] + 0.02)
            self.assertAlmostEqual(x["un"][0], x["un_th"], delta=0.12)
        self.assertIn("blind retry", render_html(r, 0.3, 3, 6, 15, 4).lower())
    def test_bad(self):
        p = load("examples/pharma_flow.json")
        with self.assertRaises(ValueError): sweep(p, [1.0], 0.3, 3, 6, 15)
        with self.assertRaises(ValueError): sweep(p, [0.1], 0.3, 0, 6, 15)
if __name__ == "__main__": unittest.main()
