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
    return Plant(st, d["products"], d["release_every"], d.get("horizon", 2016), d.get("warmup", 336), d.get("seed", 1), d.get("layout"), d.get("m_per_px", 0.0), d.get("speed_kmh", 6.0), d.get("handling_min", 6.0))

def main(argv=None):
    ap = argparse.ArgumentParser(prog="plantsim"); ap.add_argument("config"); ap.add_argument("--view", help="write animated HTML view"); ap.add_argument("--events", help="write the canonical event log (JSONL)"); ap.add_argument("--telemetry", help="write machine telemetry sensor events (JSONL)"); ap.add_argument("--kpis", help="write KPIs computed from the event log (HTML)"); ap.add_argument("--handling", help="write handling-unit and pallet events (JSONL); parameters from the config key \"handling\""); ap.add_argument("--handling-view", help="write handling-unit HTML page"); ap.add_argument("--transport", help="write transport task events (JSONL); config key \"transport\""); ap.add_argument("--transport-view", help="write fleet HTML page"); ap.add_argument("--quality", help="write quality status events (JSONL); config key \"quality\""); ap.add_argument("--quality-view", help="write quality HTML page"); ap.add_argument("--dashboard", help="write the live dashboard (animated plant + digital-twin panel, one HTML file)"); ap.add_argument("--messages", help="write interface handshake message events (JSONL); parameters from the config key \"handshake\"")
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
