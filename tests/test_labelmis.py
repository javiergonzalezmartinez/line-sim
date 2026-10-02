import unittest
from plantsim.cli import load
from plantsim.labelmis import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_conservation_and_formula(self):
        r = sweep(self.P, [0.9], 0.02, 1, 2, 6)[0]
        self.assertAlmostEqual(r["esc"][0] + r["blk"][0], 1000 * 0.02, delta=6)
        self.assertLessEqual(r["esc"][1], r["esc_th"] * 1.6 + 0.5)
        self.assertGreaterEqual(r["blk"][2], r["blk_th"] * 0.8)

    def test_no_scan_and_perfect_scan(self):
        a = sweep(self.P, [0.9], 0.05, 0, 2, 2)[0]
        self.assertEqual(a["blk"][0], 0.0); self.assertAlmostEqual(a["esc_th"], 50.0)
        b = sweep(self.P, [1.0], 0.05, 1, 2, 2)[0]
        self.assertEqual(b["esc"][0], 0.0)

    def test_second_scan_helps(self):
        one = sweep(self.P, [0.8], 0.05, 1, 2, 2)[0]["esc_th"]
        two = sweep(self.P, [0.8], 0.05, 2, 2, 2)[0]["esc_th"]
        self.assertAlmostEqual(two, one * 0.2)

    def test_zero_p(self):
        r = sweep(self.P, [0.5], 0.0, 1, 2, 2)[0]
        self.assertEqual((r["esc"][0], r["blk"][0], r["hold_h"][0]), (0.0, 0.0, 0.0))

    def test_validation(self):
        for a in (([], 0.02, 1, 2), ([0.9], 1.5, 1, 2), ([0.9], 0.02, -1, 2), ([0.9], 0.02, 1, -2), ([2], 0.02, 1, 2)):
            with self.assertRaises(ValueError):
                sweep(self.P, *a, 2)

    def test_page(self):
        h = render_html(sweep(self.P, [0.9], 0.02, 1, 2, 2), 0.02, 1, 2, 2)
        self.assertIn("FME-027", h); self.assertIn("TBD", h)
