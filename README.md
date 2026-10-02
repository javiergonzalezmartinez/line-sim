# line-sim: a digital twin of a fictitious pharma plant (synthetic, private learning project)

From a two-station line to a whole plant: discrete-event simulation of a fictitious oral-solid-dose factory (warehouse, dispensing, production, QA, packaging, shipping) that produces **canonical events**, **state machines**, **signals**, **KPIs**, **handling units and pallets**, **forklift/AGV tasks**, **interface handshakes** and **quality holds**, and shows them in one live dashboard. Python standard library plus one offline HTML/JS file. No network, no paid services.

Everything is **synthetic**: no real plant, company or personal data. Parameters the specification leaves as TBD stay TBD; the examples use values labelled **illustrative**. The "SAP-style" events are simulated, **not a real SAP integration**.

## Quick start

    python3 -m unittest discover -s tests -t .        # Python tests
    node --test tests/*.test.js                       # JS tests
    python3 -m plantsim examples/dashboard_demo.json --dashboard dashboard.html   # open it in a browser, add #t=700 to jump in time
    python3 -m plantsim examples/seed_scenario.json --events ev.jsonl --kpis kpis.html --messages msg.jsonl --handling hu.jsonl --transport tt.jsonl --quality q.jsonl

## Gallery (screenshots of the real output, illustrative numbers)

| | |
|---|---|
| ![Live dashboard](docs/img/m19_dashboard.png) **Live dashboard**: animated plant + twin layer on one clock | ![Canonical event log](docs/img/m11_events.png) **Canonical event log** of one lot |
| ![State machines](docs/img/m12_fsm.png) **State machines** with state hashes | ![Signals](docs/img/m13_signals.png) **Machine signals** timeline |
| ![KPIs](docs/img/m14_kpis.png) **KPIs from the event log** | ![Handshakes](docs/img/m15_handshakes.png) **Interface handshakes**: retries, timeouts |
| ![Handling units](docs/img/m16_handling.png) **Handling units and pallets** | ![Fleet](docs/img/m17_fleet.png) **Forklift/AGV fleet** sizing |
| ![Quality](docs/img/m18_quality.png) **Quality holds and rejections** | ![Process value](docs/img/m21_process.png) **Process value with deadband** |
| ![Material](docs/img/m10_material.png) **Material shortages** | ![Faults](docs/img/m22_faults.png) **Injected sensor faults and excursions** |
| ![What-if](docs/img/m23_whatif.png) **What-if A vs B** with 95% confidence intervals | ![Replay export](docs/img/m24_mqtt.png) **Sparkplug-style messages** and OPC UA-style nodes |
| ![Energy](docs/img/m25_energy.png) **Energy per stage** (placeholder kW) | ![Flow views](docs/img/m27_flow.png) **Heat map, material flow, Gantt** |
| ![OEE](docs/img/m28_oee.png) **OEE decomposition** and loss waterfall | ![Bottleneck](docs/img/m29_bottleneck.png) **Shifting bottleneck** (active period method) |
| ![Calibration](docs/img/m30_calibration.png) **Calibration** against a synthetic reference | ![Dispatch](docs/img/m31_dispatch.png) **Dispatch rule what-if**: FIFO vs same product first |
| ![Guard](docs/img/m32_guard.png) **Starvation guard** sweep | ![PM](docs/img/m33_pm.png) **Preventive maintenance** what-if |
| ![Demo](docs/img/m34_demo.png) **Demo index**: every page in one run | ![Pareto](docs/img/m35_pareto.png) **Pareto** of lost resource-hours |
| ![Due dates](docs/img/m37_due.png) **Due dates**: tardiness under FIFO vs EDD | ![Rules](docs/img/m38_rules.png) **Dispatch rules** FIFO/EDD/SPT/CR |
| ![Welch](docs/img/m41_welch.png) **Warm-up check** (Welch) | ![Replications](docs/img/m42_reps.png) **How many replications** |
| ![Need](docs/img/m43_need.png) **Seeds needed** to see a difference | ![Tornado](docs/img/m44_tornado.png) **Sensitivity** (tornado) |
| ![CONWIP](docs/img/m45_conwip.png) **CONWIP** card sweep | ![CRN](docs/img/m46_crn.png) **Same seeds or not** (common random numbers) |
| ![PM sweep](docs/img/m47_pmsweep.png) **PM interval sweep** | ![Little](docs/img/m51_little.png) **Little's law check** |
| ![Calib2](docs/img/m54_calib2.png) **Two-parameter calibration**: identifiability | ![Rework](docs/img/m55_rework.png) **Repeat (rework) sweep** |
| ![Yield](docs/img/m56_yield.png) **FME-022** yield below threshold | ![Expiry](docs/img/m57_expiry.png) **FME-006** expired-lot (hold-time) guard |

## Milestones

M1-M6 line simulator, plant model, signal layer, finite buffers and blocking. M7 buffer size 0. M8 capacity on wait stages. M9 shifts and breaks. M10 material shortages. M11 canonical events and schema validator. M12 8 state machines. M13 machine signals. M14 KPIs. M15 interface handshakes and a seed scenario. M16 handling units and pallets. M17 forklift/AGV transport. M18 quality status. M19 live dashboard. M21 analog process values. M22 fault injection (drift, step, stochastic excursion, calibration overdue). M23 what-if comparator with confidence intervals. M24 Sparkplug-style MQTT replay and OPC UA-style node list. M25 energy calculator (placeholder kW). M27 heat map, material flow and Gantt views. M28 OEE decomposition. M29 shifting bottleneck detector. M30 calibration against a synthetic reference. M31 dispatch rule (same product first). M32 starvation guard for that rule. M33 preventive maintenance what-if. Each one has tests and a section below.

## What is real, illustrative, or not modelled

| | |
|---|---|
| Real (computed by the code) | the simulation, every event, state change, hash, KPI and count; the tests that check them |
| Illustrative (invented, labelled) | every duration, rate, capacity-of-vehicles, failure probability and name in the examples |
| TBD in the specification, left TBD | simulation parameters; the defaults then invent nothing (ideal handshake, no extra holds, no shipment) |
| Not modelled (listed in the coverage table below) | 41 of 46 signals, 22 of 30 failure modes (18 once the M22 faults are configured), 12 of 26 KPIs, expiry, retests, travel to pick-up, charging |

Rules of the project: private repository, fictitious data only, no personal or employer data, no paid services, nothing published without the owner's OK. Public sources used: ISA-88 / ISA-95 concepts, OPC UA, GS1 EPCIS, EU Annex 11, 21 CFR 11, and the public SAP Learning pages cited below.

## What you learn here
Why a line runs below its slowest station: blocking and starving, failures, and what a buffer is worth. Buffer size 0 (direct hand-off, the finished part waits in its station) is modelled in linesim; the plant view still clamps to 1.

## Whole-plant model (plantsim)
Batch flow of a fictitious oral-solid-dose plant, warehouse receipt to dispatch: receipt and quarantine, QC sampling and release (day shift), dispensing, granulation, compression, coating, packaging, QC lab release (retests), QA record review, dispatch waves. Changeover and cleaning when the product changes, breakdowns, working calendars.

    python3 -m plantsim examples/pharma.json --view plant.html

`plant.html` is an offline interactive 2D view: floor-plan layout, lots as moving entities, forklifts as a shared resource pool, live charts (lots in the plant, cumulative finished, utilisation) and a parameter panel (release rate, servers per stage, forklifts, transport time, breakdowns, changeovers, 24/7 labs). Changing a parameter re-runs the simulation in the browser with `plantsim/engine.js`, a port of the Python model.
Use `examples/pharma_flow.json` for the material flow (dock, warehouse quarantine, dispensing, intermediate store, production, finished-goods hold, shipping) with forklift transport. Deep links: `#t=381&s=0.5&fk=1&mv=6` = start time, speed, forklifts, transport multiplier.

Tests: `python3 -m unittest discover -s tests -t .` and `node --test tests/`. The JS engine is checked against Python: identical completion times with randomness off, means within 3% over 20 seeds with randomness on.

Not modelled yet: finite buffers between stages, stock-level based material shortages, deviations and QA holds beyond a retest chance, campaign sizing. All numbers are invented and illustrative.

## Signal and transaction layer
Every simulated lot generates PLC/sensor events (dock door, barcode scans, scales, conveyors, palletizer states, labelling, serialization, forklift RFID), WMS events (goods receipt, putaway and transfer orders, bin status), QA/LIMS events and ERP events (goods receipt, quarantine to unrestricted release, goods issue to production order, operation confirmations, backflush, outbound delivery and goods issue). The page shows a live log with filters per kind and lot, an events-per-6h chart, and CSV/JSON export.

The ERP events are **SAP-style, simulated, not a real SAP integration**. They use generic concepts and only movement types 101, 261 and 321, which are named on public SAP Learning pages (checked 1 Oct 2026):
- https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/posting-a-goods-receipt-with-reference (101)
- https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-manufacturing/executing-production-orders_eebd35c8-b7ed-4f36-bd4a-fb527dfa1322 (261)
- https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/performing-transfer-postings (321)

Document numbers are simulated sequence numbers. No SAP field names or transaction codes are used; a test restricts movement types to those three. Event texts live in the config (`events` per stage), so they can be changed without code.

## Deeper model (stage 3)
- **Transport from layout distance**: `m_per_px`, `speed_kmh`, `handling_min` in the config. A leg takes Manhattan distance between area centres divided by forklift speed, plus handling (load and unload). No traffic, turning or battery model.
- **QA holds and deviations**: stage kind `hold` (probability `p`, duration, QA calendar, `reject_p`). Rejected lots leave the plant and do not count as throughput; the page shows them and the log records the deviation, the hold and the rejection. The example rates are illustrative and set high enough to be visible.
- **FEFO vs FIFO**: raw-material lots get a simulated shelf life; each dispensing picks from released, unconsumed lots by earliest expiry (FEFO) or earliest release (FIFO). The page counts the picks where the two rules differ. Tested against an independent brute-force recomputation.
- **MQTT-style message view**: each signal can be shown as a topic and JSON payload (`fictitious-plant/<area>/<device>`, invented naming), exportable as JSON lines. No broker or real protocol is involved.
- **Palletizer detail**: pattern (5 layers x 12 cases), robot pick and place per layer, pallet complete with case count.
Still not modelled: finite buffers and blocking between stages, stock-level based material shortages, AGV traffic, real OPC UA/MQTT/IDoc interfaces.

## Milestone 6: finite buffers and blocking (illustrative)

A process or move stage can have `buffer`: the maximum number of lots waiting in front of it (absent = unlimited). When any stage has a buffer, an event-driven engine runs (`simulate_des` in Python, `simulateDES` in `plantsim/engine.js`). Without buffers the old engine runs unchanged.

- Semantics: block-after-service. A finished lot stays on its resource (machine or forklift with the pallet) until the next stage has room. Blocked lots are released in FIFO order.
- Cross-checks: with no blocking the new engine gives the same times as the old one for every lot; lots are conserved; JS and Python match on times, blocked hours and max queue; buffer limits are never exceeded (see tests).
- Example `examples/pharma_buffers.json`: 7.9 batches/week and 8.83 days lead time, against 7.7 and 9.01 without buffers (single run, illustrative). Most blocked resource-hours are forklift moves holding a pallet.
- Learn: with finite buffers, forklifts blocked holding pallets become a hidden bottleneck.
- Limits: no AGV path conflicts, material availability is a simple chance of a wait per lot (`shortage_p`, `shortage_hours` on process stages: the resource waits idle), no stock levels or purchase orders; no shift-level staffing (a stage can have daily `breaks` gaps: `"breaks": [[6,6.5]]` = no new lot starts 06:00-06:30; a running lot is not interrupted), wave and hold stages have no capacity limit (a wait stage can have one: `"capacity": N`, modelled as N resources, shown as a process in the view), nothing validated against a real plant. In the view, buffer size change below 1 is clamped to 1.

## Event log (milestone 11)

`python -m plantsim examples/pharma_flow.json --events events.jsonl` writes the simulated run as canonical events (EPCIS-style fields: class, type, action, event/record time, correlation and causation ids, sequence number, object ids, result, payload hash). `examples/canonical-event.schema.json` is the schema provided by Javi (synthetic / anonymised digital-twin spec); `plantsim/events.py` validates events against the subset of JSON Schema it uses, with no external library. Ids are pseudonyms (LOT-000001, EQ-STAGE-03) on a fixed synthetic start date. The tables of the spec (state machines, signals, KPIs, handshakes, failures, parameters) are in `spec/*.json`; parameters marked TBD there stay TBD. Not a real MES or historian, not validated against a real plant.

### State machines (milestone 12)

`plantsim/fsm.py` loads the transition tables from `spec/state_machines.json` (8 machines). An event is allowed only if the table has a row for that machine, state and event; otherwise `IllegalTransition` is raised, the state is kept and the attempt is logged. The event log now drives JOB_ORDER (one per lot) and PHASE_EXECUTION (one per lot and stage); each such event carries `state_before_hash`, `state_after_hash` and the transition in `reason_code`. Not yet driven: machine item/operation mode, handling unit, transport task, quality status and message machines (the tables are loaded and tested). Guards in the spec are text and are not evaluated.

### Machine telemetry (milestone 13)

`python -m plantsim examples/pharma_flow.json --telemetry tele.jsonl` writes sensor events (state-change sampling) for every process/move stage: item_state (SIG-0001), operation_mode (SIG-0002), cycle_counter (SIG-0003), operating_time in seconds (SIG-0004) and, for single-server stages, job_id (SIG-0010). They are driven by the MACHINERY_ITEM_STATE and MACHINERY_OPERATION_MODE machines from the spec and validate against the canonical schema. A stage with several servers is treated as one equipment (EXECUTING while at least one server works). Not produced because the simulation has no basis for them: power, safety, fault, alarm, speed, temperature and other process values; signal quality is always GOOD; the SETUP mode is not used (changeover is not traced per equipment). Synthetic, not a real historian or OPC UA.

### KPIs from the event log (milestone 14)

`python -m plantsim examples/pharma_flow.json --kpis kpis.html`. `plantsim/kpis.py` computes, from the events only: throughput (KPI-001), lead time (002), cycle time per stage (003), queue wait per stage (004), time-average WIP (005), utilisation per stage as time executing (006), sensor good-quality share (018, 100% by construction) and scrap rate on a lot basis (026). Tests compare them with the simulator's own numbers: throughput, lead time, scrap count and utilisation agree (timestamps are rounded to milliseconds); queue wait agrees for stages without changeover, and is larger by the changeover time where there is one, because the traced start is after the changeover. Not computed, no basis in the log: blocking, starvation, setup fraction, downtime, first-pass yield, rework, inventory, messages and the GxP KPIs.

## M15: interface handshakes and seed scenario (synthetic)

`python3 -m plantsim examples/seed_scenario.json --messages out.jsonl` emits HS-001 MOVE_REQUEST message events (sent, timeout/rejected, retry, acknowledged, reconciled, dead-lettered, duplicate discarded) on the MESSAGE state machine, validated against the canonical schema. KPI-015/016/017 are computed from them.

- Parameters (ack latency, timeout, loss, nack, duplicate, retries) come only from the `handshake` key of the config. The spec leaves them TBD, so with no config the handshake is ideal (100% success, zero latency). The values in `examples/seed_scenario.json` are illustrative.
- Failure catalogue: FME-009/013 (timeout), FME-011 (duplicate), FME-014 (rejection) are modelled; FME-016 is the existing `breakdown_p`. The other failure modes in `spec/failures.json` are NOT modelled.
- `examples/seed_scenario.json`: capacities and equipment ids from the synthetic seed; every time is an illustrative placeholder. 1 lot stands in for 1 handling unit.
- Not a real SAP or MES integration. Synthetic data only.

## M16: handling units and pallets (synthetic)

`python3 -m plantsim examples/seed_scenario.json --handling hu.jsonl --handling-view hu.html` emits HANDLING_UNIT state-machine events (state hashes, spec table) for every lot:

- input HUs: label, quarantine, release, reserve, pick, move, consume at the first process stage, empty, closed;
- finished pallets for lots that finish accepted: `pallet.built` (palletizing; an object event that is NOT a state change in the spec), label, quarantine, release, and load/dispatch only if `ship_delay_h` is given.

Parameters (`hu_per_lot`, `hu_per_pallet`, `release_delay_h`, `ship_delay_h`) come from the `handling` key; the spec has no values, so the defaults invent nothing (1 HU per lot, no shipment) and the ones in the seed scenario are illustrative placeholders. Not modelled: incoming-material QA, partial HUs/returns, HU moves after the first one, HOLD flows (next milestones).

## M17: forklift / AGV transport tasks (synthetic)

`python3 -m plantsim examples/transport_stress.json --transport tt.jsonl --transport-view fleet.html` emits TRANSPORT_TASK state-machine events (queued, assigned, accepted, picked, departed, route blocked/cleared, dropped, completed) for every move stage, with a finite fleet taking tasks FIFO. KPI-004 queue wait, KPI-006 fleet utilisation and KPI-014 task on time are computed; the page sweeps 1-4 vehicles.

- It is an overlay: the vehicle carries the load for the modelled move time, and a late vehicle does not delay the plant model. No travel time is invented. A task is requested when the plant model starts the move.
- Parameters (`fleet_size`, `accept_h`, `route_block_p/h`, `due_h`) come from the `transport` key. The spec has no values: defaults mean unlimited vehicles, no blocking, and KPI-006/014 not computed. `examples/transport_stress.json` is a stress variant with illustrative values so the fleet size matters.
- Not modelled: move.timeout and retry, cancelled tasks, travel to the pick-up point, charging, routes.

## M18: quality status, holds and rejections (synthetic)

`python3 -m plantsim examples/seed_scenario.json --quality q.jsonl --quality-view q.html` emits QUALITY_STATUS state-machine events for every finished lot (release after sample and lab, deviation hold then release, rejection, optional extra hold after release) and computes KPI-023 HoldExposure and KPI-011 FirstPassYield at lot level. Holds and rejections reuse the plant model's own QA hold stage, so the plant and the event log agree (a test checks the rejected lots match). Sample time, lab time and extra holds come from the `quality` key; the spec has no values, so the defaults add nothing (the seed scenario's values are illustrative). Not modelled: expiry (needs a shelf life, TBD), retests, partial release.

## What the twin covers of the spec (honest list)

| Spec item | Status |
|---|---|
| State machines (8) | all 8 used: JOB_ORDER, PHASE_EXECUTION, MESSAGE, HANDLING_UNIT, TRANSPORT_TASK, QUALITY_STATUS. MACHINERY_ITEM_STATE and MACHINERY_OPERATION_MODE through the signals |
| Signals (46) | 5 always produced (SIG-0001/0002/0003/0004/0010) plus any analog signal SIG-0013..0026 you configure per stage (M21; the demo config uses temperature, rpm, vibration_rms). The rest (temperature, pressure, mass, flow, barcode, RFID, ...) have no basis in the simulation and are NOT produced |
| Failure modes (30) | modelled: FME-005 (hold after release, `hold_p`), FME-008 (destination full, via finite buffers), FME-009/013 (ACK lost/timeout), FME-010 (route blocked, `route_block_p`), FME-011 (duplicate), FME-014 (rejection), FME-016 (breakdown), and with the M22 config FME-017 (sensor drift), FME-019 (calibration overdue), FME-020 (parameter excursion), FME-028 (stochastic excursion), and with `yield_min` set (M56) FME-022 (yield below threshold), and FME-006 as a measured guard (M57, no feedback). NOT modelled: the other 16 (identity, stock mismatch, expiry, scale, calibration, excursions, human errors, printing, cold chain, audit/backup) |
| KPIs (26) | computed: 024 (excursion duration, with M22 limits), 001-006 (006 also for the vehicle fleet), 011 (lot level), 014 (only with `due_h`), 015-018, 023, 026. Not computed (no basis in the sim): 007-010 blocking/starvation/setup/downtime fractions, 012-013 inventory and FEFO, 019-022 data freshness, clock skew, audit and signatures, 024-025 excursions and rework |
| Parameters marked TBD | stay TBD: the examples use labelled illustrative values |

## M19: live dashboard (one HTML file)

`python3 -m plantsim examples/dashboard_demo.json --dashboard dashboard.html` writes a single self-contained page (no network): the animated plant (forklifts, lots, buffers, live parameter panel, charts, signal stream) plus a **digital twin layer** synchronised with the animation clock. The layer shows, for the current time, cumulative counts (canonical events, lots dispatched/rejected, active quality holds, transport tasks done, messages reconciled and retried, pallets in quarantine and shipped) and the latest events from the transport, message, quality, pallet and plant streams, with their state changes. Open it with `#t=700` to jump to a time.

- The twin layer is precomputed in Python for the loaded config (same seed and plant model). If you change a parameter in the animation panel, the animation re-runs but the layer does not, and the page says so. Counts run from hour 0 (include warm-up), so they differ from the steady-state cards.
- `examples/dashboard_demo.json` = the fictitious pharma plant plus illustrative `handshake`, `handling`, `transport` and `quality` parameters (the spec has no values).

## M21: analog process values with report-by-exception (synthetic)

`python3 -m plantsim examples/dashboard_demo.json --process-values pv.jsonl --process-view pv.html` produces analog signals (spec SIG-0013..0026: temperature, pressure, rpm, mass, vibration, ...) for the stages named in the `process_values` config key, as sensor events with the spec's signal id and unit.

- Model: first-order response, `dx/dt = (setpoint - x)/tau`, setpoint = `run` while the equipment executes and `idle` otherwise (exact solution between samples), plus seeded Gaussian measurement noise. Textbook model, no plant physics.
- Sampling: every `sample_s` seconds, reported by exception with an **absolute deadband**, as in the OPC UA DataChangeFilter: "Generate a Notification if absolute value of (last cached value - current value) > AbsoluteDeadband" (OPC 10000-4, section 7.22.2, https://reference.opcfoundation.org/specs/OPC-10000-4/7.22.2, read 2 Oct 2026). The first sample is always reported. In the demo the deadband keeps 1 to 6% of the samples.
- Every number (idle, run, tau, noise, sample time, deadband) comes from the config and is illustrative; the spec has none. No config, no events. Not modelled: sensor drift, calibration, bad or stale quality (always GOOD), coupling between signals, percent deadband.

## M22: fault injection on process values (synthetic)

Each analog signal of the `process_values` config can carry `limits` (`low`/`high`, optional `hysteresis`) and a list of `faults`, with the injection types the spec names in `spec/failures.json` (column "Inyección simulación"):

| Fault | Spec id | Injection | What the code does |
|---|---|---|---|
| `drift` | FME-017 sensor drift | drift ramp | adds `rate_per_h` x hours since `start_h` to what the sensor reports (ground truth unchanged) |
| `step` | FME-020 parameter excursion | sensor step/outlier | adds `delta` between `start_h` and `start_h + dur_h` |
| `stochastic_excursion` | FME-028 temperature excursion | stochastic excursion | seeded exponential arrivals (`rate_per_100h`), each lasting `dur_h` with `delta` |
| `calibration_overdue` | FME-019 calibration overdue | calendar event | from `valid_until_h` the signal quality is UNCERTAIN |

A limit evaluator opens and closes `excursion.opened` / `excursion.closed` events (KPI-024 ExcursionDuration). `hysteresis` closes an excursion only when the value is back inside the limit by that margin, so measurement noise does not chatter an excursion open and closed. Note what the picture shows: a slow **drift is not an excursion until it crosses the limit, then it looks exactly like one** (false excursions at the end of the run), which is why the spec detects drift by calibration/analytics, not by limits.

- Sources: injection types and detection from the provided spec (`spec/failures.json`); UNCERTAIN as "the operation was partially successful and results might not be suitable for some purposes" in OPC 10000-4 section 7.38.1 (https://reference.opcfoundation.org/specs/OPC-10000-4/7.38.1, read 2 Oct 2026); absolute deadband as in M21.
- All rates, deltas, dates and limits come from the config and are illustrative. Not modelled: FME-018 scale unstable (needs a weighing capture flow), FME-026 printer unavailable, the safe responses (holding the batch, quarantining material, removing the instrument from eligible resources), detection by analytics, drift correction.

## M23: what-if comparator with confidence intervals (synthetic)

`python -m plantsim.cli examples/whatif_a.json --whatif examples/whatif_b.json --seeds 20 --whatif-view whatif.html`

Runs scenario A (the main config) and scenario B (another config file) over N replications with consecutive seeds. For each metric it prints the mean and 95% confidence interval of each scenario, and the paired difference B - A per seed with its own interval. A difference is called "clear" only when that interval does not contain 0. Intervals use the Student t distribution (`mean +/- t * s / sqrt(N)`), following the NIST/SEMATECH e-Handbook, sections 7.2.2.1 and 7.3.1.1 (read 2 Oct 2026). The t quantile is computed in the code and tested against the published values for 1, 10 and 30 degrees of freedom.

The example pair is illustrative: B is A with a second coating unit. In one run of 20 seeds, throughput and lead time differ clearly, rejected lots do not. The numbers depend on the placeholder parameters and mean nothing about a real plant.

Not modelled: common random numbers across different structures (the paired difference is valid but the variance reduction is not guaranteed), correction for many comparisons, stopping rules. Busiest-stage utilisation saturates at 100% in this example, so it carries no information there.

## M24: MQTT replay and OPC UA-style node list (synthetic)

`python -m plantsim.cli examples/pharma_flow.json --mqtt out.jsonl --opcua-nodes nodes.json --mqtt-view replay.html`

Turns the telemetry events into a file of MQTT messages whose topics follow the Eclipse Sparkplug namespace, `spBv1.0/<group>/<NBIRTH|DBIRTH|DDATA|NDEATH>/<edge node>/<device>` (Sparkplug specification 2.2 and the 3.x asciidoc, read 2 Oct 2026). `seq` runs 0-255 and wraps; each device gets a DBIRTH at its first event and DDATA afterwards. Group, node, device and signal ids are synthetic.

Not real Sparkplug on the wire: payloads are JSON, real Sparkplug B uses Protocol Buffers. DBIRTH here carries only the first metric seen, while the specification expects the full metric set of the device. No broker, QoS, retained flags, NCMD/DCMD or primary-host STATE. The node list (76 variable nodes in the example) is flat: NodeId in a string namespace, BrowseName, DataType. It is not an OPC UA NodeSet and no server exists. Tests check topic shape, continuous seq with wrap, birth before data per device, unique node ids and matching change counts.

## M25: energy per stage and per lot (synthetic, placeholder kW)

`python -m plantsim.cli examples/energy_demo.json --energy energy.html`

Energy is power times time: 1 kWh is 1 kW for 1 hour, 3.6 MJ (Wikipedia, kilowatt-hour, read 2 Oct 2026). The calculator takes the hours each machine spends in process, setup, repair and idle from the simulation and multiplies them by the kW you put under the config key `energy` (`default` for process stages, `stages` per stage name). It reports kWh per stage and state, per week, and per finished lot (window energy divided by lots finished in the window, a plant average).

Every kW value in `examples/energy_demo.json` is an illustrative placeholder, not a measurement of any machine. Stages without a power entry are listed as "no kW configured". The ISO 50001 page was only seen as a listing, the standard was not read, so there is no claim of conformity. Not modelled: part-load curves, start-up peaks, HVAC, cleanroom and compressed-air base load, cost, CO2, vehicle energy unless given as a stage, per-lot tracing. Tests check kWh = kW x hours, hours add up to capacity, doubling kW doubles energy, defaults apply only to machines.

## M27: heat map, material flow and Gantt (synthetic)

`python -m plantsim.cli examples/pharma_flow.json --flow-view flow.html`

Three views from the simulated batch traces (stage, arrive, start, end): a utilisation heat map (occupied share of each process stage per 7-day bucket), a Sankey-style material flow between process stages with the rejected branch, and a Gantt of the first finished lots (grey = waiting before a stage, colour = stage kind). The page is one HTML file with inline SVG.

Limits: the heat map shows occupied time, which can include repair or setup inside a stage, not value-adding time. The flow diagram skips transport and wait stages and counts a lot at a stage if its trace reaches it; it is a drawn diagram with simple curves, not a layout-optimised Sankey. The Gantt axis is in simulated days, not calendar dates, and does not show shifts. Tests check heat values stay in 0-100%, occupied hours match the traces, lot counts are conserved along the flow, and each Gantt lot is sequential.

## M28: OEE decomposition per stage (synthetic)

`python -m plantsim.cli examples/pharma_flow.json --oee-view oee.html`

Availability, performance and quality per process stage, their product, and a loss waterfall for the most loaded stage (planned time, no lot waiting, setup, repair, run time, speed loss, rejected lots). The three-factor structure is the one at oee.com/oee-factors (read 2 Oct 2026). The formulas are choices made in `plantsim/oee.py` and written at its top: availability is busy / (busy + setup + repair); performance is the nominal process time of the stage times the lots finished, divided by busy time; quality is one minus the rejected share, attributed to the last process stage a lot reached; OEE x loading puts it back on planned time.

Read the numbers carefully: performance here only reflects the variability and repeated steps drawn by the simulation around the configured nominal time, so values near 100% do not say anything about a real line, and it can go above 100% (not clamped). Not modelled: minor stops, shift calendar removed from planned time, rework, per-product ideal times. Tests check A x P x Q = OEE, bounds, that time adds up to planned, that a plant without losses gives availability 1 and performance about 1, and that rejected lots add up to the simulation's count.

## M29: shifting bottleneck detector (synthetic)

`python -m plantsim.cli examples/whatif_a.json --bottleneck-view bottleneck.html`

Applies the active period method of Roser, Nakano and Tanaka (Winter Simulation Conference 2002, preprint read 2 Oct 2026): the stage with the longest uninterrupted active period at a given moment is the momentary bottleneck. Sampled every hour in the window; a strip timeline shows who it was, a table gives the share of time and the number of shifts.

Choices and limits, all in `plantsim/bottleneck.py`: a stage is active while any of its servers works (union of busy intervals), which makes multi-server stages look longer-active than a single machine, so a 3-server stage such as QC lab can dominate even though the utilisation heat map points at Coating; the two views answer different questions and should be read together. Setup time is not in the traces. Moments where the two longest periods differ by less than 5% are "unclear" and do not count as shifts. In the example (illustrative parameters) the bottleneck changes 152 times in 12 weeks, which says the line has several near-equal constraints, not that a real plant behaves this way. Not modelled: a real-time variant, tool changes, a significance test. Tests check disjoint periods, shares sum to 1, the margin effect, shift counting, and a one-machine line.

## M30: calibration against a synthetic reference (synthetic)

`python -m plantsim.cli examples/whatif_a.json --calibrate-view cal.html --calibrate-truth 10`

A hidden "truth" (a mean process time for one stage, here Coating = 10 h while the model starts at 11 h) generates a reference summary: mean throughput and mean lead time over 12 seeds. The model is then calibrated by changing only that parameter: a coarse grid over the model value +/- 3 h, then a finer grid around the best point, each point averaged over 8 other seeds. Loss is the sum of squared relative errors of throughput and lead time. The idea (compare model behaviour with the system, adjust, repeat) is the operational validity step described by Sargent, WSC 2011 (read 2 Oct 2026).

What it shows: the search recovers a known value in a controlled case (fitted 10.2 h against a truth of 10.0 h in the example). The loss curve is nearly flat between about 9.7 and 10.5 h, so the error of 0.2 h is within the noise of a few seeds, and more seeds would narrow it. What it does not show: that the model is valid for a real plant, that several parameters can be fitted together, or what a wrong model structure does. The truth is never inside the search, only used to generate the reference; a test checks the fit stops at the edge when the truth is outside the range.

## M31: dispatch rule what-if, FIFO vs same product first (synthetic)

`python -m plantsim.cli examples/dispatch_fifo.json --whatif examples/dispatch_same_product.json --seeds 20 --whatif-view dispatch.html`

The event-driven engine gets a queue rule, config key `dispatch`: `fifo` (default, unchanged) or `same_product_first`: when a resource frees up and a changeover would cost time, it takes the oldest waiting lot of the product it last made, otherwise the oldest lot. The idea of setup-oriented rules for sequence-dependent setups comes from the abstract of "Dynamic job-shop scheduling with sequence-dependent setup times: simulation modeling and analysis" (Int. J. Adv. Manuf. Technol., 2007, abstract read 2 Oct 2026; the paper itself was not read and its rules are not implemented here).

In the example (illustrative changeover times, three products, 20 seeds), the rule cuts setup hours by about 775 h in the window and raises throughput by about 3 batches a week, both clearly outside the confidence interval of zero. The example is chosen with heavy changeovers, so the size of the gain says nothing about a real line. Rejected lots go up because more lots finish in the window, not because the rejection probability changed. The rule only works in the event-driven engine, so the example configs give every process and move stage a very large `buffer` that never blocks. Not modelled: a starvation limit for lots of the less frequent products (the longest queue wait fell in this example, but that is not guaranteed), due dates, other rules (shortest process time needs per-product times, which the model does not have). Tests check the field, bad values, that a single product or zero changeover gives identical results to FIFO, fewer setup hours, and that existing suites still pass.

## M32: starvation guard for same product first (synthetic)

`python -m plantsim.cli examples/dispatch_same_product.json --dispatch-sweep guard.html --guards 24,72,168 --seeds 10`

Config key `dispatch_max_wait_h`: with `same_product_first`, a lot that has waited longer than this goes first even if it needs a changeover. The idea is aging, the standard way to stop low-priority tasks waiting forever in a scheduler (Wikipedia, "Aging (scheduling)", read 2 Oct 2026; an operating-systems description used here as an analogy, not a published factory rule). The sweep runs FIFO, no guard and several guard values over the same seeds and shows setup hours and the longest queue wait with 95% intervals.

What the example shows (illustrative changeovers): there was no visible starvation problem. Without a guard the longest wait was already well below FIFO's, because the rule finishes more lots and the queues shrink. A tight guard (24 h) gives most of the benefit back (setup hours and throughput move toward FIFO); a loose guard (168 h) behaves like no guard. So here the guard only costs; it would matter in a plant where one product is rare, which this example does not test. The guard is a hard threshold, not a smooth ageing score, and does not bound the longest wait when every resource is busy (it only changes the order). Tests: a huge guard equals no guard, a tiny guard reproduces FIFO exactly, bad values are rejected, setup hours rise with a tight guard.

## M33: preventive maintenance what-if (synthetic, placeholder values)

`python -m plantsim.cli examples/pm_a.json --whatif examples/pm_b.json --seeds 20 --whatif-view pm.html`

Three new stage keys, event-driven engine only (a stage with `pm_every_h` switches to it, like `buffer` does): `pm_every_h` (run-hours between preventive maintenance), `pm_hours` (its duration) and `wear_per_100h` (relative rise of `breakdown_p` per 100 run-hours since the last maintenance). With the defaults nothing changes (a test compares against the old output). The vocabulary of corrective versus preventive maintenance is the one in the introduction of "Maintenance Optimization for Repairable Deteriorating Systems under Imperfect Preventive Maintenance" (Mathematics 2019, introduction read 2 Oct 2026); the paper's models are not implemented.

The wear rule is this code's own assumption, not taken from any source, and all values in the examples (50% per 100 h, maintenance every 150 h taking 4 h on four stages) are illustrative placeholders. Within that assumption, 20 seeds show about 280 fewer repair hours for 104 maintenance hours and a small throughput gain (+0.35 batches a week, interval clearly above zero). That is a statement about this toy model, not about any real plant or maintenance interval. Not modelled: imperfect maintenance, condition-based triggers, spare parts, maintenance crews, a search for the best interval. The preventive hours are a separate counter (`pm`); the OEE page does not subtract them from planned time. The JS animation engine ignores these keys.


## One-command offline demo (M34)

`python3 -m plantsim.demo demo_out` runs the CLI on the bundled synthetic examples and writes all 23 HTML pages plus `demo_out/index.html` (no network, no dependencies). Fictitious plant; example values are illustrative placeholders. `tests/test_demo.py` checks that every flag used in the README exists in `cli.py` and that all pages are produced.

## Pareto of lost hours (M35)

`python -m plantsim.cli examples/pm_b.json --pareto-view pareto.html` ranks loss causes per stage (repair, setup, PM, blocked, material wait) in resource-hours, with the cumulative line and an 80% marker. Concept as read at https://pmc.ncbi.nlm.nih.gov/articles/PMC10228985/ (2 Oct 2026). Hours, not money; queue waiting and idle time are not counted as losses. Example values are illustrative placeholders: in this example setup dominates only because of the placeholder changeover times.

## Due dates and EDD dispatch (M37)

Plant keys `due_h` (hours after release, a number or `{product: hours}`) and `dispatch: "edd"` (earliest due date first, event-driven engine). `python -m plantsim.cli examples/due_fifo.json --whatif examples/due_edd.json --seeds 20 --whatif-view due.html` compares FIFO with EDD and adds tardy share, mean tardiness and maximum lateness (lateness = completion minus due date, as defined in the UCSB scheduling notes, https://sites.cs.ucsb.edu/~suri/ccs130a/Scheduling.pdf, read 2 Oct 2026; those notes state that EDD minimises the maximum lateness on a single machine). In this plant, with several stages, queues that fill up and changeovers, that result is not guaranteed: only the simulation shows it. Due dates in the examples are placeholders and the plant is overloaded by them (most lots tardy). Not modelled: customer priorities, due-date setting rules, expediting, partial deliveries.

## Queue rules: SPT and critical ratio (M38)

`dispatch` also accepts `spt` (shortest process time at the stage first) and `cr` (smallest critical ratio, time left to the due date over remaining process work, first). Plant key `hours_factor` ({product: factor}) scales process times per product in the event-driven engine; without different factors SPT equals FIFO and CR equals EDD (tests check the SPT case). `python -m plantsim.cli examples/rules.json --rules-sweep rules.html --seeds 10` compares FIFO, EDD, SPT and CR on the same seeds with 95% CI. Definitions as read at https://www.uky.edu/~dsianita/300/schedule.html and https://metricgate.com/docs/critical-ratio-dispatch-rule/ (2 Oct 2026). Remaining work counts nominal process hours only (no queues, changeovers, moves). Factors and due dates are placeholders. Not modelled: setup-aware variants, release control, due-date setting rules.

## Warm-up check with Welch's moving average (M41)

`python -m plantsim.cli examples/pharma_flow.json --warmup-view warmup.html --seeds 10 --welch-window 7` simulates the plant with warm-up 0 over several replications, averages work in progress and lots finished per day (trailing 7-day mean) across them and smooths with a symmetric moving average (window 2w+1, shrinking at the start). Procedure as read at https://hsma-tools.github.io/vidigi/reference/analysis.welch_moving_average.html (cites Law) and https://pythonhealthdatascience.github.io/des_rap_book/pages/guide/output_analysis/length_warmup.html (2 Oct 2026; at least 5 replications). The "settles" marker is a rule of this code (smoothed curve stays within 5% of the mean of its last quarter), not from the sources. In the pharma_flow example WIP settles around day 14, which matches the configured warm-up, but the output rate only settles around day 23: the configured warm-up is a little short for throughput-based results. Not modelled: per-product series, a statistical end-of-transient test.

## How many replications? (M42)

`python -m plantsim.cli examples/pharma_flow.json --reps-view reps.html --max-reps 40 --precision 0.05` runs replications one after another and shows, per measure, the 95% CI half-width relative to the mean, the first number of replications under the target and the number from which it stays under it (this last one is an addition of this code). Method as read at https://pythonhealthdatascience.github.io/des_rap_book/pages/guide/output_analysis/n_reps.html (2 Oct 2026); that page cites Hoad, Robinson and Davies (2010), whose full text was not read and whose look-ahead rule is not implemented. In the example, throughput, lead time and setup hours reach 5% within about 5-6 replications, the longest queue wait needs about 13, and rare-event counts (rejected lots, repair hours) do not reach 5% within 40: the what-if pages use 20 seeds by default, enough for the first group but not for those. Not modelled: sequential stopping inside a running experiment, common random numbers.

## Seeds needed to see a difference (M43)

Every "not clear" row of a what-if page now shows a rough planning figure: if the observed mean difference were the true one, about n x (half-width / |difference|)^2 seeds would make the paired interval just exclude 0 (the half-width shrinks like 1/sqrt(n), NIST e-Handbook 7.2.2.1, read 2 Oct 2026; the change of the t quantile is ignored). It is not evidence that the difference exists: a difference near 0 may simply not be real. Not shown when the interval already excludes 0 or the difference is about 0.

## One-at-a-time sensitivity (M44)

`python -m plantsim.cli examples/pharma_flow.json --sens-view tornado.html --sens-pct 0.2 --seeds 10` varies each non-zero input (per process stage: process time, changeover, breakdown probability, repair time; plus the plant release interval) to -20% and +20% with the rest at nominal, over the same seeds, and draws tornado bars for throughput and lead time, largest range on top. Method as read at https://docs.analytica.com/index.php/Tornado_charts and https://help.goldsim.com/Content/GS/sensitivityanalysistornadochart.htm (2 Oct 2026; same relative change for every input is one of the options listed there). Bars shorter than twice the 95% half-width of the nominal mean are faded as "within noise" (a rule of this code). In the pharma_flow example the release interval moves throughput about 10 times more than any machine parameter: with these placeholders the plant is limited by what is released, not by its machines. All parameters are placeholders, so the ranking says which placeholders matter, not what a real plant does. Interactions are not seen; several inputs together are not varied.

## CONWIP release control (M45)

`"conwip": N` in the config caps the number of lots inside the plant at N (event-driven engine). Orders that find no free card wait outside in arrival order; a card returns when a lot leaves (finished or rejected). Idea as read at https://en.wikipedia.org/wiki/CONWIP (2 Oct 2026: a card limit on total WIP, nothing enters without a card); the original paper (Spearman, Woodruff, Hopp 1990) was not read. `python -m plantsim.cli examples/conwip.json --conwip-sweep conwip.html --cards 2,4,8,12 --seeds 8` sweeps the card count over the same seeds. What-if metrics add "Mean time inside the plant" and "Mean wait for a card". Lead time keeps counting from the order release, so the wait outside is in it. In the example (fast placeholder release, 8 h, so the plant is overloaded) the time inside the plant stays about 7.5 days with 2-8 cards while throughput rises with the cards; the queue just sits outside, so lead time from the order is not better, only the WIP inside is controlled. The wait outside grows with the horizon because orders arrive faster than the plant can finish. Not modelled: cards per product, card delays, order priority; all numbers are illustrative placeholders.

## Same seeds or not? (M46)

`python -m plantsim.cli examples/whatif_a.json --whatif examples/whatif_b.json --crn-view crn.html --seeds 10` checks whether running A and B on the same seeds (what `--whatif` does) really makes the difference B-A less noisy. Idea as read at https://en.wikipedia.org/wiki/Variance_reduction (2 Oct 2026, section Common Random Numbers): positive correlation between A and B shrinks the variance of the difference, negative correlation can make it worse, and the random streams should be synchronised. This simulator has one stream per run, so they are not synchronised once the scenarios diverge; the page shows, per metric, the A-B correlation and the 95% CI half-width of B-A with the same seeds (paired) against B on other seeds (Welch). Result with the example pair and 10 seeds (illustrative, noisy): the same seeds help a little for lead time (ratio below 1), do nothing for throughput, and the longest queue wait is negatively correlated, so there the paired interval is wider. Synchronised streams per stage are not implemented.

## Preventive-maintenance interval sweep (M47)

`python -m plantsim.cli examples/pm_b.json --pm-sweep pm.html --pm-intervals 25,50,100,150,300,600 --seeds 8` sets `pm_every_h` on every stage with `wear_per_100h > 0` (each keeps its own `pm_hours`) and shows throughput, lead time, repair hours, PM hours and their sum, with 95% CI over the same seeds; "never" is the no-PM reference. Frame: fixed-interval maintenance as at https://en.wikipedia.org/wiki/Preventive_maintenance (read 2 Oct 2026); that page gives no rule for the interval, so none is claimed. With the placeholders of pm_b (wear +50% breakdown probability per 100 run-hours, PM 4 h) the simulation shows a U shape: PM every 25 h loses throughput to PM time (8.75/week vs 9.09 with no PM), 150 h gives the highest mean (9.49), 600 h drifts back toward no PM. Repair hours fall from about 500 to 170-390 as PM gets more frequent while PM hours rise from 16 to 500. Differences between neighbouring intervals can be inside the CI. The optimum belongs to the placeholders, not to a real machine. Hours only, no cost; partial restoration and condition-based PM are not modelled.

## Little's law check (M51)

`python -m plantsim.cli examples/pharma_flow.json --little-view little.html --seeds 8` compares, per seed, the time-average number of lots in the plant (L) with arrival rate x mean time in the plant (lambda W) over the measurement window. Law as read at https://en.wikipedia.org/wiki/Little%27s_law (2 Oct 2026): L = lambda W for a stationary system; the page also says an unstable system, where arrivals exceed exits, keeps growing. Result (illustrative placeholders): pharma_flow agrees within about 2.5% (from -1.3% to +2.3% over 5 seeds), which is the finite-window boundary effect. The deliberately overloaded examples do not: conwip.json shows about +105% and whatif_a.json about +40%, because lots that arrive in the window wait long beyond it (the queue grows), so the check is also a steady-state alarm. The 10% red threshold on the page is a rule of this code. Sub-systems, non-stationary phases and lots released after the horizon are not checked.

## Synchronised random streams (M52)

Follow-up of M46. `"sync_streams": true` in the config gives each (lot, stage, purpose) its own random stream, derived from the seed (event-driven engine; purposes: hold, reject, delay, shortage, process time, breakdown, repair, retest). The same lot then gets the same random numbers in scenario A and B, which is the synchronisation described at https://en.wikipedia.org/wiki/Variance_reduction (read 2 Oct 2026). `--crn-view` now shows both ways. With whatif_a vs whatif_b and 10 seeds (illustrative, noisy): repair hours correlation +0.96 (ratio of CI half-widths 0.20 against 1.18 before), setup hours 0.36, rejected lots 0.29, throughput 0.64; mean lead time does not gain (ratio 0.99, correlation -0.15). Longest queue wait is identical in A and B here (half-width 0), so it says nothing. Results with `sync_streams` differ from the same seed without it (other random numbers), so do not mix the two in one comparison. Not done: antithetic variates, streams per unit.

## Two-parameter calibration: identifiability (M54)

`python -m plantsim.cli examples/pharma_flow.json --calib2-view calib2.html --calib2-stages "Coating,Granulation + drying" --seeds 5` takes the config values of two stages as a hidden truth, builds a reference summary from 10 seeds, and evaluates a 7x7 grid (+-40%) of process hours for the two stages with other seeds. Loss = sum of squared relative errors of the observables; set 1 = throughput and mean lead time (as in calibrate.py), set 2 = set 1 plus the mean queue wait per lot at both stages. Idea of comparing model and system behaviour: Sargent, WSC 2011 (https://www.informs-sim.org/wsc11papers/016.pdf, read 2 Oct 2026); no real data. Result with the pharma_flow placeholders and 5 seeds (illustrative): with set 1, 10 of 49 cells are within the minimum plus twice the noise (the loss of the truth cell, a rule of this code), and the lowest cell has Granulation at 7.8 h instead of 9, so throughput and lead time alone do not pin down both values (the plant is limited by the release interval, as M44 showed). With set 2 only 1 cell is near the minimum and it is the truth. Caveats: one stage pair and one plant, few seeds; with a 2-server stage the queue wait is close to 0 and its relative error is noisy, so the Coating/Compression pair is not a good demo.

## Repeat (rework) sweep (M55)

`python -m plantsim.cli examples/pharma_flow.json --rework-view rework.html --rework-stage Coating --rework-probs 0,0.05,0.1,0.2,0.3,0.4 --seeds 8` sets `retest_p` of one stage to each value and shows the repeats started in the window, the resource-hours they used, their share of the stage's busy hours, throughput and lead time with 95% CI over the same seeds. New per-stage counters `reruns` and `rerun_hours` (inside the measurement window, both engines). A repeat takes a fresh draw of the process time and can repeat again (mean p/(1-p) per lot). No external source is used for the "hidden capacity" framing, so none is claimed. Result with the pharma_flow placeholders (illustrative): up to 10% repeat probability on Coating the throughput does not drop (7.9 to 8.0/week, inside noise), at 20% lead time starts to rise (8.8 to 10.3 days), at 30-40% throughput falls to 7.3 and 6.2/week and lead time to 12-16 days, while the repeat share of the stage's busy hours goes 4% to 42%. So a stage with slack hides rework until it does not. Not modelled: quality or hold effects downstream, money, shorter repeat times, a cap on repeats.

## FME-022 yield below threshold (M56)

Stage keys `yield_mean`, `yield_cv`, `yield_min` model failure mode FME-022 of the twin spec (spec/failures.json, "yield random tail"): each run draws a yield from a Beta distribution with that mean and cv (a choice of this code, no source claimed); a run below `yield_min` is repeated with a fresh time and a fresh draw and counted in the new per-stage counter `low_yield` (window only; both engines; repeats also add to `reruns`). `python -m plantsim.cli examples/pharma_flow.json --yield-view yield.html --yield-stage Coating --yield-mean 0.97 --yield-cv 0.02 --seeds 8` sweeps the threshold. Result with placeholders (illustrative): thresholds up to 95% give 0.5 to 13 low-yield runs and almost no change in throughput (8.0/week), at 96% lead time goes 8.8 to 11.3 days and throughput to 7.6, at 97% (the mean) about half of the runs repeat and throughput falls to 6.3 with lead time 17 days. The yield does not change the quantity produced, only the repeat costs time; no scrap, hold or money. Validation: `0 < yield_mean < 1` and `0 < yield_min < 1`.

## FME-006 expired lot guard (M57)

`python -m plantsim.cli examples/pharma_flow.json --expiry-view expiry.html --expiry-limits 12,24,48,72,120 --seeds 8`. Spec record FME-006 "Expired lot selected" (detection: expiry guard, effect: candidate rejected). A lot "expires" if it waits in front of a stage longer than a limit; the page shows the share of lots finished in the window that a guard with that limit would reject, with 95% CI over the same seeds, and the stage that causes most of them. Limits are placeholders: the spec gives no hold time or shelf life (TBD) and none is claimed. Result with pharma_flow (illustrative): 12 h rejects 99% of lots, 24 h 74%, 48 h 27%, 72 h 0.2%, 120 h none, so the guard limit has to sit past the plant's natural queue-wait tail, and which stage causes the rejections tells where to look. Not modelled: the rejection does not feed back into the flow (waits of later lots are not relieved, lost value not counted), no FEFO ordering, no per-material shelf life, no money.
