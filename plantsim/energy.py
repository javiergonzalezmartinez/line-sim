"""Energy calculator: kWh per stage and per finished lot from PLACEHOLDER power values per machine state.

Basic relation: energy (kWh) = power (kW) x time (h); 1 kWh = 3.6 MJ, the energy delivered by 1 kW in 1 hour
(https://en.wikipedia.org/wiki/Kilowatt-hour, read 2 Oct 2026).
Energy-performance indicators and a baseline are the ISO 50001 vocabulary (https://www.iso.org/standard/69426.html, listing page only;
the standard text was NOT read, so nothing here claims ISO 50001 conformity).

Config key "energy": {"default": {"process": kW, "setup": kW, "repair": kW, "idle": kW}, "stages": {"<stage name>": {same keys}}}.
Every kW value in the shipped example is an ILLUSTRATIVE PLACEHOLDER, not a measurement of any real machine.
The "default" applies only to stages of kind process (machines); move, wait, hold and wave stages need their own entry. A stage with no power entry is reported as "no kW configured" and adds 0.
Per stage and per resource: state hours come from the simulation (process = busy, setup, repair, idle = the rest of
servers x window). Not modelled: part-load curves, start-up peaks, standby depending on shift, compressed air / HVAC / cleanroom
base load, utility cost or CO2 factors, energy of movement vehicles (unless given as a stage), per-lot tracing (the lot figure is
total window energy divided by the lots finished in the window, a plant average, not one lot's own consumption).
"""
from __future__ import annotations

from typing import Dict, Optional

STATES = ("process", "setup", "repair", "idle")


def energy(plant, res, cfg: Optional[dict]) -> Dict:
    cfg = cfg or {}
    default = cfg.get("default") or {}
    per = cfg.get("stages") or {}
    rows = []
    total = 0.0
    for sg, st in zip(plant.stages, res.stats):
        kw = {**(default if sg.kind == "process" else {}), **(per.get(sg.name) or {})}
        cap = st.servers * res.window
        if not kw or cap <= 0:
            rows.append({"stage": sg.name, "configured": False, "hours": {}, "kwh": {}, "total_kwh": 0.0})
            continue
        h = {"process": st.busy, "setup": st.setup, "repair": st.repair}
        h["idle"] = max(0.0, cap - sum(h.values()))
        k = {s: kw.get(s, 0.0) * h[s] for s in STATES}
        t = sum(k.values())
        total += t
        rows.append({"stage": sg.name, "configured": True, "hours": h, "kwh": k, "total_kwh": t})
    lots = sum(1 for b in res.batches if b.done is not None and not b.rejected and res.horizon - res.window <= b.done <= res.horizon)
    weeks = res.window / 168.0
    return {"rows": rows, "total_kwh": total, "lots_finished": lots, "kwh_per_lot": total / lots if lots else None,
            "kwh_per_week": total / weeks if weeks else None, "window_h": res.window}


def render_html(e: Dict, title: str = "Energy per stage (synthetic, placeholder kW)") -> str:
    import html as H
    cols = {"process": "#00857c", "setup": "#c98a00", "repair": "#c0392b", "idle": "#adb5bd"}
    mx = max([r["total_kwh"] for r in e["rows"]] + [1.0])
    body = ""
    for r in e["rows"]:
        if not r["configured"]:
            body += f"<tr><td>{H.escape(r['stage'])}</td><td colspan=3 style='color:#868e96'>no kW configured</td></tr>"
            continue
        bar = "".join(f'<div title="{s}" style="display:inline-block;height:14px;width:{300 * r["kwh"][s] / mx:.1f}px;background:{cols[s]}"></div>' for s in STATES)
        body += f"<tr><td>{H.escape(r['stage'])}</td><td>{bar}</td><td style='text-align:right'>{r['total_kwh']:,.0f}</td><td>{r['kwh']['process']:,.0f} / {r['kwh']['setup']:,.0f} / {r['kwh']['repair']:,.0f} / {r['kwh']['idle']:,.0f}</td></tr>"
    leg = "".join(f'<span style="margin-right:10px"><span style="display:inline-block;width:10px;height:10px;background:{c}"></span> {s}</span>' for s, c in cols.items())
    kl = e["kwh_per_lot"]
    return f"""<!doctype html><html><head><meta charset=utf-8><title>{H.escape(title)}</title><style>body{{font:13px system-ui,sans-serif;margin:16px;max-width:1100px}}table{{border-collapse:collapse;width:100%}}th{{background:#0b1226;color:#fff;text-align:left;padding:5px 8px}}td{{padding:3px 8px;border-bottom:1px solid #dde3ea}}.n{{background:#fff4d6;border-left:4px solid #c98a00;padding:6px 10px;margin:8px 0}}.k{{display:inline-block;margin-right:24px}}.k b{{font-size:22px;display:block}}</style></head><body><h2>{H.escape(title)}</h2><div class=n>ILLUSTRATIVE. Every kW value is a placeholder, not a measurement. kWh = kW x hours of each machine state from the simulation. Lot figure = window energy / lots finished in the window (plant average). Not modelled: part-load, start-up peaks, HVAC and other base load, cost, CO2.</div>
<p><span class=k>Total in window<b>{e['total_kwh']:,.0f} kWh</b></span><span class=k>Per week<b>{e['kwh_per_week']:,.0f} kWh</b></span><span class=k>Lots finished<b>{e['lots_finished']}</b></span><span class=k>Per finished lot<b>{(f'{kl:,.0f} kWh' if kl is not None else 'n/a')}</b></span></p><p>{leg}</p>
<table><tr><th>Stage</th><th>kWh by state</th><th>Total kWh</th><th>process / setup / repair / idle</th></tr>{body}</table></body></html>"""
