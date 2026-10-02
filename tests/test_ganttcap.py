import unittest
from plantsim.ganttcap import build, render_html, _lanes
from plantsim.cli import load
from plantsim.model import simulate

class T(unittest.TestCase):
    def test_lanes(self):
        out, n = _lanes([(0, 2), (1, 3), (2, 4), (3, 5)])
        self.assertEqual(n, 2)
        self.assertEqual(sorted(j for j, *_ in out), [0, 0, 1, 1])
    def test_build(self):
        p = load("examples/pharma_flow.json"); r = simulate(p)
        g = build(p, r, 7)
        for row in g["rows"]:
            self.assertLessEqual(row["lanes_needed"], row["servers"])
            self.assertAlmostEqual(row["bars_util"], row["busy_util"], delta=0.04)
            self.assertLessEqual(row["busy_util"], row["all_util"] + 1e-9)
        h = render_html(g)
        self.assertIn("Finite-capacity", h); self.assertIn("<rect", h)
if __name__ == "__main__": unittest.main()
