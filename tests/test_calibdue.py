import unittest
from plantsim.cli import load
from plantsim.calibdue import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_on_time_never_at_risk(self):
        self.assertEqual(sweep(self.P, [0], 90, 2)[0]["share"][0], 0.0)

    def test_close_to_formula_and_monotone(self):
        r = sweep(self.P, [5, 20], 90, 4)
        self.assertLess(r[0]["share"][0], r[1]["share"][0])
        for x in r:
            self.assertAlmostEqual(x["share"][0], x["th"], delta=0.06)

    def test_validation(self):
        for a in (([1], 0), ([], 90), ([-1], 90)):
            with self.assertRaises(ValueError):
                sweep(self.P, *a, 2)

    def test_page(self):
        h = render_html(sweep(self.P, [5], 90, 2), 90, 2)
        self.assertIn("FME-019", h); self.assertIn("TBD", h)
