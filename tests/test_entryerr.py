import unittest
from plantsim.cli import load
from plantsim.entryerr import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_formula_and_ordering(self):
        r = sweep(self.P, [0.03], 0.9, 6, 5, 4)[0]
        self.assertLessEqual(r["no"][1], r["no_th"] * 1.15)
        self.assertGreaterEqual(r["no"][2], r["no_th"] * 0.85)
        self.assertLess(r["chk"][0], r["no"][0])

    def test_perfect_check_and_zero_p(self):
        self.assertEqual(sweep(self.P, [0.03], 1.0, 6, 5, 2)[0]["chk"][0], 0.0)
        r = sweep(self.P, [0.0], 0.5, 6, 5, 2)[0]
        self.assertEqual((r["no"][0], r["fix_h"][0]), (0.0, 0.0))

    def test_validation(self):
        for a in (([], 0.9, 6, 5), ([0.1], 1.5, 6, 5), ([0.1], 0.9, 0, 5), ([2], 0.9, 6, 5)):
            with self.assertRaises(ValueError):
                sweep(self.P, *a, 2)

    def test_page(self):
        h = render_html(sweep(self.P, [0.01], 0.9, 6, 5, 2), 0.9, 6, 5, 2)
        self.assertIn("FME-024", h); self.assertIn("TBD", h)
