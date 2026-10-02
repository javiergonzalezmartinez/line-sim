import unittest
from plantsim.cli import load
from plantsim.printer import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_zero_repair_no_delay(self):
        r = sweep(self.P, [0], 100, 2)[0]
        self.assertEqual((r["share"][0], r["mean"][0], r["p95"][0]), (0.0, 0.0, 0.0))

    def test_close_to_formula_and_monotone(self):
        r = sweep(self.P, [1, 8], 100, 4)
        self.assertLess(r[0]["share"][0], r[1]["share"][0])
        self.assertAlmostEqual(r[1]["share"][0], r[1]["p_down"], delta=0.05)
        self.assertAlmostEqual(r[1]["mean"][0], r[1]["mean_th"], delta=0.4)

    def test_validation(self):
        for a in (([1], 0), ([], 100), ([-1], 100)):
            with self.assertRaises(ValueError):
                sweep(self.P, *a, 2)

    def test_page(self):
        h = render_html(sweep(self.P, [2], 100, 2), 100, 2)
        self.assertIn("FME-026", h); self.assertIn("TBD", h)
