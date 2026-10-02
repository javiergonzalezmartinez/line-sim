import os, dataclasses, unittest
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.whatif import metrics

EX = os.path.join(os.path.dirname(__file__), "..", "examples")
A = load(os.path.join(EX, "due_fifo.json")); B = load(os.path.join(EX, "due_edd.json"))


class T(unittest.TestCase):
    def test_edd_needs_due(self):
        with self.assertRaises(ValueError):
            dataclasses.replace(B, due_h=None)

    def test_due_must_cover_products(self):
        with self.assertRaises(ValueError):
            dataclasses.replace(A, due_h={"A": 10})

    def test_metrics_consistent(self):
        m = metrics(A, simulate(A))
        self.assertGreaterEqual(m["Maximum lateness (h)"], m["Mean tardiness (h)"] - 1e-9)
        self.assertTrue(0.0 <= m["Tardy lots (share)"] <= 1.0)
        self.assertGreaterEqual(m["Mean tardiness (h)"], 0.0)

    def test_edd_changes_order_not_lot_count_much(self):
        ra, rb = simulate(A), simulate(B)
        self.assertGreater(len(rb.finished), 0)
        self.assertNotEqual([b.done for b in ra.finished][:20], [b.done for b in rb.finished][:20])

    def test_edd_lowers_max_lateness_over_seeds(self):
        la = lb = 0.0
        for sd in range(1, 9):
            a = dataclasses.replace(A, seed=sd); b = dataclasses.replace(B, seed=sd)
            la += metrics(a, simulate(a))["Maximum lateness (h)"]; lb += metrics(b, simulate(b))["Maximum lateness (h)"]
        self.assertLess(lb, la)

    def test_no_due_no_extra_metrics(self):
        p = load(os.path.join(EX, "dispatch_fifo.json"))
        self.assertNotIn("Tardy lots (share)", metrics(p, simulate(p)))

if __name__ == "__main__":
    unittest.main()
