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
| ![Quality](docs/img/m18_quality.png) **Quality holds and rejections** | ![Material](docs/img/m10_material.png) **Material shortages** |

## Milestones

M1-M6 line simulator, plant model, signal layer, finite buffers and blocking. M7 buffer size 0. M8 capacity on wait stages. M9 shifts and breaks. M10 material shortages. M11 canonical events and schema validator. M12 8 state machines. M13 machine signals. M14 KPIs. M15 interface handshakes and a seed scenario. M16 handling units and pallets. M17 forklift/AGV transport. M18 quality status. M19 live dashboard. Each one has tests and a section below.

## What is real, illustrative, or not modelled

| | |
|---|---|
| Real (computed by the code) | the simulation, every event, state change, hash, KPI and count; the tests that check them |
| Illustrative (invented, labelled) | every duration, rate, capacity-of-vehicles, failure probability and name in the examples |
| TBD in the specification, left TBD | simulation parameters; the defaults then invent nothing (ideal handshake, no extra holds, no shipment) |
| Not modelled (listed in the coverage table below) | 41 of 46 signals, 22 of 30 failure modes, 12 of 26 KPIs, expiry, retests, travel to pick-up, charging |

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
| Signals (46) | 5 produced (SIG-0001/0002/0003/0004/0010). The other 41 (temperature, pressure, mass, flow, barcode, RFID, ...) have no basis in the simulation and are NOT produced |
| Failure modes (30) | modelled: FME-005 (hold after release, `hold_p`), FME-008 (destination full, via finite buffers), FME-009/013 (ACK lost/timeout), FME-010 (route blocked, `route_block_p`), FME-011 (duplicate), FME-014 (rejection), FME-016 (breakdown). NOT modelled: the other 22 (identity, stock mismatch, expiry, scale, calibration, excursions, human errors, printing, cold chain, audit/backup) |
| KPIs (26) | computed: 001-006 (006 also for the vehicle fleet), 011 (lot level), 014 (only with `due_h`), 015-018, 023, 026. Not computed (no basis in the sim): 007-010 blocking/starvation/setup/downtime fractions, 012-013 inventory and FEFO, 019-022 data freshness, clock skew, audit and signatures, 024-025 excursions and rework |
| Parameters marked TBD | stay TBD: the examples use labelled illustrative values |

## M19: live dashboard (one HTML file)

`python3 -m plantsim examples/dashboard_demo.json --dashboard dashboard.html` writes a single self-contained page (no network): the animated plant (forklifts, lots, buffers, live parameter panel, charts, signal stream) plus a **digital twin layer** synchronised with the animation clock. The layer shows, for the current time, cumulative counts (canonical events, lots dispatched/rejected, active quality holds, transport tasks done, messages reconciled and retried, pallets in quarantine and shipped) and the latest events from the transport, message, quality, pallet and plant streams, with their state changes. Open it with `#t=700` to jump to a time.

- The twin layer is precomputed in Python for the loaded config (same seed and plant model). If you change a parameter in the animation panel, the animation re-runs but the layer does not, and the page says so. Counts run from hour 0 (include warm-up), so they differ from the steady-state cards.
- `examples/dashboard_demo.json` = the fictitious pharma plant plus illustrative `handshake`, `handling`, `transport` and `quality` parameters (the spec has no values).
