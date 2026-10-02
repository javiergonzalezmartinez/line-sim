"""Interface handshakes (spec HS-001 MoveRequest) as MESSAGE state-machine events, plus message KPIs.

For every move stage of every lot, the orchestrator sends MOVE_REQUEST and waits for MOVE_ACCEPTED.
The MESSAGE machine from the spec runs: CREATED > SENT > ACK > RECONCILED, or TIMEOUT / NACK > retry > ... >
DEAD_LETTER. Failure behaviour comes ONLY from the parameters given in `cfg` (ack_latency_h, timeout_h,
loss_p, nack_p, duplicate_p, max_retries). The spec leaves all of these as TBD, so with an empty cfg the
handshake is ideal (immediate ACK, no loss) and nothing is invented. The messages run beside the transport:
a failed handshake does NOT delay the move in this model.
Failure ids used (spec/failures.json): FME-009 ACK lost, FME-011 duplicate message, FME-013 ACK timeout,
FME-014 rejected/invalid message.
"""
from __future__ import annotations

import random
import uuid
from typing import Dict, List, Optional

from .events import NS, _hash, _iso
from .fsm import Machine, state_hash

KEYS = ("ack_latency_h", "timeout_h", "loss_p", "nack_p", "duplicate_p", "max_retries")


def messages(plant, result, cfg: Optional[Dict] = None, schema_version: str = "2.0") -> List[dict]:
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    unknown = set(cfg) - set(KEYS)
    if unknown:
        raise ValueError(f"unknown handshake parameters: {sorted(unknown)}")
    lat, tmo = cfg.get("ack_latency_h", 0.0), cfg.get("timeout_h", 1.0)
    loss, nack, dup, maxr = cfg.get("loss_p", 0.0), cfg.get("nack_p", 0.0), cfg.get("duplicate_p", 0.0), cfg.get("max_retries", 3)
    for n, v in (("loss_p", loss), ("nack_p", nack), ("duplicate_p", dup)):
        if not 0 <= v <= 1:
            raise ValueError(f"{n} must be between 0 and 1")
    if lat < 0 or tmo <= 0 or maxr < 0:
        raise ValueError("ack_latency_h >= 0, timeout_h > 0, max_retries >= 0")
    rng = random.Random(plant.seed + 1)
    out: List[dict] = []
    seq = [0]
    for b in result.batches:
        lot = f"LOT-{b.id + 1:06d}"
        for rec in b.trace:
            k = rec[0]
            if plant.stages[k].kind != "move":
                continue
            msg = f"MSG-{b.id + 1:06d}-{k + 1:02d}"
            m = Machine("MESSAGE", "CREATED", msg)
            t, attempt, last = rec[1], 0, [None]

            def emit(time, ev, bf, af, extra=None, tag="HS-001"):
                seq[0] += 1
                e = {"event_id": str(uuid.uuid5(NS, f"{plant.seed}/msg/{seq[0]}")), "event_class": "CONTROL", "event_type": ev, "action": "OBSERVE",
                     "event_time": _iso(time), "record_time": _iso(time), "event_time_zone_offset": "+00:00", "correlation_id": f"CORR-{b.id + 1:06d}",
                     "causation_id": last[0], "sequence_no": None, "object_ids": [msg], "lot_id": lot, "business_step": plant.stages[k].name,
                     "result": "OK", "idempotency_key": f"IDEM-{msg}", "attempt": attempt, "reason_code": f"{tag} MESSAGE:{bf}>{af}", "schema_version": schema_version}
                if extra:
                    e.update(extra)
                if bf != af:
                    e["state_before_hash"], e["state_after_hash"] = state_hash("MESSAGE", bf), state_hash("MESSAGE", af)
                e["payload_hash"] = _hash(e)
                last[0] = e["event_id"]
                out.append(e)

            while True:
                attempt += 1
                if attempt == 1:
                    emit(t, "message.sent", *m.fire("message.sent"))
                if dup and rng.random() < dup:
                    emit(t + lat, "message.duplicate_discarded", m.state, m.state, {"result": "OK"}, tag="FME-011")
                r = rng.random()
                if r < loss:
                    t += tmo
                    emit(t, "message.timeout", *m.fire("message.timeout"), {"result": "ERROR"}, tag="FME-009/FME-013")
                elif r < loss + nack:
                    t += lat
                    emit(t, "message.rejected", *m.fire("message.rejected"), {"result": "REJECTED"}, tag="FME-014")
                else:
                    t += lat
                    emit(t, "message.acknowledged", *m.fire("message.acknowledged"))
                    emit(t, "message.reconciled", *m.fire("message.reconciled"))
                    break
                if attempt > maxr:
                    emit(t, "message.dead_lettered", *m.fire("message.dead_lettered"), {"result": "ERROR"})
                    break
                emit(t, "message.retry", *m.fire("message.retry"))     # the table moves TIMEOUT/NACK straight back to SENT
    out.sort(key=lambda e: (e["event_time"], e["object_ids"][0], e["attempt"]))
    return out


def message_kpis(msgs: List[dict]) -> dict:
    """KPI-015 MessageSuccess, KPI-016 MessageP95Latency (h, first send to RECONCILED), KPI-017 RetryRate."""
    from .kpis import hours
    first, done, sends, retries, total = {}, {}, 0, 0, set()
    for e in msgs:
        o = e["object_ids"][0]
        if e["event_type"] == "message.sent":
            sends += 1
            total.add(o)
            first.setdefault(o, hours(e["event_time"]))
        elif e["event_type"] == "message.retry":
            retries += 1
        elif e["event_type"] == "message.reconciled":
            done[o] = hours(e["event_time"])
    lat = sorted(done[o] - first[o] for o in done)
    p95 = lat[min(len(lat) - 1, int(0.95 * len(lat)))] if lat else None
    return {"messages": len(total), "KPI-015 MessageSuccess": len(done) / len(total) if total else None,
            "KPI-016 MessageP95Latency (h)": p95, "KPI-017 RetryRate": retries / len(total) if total else None,
            "dead_lettered": sum(1 for e in msgs if e["event_type"] == "message.dead_lettered")}
