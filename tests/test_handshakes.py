import json, os, unittest
from collections import defaultdict
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.handshakes import messages, message_kpis
from plantsim.events import validate
from plantsim.fsm import state_hash
from tests.test_events import PLANT, RES, SCHEMA

ROOT = os.path.join(os.path.dirname(__file__), "..")


def by_msg(ms):
    d = defaultdict(list)
    for e in ms:
        d[e["object_ids"][0]].append(e)
    return d


class HandshakeTests(unittest.TestCase):
    def test_ideal_handshake_when_parameters_are_tbd(self):
        ms = messages(PLANT, RES)
        k = message_kpis(ms)
        self.assertGreater(k["messages"], 100)
        self.assertEqual(k["KPI-015 MessageSuccess"], 1.0)
        self.assertEqual(k["KPI-017 RetryRate"], 0.0)
        self.assertEqual(k["KPI-016 MessageP95Latency (h)"], 0.0)
        self.assertEqual({e["event_type"] for e in ms}, {"message.sent", "message.acknowledged", "message.reconciled"})

    def test_one_message_per_move_stage_per_lot(self):
        n = sum(1 for b in RES.batches for rec in b.trace if PLANT.stages[rec[0]].kind == "move")
        self.assertEqual(message_kpis(messages(PLANT, RES))["messages"], n)

    def test_all_events_validate(self):
        for e in messages(PLANT, RES, {"loss_p": 0.2, "nack_p": 0.1, "duplicate_p": 0.1, "timeout_h": 0.1, "max_retries": 2})[:3000]:
            self.assertEqual(validate(e, SCHEMA), [], e["event_type"])

    def test_total_loss_ends_in_dead_letter_after_retries(self):
        ms = messages(PLANT, RES, {"loss_p": 1.0, "timeout_h": 0.1, "max_retries": 2})
        k = message_kpis(ms)
        self.assertEqual(k["KPI-015 MessageSuccess"], 0.0)
        self.assertEqual(k["dead_lettered"], k["messages"])
        for lst in list(by_msg(ms).values())[:20]:
            kinds = [e["event_type"] for e in lst]
            self.assertEqual(kinds.count("message.timeout"), 3)
            self.assertEqual(kinds.count("message.retry"), 2)
            self.assertEqual(kinds[-1], "message.dead_lettered")
            self.assertEqual(len({e["idempotency_key"] for e in lst}), 1)

    def test_nack_then_retry_can_succeed(self):
        ms = messages(PLANT, RES, {"nack_p": 0.5, "max_retries": 10})
        k = message_kpis(ms)
        self.assertGreater(k["KPI-017 RetryRate"], 0.3)
        self.assertGreater(k["KPI-015 MessageSuccess"], 0.99)

    def test_duplicate_is_discarded_without_state_change(self):
        ms = messages(PLANT, RES, {"duplicate_p": 1.0})
        d = [e for e in ms if e["event_type"] == "message.duplicate_discarded"]
        self.assertTrue(d)
        for e in d:
            self.assertNotIn("state_before_hash", e)
            self.assertIn("FME-011", e["reason_code"])

    def test_latency_kpi_follows_the_parameter(self):
        k = message_kpis(messages(PLANT, RES, {"ack_latency_h": 0.02}))
        self.assertAlmostEqual(k["KPI-016 MessageP95Latency (h)"], 0.02, places=6)

    def test_bad_parameters_rejected_and_run_is_deterministic(self):
        for bad in ({"loss_p": 1.5}, {"timeout_h": 0}, {"bogus": 1}, {"max_retries": -1}):
            with self.assertRaises(ValueError):
                messages(PLANT, RES, bad)
        c = {"loss_p": 0.3, "nack_p": 0.1}
        self.assertEqual([e["event_id"] for e in messages(PLANT, RES, c)], [e["event_id"] for e in messages(PLANT, RES, c)])

    def test_failure_ids_exist_in_the_spec(self):
        ids = {r["ID"] for r in json.load(open(os.path.join(ROOT, "spec", "failures.json"), encoding="utf-8"))["records"]}
        self.assertTrue({"FME-009", "FME-011", "FME-013", "FME-014"} <= ids)


class SeedScenarioTests(unittest.TestCase):
    def test_scenario_matches_seed_capacities_and_runs(self):
        seed = {r["ID"]: r for r in json.load(open(os.path.join(ROOT, "spec", "synthetic_seed.json"), encoding="utf-8"))["records"]}
        sc = json.load(open(os.path.join(ROOT, "examples", "seed_scenario.json"), encoding="utf-8"))
        cap = lambda i: int(seed[i]["Propiedades"].split("capacity_hu=")[1].split(";")[0])
        by_loc = {s.get("loc"): s for s in sc["stages"]}
        self.assertEqual(by_loc["LOC-WH-REC-001"]["buffer"], cap("LOC-WH-REC-001"))
        self.assertEqual(by_loc["LOC-WH-BUF-001"]["capacity"], cap("LOC-WH-BUF-001"))
        self.assertEqual(by_loc["LOC-DISP-BUF-001"]["buffer"], cap("LOC-DISP-BUF-001"))
        self.assertEqual(by_loc["LOC-PROC-BUF-001"]["buffer"], cap("LOC-PROC-BUF-001"))
        self.assertIn("ILLUSTRATIVE", sc["_note"])
        p = load(os.path.join(ROOT, "examples", "seed_scenario.json"))
        r = simulate(p)
        self.assertGreater(r.throughput_per_week, 5)
        ms = messages(p, r, sc["handshake"])
        self.assertGreater(len(ms), 10)
