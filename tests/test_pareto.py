import os, unittest
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.pareto import losses, render_html

EX = os.path.join(os.path.dirname(__file__), "..", "examples", "pm_b.json")
P = load(EX); R = simulate(P); ROWS = losses(P, R)


class T(unittest.TestCase):
    def test_sorted_and_cumulative(self):
        hs = [r["hours"] for r in ROWS]
        self.assertEqual(hs, sorted(hs, reverse=True))
        self.assertAlmostEqual(ROWS[-1]["cum"], 1.0, 9)
        self.assertAlmostEqual(sum(r["share"] for r in ROWS), 1.0, 9)

    def test_matches_stats(self):
        tot = sum(r["hours"] for r in ROWS)
        exp = sum(s.repair + s.setup + s.pm + s.blocked + s.short_hours for s in R.stats)
        self.assertAlmostEqual(tot, exp, 6)

    def test_page(self):
        h = render_html(ROWS)
        self.assertIn("illustrative", h); self.assertIn("Not modelled", h)

if __name__ == "__main__":
    unittest.main()
