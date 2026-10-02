import unittest
from plantsim.dupid import sweep, render_html
from plantsim.cli import load

class T(unittest.TestCase):
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [5, 6, 9], 4, 3, 30)
        self.assertGreater(r[0]["any"][0], r[1]["any"][0])
        self.assertGreaterEqual(r[1]["any"][0], r[2]["any"][0])
        self.assertAlmostEqual(r[0]["any"][0], r[0]["any_th"], delta=0.1)
        self.assertLess(r[2]["any_th"], 1e-2)
        self.assertIn("birthday", render_html(r, 4, 3, 30))
    def test_bad(self):
        p = load("examples/pharma_flow.json")
        for a in ([], [0], [10]):
            with self.assertRaises(ValueError): sweep(p, a, 4)
        with self.assertRaises(ValueError): sweep(p, [3], 0)
if __name__ == "__main__": unittest.main()
