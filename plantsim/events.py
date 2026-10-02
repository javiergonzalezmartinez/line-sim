"""Canonical event log from a simulation result (EPCIS-style fields, synthetic ids).

Each batch becomes a stream of events with correlation id, causation id (the previous event of the
same batch), sequence number and a payload hash. Times are the simulated hours from Monday 00:00 on a
fixed synthetic start date. Ids are pseudonyms (LOT-000001, EQ-STAGE-03); nothing is real data.
Validation covers the subset of JSON Schema that the canonical event schema uses (no external library).
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from .fsm import Machine, state_hash
from datetime import datetime, timedelta, timezone
from typing import Iterable, List

START = datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)   # a Monday, synthetic
NS = uuid.UUID("00000000-0000-4000-8000-000000000011")


def _iso(h: float) -> str:
    return (START + timedelta(hours=h)).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _hash(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def events(plant, result, schema_version: str = "2.0") -> List[dict]:
    out: List[dict] = []
    for b in result.batches:
        lot = f"LOT-{b.id + 1:06d}"
        corr = f"CORR-{b.id + 1:06d}"
        last = [None]
        seq = [0]

        def emit(cls, etype, action, t, k=None, result_="OK", disp=None, st=None):
            seq[0] += 1
            s = plant.stages[k] if k is not None else None
            e = {
                "event_id": str(uuid.uuid5(NS, f"{plant.seed}/{b.id}/{seq[0]}")),
                "event_class": cls, "event_type": etype, "action": action,
                "event_time": _iso(t), "record_time": _iso(t), "event_time_zone_offset": "+00:00",
                "correlation_id": corr, "causation_id": last[0], "sequence_no": seq[0] - 1,
                "object_ids": [lot], "lot_id": lot, "material_id": f"MAT-{plant.products.index(b.product) + 1:06d}",
                "business_step": s.name if s else None, "business_location": s.loc if s else None,
                "equipment_id": f"EQ-STAGE-{k + 1:02d}" if k is not None and s.kind in ("process", "move") else None,
                "disposition": disp, "result": result_, "schema_version": schema_version,
            }
            if st:
                e["state_before_hash"], e["state_after_hash"] = state_hash(st[0], st[1]), state_hash(st[0], st[2])
                e["reason_code"] = f"{st[0]}:{st[1]}>{st[2]}"
            e["payload_hash"] = _hash(e)
            last[0] = e["event_id"]
            out.append(e)

        job = Machine("JOB_ORDER", "NOT_ALLOWED_TO_START", lot)
        jb, ja = job.fire("Start")
        emit("OBJECT", "lot.released", "ADD", b.released, disp="in_progress", st=("JOB_ORDER", jb, ja))
        first = True
        for rec in b.trace:
            k, arrive, start, end = rec[0], rec[1], rec[2], rec[3]
            s = plant.stages[k]
            ph = Machine("PHASE_EXECUTION", "QUEUED", f"{lot}/{k}")
            emit("OBJECT", "queue.entered", "OBSERVE", arrive, k)
            bf, af = ph.fire("phase.ready")
            emit("CONTROL", "phase.ready", "EXECUTE", start, k, st=("PHASE_EXECUTION", bf, af))
            bf, af = ph.fire("phase.started")
            emit("CONTROL", "phase.started", "EXECUTE", start, k, st=("PHASE_EXECUTION", bf, af))
            if first:
                job.fire("ExecutionBegins")
                first = False
            rej = b.rejected and s.kind == "hold" and b.done is not None and abs(end - b.done) < 1e-9
            ev = "phase.aborted" if rej else "phase.completed"
            bf, af = ph.fire(ev)
            if rej:
                emit("OBJECT", ev, "OBSERVE", end, k, "REJECTED", "rejected", st=("PHASE_EXECUTION", bf, af))
            elif s.kind in ("process", "move"):
                emit("TRANSFORMATION" if s.kind == "process" else "OBJECT", ev, "EXECUTE" if s.kind == "process" else "OBSERVE", end, k,
                     st=("PHASE_EXECUTION", bf, af))
            else:
                emit("OBJECT", ev, "OBSERVE", end, k, st=("PHASE_EXECUTION", bf, af))
        if b.done is not None:
            jev = "Abort" if b.rejected else "StopOrNaturalEnd"
            bf, af = job.fire(jev)
            emit("TRANSACTION", "lot.rejected" if b.rejected else "lot.dispatched", "DELETE" if b.rejected else "OBSERVE", b.done,
                 result_="REJECTED" if b.rejected else "OK", disp="rejected" if b.rejected else "dispatched", st=("JOB_ORDER", bf, af))
    out.sort(key=lambda e: (e["event_time"], e["correlation_id"], e["sequence_no"]))
    return out


def write_jsonl(evs: Iterable[dict], path: str) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for e in evs:
            f.write(json.dumps(e, sort_keys=True) + "\n")
            n += 1
    return n


_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_DT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict, "null": type(None)}


def validate(inst, schema, path="$") -> List[str]:
    """Return a list of error strings (empty = valid). Supports type, enum, required, properties, items,
    minLength, minItems, minimum and the formats uuid / date-time."""
    errs: List[str] = []
    t = schema.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        ok = False
        for x in ts:
            py = _TYPES[x]
            if isinstance(inst, bool) and x in ("integer", "number"):
                continue
            if isinstance(inst, py):
                ok = True
        if not ok:
            return [f"{path}: expected {t}, got {type(inst).__name__}"]
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: {inst!r} not in enum")
    if isinstance(inst, str):
        if len(inst) < schema.get("minLength", 0):
            errs.append(f"{path}: too short")
        f = schema.get("format")
        if f == "uuid" and not _UUID.match(inst):
            errs.append(f"{path}: not a uuid")
        if f == "date-time" and not _DT.match(inst):
            errs.append(f"{path}: not a date-time")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool) and "minimum" in schema and inst < schema["minimum"]:
        errs.append(f"{path}: below minimum")
    if isinstance(inst, list):
        if len(inst) < schema.get("minItems", 0):
            errs.append(f"{path}: too few items")
        if "items" in schema:
            for i, x in enumerate(inst):
                errs += validate(x, schema["items"], f"{path}[{i}]")
    if isinstance(inst, dict):
        for r in schema.get("required", []):
            if r not in inst:
                errs.append(f"{path}: missing {r}")
        for k, sub in schema.get("properties", {}).items():
            if k in inst:
                errs += validate(inst[k], sub, f"{path}.{k}")
    return errs


def render_html(evs: List[dict], lot: str, title: str = "Event log of one lot (synthetic)") -> str:
    """Self-contained HTML table of the events of one lot (no scripts, no network)."""
    from html import escape
    col = {"OBJECT": "#2b6cb0", "CONTROL": "#b7791f", "TRANSFORMATION": "#2f855a", "TRANSACTION": "#805ad5"}
    rows = [e for e in evs if e["lot_id"] == lot]
    body = "".join(
        f'<tr><td>{e["sequence_no"]}</td><td>{escape(e["event_time"][:19].replace("T", " "))}</td>'
        f'<td><span style="background:{col.get(e["event_class"], "#555")}">{e["event_class"]}</span></td>'
        f'<td>{escape(e["event_type"])}</td><td>{e["action"]}</td><td>{escape(e["business_step"] or "")}</td>'
        f'<td>{escape(e["equipment_id"] or "")}</td><td>{escape((e.get("reason_code") or "").replace("PHASE_EXECUTION:", "PHASE ").replace("JOB_ORDER:", "JOB "))}</td><td>{e["result"]}</td><td class="h">{e["payload_hash"][:10]}</td></tr>' for e in rows)
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>{escape(title)}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;color:#111}}'
            'table{border-collapse:collapse;width:100%}th{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}td{padding:4px 8px;border-bottom:1px solid #dde3ea}'
            'span{color:#fff;padding:1px 7px;border-radius:9px;font-size:11px}.h{font-family:monospace;color:#667}.n{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}</style></head><body>'
            f'<h2>{escape(title)} · {escape(lot)}</h2><div class="n">Illustrative: events of a simulated lot, synthetic ids, not real plant data.</div>'
            '<table><tr><th>#</th><th>Time (synthetic date)</th><th>Class</th><th>Type</th><th>Action</th><th>Step</th><th>Equipment</th><th>State change</th><th>Result</th><th>Hash</th></tr>'
            f'{body}</table></body></html>')
