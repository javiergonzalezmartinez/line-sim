import unittest
from plantsim.cli import load
from plantsim.hushscan import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_close_to_formula(self):
        r = sweep(self.P, [0.05], 1.0, 4, 2, 8)[0]
        self.assertLessEqual(r["rej"][1], r["rej_th"] * 1.2); self.assertGreaterEqual(r["rej"][2], r["rej_th"] * 0.8)
        self.assertEqual(r["esc"][0], 0.0); self.assertEqual(r["esc_th"], 0.0)

    def test_no_detection_means_escapes_and_no_rejects(self):
        r = sweep(self.P, [0.05], 0.0, 4, 2, 4)[0]
        self.assertEqual(r["rej"][0], 0.0); self.assertAlmostEqual(r["esc_th"], 1000 * 4 * 0.05)
        self.assertGreater(r["esc"][0], 0.0)

    def test_zero_rate_and_monotone(self):
        z = sweep(self.P, [0.0], 1.0, 4, 2, 2)[0]
        self.assertEqual((z["rej"][0], z["hours"][0]), (0.0, 0.0))
        a, b = sweep(self.P, [0.01, 0.1], 1.0, 4, 2, 4)
        self.assertLess(a["rej_th"], b["rej_th"]); self.assertLess(a["rej"][0], b["rej"][0])

    def test_closed_forms_balance(self):
        # P(escape) + P(correct) = 1 per move, so per-move escape share never exceeds s
        r = sweep(self.P, [0.2], 0.5, 1, 0, 2)[0]
        self.assertLess(r["esc_th"], 1000 * 0.2 / (1 - 0.1) + 1e-9)

    def test_validation(self):
        for a in (([], 1, 4, 2), ([1.0], 1, 4, 2), ([0.1], 1.5, 4, 2), ([0.1], 1, 0, 2), ([0.1], 1, 4, -1), ([-0.1], 1, 4, 2)):
            with self.assertRaises(ValueError):
                sweep(self.P, *a, 2)

    def test_page(self):
        h = render_html(sweep(self.P, [0.05], 1.0, 4, 2, 2), 1.0, 4, 2, 2)
        self.assertIn("FME-001", h); self.assertIn("TBD", h)
