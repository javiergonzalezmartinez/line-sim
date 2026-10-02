import unittest
from plantsim.cli import load
from plantsim.crn import check, render_html


class T(unittest.TestCase):
    def test_check(self):
        a, b = load("examples/whatif_a.json"), load("examples/whatif_b.json")
        c = check(a, b, 5)
        m = c["metrics"]["Mean lead time (days)"]
        self.assertGreater(m["paired"], 0); self.assertGreater(m["indep"], 0)
        self.assertTrue(-1.0 <= m["rho"] <= 1.0)
        self.assertEqual(c["metrics"]["Mean lead time (days)"]["diff"], check(a, b, 5)["metrics"]["Mean lead time (days)"]["diff"])
        h = render_html(c)
        self.assertIn("Variance_reduction", h); self.assertIn("ONE stream", h)

    def test_same_scenario_is_perfectly_correlated(self):
        a = load("examples/whatif_a.json")
        m = check(a, a, 5)["metrics"]["Mean lead time (days)"]
        self.assertAlmostEqual(m["rho"], 1.0, places=6)
        self.assertAlmostEqual(m["paired"], 0.0, places=9)

    def test_needs_3(self):
        a = load("examples/whatif_a.json")
        with self.assertRaises(ValueError):
            check(a, a, 2)
