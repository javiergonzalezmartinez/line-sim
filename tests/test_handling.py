import math, unittest
from collections import defaultdict
from plantsim.handling import handling, handling_kpis
from plantsim.events import validate
from plantsim.fsm import Machine
from tests.test_events import PLANT, RES, SCHEMA


def per_obj(evs):
    d = defaultdict(list)
    for e in evs:
        d[e["object_ids"][0]].append(e)
    return d


class HandlingTests(unittest.TestCase):
    CFG = {"hu_per_lot": 6, "hu_per_pallet": 4, "release_delay_h": 2, "ship_delay_h": 12}

    def test_counts(self):
        ev = handling(PLANT, RES, self.CFG)
        k = handling_kpis(ev)
        lots = len(RES.batches)
        done = sum(1 for b in RES.batches if b.done is not None and not b.rejected)
        self.assertEqual(k["input_HUs"], 6 * lots)
        self.assertEqual(k["pallets"], 2 * done)
        self.assertEqual(k["pallets_shipped"], k["pallets"])
        self.assertEqual(k["pallet_quarantine_mean_h"], 2.0)

    def test_units_sum_to_hu_per_lot(self):
        ev = handling(PLANT, RES, self.CFG)
        tot = defaultdict(int)
        for e in ev:
            if e["event_type"] == "pallet.built":
                tot[e["lot_id"]] += e["payload"]["units"]
        self.assertTrue(tot and all(v == 6 for v in tot.values()))

    def test_every_hu_sequence_is_legal_in_the_spec_and_ordered_in_time(self):
        for obj, lst in list(per_obj(handling(PLANT, RES, self.CFG)).items())[:300]:
            m = Machine("HANDLING_UNIT", "CREATED", obj)
            for e in lst:
                if e["reason_code"].startswith("HANDLING_UNIT:"):
                    m.fire(e["event_type"])
            ts = [e["event_time"] for e in lst]
            self.assertEqual(ts, sorted(ts))

    def test_defaults_invent_nothing(self):
        ev = handling(PLANT, RES)
        self.assertEqual(handling_kpis(ev)["pallets_shipped"], 0)
        self.assertEqual(handling_kpis(ev)["units_per_pallet_mean"], 1.0)

    def test_schema_and_determinism_and_bad_cfg(self):
        ev = handling(PLANT, RES, self.CFG)
        for e in ev[:2000]:
            self.assertEqual(validate(e, SCHEMA), [])
        self.assertEqual([e["event_id"] for e in ev], [e["event_id"] for e in handling(PLANT, RES, self.CFG)])
        for bad in ({"hu_per_lot": 0}, {"hu_per_pallet": 1.5}, {"ship_delay_h": -1}, {"nope": 1}):
            with self.assertRaises(ValueError):
                handling(PLANT, RES, bad)

    def test_rejected_lots_make_no_pallets(self):
        rej = {f"LOT-{b.id + 1:06d}" for b in RES.batches if b.rejected}
        for e in handling(PLANT, RES, self.CFG):
            if e["object_ids"][0].startswith("PAL-"):
                self.assertNotIn(e["lot_id"], rej)
