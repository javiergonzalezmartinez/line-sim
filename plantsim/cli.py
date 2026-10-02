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
    return Plant(st, d["products"], d["release_every"], d.get("horizon", 2016), d.get("warmup", 336), d.get("seed", 1), d.get("layout"), d.get("m_per_px", 0.0), d.get("speed_kmh", 6.0), d.get("handling_min", 6.0), d.get("dispatch", "fifo"), dispatch_max_wait_h=d.get("dispatch_max_wait_h"), due_h=d.get("due_h"), hours_factor=d.get("hours_factor"), conwip=d.get("conwip"), sync_streams=bool(d.get("sync_streams", False)))

def main(argv=None):
    ap = argparse.ArgumentParser(prog="plantsim"); ap.add_argument("config"); ap.add_argument("--view", help="write animated HTML view"); ap.add_argument("--events", help="write the canonical event log (JSONL)"); ap.add_argument("--telemetry", help="write machine telemetry sensor events (JSONL)"); ap.add_argument("--kpis", help="write KPIs computed from the event log (HTML)"); ap.add_argument("--handling", help="write handling-unit and pallet events (JSONL); parameters from the config key \"handling\""); ap.add_argument("--handling-view", help="write handling-unit HTML page"); ap.add_argument("--transport", help="write transport task events (JSONL); config key \"transport\""); ap.add_argument("--transport-view", help="write fleet HTML page"); ap.add_argument("--quality", help="write quality status events (JSONL); config key \"quality\""); ap.add_argument("--quality-view", help="write quality HTML page"); ap.add_argument("--dashboard", help="write the live dashboard (animated plant + digital-twin panel, one HTML file)"); ap.add_argument("--process-values", help="write analog process value events (JSONL); config key \"process_values\""); ap.add_argument("--process-view", help="write HTML chart of the first configured process value"); ap.add_argument("--whatif", help="scenario B config (JSON); compares it with the main config over --seeds replications"); ap.add_argument("--whatif-view", help="write the what-if HTML page (default whatif.html)"); ap.add_argument("--seeds", type=int, default=20, help="replications per scenario for --whatif"); ap.add_argument("--mqtt", help="write Sparkplug-style MQTT messages (JSONL, no broker)"); ap.add_argument("--opcua-nodes", help="write an OPC UA-style flat node list (JSON)"); ap.add_argument("--mqtt-view", help="write HTML summary of the replay export"); ap.add_argument("--energy", help="write HTML energy page (kWh per stage and lot); config key \"energy\" with placeholder kW"); ap.add_argument("--flow-view", help="write heat map + material flow + Gantt page (HTML)"); ap.add_argument("--oee-view", help="write OEE decomposition page (HTML)"); ap.add_argument("--bottleneck-view", help="write shifting-bottleneck page (active period method, HTML)"); ap.add_argument("--calibrate-view", help="write calibration page against a synthetic reference (needs --calibrate-truth)"); ap.add_argument("--calibrate-stage", default="Coating"); ap.add_argument("--calibrate-truth", type=float, help="hidden true mean process time (h) used to generate the synthetic reference"); ap.add_argument("--dispatch-sweep", help="write guard trade-off page for the same_product_first rule (guards from --guards)"); ap.add_argument("--guards", default="24,72,168", help="comma-separated guard values in hours"); ap.add_argument("--pareto-view", help="write Pareto of lost resource-hours by cause and stage (HTML)"); ap.add_argument("--rules-sweep", help="write FIFO/EDD/SPT/CR comparison page (needs due_h in the config)"); ap.add_argument("--warmup-view", help="write Welch warm-up check page (several replications with warm-up 0)"); ap.add_argument("--welch-window", type=int, default=7, help="half-width of the moving average, in days"); ap.add_argument("--reps-view", help="write the how-many-replications page (confidence interval method)"); ap.add_argument("--precision", type=float, default=0.05, help="target relative CI half-width for --reps-view"); ap.add_argument("--max-reps", type=int, default=40); ap.add_argument("--sens-view", help="write the one-at-a-time sensitivity (tornado) page"); ap.add_argument("--sens-pct", type=float, default=0.2, help="relative change low/high, e.g. 0.2 = -20%%/+20%%"); ap.add_argument("--crn-view", help="with --whatif: write the same-seeds-or-not (common random numbers) check page"); ap.add_argument("--yield-view", help="write the FME-022 yield-threshold sweep page"); ap.add_argument("--yield-stage", default="Coating"); ap.add_argument("--yield-mean", type=float, default=0.97); ap.add_argument("--yield-cv", type=float, default=0.02); ap.add_argument("--yield-thresholds", default="0.9,0.93,0.95,0.96,0.97"); ap.add_argument("--expiry-view", help="write the FME-006 hold-time guard page (share of lots with a queue wait above each limit)"); ap.add_argument("--expiry-limits", default="12,24,48,72,120"); ap.add_argument("--entry-view", help="write the FME-024 manual-entry-error page (second check)"); ap.add_argument("--entry-probs", default="0.001,0.003,0.01,0.03"); ap.add_argument("--entry-detect", type=float, default=0.9); ap.add_argument("--entry-count", type=int, default=6); ap.add_argument("--entry-fix-min", type=float, default=5.0); ap.add_argument("--printer-view", help="write the FME-026 label printer downtime page"); ap.add_argument("--printer-mttr", default="0.5,1,2,4,8"); ap.add_argument("--printer-mtbf", type=float, default=100.0); ap.add_argument("--stock-view", help="write the FME-003 stock mismatch (cycle count) page"); ap.add_argument("--stock-days", default="1,3,7,14,30"); ap.add_argument("--stock-e", type=float, default=0.05); ap.add_argument("--stock-postings", type=int, default=6); ap.add_argument("--stock-delta", type=float, default=5.0); ap.add_argument("--scale-view", help="write the FME-018 scale unstable (stability criterion) page"); ap.add_argument("--scale-tols", default="0.25,0.5,1,2,5"); ap.add_argument("--scale-offset", type=float, default=20.0); ap.add_argument("--scale-tau", type=float, default=4.0); ap.add_argument("--scale-sigma", type=float, default=0.5); ap.add_argument("--scale-dt", type=float, default=0.5); ap.add_argument("--scale-weighings", type=int, default=6); ap.add_argument("--gantt-res-view", help="write the finite-capacity Gantt by resource page"); ap.add_argument("--gantt-days", type=float, default=14.0); ap.add_argument("--qual-view", help="write the FME-025 qualified pool page"); ap.add_argument("--qual-pool", default="1,2,3,4"); ap.add_argument("--qual-hours", type=float, default=16.0); ap.add_argument("--auth-view", help="write the FME-023 unauthorized operation (authority check) page"); ap.add_argument("--auth-probs", default="0.005,0.02,0.05,0.1,0.2"); ap.add_argument("--auth-cover", type=float, default=0.95); ap.add_argument("--auth-ops", type=int, default=6); ap.add_argument("--auth-review-min", type=float, default=60.0); ap.add_argument("--audit-view", help="write the FME-029 audit write failure (fail closed) page"); ap.add_argument("--audit-minutes", default="30,60,240,480,1440"); ap.add_argument("--audit-mutations", type=int, default=3); ap.add_argument("--dupid-view", help="write the FME-002 duplicate HU identifier page"); ap.add_argument("--dupid-digits", default="4,5,6,7,8"); ap.add_argument("--dupid-hu", type=int, default=4); ap.add_argument("--negstock-view", help="write the FME-004 negative available quantity (race) page"); ap.add_argument("--negstock-gaps", default="0,1,5,15,60"); ap.add_argument("--negstock-q", type=float, default=10.0); ap.add_argument("--negstock-cover", type=float, default=0.9); ap.add_argument("--scan-view", help="write the FME-001 wrong HU scanned page"); ap.add_argument("--scan-probs", default="0.005,0.01,0.03,0.1"); ap.add_argument("--scan-detect", type=float, default=1.0); ap.add_argument("--scan-moves", type=int, default=4); ap.add_argument("--scan-rescan-min", type=float, default=2.0); ap.add_argument("--label-view", help="write the FME-027 wrong label association page (verification scan)"); ap.add_argument("--label-detect", default="0,0.5,0.9,0.99"); ap.add_argument("--label-p", type=float, default=0.02); ap.add_argument("--label-scans", type=int, default=1); ap.add_argument("--label-reissue-h", type=float, default=2.0); ap.add_argument("--caldue-view", help="write the FME-019 calibration overdue page"); ap.add_argument("--caldue-late", default="0,2,5,10,20"); ap.add_argument("--caldue-interval", type=float, default=90.0); ap.add_argument("--rework-view", help="write the repeat-probability sweep page (retest_p of one stage)"); ap.add_argument("--rework-stage", default="Coating"); ap.add_argument("--rework-probs", default="0,0.05,0.1,0.2,0.3,0.4"); ap.add_argument("--calib2-view", help="write the two-parameter calibration page (hidden truth = the config values of two stages)"); ap.add_argument("--calib2-stages", default="Coating,Granulation + drying", help="two stage names, comma separated"); ap.add_argument("--little-view", help="write the Little's law check page"); ap.add_argument("--pm-sweep", help="write PM interval sweep page"); ap.add_argument("--pm-intervals", default="25,50,100,150,300,600", help="comma-separated PM intervals in run-hours"); ap.add_argument("--conwip-sweep", help="write CONWIP card sweep page"); ap.add_argument("--cards", default="2,3,4,5,6,8,12", help="comma-separated card counts for --conwip-sweep"); ap.add_argument("--messages", help="write interface handshake message events (JSONL); parameters from the config key \"handshake\"")
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
    if a.crn_view:
        from .crn import check as _crn, render_html as _crr
        import dataclasses as _dc
        qq = load(a.whatif or a.config); nn = a.seeds if a.seeds != 20 else 10
        cc = _crn(p, qq, nn)
        cs = _crn(_dc.replace(p, sync_streams=True), _dc.replace(qq, sync_streams=True), nn)
        open(a.crn_view, "w", encoding="utf-8").write(_crr(cc, cs))
        for k, v in cs["metrics"].items(): print(f"  [sync] {k:<30} rho {v['rho'] if v['rho'] is None else round(v['rho'], 2)}  ratio {v['ratio'] if v['ratio'] is None else round(v['ratio'], 2)}")
        for k, v in cc["metrics"].items(): print(f"  {k:<30} rho {v['rho'] if v['rho'] is None else round(v['rho'], 2)}  paired {v['paired']:.3f}  other-seeds {v['indep']:.3f}")
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
    if a.pareto_view:
        from .pareto import losses as _pl, render_html as _ph
        prow = _pl(p, r); open(a.pareto_view, "w", encoding="utf-8").write(_ph(prow)); print(f"Pareto: {len(prow)} causes; page written to {a.pareto_view}")
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
    if a.yield_view:
        from .yieldsweep import sweep as _ys, render_html as _ysr
        yr = _ys(p, a.yield_stage, a.yield_mean, a.yield_cv, [float(x) for x in a.yield_thresholds.split(",") if x.strip()], a.seeds if a.seeds != 20 else 8)
        open(a.yield_view, "w", encoding="utf-8").write(_ysr(yr, a.yield_stage, a.yield_mean, a.yield_cv))
        for rw in yr: print(f"  threshold {rw['th']:.2f}  low-yield runs {rw['low'][0]:.1f}  throughput {rw['thr'][0]:.2f}/week  lead {rw['lt'][0]:.1f} d")
    if a.expiry_view:
        from .expiry import sweep as _ex, render_html as _exr
        ne = a.seeds if a.seeds != 20 else 8
        er = _ex(p, [float(x) for x in a.expiry_limits.split(",") if x.strip()], ne)
        open(a.expiry_view, "w", encoding="utf-8").write(_exr(er, ne))
        for rw in er: print(f"  limit {rw['limit']:g} h  lots over {rw['share'][0] * 100:.1f}%")
    if a.entry_view:
        from .entryerr import sweep as _en, render_html as _enr
        nn = a.seeds if a.seeds != 20 else 8
        er2 = _en(p, [float(x) for x in a.entry_probs.split(",") if x.strip()], a.entry_detect, a.entry_count, a.entry_fix_min, nn)
        open(a.entry_view, "w", encoding="utf-8").write(_enr(er2, a.entry_detect, a.entry_count, a.entry_fix_min, nn))
        for rw in er2: print(f"  p {rw['p']:.4f}  wrong/1000 lots no check {rw['no'][0]:.1f} (formula {rw['no_th']:.1f}), with check {rw['chk'][0]:.1f} (formula {rw['chk_th']:.1f})")
    if a.scale_view:
        from .scalesettle import sweep as _sc, render_html as _scr
        nsc = min(a.seeds, 40)
        sc = _sc(p, [float(x) for x in a.scale_tols.split(",") if x.strip()], a.scale_offset, a.scale_tau, a.scale_sigma, a.scale_dt, a.scale_weighings, nsc)
        open(a.scale_view, "w", encoding="utf-8").write(_scr(sc, a.scale_offset, a.scale_tau, a.scale_sigma, a.scale_dt, a.scale_weighings, nsc))
    if a.gantt_res_view:
        from .ganttcap import build as _gb, render_html as _gbr
        from .model import simulate as _gs
        open(a.gantt_res_view, "w", encoding="utf-8").write(_gbr(_gb(p, _gs(p), a.gantt_days)))
    if a.qual_view:
        from .qualpool import sweep as _ql, render_html as _qlr
        nql = min(a.seeds, 40)
        ql = _ql(p, [int(x) for x in a.qual_pool.split(",") if x.strip()], a.qual_hours, nql)
        open(a.qual_view, "w", encoding="utf-8").write(_qlr(ql, a.qual_hours, nql))
    if a.auth_view:
        from .authcheck import sweep as _ac, render_html as _acr
        nac = min(a.seeds, 40)
        ac = _ac(p, [float(x) for x in a.auth_probs.split(",") if x.strip()], a.auth_cover, a.auth_ops, a.auth_review_min, nac)
        open(a.auth_view, "w", encoding="utf-8").write(_acr(ac, a.auth_cover, a.auth_ops, a.auth_review_min, nac))
    if a.audit_view:
        from .auditfail import sweep as _au, render_html as _aur
        nau = min(a.seeds, 40)
        au = _au(p, [float(x) for x in a.audit_minutes.split(",") if x.strip()], a.audit_mutations, nau)
        open(a.audit_view, "w", encoding="utf-8").write(_aur(au, a.audit_mutations, nau))
    if a.dupid_view:
        from .dupid import sweep as _dp, render_html as _dpr
        ndp = min(a.seeds, 40)
        dp = _dp(p, [int(x) for x in a.dupid_digits.split(",") if x.strip()], a.dupid_hu, ndp)
        open(a.dupid_view, "w", encoding="utf-8").write(_dpr(dp, a.dupid_hu, ndp, 40))
    if a.negstock_view:
        from .negstock import sweep as _ng, render_html as _ngr
        nng = min(a.seeds, 40)
        ng = _ng(p, [float(x) for x in a.negstock_gaps.split(",") if x.strip()], a.negstock_q, a.negstock_cover, nng)
        open(a.negstock_view, "w", encoding="utf-8").write(_ngr(ng, a.negstock_q, a.negstock_cover, nng))
    if a.stock_view:
        from .stockcount import sweep as _sk, render_html as _skr
        nsk = a.seeds if a.seeds != 20 else 8
        sk = _sk(p, [float(x) for x in a.stock_days.split(",") if x.strip()], a.stock_e, a.stock_postings, a.stock_delta, nsk)
        open(a.stock_view, "w", encoding="utf-8").write(_skr(sk, a.stock_e, a.stock_postings, a.stock_delta, nsk))
    if a.scan_view:
        from .hushscan import sweep as _sc, render_html as _scr
        nsc = a.seeds if a.seeds != 20 else 8
        sc = _sc(p, [float(x) for x in a.scan_probs.split(",") if x.strip()], a.scan_detect, a.scan_moves, a.scan_rescan_min, nsc)
        open(a.scan_view, "w", encoding="utf-8").write(_scr(sc, a.scan_detect, a.scan_moves, a.scan_rescan_min, nsc))
    if a.label_view:
        from .labelmis import sweep as _lb, render_html as _lbr
        nl = a.seeds if a.seeds != 20 else 8
        lb = _lb(p, [float(x) for x in a.label_detect.split(",") if x.strip()], a.label_p, a.label_scans, a.label_reissue_h, nl)
        open(a.label_view, "w", encoding="utf-8").write(_lbr(lb, a.label_p, a.label_scans, a.label_reissue_h, nl))
    if a.printer_view:
        from .printer import sweep as _pr, render_html as _prr
        npr = a.seeds if a.seeds != 20 else 8
        pr = _pr(p, [float(x) for x in a.printer_mttr.split(",") if x.strip()], a.printer_mtbf, npr)
        open(a.printer_view, "w", encoding="utf-8").write(_prr(pr, a.printer_mtbf, npr))
        for rw in pr: print(f"  mttr {rw['mttr']:g} h  delayed {rw['share'][0] * 100:.1f}% (P(down) {rw['p_down'] * 100:.1f}%)  mean delay {rw['mean'][0]:.2f} h (formula {rw['mean_th']:.2f})")
    if a.caldue_view:
        from .calibdue import sweep as _cd, render_html as _cdr
        ncd = a.seeds if a.seeds != 20 else 8
        cd = _cd(p, [float(x) for x in a.caldue_late.split(",") if x.strip()], a.caldue_interval, ncd)
        open(a.caldue_view, "w", encoding="utf-8").write(_cdr(cd, a.caldue_interval, ncd))
        for rw in cd: print(f"  late {rw['late']:g} d  at risk {rw['share'][0] * 100:.1f}% (formula {rw['th'] * 100:.1f}%)")
    if a.rework_view:
        from .rework import sweep as _rw, render_html as _rwr
        rr = _rw(p, a.rework_stage, [float(x) for x in a.rework_probs.split(",") if x.strip()], a.seeds if a.seeds != 20 else 8)
        open(a.rework_view, "w", encoding="utf-8").write(_rwr(rr, a.rework_stage))
        for rw in rr: print(f"  retest_p {rw['p']:.2f}  repeats {rw['reruns'][0]:.1f}  share {rw['share'][0] * 100:.1f}%  throughput {rw['thr'][0]:.2f}/week  lead {rw['lt'][0]:.1f} d")
    if a.calib2_view:
        from .multicalib import run as _mc, render_html as _mr
        sa, sb = [x.strip() for x in a.calib2_stages.split(",")]
        hh = {st.name: st.hours for st in p.stages}
        mc = _mc(p, sa, sb, (hh[sa], hh[sb]), 0.4, 7, a.seeds if a.seeds != 20 else 5)
        open(a.calib2_view, "w", encoding="utf-8").write(_mr(mc))
        print(f"  set 1 best {mc['l1_best'][0]:.1f} / {mc['l1_best'][1]:.1f} h, near cells {mc['l1_near']}/49; set 2 best {mc['l2_best'][0]:.1f} / {mc['l2_best'][1]:.1f} h, near cells {mc['l2_near']}/49; truth {hh[sa]} / {hh[sb]}")
    if a.little_view:
        from .little import check as _lc, render_html as _lr
        lr = _lc(p, a.seeds if a.seeds != 20 else 8)
        open(a.little_view, "w", encoding="utf-8").write(_lr(lr, a.config))
        for rw in lr: print(f"  L {rw['L']:.2f}  lambda*W {rw['lamW']:.2f}  gap {rw['gap'] * 100:+.1f}%")
    if a.pm_sweep:
        from .pmsweep import sweep as _ps, render_html as _psr
        pr = _ps(p, [None] + [float(x) for x in a.pm_intervals.split(",") if x.strip()], a.seeds if a.seeds != 20 else 8)
        open(a.pm_sweep, "w", encoding="utf-8").write(_psr(pr))
        for rw in pr: print(f"  PM every {str(rw['iv']):>6}  throughput {rw['thr'][0]:.2f}/week  repair {rw['rep'][0]:.0f} h  pm {rw['pm'][0]:.0f} h")
    if a.conwip_sweep:
        from .conwipsweep import sweep as _cs, render_html as _csr
        cr = _cs(p, [None] + [int(x) for x in a.cards.split(",") if x.strip()], a.seeds if a.seeds != 20 else 8)
        open(a.conwip_sweep, "w", encoding="utf-8").write(_csr(cr))
        for rw in cr: print(f"  cards {str(rw['cards']):>5}  throughput {rw['thr'][0]:.2f}/week  inside {rw['ins'][0] if rw['ins'] else float('nan'):6.1f} d  lead {rw['lt'][0]:6.1f} d")
    if a.sens_view:
        from .sensitivity import run as _sr, render_html as _srh
        sa = _sr(p, a.sens_pct, a.seeds if a.seeds != 20 else 10)
        open(a.sens_view, "w", encoding="utf-8").write(_srh(sa))
        top = sorted(sa["rows"], key=lambda r: -r["thr"]["range"])[:3]
        print("sensitivity: top throughput inputs: " + "; ".join(f"{r['label']} ({r['thr']['range']:.2f})" for r in top) + f"; page written to {a.sens_view}")
    if a.reps_view:
        from .replications import run as _rr, render_html as _rrh
        ra = _rr(p, a.max_reps, a.precision)
        open(a.reps_view, "w", encoding="utf-8").write(_rrh(ra))
        for m in ra["measures"]: print(f"  {m['name']:<30} first n {m['first']}  stable from {m['stable']}")
    if a.warmup_view:
        from .warmup import analyse as _wa, render_html as _wr
        wa = _wa(p, max(a.seeds if a.seeds != 20 else 10, 5), a.welch_window)
        open(a.warmup_view, "w", encoding="utf-8").write(_wr(wa))
        print(f"warm-up check: configured day {wa['warmup_day']:.0f}; WIP settles day {wa['wip']['settles']}, finished/day settles day {wa['done']['settles']}; page written to {a.warmup_view}")
    if a.rules_sweep:
        from .rulesweep import sweep as _rs, render_html as _rsr
        rr = _rs(p, a.seeds if a.seeds != 20 else 10)
        open(a.rules_sweep, "w", encoding="utf-8").write(_rsr(rr))
        for rw in rr: print(f"  {rw['name']:<5} tardy {rw['tardy'][0]:.1%}  mean tardiness {rw['mt'][0]:6.0f} h  max lateness {rw['ml'][0]:6.0f} h  throughput {rw['thr'][0]:.2f}")
    if a.dispatch_sweep:
        from .dispatchsweep import sweep as _sw, render_html as _swr
        gv = [float(x) for x in a.guards.split(",") if x.strip()]
        rows = _sw(p, [None] + gv, a.seeds if a.seeds != 20 else 10)
        open(a.dispatch_sweep, "w", encoding="utf-8").write(_swr(rows))
        for rw in rows: print(f"  {rw['name']:<14} setup {rw['setup'][0]:8.0f} h  longest wait {rw['wait'][0]:6.0f} h  throughput {rw['thr'][0]:.2f}")
        print("sweep page written to", a.dispatch_sweep)
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
