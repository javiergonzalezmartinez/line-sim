import unittest
from collections import defaultdict
from plantsim.model import simulate
from plantsim.signals import telemetry, render_timeline, SIGNALS
from plantsim.events import validate
from tests.test_events import PLANT, RES, SCHEMA
from plantsim.cli import load
import os

TL = telemetry(PLANT, RES)


def vals(eq, sig):
    return [(e["sensor_elements"][0]["time"], e["sensor_elements"][0].get("string_value", e["sensor_elements"][0].get("value")))
            for e in TL if e["equipment_id"] == eq and e["sensor_elements"][0]["measurement_type"] == sig]


class SignalTests(unittest.TestCase):
    def test_all_events_validate_and_are_sensor_events_with_good_quality(self):
        self.assertGreater(len(TL), 1000)
        for e in TL:
            self.assertEqual(validate(e, SCHEMA), [])
            self.assertEqual(e["event_class"], "SENSOR")
            self.assertEqual(e["sensor_elements"][0]["signal_quality"], "GOOD")

    def test_signal_ids_exist_in_the_spec(self):
        import json
        spec = {r["ID"]: r["Señal"] for r in json.load(open(os.path.join(os.path.dirname(__file__), "..", "spec", "signals.json"), encoding="utf-8"))["records"]}
        for name, sid in SIGNALS.items():
            self.assertEqual(spec[sid], name)

    def test_state_change_sampling_no_repeated_values(self):
        for eq in {e["equipment_id"] for e in TL}:
            for sig in ("item_state", "operation_mode", "job_id"):
                v = [x[1] for x in vals(eq, sig)]
                if sig == "job_id":
                    continue
                for a, b in zip(v, v[1:]):
                    self.assertNotEqual(a, b, (eq, sig))

    def test_item_state_alternates_and_ends_not_executing(self):
        for eq in {e["equipment_id"] for e in TL}:
            v = [x[1] for x in vals(eq, "item_state")]
            self.assertEqual(v[0], "NOT_EXECUTING")
            self.assertEqual(v[-1], "NOT_EXECUTING")
            self.assertEqual(v[1::2], ["EXECUTING"] * len(v[1::2]))

    def test_counters_never_decrease(self):
        for eq in {e["equipment_id"] for e in TL}:
            for sig in ("cycle_counter", "operating_time"):
                v = [x[1] for x in vals(eq, sig)]
                self.assertEqual(v, sorted(v), (eq, sig))

    def test_cycles_equal_completed_phases_of_that_equipment(self):
        done = defaultdict(int)
        for b in RES.batches:
            for rec in b.trace:
                if rec[3] > rec[2]:
                    done[rec[0]] += 1
        for k, n in done.items():
            if PLANT.stages[k].kind in ("process", "move"):
                self.assertEqual(vals(f"EQ-STAGE-{k + 1:02d}", "cycle_counter")[-1][1], n)

    def test_operating_time_of_single_server_stage_matches_busy_time(self):
        for k, s in enumerate(PLANT.stages):
            if s.kind in ("process", "move") and s.servers == 1:
                busy = sum(rec[3] - rec[2] for b in RES.batches for rec in b.trace if rec[0] == k and rec[3] > rec[2])
                last = vals(f"EQ-STAGE-{k + 1:02d}", "operating_time")[-1][1]
                self.assertAlmostEqual(last, busy * 3600.0, delta=1.0)
                break

    def test_only_signals_with_a_basis_are_produced(self):
        self.assertEqual({e["sensor_elements"][0]["measurement_type"] for e in TL}, set(SIGNALS))

    def test_timeline_svg(self):
        h = render_timeline(TL)
        self.assertIn("EXECUTING", h)
        self.assertNotIn("<script", h)
        self.assertNotIn("http://", h.replace("http://www.w3.org/2000/svg", ""))
