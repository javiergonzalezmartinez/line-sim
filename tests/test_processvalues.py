import json, math, os, unittest
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.processvalues import process_values, first_order, deadband_filter, reduction, _analog_signals
from plantsim.events import validate
from tests.test_events import SCHEMA

ROOT = os.path.join(os.path.dirname(__file__), "..")
CFGF = os.path.join(ROOT, "examples", "dashboard_demo.json")
P = load(CFGF)
R = simulate(P)
PV = json.load(open(CFGF, encoding="utf-8"))["process_values"]


class ProcessValueTests(unittest.TestCase):
    def test_first_order_step_response(self):
        self.assertAlmostEqual(first_order(0, 100, 1.0, 1.0), 100 * (1 - math.exp(-1)), places=9)
        self.assertAlmostEqual(first_order(0, 100, 0.0, 1.0), 0.0)
        self.assertAlmostEqual(first_order(40, 40, 5.0, 0.3), 40.0)

    def test_deadband_semantics_match_opcua_absolute(self):
        s = [(0, 10.0), (1, 10.5), (2, 11.1), (3, 10.9), (4, 12.2)]
        got = deadband_filter(s, 1.0)
        self.assertEqual([v for _, v in got], [10.0, 11.1, 12.2])   # 10.5 within 1 of 10.0; 11.1 > 1; 10.9 within; 12.2 > 1 from 11.1
        self.assertEqual(len(deadband_filter(s, 0.0)), 5)
        last = None
        for t, v in s:
            rep = (t, v) in got
            if last is not None and not rep:
                self.assertLessEqual(abs(v - last), 1.0)
            if rep:
                last = v

    def test_no_config_no_events(self):
        self.assertEqual(process_values(P, R, {}), [])

    def test_events_valid_and_spec_ids(self):
        ev = process_values(P, R, PV)
        ids = _analog_signals()
        self.assertTrue(ev)
        for e in ev[:2000]:
            self.assertEqual(validate(e, SCHEMA), [])
            el = e["sensor_elements"][0]
            self.assertEqual(el["signal_id"], ids[el["measurement_type"]][0])
            self.assertEqual(el["uom"], ids[el["measurement_type"]][1])

    def test_values_follow_busy_state(self):
        cfg = {"Granulation + drying": {"temperature": {"idle": 22, "run": 60, "tau_h": 0.05, "sample_s": 60, "deadband": 0.0}}}
        ev = process_values(P, R, cfg)
        k = [s.name for s in P.stages].index("Granulation + drying")
        from plantsim.kpis import hours
        busy = [(r[2], r[3]) for b in R.batches for r in b.trace if r[0] == k and r[3] > r[2]]
        a, b = max(busy, key=lambda x: x[1] - x[0])
        mid = [e["sensor_elements"][0]["value"] for e in ev if a + 0.5 < hours(e["event_time"]) < b - 0.1]
        self.assertTrue(mid and all(abs(v - 60) < 0.5 for v in mid))
        self.assertAlmostEqual(ev[0]["sensor_elements"][0]["value"], 22.0, places=3)

    def test_deadband_reduces_data_and_is_deterministic(self):
        ev = process_values(P, R, PV)
        for v in reduction(P, ev, PV).values():
            self.assertLess(v["kept"], 0.2)
        self.assertEqual([e["event_id"] for e in ev[:50]], [e["event_id"] for e in process_values(P, R, PV)[:50]])

    def test_bad_config_rejected(self):
        good = {"idle": 1, "run": 2, "tau_h": 0.1}
        for bad in ({"Nope": {"temperature": good}}, {"Granulation + drying": {"banana": good}}, {"Granulation + drying": {"temperature": {"idle": 1}}},
                    {"Granulation + drying": {"temperature": dict(good, tau_h=0)}}, {"Granulation + drying": {"temperature": dict(good, zzz=1)}},
                    {"Quarantine (waiting for QC)": {"temperature": good}}):
            with self.assertRaises(ValueError):
                process_values(P, R, bad)


class FaultTests(unittest.TestCase):
    def test_drift_is_a_linear_ramp_from_start(self):
        from plantsim.processvalues import apply_faults
        base = [(float(t), 10.0) for t in range(0, 11)]
        out, cal, inj = apply_faults(base, {"faults": [{"type": "drift", "start_h": 4, "rate_per_h": 0.5}]}, "k", 10)
        self.assertEqual([v for _, v in out][:5], [10.0] * 5)
        self.assertAlmostEqual(out[8][1], 10 + 0.5 * 4)
        self.assertIsNone(cal)

    def test_step_only_inside_its_window(self):
        from plantsim.processvalues import apply_faults
        base = [(float(t), 0.0) for t in range(10)]
        out, _, _ = apply_faults(base, {"faults": [{"type": "step", "start_h": 2, "dur_h": 3, "delta": 5}]}, "k", 10)
        self.assertEqual([v for _, v in out], [0, 0, 5, 5, 5, 0, 0, 0, 0, 0])

    def test_excursion_evaluator_hysteresis_stops_chatter(self):
        from plantsim.processvalues import excursions
        s = [(0, 60), (1, 67), (2, 65.5), (3, 66.5), (4, 63), (5, 60)]
        self.assertEqual(len(excursions(s, {"high": 66})), 2)                      # chatters around the limit
        self.assertEqual(excursions(s, {"high": 66, "hysteresis": 1.5}), [(1, 4)])  # one excursion, closes below 64.5
        self.assertEqual(excursions([(0, 1), (1, 9)], {"high": 5}), [(1, None)])
        self.assertEqual(excursions(s, None), [])

    def test_calibration_overdue_marks_quality_uncertain_only_after_the_date(self):
        cfg = {"Granulation + drying": {"temperature": {"idle": 22, "run": 60, "tau_h": 0.1, "sample_s": 600, "deadband": 0.0,
                                                          "faults": [{"type": "calibration_overdue", "valid_until_h": 1000}]}}}
        from plantsim.kpis import hours
        for e in process_values(P, R, cfg):
            q = e["sensor_elements"][0]["signal_quality"]
            self.assertEqual(q, "UNCERTAIN" if hours(e["event_time"]) >= 1000 else "GOOD")

    def test_injected_step_opens_and_closes_one_excursion_with_kpi(self):
        from plantsim.processvalues import excursion_kpis
        cfg = {"Granulation + drying": {"temperature": {"idle": 22, "run": 60, "tau_h": 0.05, "sample_s": 60, "deadband": 1.0, "limits": {"high": 70, "hysteresis": 1.0},
                                                          "faults": [{"type": "step", "start_h": 800, "dur_h": 2, "delta": 20}]}}}
        ev = process_values(P, R, cfg)
        k = excursion_kpis(ev)
        self.assertGreaterEqual(k["excursions_closed"], 1)
        self.assertEqual(k["excursions_open_at_end"], 0)
        self.assertGreater(k["KPI-024 ExcursionDuration mean (h)"], 0)
        for e in ev:
            if e["event_class"] == "CONTROL":
                self.assertEqual(validate(e, SCHEMA), [])

    def test_no_limits_no_excursions_and_stochastic_is_deterministic(self):
        from plantsim.processvalues import apply_faults
        ev = process_values(P, R, {"Granulation + drying": {"temperature": {"idle": 22, "run": 60, "tau_h": 0.1, "faults": [{"type": "drift", "start_h": 5, "rate_per_h": 1}]}}})
        self.assertFalse([e for e in ev if e["event_class"] == "CONTROL"])
        f = {"faults": [{"type": "stochastic_excursion", "rate_per_100h": 3, "dur_h": 1, "delta": 5}]}
        base = [(float(t), 0.0) for t in range(500)]
        self.assertEqual(apply_faults(base, f, "a", 500), apply_faults(base, f, "a", 500))
        self.assertNotEqual(apply_faults(base, f, "a", 500)[0], apply_faults(base, f, "b", 500)[0])
        z = {"faults": [{"type": "stochastic_excursion", "rate_per_100h": 0, "dur_h": 1, "delta": 5}]}
        self.assertEqual(apply_faults(base, z, "a", 500)[0], base)

    def test_bad_fault_config_rejected(self):
        g = {"idle": 1, "run": 2, "tau_h": 0.1}
        st = "Granulation + drying"
        for bad in ({"faults": [{"type": "nope"}]}, {"faults": [{"type": "drift", "start_h": 1}]}, {"faults": [{"type": "step", "start_h": 1, "dur_h": 1, "delta": 1, "zzz": 2}]},
                    {"limits": {"hysteresis": 1}}, {"limits": {"low": 5, "high": 1}}, {"faults": [{"type": "stochastic_excursion", "rate_per_100h": 1, "dur_h": 0, "delta": 1}]}):
            with self.assertRaises(ValueError):
                process_values(P, R, {st: {"temperature": dict(g, **bad)}})
