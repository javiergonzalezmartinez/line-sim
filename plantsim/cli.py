from __future__ import annotations
import argparse, json, sys
from .model import Plant, Stage, simulate

def load(path):
    d = json.load(open(path, encoding="utf-8"))
    st = []
    for s in d["stages"]:
        s = dict(s)
        if "window" in s:
            s["window"] = tuple(s["window"])
        st.append(Stage(**s))
    return Plant(st, d["products"], d["release_every"], d.get("horizon", 2016), d.get("warmup", 336), d.get("seed", 1), d.get("layout"), d.get("m_per_px", 0.0), d.get("speed_kmh", 6.0), d.get("handling_min", 6.0), d.get("dispatch", "fifo"))

def main(argv=None):
    ap = argparse.ArgumentParser(prog="plantsim"); ap.add_argument("config"); ap.add_argument("--view", help="write animated HTML view"); ap.add_argument("--events", help="write the canonical event log (JSONL)"); ap.add_argument("--telemetry", help="write machine telemetry sensor events (JSONL)"); ap.add_argument("--kpis", help="write KPIs computed from the event log (HTML)"); ap.add_argument("--handling", help="write handling-unit and pallet events (JSONL); parameters from the config key \"handling\""); ap.add_argument("--handling-view", help="write handling-unit HTML page"); ap.add_argument("--transport", help="write transport task events (JSONL); config key \"transport\""); ap.add_argument("--transport-view", help="write fleet HTML page"); ap.add_argument("--quality", help="write quality status events (JSONL); config key \"quality\""); ap.add_argument("--quality-view", help="write quality HTML page"); ap.add_argument("--dashboard", help="write the live dashboard (animated plant + digital-twin panel, one HTML file)"); ap.add_argument("--process-values", help="write analog process value events (JSONL); config key \"process_values\""); ap.add_argument("--process-view", help="write HTML chart of the first configured process value"); ap.add_argument("--whatif", help="scenario B config (JSON); compares it with the main config over --seeds replications"); ap.add_argument("--whatif-view", help="write the what-if HTML page (default whatif.html)"); ap.add_argument("--seeds", type=int, default=20, help="replications per scenario for --whatif"); ap.add_argument("--mqtt", help="write Sparkplug-style MQTT messages (JSONL, no broker)"); ap.add_argument("--opcua-nodes", help="write an OPC UA-style flat node list (JSON)"); ap.add_argument("--mqtt-view", help="write HTML summary of the replay export"); ap.add_argument("--energy", help="write HTML energy page (kWh per stage and lot); config key \"energy\" with placeholder kW"); ap.add_argument("--flow-view", help="write heat map + material flow + Gantt page (HTML)"); ap.add_argument("--oee-view", help="write OEE decomposition page (HTML)"); ap.add_argument("--bottleneck-view", help="write shifting-bottleneck page (active period method, HTML)"); ap.add_argument("--calibrate-view", help="write calibration page against a synthetic reference (needs --calibrate-truth)"); ap.add_argument("--calibrate-stage", default="Coating"); ap.add_argument("--calibrate-truth", type=float, help="hidden true mean process time (h) used to generate the synthetic reference"); ap.add_argument("--messages", help="write interface handshake message events (JSONL); parameters from the config key \"handshake\"")
    a = ap.parse_args(argv)
    p = load(a.config); r = simulate(p)
    print(f"throughput {r.throughput_per_week:.2f} batches/week, mean lead time {r.mean_lead_time_days:.1f} days, busiest: {r.bottleneck}, rejected lots in window: {r.rejected}")
    for st, sg in zip(r.stats, p.stages):
        if sg.kind == 'hold':
            continue
        u = r.utilisation(st); n = max(st.batches, 1)
        print(f"  {st.name:<28} proc {u['process']:5.0%} setup {u['setup']:5.0%} repair {u['repair']:5.0%}  mean wait {st.wait/n:6.1f} h" + (f"  material waits {st.short_lots} lots, {st.short_hours:.0f} h" if st.short_lots else ""))
    for n, u in r.pool_utilisation(p).items():
        print(f"  pool {n}: busy {u:.0%}")
    if a.whatif:
        from .whatif import compare, render_html as wrender
        q = load(a.whatif); c = compare(p, q, a.seeds)
        for k, v in c["metrics"].items():
            print(f"  {k:<28} A {v['A'][0]:9.3f}  B {v['B'][0]:9.3f}  B-A {v['diff'][0]:+9.3f} [{v['diff'][1]:+.3f}, {v['diff'][2]:+.3f}]  {'clear' if v['clear'] else 'not clear'}")
        out = a.whatif_view or "whatif.html"
        open(out, "w", encoding="utf-8").write(wrender(c, "main config", "scenario B", "", "", "What-if: " + a.config + " vs " + a.whatif))
        print("what-if page written to", out)
    if a.mqtt or a.opcua_nodes or a.mqtt_view:
        from .signals import telemetry as _tl
        from . import mqttexport as mx
        tl = _tl(p, r); ms = mx.sparkplug_messages(tl); nd = mx.opcua_nodes(tl)
        if a.mqtt: print(f"{mx.write_jsonl(ms, a.mqtt)} MQTT messages written to {a.mqtt}")
        if a.opcua_nodes:
            json.dump(nd, open(a.opcua_nodes, "w", encoding="utf-8"), indent=1); print(f"{len(nd)} nodes written to {a.opcua_nodes}")
        if a.mqtt_view:
            open(a.mqtt_view, "w", encoding="utf-8").write(mx.render_html(ms, nd)); print("replay page written to", a.mqtt_view)
    if a.energy:
        from .energy import energy as _en, render_html as _er
        ee = _en(p, r, json.load(open(a.config, encoding="utf-8")).get("energy"))
        open(a.energy, "w", encoding="utf-8").write(_er(ee))
        print(f"energy: {ee['total_kwh']:,.0f} kWh in window, {ee['lots_finished']} lots finished, " + (f"{ee['kwh_per_lot']:,.0f} kWh per lot (placeholder kW)" if ee['kwh_per_lot'] is not None else "no lots") + f"; page written to {a.energy}")
    if a.flow_view:
        from .flowviews import render_html as _fv
        open(a.flow_view, "w", encoding="utf-8").write(_fv(p, r)); print("flow views written to", a.flow_view)
    if a.oee_view:
        from .oee import oee as _oee, render_html as _orh
        orows = _oee(p, r); open(a.oee_view, "w", encoding="utf-8").write(_orh(orows)); print("OEE page written to", a.oee_view)
    if a.bottleneck_view:
        from .bottleneck import detect as _bd, render_html as _bh
        bd = _bd(p, r); open(a.bottleneck_view, "w", encoding="utf-8").write(_bh(bd)); print(f"bottleneck: {bd['shifts']} shifts; " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(bd['share'].items(), key=lambda x: -x[1])[:4]) + f"; page written to {a.bottleneck_view}")
    if a.calibrate_view:
        from .calibrate import calibrate as _cal, render_html as _calr
        if a.calibrate_truth is None: ap.error("--calibrate-view needs --calibrate-truth")
        st0 = next(s.hours for s in p.stages if s.name == a.calibrate_stage); cr = _cal(p, a.calibrate_stage, a.calibrate_truth, st0 - 3, st0 + 3)
        open(a.calibrate_view, "w", encoding="utf-8").write(_calr(cr))
        print(f"calibration: stage {cr['stage']} start {cr['start']:.2f} h, truth {cr['truth']:.2f} h, fitted {cr['fitted']:.2f} h (error {cr['error']:+.2f}); page written to {a.calibrate_view}")
    if a.events:
        from .events import events, write_jsonl
        print(f"{write_jsonl(events(p, r), a.events)} events written to {a.events}")
    if a.telemetry:
        from .events import write_jsonl
        from .signals import telemetry
        print(f"{write_jsonl(telemetry(p, r), a.telemetry)} telemetry events written to {a.telemetry}")
    if a.kpis:
        from .events import events
        from .signals import telemetry
        from .kpis import kpis, render_html
        open(a.kpis, "w", encoding="utf-8").write(render_html(kpis(p, events(p, r), telemetry(p, r))))
        print("KPI page written to", a.kpis)
    if a.handling:
        from .events import write_jsonl
        from .handling import handling, handling_kpis
        hs = handling(p, r, json.load(open(a.config, encoding="utf-8")).get("handling"))
        print(f"{write_jsonl(hs, a.handling)} handling events written to {a.handling}; {handling_kpis(hs)}")
    if a.handling_view:
        from .handling import handling, render_html as hr
        open(a.handling_view, "w", encoding="utf-8").write(hr(handling(p, r, json.load(open(a.config, encoding="utf-8")).get("handling"))))
        print("handling page written to", a.handling_view)
    if a.transport or a.transport_view:
        from .events import write_jsonl
        from .transport import transport, transport_kpis, render_html as tr
        tc = json.load(open(a.config, encoding="utf-8")).get("transport")
        if a.transport:
            te = transport(p, r, tc)
            print(f"{write_jsonl(te, a.transport)} transport events written to {a.transport}; {transport_kpis(te, tc, p.horizon)}")
        if a.transport_view:
            open(a.transport_view, "w", encoding="utf-8").write(tr(p, r, tc))
            print("fleet page written to", a.transport_view)
    if a.quality or a.quality_view:
        from .events import write_jsonl
        from .quality import quality, quality_kpis, render_html as qr
        cj = json.load(open(a.config, encoding="utf-8"))
        qe = quality(p, r, cj.get("quality"))
        hu = (cj.get("handling") or {}).get("hu_per_lot", 1)
        if a.quality:
            print(f"{write_jsonl(qe, a.quality)} quality events written to {a.quality}; {quality_kpis(qe, hu)}")
        if a.quality_view:
            open(a.quality_view, "w", encoding="utf-8").write(qr(qe, hu))
            print("quality page written to", a.quality_view)
    if a.dashboard:
        from .dashboard import build
        open(a.dashboard, "w", encoding="utf-8").write(build(p, json.load(open(a.config, encoding="utf-8"))))
        print("dashboard written to", a.dashboard)
    if a.process_values or a.process_view:
        from .events import write_jsonl
        from .processvalues import process_values, reduction, render_html as pr
        pc = json.load(open(a.config, encoding="utf-8")).get("process_values") or {}
        if a.process_values:
            pe = process_values(p, r, pc)
            print(f"{write_jsonl(pe, a.process_values)} process value events written to {a.process_values}; {reduction(p, pe, pc)}")
        if a.process_view:
            st = next(k for k in pc if not k.startswith("_"))
            open(a.process_view, "w", encoding="utf-8").write(pr(p, r, pc, st, next(iter(pc[st]))))
            print("process value page written to", a.process_view)
    if a.messages:
        from .events import write_jsonl
        from .handshakes import messages, message_kpis
        ms = messages(p, r, json.load(open(a.config, encoding="utf-8")).get("handshake"))
        print(f"{write_jsonl(ms, a.messages)} message events written to {a.messages}; {message_kpis(ms)}")
    if a.view:
        from .view import render
        open(a.view, 'w', encoding='utf-8').write(render(p, r))
        print('view written to', a.view)
    return 0
if __name__ == "__main__":
    sys.exit(main())
