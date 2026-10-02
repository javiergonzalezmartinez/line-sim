import json, os, tempfile, unittest
from collections import defaultdict
from plantsim.cli import load
from plantsim.model import simulate
from plantsim.events import events, validate, write_jsonl

ROOT = os.path.join(os.path.dirname(__file__), "..")
with open(os.path.join(ROOT, "examples", "canonical-event.schema.json"), encoding="utf-8") as f:
    SCHEMA = json.load(f)
PLANT = load(os.path.join(ROOT, "examples", "pharma_flow.json"))
RES = simulate(PLANT)
EV = events(PLANT, RES)


class EventLogTests(unittest.TestCase):
    def test_every_event_validates_against_the_canonical_schema(self):
        self.assertGreater(len(EV), 1000)
        for e in EV:
            self.assertEqual(validate(e, SCHEMA), [], e["event_type"])

    def test_validator_catches_problems(self):
        e = dict(EV[0])
        del e["result"]
        self.assertTrue(validate(e, SCHEMA))
        self.assertTrue(validate({**EV[0], "event_class": "NOPE"}, SCHEMA))
        self.assertTrue(validate({**EV[0], "event_id": "abc"}, SCHEMA))
        self.assertTrue(validate({**EV[0], "event_time": "yesterday"}, SCHEMA))
        self.assertTrue(validate({**EV[0], "object_ids": []}, SCHEMA))
        self.assertTrue(validate({**EV[0], "sequence_no": -1}, SCHEMA))

    def test_causation_chain_and_sequence_per_batch(self):
        by = defaultdict(list)
        for e in EV:
            by[e["correlation_id"]].append(e)
        for corr, lst in by.items():
            lst.sort(key=lambda e: e["sequence_no"])
            self.assertEqual([e["sequence_no"] for e in lst], list(range(len(lst))))
            self.assertIsNone(lst[0]["causation_id"])
            for a, b in zip(lst, lst[1:]):
                self.assertEqual(b["causation_id"], a["event_id"])
                self.assertLessEqual(a["event_time"], b["event_time"], corr)

    def test_event_ids_unique_and_deterministic(self):
        self.assertEqual(len({e["event_id"] for e in EV}), len(EV))
        self.assertEqual([e["event_id"] for e in events(PLANT, simulate(PLANT))], [e["event_id"] for e in EV])

    def test_every_finished_or_rejected_batch_has_one_closing_event(self):
        closed = [e for e in EV if e["event_type"] in ("lot.dispatched", "lot.rejected")]
        self.assertEqual(len(closed), sum(1 for b in RES.batches if b.done is not None))
        self.assertEqual(sum(1 for e in closed if e["event_type"] == "lot.dispatched"), len(RES.finished))

    def test_hash_covers_the_content(self):
        import hashlib
        e = dict(EV[5]); h = e.pop("payload_hash")
        self.assertEqual(h, hashlib.sha256(json.dumps(e, sort_keys=True, separators=(",", ":")).encode()).hexdigest())

    def test_jsonl_roundtrip(self):
        with tempfile.NamedTemporaryFile("r", suffix=".jsonl", delete=False) as t:
            n = write_jsonl(EV[:50], t.name)
            lines = open(t.name, encoding="utf-8").read().splitlines()
        os.unlink(t.name)
        self.assertEqual((n, len(lines)), (50, 50))
        self.assertEqual(json.loads(lines[3])["event_id"], EV[3]["event_id"])

    def test_no_real_names_only_pseudonyms(self):
        for e in EV[:500]:
            self.assertRegex(e["lot_id"], r"^LOT-\d{6}$")
            self.assertRegex(e["material_id"], r"^MAT-\d{6}$")


class HtmlTests(unittest.TestCase):
    def test_html_lists_only_that_lot_and_has_no_scripts(self):
        from plantsim.events import render_html
        h = render_html(EV, "LOT-000003")
        self.assertIn("LOT-000003", h)
        self.assertEqual(h.count("<tr>"), 1 + sum(1 for e in EV if e["lot_id"] == "LOT-000003"))
        self.assertNotIn("<script", h)
        self.assertNotIn("http", h)
