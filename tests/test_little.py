import unittest
from plantsim.cli import load
from plantsim.little import check, one, render_html


class T(unittest.TestCase):
    def test_stable_plant_matches(self):
        rows = check(load("examples/pharma_flow.json"), 3)
        for r in rows:
            self.assertLess(abs(r["gap"]), 0.05)

    def test_overloaded_plant_flags(self):
        r = one(load("examples/conwip.json"))
        self.assertGreater(r["gap"], 0.3)

    def test_page(self):
        h = render_html(check(load("examples/pharma_flow.json"), 2), "x")
        self.assertIn("Little%27s_law", h); self.assertIn("approximate", h)
