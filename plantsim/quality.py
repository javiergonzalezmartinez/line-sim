"""Quality disposition of every finished lot as QUALITY_STATUS state-machine events, plus quality KPIs.

Paths (all legal in the spec table, machine starts in QUARANTINE):
  * lot with no deviation hold: sample.request_created > sample.sent_to_lab > sample.status_released
    (all at lot completion; with cfg sample_h / lab_h the release is that much later: an overlay, the plant is not delayed);
  * lot held by the plant model (stage kind "hold", deviation investigation) and accepted:
    quality.hold_applied at hold start > quality.hold_released at hold end (state RELEASED);
  * lot held and rejected by the plant model: sample request, sent to lab, sample.status_rejected at hold end;
  * optional extra hold after release (cfg hold_p, hold_h): quality.hold_applied > quality.hold_released.
There are no spec values for sample_h, lab_h, hold_p, hold_h: defaults are 0 / 0 / 0 / 0 (instant, no extra holds), so the
only holds and rejections are the ones the plant model already simulates. Not modelled: expiry.reached (needs shelf life, TBD),
retests, partial release, a hold applied while still in QUARANTINE by the random hold.
KPIs: KPI-023 HoldExposure (qty x hours under hold; qty = HU per lot from the handling config, default 1 lot = 1),
KPI-011 FirstPassYield at lot level (accepted lots that never had a hold / lots dispositioned), plus reject and hold rates.
"""
from __future__ import annotations

import random
import uuid
from typing import Dict, List, Optional

from .events import NS, _hash, _iso
from .fsm import Machine, state_hash

KEYS = ("sample_h", "lab_h", "hold_p", "hold_h")


def quality(plant, result, cfg: Optional[Dict] = None, schema_version: str = "2.0") -> List[dict]:
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    unknown = set(cfg) - set(KEYS)
    if unknown:
        raise ValueError(f"unknown quality parameters: {sorted(unknown)}")
    sh, lh, hp, hh = cfg.get("sample_h", 0.0), cfg.get("lab_h", 0.0), cfg.get("hold_p", 0.0), cfg.get("hold_h", 0.0)
    if sh < 0 or lh < 0 or hh < 0 or not 0 <= hp <= 1:
        raise ValueError("sample_h, lab_h, hold_h >= 0 and hold_p in [0,1]")
    rng = random.Random(plant.seed + 3)
    out: List[dict] = []
    seq = [0]
    for b in result.batches:
        if b.done is None:
            continue
        lot = f"LOT-{b.id + 1:06d}"
        held = next((r for r in b.trace if plant.stages[r[0]].kind == "hold" and r[3] > r[2] + 1e-9), None)
        m = Machine("QUALITY_STATUS", "QUARANTINE", lot)
        last = [None]

        def emit(t, ev, res="OK", disp=None, step=None):
            bf, af = m.fire(ev)
            seq[0] += 1
            e = {"event_id": str(uuid.uuid5(NS, f"{plant.seed}/q/{seq[0]}")), "event_class": "OBJECT", "event_type": ev, "action": "OBSERVE",
                 "event_time": _iso(t), "record_time": _iso(t), "event_time_zone_offset": "+00:00", "correlation_id": f"CORR-{b.id + 1:06d}",
                 "causation_id": last[0], "sequence_no": None, "object_ids": [lot], "lot_id": lot, "material_id": f"MAT-{plant.products.index(b.product) + 1:06d}",
                 "business_step": step, "disposition": disp, "result": res, "reason_code": f"QUALITY_STATUS:{bf}>{af}", "schema_version": schema_version,
                 "state_before_hash": state_hash("QUALITY_STATUS", bf), "state_after_hash": state_hash("QUALITY_STATUS", af), "_o": seq[0]}
            e["payload_hash"] = _hash(e)
            last[0] = e["event_id"]
            out.append(e)

        if held and b.rejected:
            hs = plant.stages[held[0]].name
            emit(held[2], "sample.request_created", step=hs)
            emit(held[2] + sh, "sample.sent_to_lab", step=hs)
            emit(held[3], "sample.status_rejected", "REJECTED", "rejected", hs)
            continue
        if held:
            hs = plant.stages[held[0]].name
            emit(held[2], "quality.hold_applied", step=hs)
            emit(held[3], "quality.hold_released", disp="released", step=hs)
            t_rel = held[3]
        else:
            emit(b.done, "sample.request_created")
            emit(b.done + sh, "sample.sent_to_lab")
            t_rel = b.done + sh + lh
            emit(t_rel, "sample.status_released", disp="released")
        if hp and rng.random() < hp:
            emit(t_rel, "quality.hold_applied", step="extra hold (illustrative)")
            emit(t_rel + hh, "quality.hold_released", disp="released", step="extra hold (illustrative)")
    out.sort(key=lambda e: (e["event_time"], e["object_ids"][0], e["_o"]))
    for e in out:
        del e["_o"]
    return out


def quality_kpis(evs: List[dict], hu_per_lot: int = 1) -> dict:
    from .kpis import hours
    lots, held, rej, exposure, open_ = set(), set(), set(), 0.0, {}
    for e in evs:
        o, ty, t = e["object_ids"][0], e["event_type"], hours(e["event_time"])
        lots.add(o)
        if ty == "quality.hold_applied":
            held.add(o)
            open_[o] = t
        elif ty == "quality.hold_released":
            exposure += (t - open_.pop(o)) * hu_per_lot
        elif ty == "sample.status_rejected":
            rej.add(o)
    n = len(lots)
    return {"lots_dispositioned": n, "KPI-011 FirstPassYield (lot level)": round((n - len(held) - len(rej)) / n, 4) if n else None,
            "lots_with_hold": len(held), "lots_rejected": len(rej), "reject_rate": round(len(rej) / n, 4) if n else None,
            f"KPI-023 HoldExposure ({'HU' if hu_per_lot != 1 else 'lot'}.h)": round(exposure, 2)}


def render_html(evs: List[dict], hu_per_lot: int = 1, title: str = "Quality status of lots (synthetic)") -> str:
    import html
    from .kpis import hours
    k = quality_kpis(evs, hu_per_lot)
    counts, last = {}, {}
    for e in evs:
        last[e["object_ids"][0]] = e["event_type"]
    names = {"sample.status_released": "released after test", "quality.hold_released": "released after hold", "sample.status_rejected": "rejected",
             "quality.hold_applied": "still on hold", "sample.sent_to_lab": "in lab", "sample.request_created": "sampling"}
    for v in last.values():
        counts[names.get(v, v)] = counts.get(names.get(v, v), 0) + 1
    cols = {"released after test": "#00857c", "released after hold": "#3b5bdb", "rejected": "#c92a2a", "still on hold": "#c98a00", "in lab": "#868e96", "sampling": "#868e96"}
    tot = sum(counts.values()) or 1
    bars = "".join(f'<div style="flex:{v};background:{cols.get(n, "#868e96")};color:#fff;padding:6px 8px;min-width:0;white-space:nowrap;overflow:hidden">{html.escape(n)}: {v}</div>' for n, v in counts.items())
    ex = next((o for o in dict.fromkeys(e["object_ids"][0] for e in evs) if any(x["object_ids"][0] == o and x["event_type"] == "sample.status_rejected" for x in evs)), None)
    ex2 = next((o for o in dict.fromkeys(e["object_ids"][0] for e in evs) if any(x["object_ids"][0] == o and x["event_type"] == "quality.hold_applied" for x in evs) and o != ex), None)
    tabs = ""
    for o, lab in ((ex, "rejected lot"), (ex2, "held, then released lot")):
        if o:
            tabs += f"<h3>{lab}: {o}</h3><table><tr><th>Hour</th><th>Event</th><th>State change</th><th>Result</th></tr>" + "".join(
                f"<tr><td>{hours(e['event_time']):.2f}</td><td>{html.escape(e['event_type'])}</td><td>{html.escape(e['reason_code'])}</td><td>{e['result']}</td></tr>" for e in evs if e["object_ids"][0] == o) + "</table>"
    cards = "".join(f"<div class=c><small>{html.escape(n)}</small><b>{v}</b></div>" for n, v in k.items())
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{title}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.g{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.c{{border:1px solid #dde3ea;border-top:3px solid #00857c;border-radius:8px;padding:8px 10px}}.c small{{display:block;color:#556}}.c b{{font-size:18px}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>{title}</h2><div class=n>Synthetic. Holds and rejections come from the plant model's illustrative parameters; sample, lab and extra-hold times are placeholders (no spec values). Expiry, retests and partial release are not modelled.</div><div class=g>{cards}</div><h3>Final status of {tot} lots</h3><div style="display:flex;font-size:12px">{bars}</div>{tabs}</body></html>"""
