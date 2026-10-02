import unittest
from plantsim.fsm import Machine, IllegalTransition, Spec, spec, state_hash
from tests.test_events import EV, RES, PLANT


class FsmTests(unittest.TestCase):
    def test_spec_has_the_eight_machines(self):
        self.assertEqual(len(spec().machines()), 8)
        self.assertIn("JOB_ORDER", spec().machines())

    def test_job_order_happy_path_and_abort(self):
        m = Machine("JOB_ORDER", "NOT_ALLOWED_TO_START")
        for e, s in (("Start", "ALLOWED_TO_START"), ("ExecutionBegins", "RUNNING"), ("Pause", "INTERRUPTED"), ("Resume", "RUNNING"), ("StopOrNaturalEnd", "ENDED")):
            self.assertEqual(m.fire(e)[1], s)
        a = Machine("JOB_ORDER", "RUNNING")
        a.fire("Abort")
        self.assertEqual(a.state, "ABORTED")

    def test_illegal_transition_is_rejected_logged_and_state_kept(self):
        m = Machine("JOB_ORDER", "NOT_ALLOWED_TO_START")
        with self.assertRaises(IllegalTransition):
            m.fire("ExecutionBegins")
        self.assertEqual(m.state, "NOT_ALLOWED_TO_START")
        self.assertEqual(m.rejected, [("ExecutionBegins", "NOT_ALLOWED_TO_START")])
        self.assertEqual(m.history, [])

    def test_ended_is_final(self):
        m = Machine("JOB_ORDER", "ENDED")
        for e in ("Start", "Pause", "Abort", "ExecutionBegins"):
            with self.assertRaises(IllegalTransition):
                m.fire(e)

    def test_unknown_state_and_machine_rejected(self):
        with self.assertRaises(ValueError):
            Machine("JOB_ORDER", "FLYING")
        with self.assertRaises(ValueError):
            Machine("NOPE", "X")

    def test_phase_execution_cannot_skip_ready(self):
        m = Machine("PHASE_EXECUTION", "QUEUED")
        with self.assertRaises(IllegalTransition):
            m.fire("phase.started")

    def test_every_transition_in_the_spec_is_reachable_by_fire(self):
        sp = spec()
        for (mach, frm, ev), to in sp.table.items():
            m = Machine(mach, frm)
            self.assertEqual(m.fire(ev), (frm, to))

    def test_simulated_events_carry_state_hashes_that_match_the_spec(self):
        ph = [e for e in EV if e["event_type"] == "phase.started"]
        self.assertTrue(ph)
        for e in ph[:200]:
            self.assertEqual(e["state_before_hash"], state_hash("PHASE_EXECUTION", "READY"))
            self.assertEqual(e["state_after_hash"], state_hash("PHASE_EXECUTION", "RUNNING"))

    def test_rejected_lots_abort_their_job_and_phase(self):
        rej = [e for e in EV if e["event_type"] == "lot.rejected"]
        self.assertEqual(len(rej), sum(1 for b in RES.batches if b.rejected and b.done is not None))
        for e in rej:
            self.assertEqual(e["state_after_hash"], state_hash("JOB_ORDER", "ABORTED"))
        ab = [e for e in EV if e["event_type"] == "phase.aborted"]
        self.assertEqual(len(ab), len(rej))

    def test_each_phase_goes_ready_started_then_a_final_event(self):
        from collections import Counter
        c = Counter(e["event_type"] for e in EV)
        self.assertEqual(c["phase.ready"], c["phase.started"])
        self.assertEqual(c["phase.started"], c["phase.completed"] + c["phase.aborted"])
