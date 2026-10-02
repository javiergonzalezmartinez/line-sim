"""One-command offline demo: python3 -m plantsim.demo [outdir]
Runs the CLI on the bundled synthetic examples and writes every HTML page
plus an index.html. Everything is simulated; example values are illustrative."""
import os, subprocess, sys, html

PAGES = [
 ("dashboard.html", "Animated plant dashboard", "examples/dashboard_demo.json", ["--dashboard"]),
 ("plant.html", "Layout view", "examples/pharma.json", ["--view"]),
 ("kpis.html", "KPIs from events", "examples/pharma_flow.json", ["--kpis"]),
 ("handling.html", "Handling-unit state machine", "examples/seed_scenario.json", ["--handling-view"]),
 ("transport.html", "Transport tasks / fleet", "examples/transport_stress.json", ["--transport-view"]),
 ("quality.html", "Quality status", "examples/seed_scenario.json", ["--quality-view"]),
 ("process.html", "Analog process values", "examples/dashboard_demo.json", ["--process-view"]),
 ("whatif.html", "What-if A vs B (20 seeds)", "examples/whatif_a.json", ["--whatif", "examples/whatif_b.json", "--seeds", "20", "--whatif-view"]),
 ("mqtt.html", "MQTT / OPC UA replay", "examples/pharma_flow.json", ["--mqtt-view"]),
 ("energy.html", "Energy (placeholder kW)", "examples/energy_demo.json", ["--energy"]),
 ("flow.html", "Flow heat map, Sankey, Gantt", "examples/pharma_flow.json", ["--flow-view"]),
 ("oee.html", "OEE", "examples/pharma_flow.json", ["--oee-view"]),
 ("bottleneck.html", "Bottleneck (active period)", "examples/whatif_a.json", ["--bottleneck-view"]),
 ("calibrate.html", "Calibration vs synthetic truth", "examples/whatif_a.json", ["--calibrate-truth", "10", "--calibrate-view"]),
 ("dispatch.html", "Dispatch rule: FIFO vs same-product", "examples/dispatch_fifo.json", ["--whatif", "examples/dispatch_same_product.json", "--seeds", "20", "--whatif-view"]),
 ("guard.html", "Dispatch wait-guard sweep", "examples/dispatch_same_product.json", ["--dispatch-sweep"]),
 ("due.html", "Due dates: FIFO vs earliest-due-date-first", "examples/due_fifo.json", ["--whatif", "examples/due_edd.json", "--seeds", "20", "--whatif-view"]),
 ("rules.html", "Queue rules: FIFO, EDD, SPT, critical ratio", "examples/rules.json", ["--seeds", "10", "--rules-sweep"]),
 ("warmup.html", "Warm-up check (Welch)", "examples/pharma_flow.json", ["--seeds", "10", "--warmup-view"]),
 ("reps.html", "How many replications", "examples/pharma_flow.json", ["--max-reps", "30", "--reps-view"]),
 ("yield.html", "FME-022 yield threshold sweep", "examples/pharma_flow.json", ["--seeds", "3", "--yield-thresholds", "0.93,0.96", "--yield-view"]),
 ("expiry.html", "FME-006 hold-time guard", "examples/pharma_flow.json", ["--seeds", "3", "--expiry-limits", "24,72", "--expiry-view"]),
 ("rework.html", "Repeat probability sweep (rework)", "examples/pharma_flow.json", ["--seeds", "3", "--rework-probs", "0,0.2,0.4", "--rework-view"]),
 ("calib2.html", "Two-parameter calibration (identifiability)", "examples/pharma_flow.json", ["--seeds", "3", "--calib2-view"]),
 ("little.html", "Little's law check", "examples/pharma_flow.json", ["--seeds", "4", "--little-view"]),
 ("pmsweep.html", "Preventive-maintenance interval sweep", "examples/pm_b.json", ["--seeds", "5", "--pm-intervals", "50,150,600", "--pm-sweep"]),
 ("crn.html", "Same seeds or not (common random numbers check)", "examples/whatif_a.json", ["--whatif", "examples/whatif_b.json", "--seeds", "8", "--crn-view"]),
 ("conwip.html", "CONWIP card sweep", "examples/conwip.json", ["--seeds", "5", "--cards", "2,4,8,12", "--conwip-sweep"]),
 ("sensitivity.html", "One-at-a-time sensitivity (tornado)", "examples/pharma_flow.json", ["--seeds", "6", "--sens-view"]),
 ("pareto.html", "Pareto of lost hours", "examples/pm_b.json", ["--pareto-view"]),
 ("pm.html", "Preventive maintenance what-if", "examples/pm_a.json", ["--whatif", "examples/pm_b.json", "--seeds", "20", "--whatif-view"]),
]
EXTRA = {"guard.html": ["--guards", "24,72,168", "--seeds", "10"]}

def build(out, root=None, pages=PAGES):
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(out, exist_ok=True)
    done = []
    for name, title, cfg, flags in pages:
        dest = os.path.join(out, name)
        cmd = [sys.executable, "-m", "plantsim.cli", os.path.join(root, cfg)] + flags + [dest] + EXTRA.get(name, [])
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        ok = r.returncode == 0 and os.path.exists(dest)
        done.append((name, title, ok))
    rows = "".join(
        f'<li>{"<a href=%s>" % html.escape(n) if ok else ""}{html.escape(t)}{"</a>" if ok else " (failed)"}</li>'
        for n, t, ok in done)
    with open(os.path.join(out, "index.html"), "w") as f:
        f.write("<!doctype html><meta charset=utf-8><title>line-sim demo</title>"
                "<body style='font-family:sans-serif;max-width:640px;margin:2em auto'>"
                "<h1>line-sim demo</h1><p>Fictitious plant, simulated. Example values are illustrative placeholders.</p>"
                f"<ul>{rows}</ul></body>")
    return done

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "demo_out"
    res = build(out)
    for n, t, ok in res:
        print(("ok   " if ok else "FAIL ") + n)
    sys.exit(0 if all(o for _, _, o in res) else 1)
