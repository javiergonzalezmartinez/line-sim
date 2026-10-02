import dataclasses, unittest
from plantsim.cli import load
from plantsim.crn import check, render_html
from plantsim.model import simulate


class T(unittest.TestCase):
    def test_deterministic(self):
        P = dataclasses.replace(load("examples/whatif_a.json"), sync_streams=True)
        a, b = simulate(P), simulate(P)
        self.assertEqual([x.done for x in a.batches], [x.done for x in b.batches])

    def test_sync_raises_correlation_of_repair_hours(self):
        a, b = load("examples/whatif_a.json"), load("examples/whatif_b.json")
        s = check(dataclasses.replace(a, sync_streams=True), dataclasses.replace(b, sync_streams=True), 8)["metrics"]["Repair hours (all stages)"]
        self.assertGreater(s["rho"], 0.5)

    def test_page_has_both(self):
        a, b = load("examples/whatif_a.json"), load("examples/whatif_b.json")
        c = check(a, b, 4); c2 = check(dataclasses.replace(a, sync_streams=True), dataclasses.replace(b, sync_streams=True), 4)
        h = render_html(c, c2)
        self.assertIn("synchronised", h); self.assertNotIn("not implemented", h)
