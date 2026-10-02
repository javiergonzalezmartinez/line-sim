import dataclasses, os, unittest
from plantsim.cli import load
from plantsim.model import simulate

D = os.path.join(os.path.dirname(__file__), "..", "examples")
A = load(os.path.join(D, "dispatch_fifo.json"))
B = load(os.path.join(D, "dispatch_same_product.json"))


def sig(r):
    return [(b.id, b.done, b.rejected, [tuple(x) for x in b.trace]) for b in r.batches]


class T(unittest.TestCase):
    def test_default_is_fifo_and_loader_reads_field(self):
        self.assertEqual(A.dispatch, "fifo"); self.assertEqual(B.dispatch, "same_product_first")

    def test_bad_rule_rejected(self):
        with self.assertRaises(ValueError):
            dataclasses.replace(A, dispatch="spt")

    def test_single_product_rule_changes_nothing(self):
        a = dataclasses.replace(A, products=["A"]); b = dataclasses.replace(B, products=["A"])
        self.assertEqual(sig(simulate(a)), sig(simulate(b)))

    def test_rule_cuts_setup_hours(self):
        sa = sum(s.setup for s in simulate(A).stats); sb = sum(s.setup for s in simulate(B).stats)
        self.assertLess(sb, sa)

    def test_same_lots_released(self):
        self.assertEqual(len(simulate(A).batches), len(simulate(B).batches))

    def test_fifo_without_changeover_is_identical(self):
        st = [dataclasses.replace(s, changeover=0.0) for s in A.stages]
        a = dataclasses.replace(A, stages=st); b = dataclasses.replace(B, stages=st)
        self.assertEqual(sig(simulate(a)), sig(simulate(b)))
