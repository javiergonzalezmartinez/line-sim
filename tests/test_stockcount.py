import unittest
from plantsim.cli import load
from plantsim.stockcount import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_close_to_formulas(self):
        r = sweep(self.P, [7], 0.1, 6, 5, 12)[0]
        self.assertAlmostEqual(r["share"][0], r["share_th"], delta=0.1)
        self.assertAlmostEqual(r["rms"][0], r["rms_th"], delta=r["rms_th"] * 0.3)
        self.assertAlmostEqual(r["age"][0], r["age_th"], delta=1.0)

    def test_more_counting_means_less_exposure(self):
        a, b = sweep(self.P, [2, 14], 0.1, 6, 5, 6)
        self.assertLess(a["share"][0], b["share"][0]); self.assertLess(a["rms"][0], b["rms"][0])
        self.assertLess(a["share_th"], b["share_th"])

    def test_no_errors(self):
        r = sweep(self.P, [7], 0.0, 6, 5, 2)[0]
        self.assertEqual((r["share"][0], r["rms"][0], r["share_th"], r["rms_th"]), (0.0, 0.0, 0.0, 0.0))

    def test_interval_longer_than_window_gives_zero(self):
        r = sweep(self.P, [200], 0.1, 6, 5, 2)[0]
        self.assertEqual(r["share"][0], 0.0)

    def test_validation(self):
        for a in (([], 0.1, 6, 5), ([7], 1.5, 6, 5), ([7], 0.1, 0, 5), ([7], 0.1, 6, -1), ([0], 0.1, 6, 5)):
            with self.assertRaises(ValueError):
                sweep(self.P, *a, 2)

    def test_page(self):
        h = render_html(sweep(self.P, [7], 0.1, 6, 5, 2), 0.1, 6, 5, 2)
        self.assertIn("FME-003", h); self.assertIn("TBD", h)
