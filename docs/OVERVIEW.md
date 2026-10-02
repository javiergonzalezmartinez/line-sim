# line-sim overview (synthetic, private learning project)

What this is: a discrete-event simulation of a fictitious pharma plant, with analysis pages. All data is invented, parameters the spec leaves TBD stay TBD, the "SAP-style" events are simulated and not a real SAP integration.

## Run it

    python3 -m unittest discover -s tests          # 62 test files, a minute and a half
    python3 -m plantsim examples/dashboard_demo.json --dashboard dashboard.html
    python3 -m plantsim.cli examples/pharma_flow.json --seeds 3 --backup-view backuptest.html

The offline demo (M34) writes all pages into `paginas_html/`; `LEEME_ES.txt` explains them in Spanish. Python standard library only, no network, no paid services.

## Pages (49 in the index)

- `dashboard.html`: Animated plant dashboard
- `plant.html`: Layout view
- `kpis.html`: KPIs from events
- `handling.html`: Handling-unit state machine
- `transport.html`: Transport tasks / fleet
- `quality.html`: Quality status
- `process.html`: Analog process values
- `whatif.html`: What-if A vs B (20 seeds)
- `mqtt.html`: MQTT / OPC UA replay
- `energy.html`: Energy (placeholder kW)
- `flow.html`: Flow heat map, Sankey, Gantt
- `oee.html`: OEE
- `bottleneck.html`: Bottleneck (active period)
- `calibrate.html`: Calibration vs synthetic truth
- `dispatch.html`: Dispatch rule: FIFO vs same-product
- `guard.html`: Dispatch wait-guard sweep
- `due.html`: Due dates: FIFO vs earliest-due-date-first
- `rules.html`: Queue rules: FIFO, EDD, SPT, critical ratio
- `warmup.html`: Warm-up check (Welch)
- `reps.html`: How many replications
- `yield.html`: FME-022 yield threshold sweep
- `expiry.html`: FME-006 hold-time guard
- `entry.html`: FME-024 manual entry error
- `printer.html`: FME-026 label printer downtime
- `backuptest.html`: FME-030 backup and restore test interval
- `interlock.html`: FME-021 phase interlock trip (hold or abort)
- `presence.html`: FME-007 source presence missing (retry or reconcile)
- `clockskew.html`: FME-015 clock skew (sync interval)
- `seqbuffer.html`: FME-012 out-of-order messages (sequence buffer)
- `scalesettle.html`: FME-018 scale unstable (stability criterion)
- `ganttcap.html`: Finite-capacity Gantt by resource
- `qualpool.html`: FME-025 task by unqualified person (qualified pool)
- `authcheck.html`: FME-023 unauthorized operation (authority check)
- `auditfail.html`: FME-029 audit write failure (fail closed)
- `dupid.html`: FME-002 duplicate HU identifier
- `negstock.html`: FME-004 negative available quantity (race)
- `stockcount.html`: FME-003 stock mismatch (cycle count)
- `hushscan.html`: FME-001 wrong HU scanned
- `labelmis.html`: FME-027 wrong label association
- `caldue.html`: FME-019 calibration overdue
- `rework.html`: Repeat probability sweep (rework)
- `calib2.html`: Two-parameter calibration (identifiability)
- `little.html`: Little's law check
- `pmsweep.html`: Preventive-maintenance interval sweep
- `crn.html`: Same seeds or not (common random numbers check)
- `conwip.html`: CONWIP card sweep
- `sensitivity.html`: One-at-a-time sensitivity (tornado)
- `pareto.html`: Pareto of lost hours
- `pm.html`: Preventive maintenance what-if

Pages named FMEnnn each take one failure mode of the spec (`spec/failures.json`, 30 records) and compare a simulated detection or safe response with a closed form where one exists. Where simulation and formula disagree (for example FME-030 with tests every 90 or 180 days), the page says so.

## How to read a page

1. The amber box states what is synthetic and what is a placeholder.
2. The chart and table show simulation results with confidence intervals over several seeds.
3. A line "not modelled" lists what the layer leaves out.

## Limits

Every number in the examples is illustrative. Nothing here is validated against a real plant, so do not quote results as plant performance.
