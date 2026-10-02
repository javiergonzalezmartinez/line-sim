import unittest
from plantsim.auditfail import sweep, render_html
from plantsim.cli import load

class T(unittest.TestCase):
    def test_sweep(self):
        p = load("examples/pharma_flow.json")
        r = sweep(p, [60, 1440, 4320], 3, 3, 60)
        self.assertLess(r[0]["blk"][0], r[1]["blk"][0]); self.assertLess(r[1]["blk"][0], r[2]["blk"][0])
        self.assertAlmostEqual(r[2]["blk"][0], r[2]["blk_th"], delta=0.35 * r[2]["blk_th"])
        self.assertLessEqual(r[2]["wait"][0], r[2]["D"])
        self.assertIn("fail closed", render_html(r, 3, 3).lower())
    def test_bad(self):
        p = load("examples/pharma_flow.json")
        with self.assertRaises(ValueError): sweep(p, [], 3)
        with self.assertRaises(ValueError): sweep(p, [10], 0)
if __name__ == "__main__": unittest.main()
