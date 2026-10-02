import dataclasses, unittest
from plantsim.cli import load
from plantsim.model import simulate, Plant


def _p():
    return load("examples/conwip.json")


class T(unittest.TestCase):
    def test_cards_cap_wip_inside(self):
        P = dataclasses.replace(_p(), conwip=3)
        r = simulate(P)
        ev = []
        for b in r.batches:
            assert b.entered is not None and b.entered >= b.released - 1e-9
            ev.append((b.entered, 1)); ev.append((b.done, -1))
        ev.sort(key=lambda x: (x[0], x[1]))
        w = m = 0
        for _, d in ev:
            w += d; m = max(m, w)
        assert m <= 3

    def test_more_cards_more_throughput(self):
        a = simulate(dataclasses.replace(_p(), conwip=2)).throughput_per_week
        b = simulate(dataclasses.replace(_p(), conwip=8)).throughput_per_week
        assert b > a

    def test_no_conwip_unchanged_entry(self):
        r = simulate(dataclasses.replace(_p(), conwip=None))
        assert all(x.entered is None or abs(x.entered - x.released) < 1e-9 for x in r.batches)

    def test_invalid(self):
        try:
            dataclasses.replace(_p(), conwip=0)
        except ValueError:
            return
        raise AssertionError('expected ValueError')

