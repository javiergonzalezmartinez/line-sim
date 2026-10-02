import dataclasses, os, unittest
from plantsim.cli import load
from plantsim.model import simulate

D = os.path.join(os.path.dirname(__file__), "..", "examples")
A = load(os.path.join(D, "pm_a.json")); B = load(os.path.join(D, "pm_b.json"))
BASE = load(os.path.join(D, "dispatch_fifo.json"))


def sig(r):
    return [(b.id, b.done, b.rejected, [tuple(x) for x in b.trace]) for b in r.batches]


class P(unittest.TestCase):
    def test_defaults_unchanged(self):
        # no wear, no pm: identical to a plant that never heard of the fields
        st = [dataclasses.replace(s, wear_per_100h=0.0, pm_every_h=None, pm_hours=0.0) for s in A.stages]
        self.assertEqual(sig(simulate(dataclasses.replace(A, stages=st))), sig(simulate(BASE)))

    def test_pm_adds_hours_only_where_configured(self):
        r = simulate(B)
        for sg, st in zip(B.stages, r.stats):
            if sg.pm_every_h:
                self.assertGreater(st.pm, 0)
            else:
                self.assertEqual(st.pm, 0)

    def test_pm_cuts_repair_hours(self):
        self.assertLess(sum(s.repair for s in simulate(B).stats), sum(s.repair for s in simulate(A).stats))

    def test_pm_hours_scale_with_duration(self):
        st = [dataclasses.replace(s, pm_hours=8.0) if s.pm_every_h else s for s in B.stages]
        a = sum(s.pm for s in simulate(B).stats); b = sum(s.pm for s in simulate(dataclasses.replace(B, stages=st)).stats)
        self.assertGreater(b, a * 1.5)

    def test_pm_routes_to_event_engine(self):
        st = [dataclasses.replace(s, buffer=None) for s in B.stages]
        self.assertGreater(sum(s.pm for s in simulate(dataclasses.replace(B, stages=st)).stats), 0)
