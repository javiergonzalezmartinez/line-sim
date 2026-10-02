import json, os, tempfile, unittest
from plantsim.cli import load, main
from plantsim.model import simulate
from plantsim.signals import telemetry
from plantsim.mqttexport import sparkplug_messages, opcua_nodes

P = load(os.path.join(os.path.dirname(__file__), "..", "examples", "pharma_flow.json"))
T = telemetry(P, simulate(P))
M = sparkplug_messages(T)


class Q(unittest.TestCase):
    def test_structure(self):
        self.assertTrue(M[0]["topic"].endswith("/NBIRTH/LINESIM_EDGE_01"))
        self.assertTrue(M[-1]["topic"].endswith("/NDEATH/LINESIM_EDGE_01"))
        self.assertEqual(len(M), len(T) + 2)
        for m in M:
            parts = m["topic"].split("/")
            self.assertEqual(parts[0], "spBv1.0")
            self.assertIn(parts[2], ("NBIRTH", "DBIRTH", "DDATA", "NDEATH"))

    def test_seq_wraps_and_is_continuous(self):
        seqs = [m["payload"]["seq"] for m in M[:-1]]
        for a, b in zip(seqs, seqs[1:]):
            self.assertEqual(b, (a + 1) % 256)
        self.assertIn(255, seqs)

    def test_birth_before_data_per_device(self):
        born = set()
        for m in M:
            parts = m["topic"].split("/")
            if parts[2] == "DBIRTH":
                self.assertNotIn(parts[4], born); born.add(parts[4])
            elif parts[2] == "DDATA":
                self.assertIn(parts[4], born)

    def test_nodes_unique_and_counts_match(self):
        n = opcua_nodes(T)
        self.assertEqual(len({x["NodeId"] for x in n}), len(n))
        self.assertEqual(sum(x["DataChanges"] for x in n), sum(len(e["sensor_elements"]) for e in T))

    def test_cli_files(self):
        d = tempfile.mkdtemp()
        a, b, c = (os.path.join(d, x) for x in ("m.jsonl", "n.json", "v.html"))
        main([os.path.join(os.path.dirname(__file__), "..", "examples", "pharma_flow.json"), "--mqtt", a, "--opcua-nodes", b, "--mqtt-view", c])
        self.assertEqual(sum(1 for _ in open(a)), len(M))
        json.loads(open(a).readline()); self.assertTrue(json.load(open(b)))
        self.assertIn("not the protobuf wire format", open(c).read())
