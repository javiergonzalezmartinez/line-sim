import unittest
from plantsim.interlock import sweep, render_html
from plantsim.cli import load

class T(unittest.TestCase):
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [0.003, 0.03], 2.0, 3)
        self.assertLess(r[0]["trips"][0], r[1]["trips"][0])
        for x in r:
            self.assertAlmostEqual(x["trips"][0], x["trips_th"], delta=0.35 * x["trips_th"] + 0.2)
            self.assertAlmostEqual(x["aff"][0], x["aff_th"], delta=0.03)
            self.assertAlmostEqual(x["abort"][0], x["abort_th"], delta=0.5 * x["abort_th"] + 0.5)
            self.assertGreater(x["rstar"], 0)
        self.assertIn("restart", render_html(r, 2.0, 3).lower())
    def test_bad(self):
        p = load("examples/pharma_flow.json")
        with self.assertRaises(ValueError): sweep(p, [0], 2.0)
        with self.assertRaises(ValueError): sweep(p, [0.1], -1)
if __name__ == "__main__": unittest.main()
