import unittest
from plantsim.cli import load
from plantsim.expiry import sweep, render_html


class T(unittest.TestCase):
    def setUp(self):
        self.P = load("examples/pharma_flow.json")

    def test_monotone_and_bounds(self):
        r = sweep(self.P, [12, 48, 5000], 2)
        self.assertGreaterEqual(r[0]["share"][0], r[1]["share"][0])
        self.assertGreaterEqual(r[1]["share"][0], r[2]["share"][0])
        self.assertEqual(r[2]["share"][0], 0.0)
        self.assertTrue(all(0 <= x["share"][0] <= 1 for x in r))

    def test_causes_add_up(self):
        r = sweep(self.P, [24], 2)
        self.assertGreater(sum(r[0]["top"].values()), 0)

    def test_validation(self):
        for bad in ([], [0], [-1]):
            with self.assertRaises(ValueError):
                sweep(self.P, bad, 2)

    def test_page(self):
        h = render_html(sweep(self.P, [24], 2), 2)
        self.assertIn("FME-006", h); self.assertIn("TBD", h)
