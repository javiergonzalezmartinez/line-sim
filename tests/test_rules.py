import os, dataclasses, unittest
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.rulesweep import sweep, render_html

P = load(os.path.join(os.path.dirname(__file__), "..", "examples", "rules.json"))


class T(unittest.TestCase):
    def test_validation(self):
        with self.assertRaises(ValueError):
            dataclasses.replace(P, due_h=None, dispatch="cr")
        with self.assertRaises(ValueError):
            dataclasses.replace(P, hours_factor={"A": 1.0})
        with self.assertRaises(ValueError):
            dataclasses.replace(P, dispatch="lifo")

    def test_equal_factors_make_spt_equal_fifo(self):
        q = dataclasses.replace(P, hours_factor={"A": 1.0, "B": 1.0, "C": 1.0})
        a = simulate(dataclasses.replace(q, dispatch="fifo")); b = simulate(dataclasses.replace(q, dispatch="spt"))
        self.assertEqual([x.done for x in a.finished], [x.done for x in b.finished])

    def test_factor_scales_busy_time(self):
        q1 = dataclasses.replace(P, hours_factor={"A": 1.0, "B": 1.0, "C": 1.0}, dispatch="fifo")
        q2 = dataclasses.replace(P, hours_factor={"A": 2.0, "B": 2.0, "C": 2.0}, dispatch="fifo")
        b1 = sum(s.busy for s in simulate(q1).stats); b2 = sum(s.busy for s in simulate(q2).stats)
        self.assertGreater(b2, b1)

    def test_sweep_and_page(self):
        rows = sweep(P, 3)
        self.assertEqual([r["name"] for r in rows], ["FIFO", "EDD", "SPT", "CR"])
        h = render_html(rows)
        self.assertIn("illustrative", h); self.assertIn("placeholders", h)

    def test_remaining_work(self):
        k0 = P.remaining_work(0, "B"); self.assertGreater(k0, P.remaining_work(len(P.stages) - 1, "B"))
        self.assertAlmostEqual(P.remaining_work(0, "C") / k0, 1.6, 9)

if __name__ == "__main__":
    unittest.main()
