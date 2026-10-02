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
