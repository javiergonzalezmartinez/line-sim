import os, unittest
from plantsim.cli import load
from plantsim.warmup import welch, settles, analyse, render_html, done_series, wip_series
from plantsim.model import simulate
import dataclasses

P = load(os.path.join(os.path.dirname(__file__), "..", "examples", "pharma_flow.json"))


class T(unittest.TestCase):
    def test_welch_shrinks_at_start(self):
        sm = welch([1, 2, 3, 4, 5, 6, 7], 2)
        self.assertEqual(len(sm), 5)
        self.assertAlmostEqual(sm[0], 1.0)            # window half-width 0 at i=0
        self.assertAlmostEqual(sm[1], 2.0)            # half-width 1: mean(1,2,3)
        self.assertAlmostEqual(sm[2], 3.0)            # full width 5: mean(1..5)
        self.assertAlmostEqual(sm[4], 5.0)

    def test_welch_bad_window(self):
        for w in (0, 7, 9):
            with self.assertRaises(ValueError):
                welch([1.0] * 7, w)

    def test_settles(self):
        self.assertEqual(settles([0, 1, 2, 10, 10, 10, 10, 10, 10, 10, 10, 10]), 3)
        self.assertEqual(settles([5.0] * 8), 0)

    def test_series_lengths_and_totals(self):
        r = simulate(dataclasses.replace(P, warmup=0.0))
        n = int(r.horizon // 24)
        self.assertEqual(len(wip_series(r)), n); self.assertEqual(len(done_series(r)), n)
        self.assertTrue(all(v >= 0 for v in wip_series(r)))

    def test_needs_five_replications_and_page(self):
        with self.assertRaises(ValueError):
            analyse(P, 4)
        a = analyse(P, 5, 7)
        h = render_html(a)
        self.assertIn("rule of this code", h); self.assertIn("Synthetic and illustrative", h)

if __name__ == "__main__":
    unittest.main()
