"""Handling units (HU) and pallets as HANDLING_UNIT state-machine events (spec 08_ESTADOS, machine HANDLING_UNIT).

Two kinds of HU per lot, both inside the spec table:
  * input HUs (hu_per_lot of them): label.printed > label.verified > QUARANTINE > released > AVAILABLE > reserved >
    picked > MOVING > staged > consumed (start of the first process stage after that move) > EMPTY > CLOSED.
    Without a move stage the HU arrives by dispense.hu_arrived instead of the pick sequence.
  * finished pallets (only for lots that finish accepted): ceil(hu_per_lot / hu_per_pallet) pallets, built when the lot
    is done (event pallet.built, an OBJECT event that is NOT a state change in the spec), labelled, quarantined,
    released after release_delay_h, and shipped only if ship_delay_h is given (load + dispatch).
All numbers come from the `handling` config key; there are no spec values (TBD), so defaults are: hu_per_lot 1,
hu_per_pallet = hu_per_lot, release_delay_h 0, ship_delay_h None (no shipment events). Incoming material QA is NOT
modelled: input HUs are released at lot release time. Transport of HUs between locations is not modelled beyond the first move.
"""
from __future__ import annotations

import math
import uuid
from typing import Dict, List, Optional

from .events import NS, _hash, _iso
from .fsm import Machine, state_hash

KEYS = ("hu_per_lot", "hu_per_pallet", "release_delay_h", "ship_delay_h")


def handling(plant, result, cfg: Optional[Dict] = None, schema_version: str = "2.0") -> List[dict]:
    cfg = {k: v for k, v in (cfg or {}).items() if not k.startswith("_")}
    unknown = set(cfg) - set(KEYS)
    if unknown:
        raise ValueError(f"unknown handling parameters: {sorted(unknown)}")
    n = cfg.get("hu_per_lot", 1)
    per = cfg.get("hu_per_pallet", n)
    rel, ship = cfg.get("release_delay_h", 0.0), cfg.get("ship_delay_h")
    if not (isinstance(n, int) and n >= 1 and isinstance(per, int) and per >= 1):
        raise ValueError("hu_per_lot and hu_per_pallet must be integers >= 1")
    if rel < 0 or (ship is not None and ship < 0):
        raise ValueError("release_delay_h and ship_delay_h must be >= 0")
    out: List[dict] = []
    seq = [0]

    for b in result.batches:
        lot = f"LOT-{b.id + 1:06d}"
        mat = f"MAT-{plant.products.index(b.product) + 1:06d}"

        def run(obj, steps, step_name=None):
            """steps: list of (time, event_type, machine event, extra). Fires on one machine, emits one event each."""
            m = Machine("HANDLING_UNIT", "CREATED", obj)
            last = None
            for t, etype, fev, extra in steps:
                if fev is None:
                    bf = af = m.state
                else:
                    bf, af = m.fire(fev)
                seq[0] += 1
                e = {"event_id": str(uuid.uuid5(NS, f"{plant.seed}/hu/{seq[0]}")), "event_class": "OBJECT", "event_type": etype,
                     "action": "OBSERVE", "event_time": _iso(t), "record_time": _iso(t), "event_time_zone_offset": "+00:00",
                     "correlation_id": f"CORR-{b.id + 1:06d}", "causation_id": last, "sequence_no": None, "object_ids": [obj],
                     "lot_id": lot, "material_id": mat, "business_step": (extra or {}).pop("step", step_name), "result": "OK",
                     "reason_code": f"HANDLING_UNIT:{bf}>{af}" if fev else "not a spec state change", "schema_version": schema_version}
                if extra:
                    e.update(extra)
                if fev:
                    e["state_before_hash"], e["state_after_hash"] = state_hash("HANDLING_UNIT", bf), state_hash("HANDLING_UNIT", af)
                e["payload_hash"] = _hash(e)
                last = e["event_id"]
                e["_o"] = seq[0]
                out.append(e)
            return m

        tr = b.trace
        mv = next((r for r in tr if plant.stages[r[0]].kind == "move"), None)
        pr = next((r for r in tr if plant.stages[r[0]].kind == "process" and (mv is None or r[2] >= mv[3] - 1e-9)), None)
        for i in range(1, n + 1):
            hu = f"HU-{b.id + 1:06d}-{i:02d}"
            t0 = b.released
            st = [(t0, "label.printed", "label.printed", None), (t0, "label.verified", "label.verified", None),
                  (t0, "quality.status_changed:RELEASED", "quality.status_changed:RELEASED", {"disposition": "released"}),
                  ]
            if mv:
                st += [(mv[1], "reserve.created", "reserve.created", None), (mv[2], "move.picked", "move.picked", {"step": plant.stages[mv[0]].name}),
                       (mv[3], "move.completed", "move.completed", {"step": plant.stages[mv[0]].name})]
            else:
                st += [(t0, "dispense.hu_arrived", "dispense.hu_arrived", None)]
            if pr:
                tc = max(pr[2], mv[3] if mv else 0)
                st += [(tc, "phase.material_consumed", "phase.material_consumed", {"step": plant.stages[pr[0]].name}),
                       (pr[3], "dispense.source_empty", "dispense.source_empty", None), (pr[3], "container.closed", "container.closed", None)]
            run(hu, st)
        if b.done is not None and not b.rejected:
            for j in range(1, math.ceil(n / per) + 1):
                pal = f"PAL-{b.id + 1:06d}-{j:02d}"
                t = b.done
                st = [(t, "pallet.built", None, {"payload": {"units": min(per, n - (j - 1) * per)}}),
                      (t, "label.printed", "label.printed", None), (t, "label.verified", "label.verified", None),
                      (t + rel, "quality.status_changed:RELEASED", "quality.status_changed:RELEASED", {"disposition": "released"})]
                if ship is not None:
                    st += [(t + rel + ship, "shipment.hu_loaded", "shipment.hu_loaded", None),
                           (t + rel + ship, "shipment.dispatched", "shipment.dispatched", None)]
                run(pal, st, "Palletizing")
    out.sort(key=lambda e: (e["event_time"], e["object_ids"][0], e["_o"]))
    for e in out:
        del e["_o"]
    return out


def handling_kpis(evs: List[dict]) -> dict:
    """Counts only (no spec KPI for these): HUs, pallets, units per pallet, final state counts, mean quarantine of pallets (h)."""
    from .kpis import hours
    hus = {e["object_ids"][0] for e in evs if e["object_ids"][0].startswith("HU-")}
    pal = {e["object_ids"][0] for e in evs if e["object_ids"][0].startswith("PAL-")}
    built = {e["object_ids"][0]: hours(e["event_time"]) for e in evs if e["event_type"] == "pallet.built"}
    rel = {e["object_ids"][0]: hours(e["event_time"]) for e in evs if e["object_ids"][0] in pal and e["event_type"] == "quality.status_changed:RELEASED"}
    units = [e["payload"]["units"] for e in evs if e["event_type"] == "pallet.built"]
    shipped = sum(1 for e in evs if e["event_type"] == "shipment.dispatched")
    q = [rel[p] - built[p] for p in rel if p in built]
    return {"input_HUs": len(hus), "pallets": len(pal), "units_per_pallet_mean": round(sum(units) / len(units), 2) if units else 0.0,
            "pallets_released": len(rel), "pallets_shipped": shipped, "pallet_quarantine_mean_h": round(sum(q) / len(q), 3) if q else 0.0}


def render_html(evs: List[dict], title: str = "Handling units and pallets (synthetic)") -> str:
    import html
    from .kpis import hours
    k = handling_kpis(evs)
    pal = [e for e in evs if e["object_ids"][0].startswith("PAL-")]
    delta = {"label.verified": ("QUARANTINE", 1), "quality.status_changed:RELEASED": ("AVAILABLE", 1), "shipment.hu_loaded": ("LOADED", 1), "shipment.dispatched": ("SHIPPED", 1)}
    # count of pallets per state over time (a pallet leaves the previous state when it enters the next one)
    prev = {"quality.status_changed:RELEASED": "QUARANTINE", "shipment.hu_loaded": "AVAILABLE", "shipment.dispatched": "LOADED"}
    pts, cnt = [(0.0, {"QUARANTINE": 0, "AVAILABLE": 0, "LOADED": 0, "SHIPPED": 0})], {"QUARANTINE": 0, "AVAILABLE": 0, "LOADED": 0, "SHIPPED": 0}
    for e in pal:
        if e["event_type"] in delta:
            cnt = dict(cnt)
            cnt[delta[e["event_type"]][0]] += 1
            if e["event_type"] in prev:
                cnt[prev[e["event_type"]]] -= 1
            pts.append((hours(e["event_time"]), cnt))
    W, H, L, B = 1000, 260, 44, 28
    tmax = max(p[0] for p in pts) or 1
    ymax = max(max(c.values()) for _, c in pts) or 1
    X = lambda t: L + (W - L - 10) * t / tmax
    Y = lambda v: H - B - (H - B - 10) * v / ymax
    cols = {"QUARANTINE": "#c98a00", "AVAILABLE": "#00857c", "SHIPPED": "#3b5bdb"}
    paths = ""
    for st, col in cols.items():
        d, last = "", None
        for t, c in pts:
            if last is not None:
                d += f" L{X(t):.1f},{Y(last):.1f}"
            d += (" M" if last is None else " L") + f"{X(t):.1f},{Y(c[st]):.1f}"
            last = c[st]
        paths += f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.6"/>'
    leg = "".join(f'<span style="color:{c}">&#9632;</span> pallets {s.lower()} &nbsp; ' for s, c in cols.items())
    first = pal[0]["object_ids"][0] if pal else ""
    rows = "".join(f"<tr><td>{hours(e['event_time']):.2f}</td><td>{html.escape(e['event_type'])}</td><td>{html.escape(e['reason_code'])}</td></tr>" for e in pal if e["object_ids"][0] == first)
    cards = "".join(f"<div class=c><small>{html.escape(n)}</small><b>{v}</b></div>" for n, v in k.items())
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{title}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1040px}}.g{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.c{{border:1px solid #dde3ea;border-top:3px solid #00857c;border-radius:8px;padding:8px 10px}}.c small{{display:block;color:#556}}.c b{{font-size:18px}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:4px 8px;border-bottom:1px solid #dde3ea}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}</style></head><body><h2>{title}</h2><div class=n>Synthetic. Units per lot, per pallet and the delays are illustrative placeholders (the spec has no values). Incoming-material QA is not modelled.</div><div class=g>{cards}</div><h3>Pallets by state over time (h); shipped is cumulative</h3><svg width={W} height={H} style="background:#fafbfc;border:1px solid #dde3ea"><line x1={L} y1={H-B} x2={W-10} y2={H-B} stroke="#889"/><line x1={L} y1=10 x2={L} y2={H-B} stroke="#889"/><text x=4 y=16 font-size=11>{ymax}</text><text x=4 y={H-B} font-size=11>0</text><text x={W-60} y={H-8} font-size=11>{tmax:.0f} h</text>{paths}</svg><div>{leg}</div><h3>Life of {first}</h3><table><tr><th>Hour</th><th>Event</th><th>State change</th></tr>{rows}</table></body></html>"""
