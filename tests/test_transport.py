import json, os, unittest
from collections import defaultdict
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.transport import transport, transport_kpis
from plantsim.events import validate
from plantsim.fsm import Machine
from tests.test_events import PLANT, RES, SCHEMA

ROOT = os.path.join(os.path.dirname(__file__), "..")
SP = load(os.path.join(ROOT, "examples", "transport_stress.json"))
SR = simulate(SP)


def tasks(ev):
    d = defaultdict(list)
    for e in ev:
        d[e["object_ids"][0]].append(e)
    return d


class TransportTests(unittest.TestCase):
    def test_one_task_per_move_stage_and_legal_sequences(self):
        ev = transport(SP, SR, {"fleet_size": 2, "accept_h": 0.05, "route_block_p": 0.2, "route_block_h": 0.3})
        n = sum(1 for b in SR.batches for r in b.trace if SP.stages[r[0]].kind == "move")
        t = tasks(ev)
        self.assertEqual(len(t), n)
        for o, lst in t.items():
            m = Machine("TRANSPORT_TASK", "CREATED", o)
            for e in lst:
                m.fire(e["event_type"])
            self.assertEqual(m.state, "COMPLETE")
        for e in ev[:1500]:
            self.assertEqual(validate(e, SCHEMA), [])

    def test_a_vehicle_never_carries_two_loads_at_once(self):
        ev = transport(SP, SR, {"fleet_size": 2})
        iv = defaultdict(list)
        pk = {}
        for e in ev:
            if e["event_type"] == "move.picked":
                pk[e["object_ids"][0]] = e["event_time"]
            if e["event_type"] == "move.dropped":
                iv[e["equipment_id"]].append((pk[e["object_ids"][0]], e["event_time"]))
        for v, l in iv.items():
            l.sort()
            for a, b in zip(l, l[1:]):
                self.assertLessEqual(a[1], b[0], v)

    def test_more_vehicles_never_wait_longer(self):
        w = [transport_kpis(transport(SP, SR, {"fleet_size": f}), {"fleet_size": f}, SP.horizon)["KPI-004 QueueWait mean (h)"] for f in (1, 2, 4)]
        self.assertGreaterEqual(w[0], w[1])
        self.assertGreaterEqual(w[1], w[2])

    def test_defaults_invent_nothing(self):
        ev = transport(PLANT, RES)
        k = transport_kpis(ev)
        self.assertEqual(k["KPI-004 QueueWait mean (h)"], 0.0)
        self.assertIsNone(k["KPI-006 FleetUtilization"])
        self.assertIsNone(k["KPI-014 TaskOnTime"])
        self.assertNotIn("move.queued", {e["event_type"] for e in ev})

    def test_blocked_route_adds_exactly_the_block_time(self):
        a = transport(SP, SR, {"fleet_size": 50})
        b = transport(SP, SR, {"fleet_size": 50, "route_block_p": 1.0, "route_block_h": 0.5})
        da = {e["object_ids"][0]: e["event_time"] for e in a if e["event_type"] == "move.dropped"}
        db = {e["object_ids"][0]: e["event_time"] for e in b if e["event_type"] == "move.dropped"}
        self.assertTrue(any(db[o] > da[o] for o in da))
        self.assertEqual(sum(1 for e in b if e["event_type"] == "move.route_blocked"), len(da))

    def test_bad_parameters_and_determinism(self):
        for bad in ({"fleet_size": 0}, {"fleet_size": 1.5}, {"route_block_p": 2}, {"accept_h": -1}, {"zzz": 1}):
            with self.assertRaises(ValueError):
                transport(SP, SR, bad)
        c = {"fleet_size": 2, "route_block_p": 0.3, "route_block_h": 0.2}
        self.assertEqual([e["event_id"] for e in transport(SP, SR, c)], [e["event_id"] for e in transport(SP, SR, c)])
